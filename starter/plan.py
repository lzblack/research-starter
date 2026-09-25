"""The set of files a project should contain, computed from answers and the template tree.

Template tree (appendix A1.4): `base/` is always copied; `if-<flag>/` and `if-not-<flag>/` are
copied according to a derived flag (A2.1); `parts/` holds per-item templates. Files ending in
`.tmpl` are rendered and written without the suffix; other files are copied byte for byte.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from starter.answers import Answers, dump_yaml, quote
from starter.patterns import compile_pattern
from starter.render import Context, TemplateError, render

TEMPLATE_URL = "https://github.com/lzblack/research-starter"
FLAGS = ["collaboration", "open", "docx", "pdf", "csl", "human_drafted", "review_gates", "large_store"]
PARTS = {"section": "section.qmd.tmpl", "provenance": "template-provenance.md.tmpl"}
SKIP_NAMES = {".DS_Store", "__pycache__"}


@dataclass(frozen=True)
class FileSpec:
    content: bytes
    executable: bool = False


@dataclass
class Plan:
    files: dict[str, FileSpec] = field(default_factory=dict)
    warnings: list[tuple[str, str]] = field(default_factory=list)


def derived_flags(n: dict[str, Any]) -> dict[str, bool]:
    return {
        "collaboration": n["mode"] == "team",
        "open": n["visibility"] == "open",
        "docx": "docx" in n["writing"]["formats"],
        "pdf": "pdf" in n["writing"]["formats"],
        "csl": bool(n["writing"]["csl"]),
        "human_drafted": bool(n["writing"]["human_drafted"]),
        "review_gates": bool(n["review_gates"]),
        "large_store": bool(n["data"]["large_store"]),
    }


def section_title(section_id: str) -> str:
    text = section_id.replace("-", " ")
    return text[:1].upper() + text[1:]


def _reviewers(n: dict[str, Any]) -> dict[str, list[str]]:
    """Distinct `reviews` patterns in first-appearance order, each with its reviewers' handles."""
    patterns: dict[str, list[str]] = {}
    for person in n["people"]:
        for pattern in person["reviews"]:
            patterns.setdefault(pattern, [])
            if person["github"] not in patterns[pattern]:
                patterns[pattern].append(person["github"])
    return patterns


def build_context(n: dict[str, Any], generated: dict[str, str]) -> Context:
    lead = n["people"][0]
    sections = n["writing"]["sections"]
    scalars = {
        "name": n["name"],
        "slug": n["slug"],
        "description": n["description"],
        "language": n["language"],
        "type": n["type"],
        "mode": n["mode"],
        "visibility": n["visibility"],
        "reviewer_persona": n["reviewer_persona"],
        "project_rules": n["project_rules"],
        "writing.csl": n["writing"]["csl"],
        "data.large_store": n["data"]["large_store"],
        "generated.date": generated["date"],
        "generated.template_commit": generated["template_commit"],
        "template.url": TEMPLATE_URL,
        "lead.name": lead["name"],
        "lead.github": lead.get("github", ""),
    }
    lists = {
        "authors": [f"- {quote(p['name'])}" for p in n["people"]],
        "section-includes": [
            line for s in sections for line in (f"{{{{< include sections/{s}.qmd >}}}}", "")
        ],
        "human-drafted": [f"- {s}" for s in sections if s in n["writing"]["human_drafted"]],
        "review-gates": [f"- {g}" for g in n["review_gates"]],
        "codeowners": [
            f"{pattern} " + " ".join(f"@{h}" for h in handles)
            for pattern, handles in _reviewers(n).items()
        ],
    }
    return Context(scalars=scalars, flags=derived_flags(n), lists=lists)


def project_yml(n: dict[str, Any], generated: dict[str, str]) -> bytes:
    return dump_yaml({**n, "generated": dict(generated)}).encode()


def _tree_roots(template_dir: Path, flags: dict[str, bool]) -> list[Path]:
    allowed = {"base", "parts"} | {f"if-{f}" for f in FLAGS} | {f"if-not-{f}" for f in FLAGS}
    roots = [template_dir / "base"]
    for entry in sorted(template_dir.iterdir()):
        if entry.name in SKIP_NAMES:
            continue
        if not entry.is_dir() or entry.name not in allowed:
            raise TemplateError(f"unexpected entry in template directory: {entry.name}")
        for flag in FLAGS:
            if (entry.name == f"if-{flag}" and flags[flag]) or (
                entry.name == f"if-not-{flag}" and not flags[flag]
            ):
                roots.append(entry)
    return roots


def _add(plan: Plan, path: str, spec: FileSpec, origin: str) -> None:
    if path in plan.files:
        raise TemplateError(f"{origin} collides with another template file at {path}")
    plan.files[path] = spec


def _render_file(source: Path, ctx: Context, label: str) -> bytes:
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise TemplateError(f"{label}: .tmpl files must be UTF-8 text") from exc
    return render(text, ctx, label).encode()


def build_plan(answers: Answers, generated: dict[str, str], template_dir: Path) -> Plan:
    n = answers.normalized
    ctx = build_context(n, generated)
    plan = Plan()
    _add(plan, "project.yml", FileSpec(project_yml(n, generated)), "project.yml")

    for root in _tree_roots(template_dir, ctx.flags):
        for source in sorted(p for p in root.rglob("*") if p.is_file() or p.is_symlink()):
            if SKIP_NAMES & set(source.relative_to(root).parts):
                continue
            if source.is_symlink():
                raise TemplateError(f"template files must not be symbolic links: {source}")
            rel = source.relative_to(root).as_posix()
            label = f"{root.name}/{rel}"
            executable = bool(source.stat().st_mode & 0o111)
            if rel.endswith(".tmpl"):
                spec = FileSpec(_render_file(source, ctx, label), executable)
                _add(plan, rel.removesuffix(".tmpl"), spec, label)
            else:
                _add(plan, rel, FileSpec(source.read_bytes(), executable), label)

    parts = template_dir / "parts"
    sections = n["writing"]["sections"]
    for index, section in enumerate(sections):
        section_ctx = Context(
            scalars={**ctx.scalars, "section.id": section, "section.title": section_title(section)},
            flags={
                **ctx.flags,
                "section.first": index == 0,
                "section.human_drafted": section in n["writing"]["human_drafted"],
            },
            lists=ctx.lists,
        )
        content = _render_file(parts / PARTS["section"], section_ctx, f"parts/{PARTS['section']}")
        _add(plan, f"paper/sections/{section}.qmd", FileSpec(content), "parts/section")

    provenance = _render_file(parts / PARTS["provenance"], ctx, f"parts/{PARTS['provenance']}")
    record = f"docs/decisions/{generated['date']}-template-provenance-0000.md"
    _add(plan, record, FileSpec(provenance), "parts/provenance")

    if answers.csl_source is not None:
        _add(plan, f"paper/{n['writing']['csl']}", FileSpec(answers.csl_source.read_bytes()), "csl")

    if ctx.flags["collaboration"]:
        plan.warnings.extend(_codeowners_overlaps(n, sorted(plan.files)))
    plan.files = dict(sorted(plan.files.items()))
    return plan


def _codeowners_overlaps(n: dict[str, Any], paths: list[str]) -> list[tuple[str, str]]:
    patterns = list(_reviewers(n).items())
    compiled = [(p, handles, compile_pattern(p)) for p, handles in patterns]
    seen: set[tuple[str, str]] = set()
    warnings = []
    for path in paths:
        hits = [(p, handles) for p, handles, rx in compiled if rx.match(path)]
        for i, (first, first_handles) in enumerate(hits):
            for later, later_handles in hits[i + 1 :]:
                if first_handles != later_handles and (first, later) not in seen:
                    seen.add((first, later))
                    warnings.append(
                        (
                            "CODEOWNERS",
                            f"'{first}' and '{later}' both match {path}; GitHub requests review "
                            f"only from the last matching line ({' '.join('@' + h for h in later_handles)})",
                        )
                    )
    return warnings
