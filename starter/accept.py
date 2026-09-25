"""`accept`: acceptance checks on a generated project (appendix A1.6, A7.3).

Local checks run in a temporary git repository holding a copy of the target's tracked files, so
the target is never changed. Checks whose prerequisites are missing report `not-tested`.
"""

import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from starter.answers import AnswersError, load_yaml_strict
from starter.generate import Refused, template_commit
from starter.plan import section_title

UNRESOLVED = re.compile(r"\?var:|\?@|\b[A-Za-z][A-Za-z0-9_:-]*\?\)")
EXAMPLE_VARIABLE = "example_n_obs"
EXTENSIONS = {"docx": "docx", "pdf": "pdf"}
TIMEOUT = 3600


@dataclass
class Result:
    check: str
    status: str  # pass, fail, not-tested
    reason: str = ""


@dataclass
class AcceptOutcome:
    code: int
    results: list[Result] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in {"VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"}}
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=TIMEOUT, check=False)


def _last_line(result: subprocess.CompletedProcess[str]) -> str:
    lines = (result.stderr or result.stdout).strip().splitlines()
    return lines[-1] if lines else f"exit code {result.returncode}"


def _copy_tracked(target: Path, dest: Path) -> None:
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=target, capture_output=True, check=True
    ).stdout.decode()
    for rel in filter(None, listed.split("\0")):
        source, out = target / rel, dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, out, follow_symlinks=False)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dest, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True)


def extract_text(path: Path) -> str:
    if path.suffix == ".docx":
        xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
        text = re.sub(r"<[^>]+>", " ", xml)
    else:
        text = " ".join(page.extract_text() for page in PdfReader(path).pages)
    return re.sub(r"\s+", " ", text)


def render_problems(text: str, *, value: str, first_title: str, english: bool) -> list[str]:
    """What the rendered text lacks under check `render-content` (A7.3)."""
    problems = []
    if value not in text:
        problems.append(f"example value {value!r} missing")
    if not re.search(rf"\b1\.?\s+{re.escape(first_title)}\b", text):
        problems.append(f"numbered heading '1 {first_title}' missing")
    if english and "Table 1" not in text:
        problems.append("table cross-reference 'Table 1' missing")
    marker = UNRESOLVED.search(text)
    if marker:
        problems.append(f"unresolved reference marker {marker.group(0)!r}")
    return problems


def _render_content(copy: Path, project: dict[str, Any]) -> Result:
    check = "render-content"
    render = _run(["uv", "run", "--locked", "quarto", "render"], copy / "paper")
    if render.returncode != 0:
        return Result(check, "fail", f"quarto render failed: {_last_line(render)}")
    variables = load_yaml_strict((copy / "paper" / "_variables.yml").read_text(), "_variables.yml")
    if not isinstance(variables, dict) or EXAMPLE_VARIABLE not in variables:
        return Result(check, "fail", f"paper/_variables.yml has no {EXAMPLE_VARIABLE}")
    value = str(variables[EXAMPLE_VARIABLE])
    first = section_title(project["writing"]["sections"][0])
    english = project["language"].split("-")[0] == "en"
    problems = []
    for fmt in project["writing"]["formats"]:
        path = copy / "paper" / "_output" / f"{project['slug']}.{EXTENSIONS[fmt]}"
        if not path.is_file():
            problems.append(f"{path.name} not produced")
            continue
        problems += [f"{path.name}: {p}" for p in render_problems(
            extract_text(path), value=value, first_title=first, english=english
        )]  # fmt: skip
    if problems:
        return Result(check, "fail", "; ".join(problems))
    return Result(check, "pass")


def _provenance(target: Path, generated: dict[str, str]) -> Result:
    check = "template-provenance"
    record = target / "docs" / "decisions" / f"{generated['date']}-template-provenance-0000.md"
    if not record.is_file():
        return Result(check, "fail", f"{record.relative_to(target)} missing")
    if generated["template_commit"] not in record.read_text(encoding="utf-8"):
        return Result(check, "fail", "the record does not name the template commit")
    return Result(check, "pass")


def accept(target: Path, *, github: bool, template_root: Path) -> AcceptOutcome:
    project_file = target / "project.yml"
    if not project_file.is_file():
        return AcceptOutcome(5, errors=[("-", f"not a generated project (no project.yml): {target}")])
    try:
        project = load_yaml_strict(project_file.read_text(encoding="utf-8"), "project.yml")
        generated = project["generated"]
        generated["date"], generated["template_commit"]  # noqa: B018 - presence check
    except (AnswersError, OSError, UnicodeDecodeError, KeyError, TypeError) as exc:
        return AcceptOutcome(5, errors=[("project.yml", f"cannot be read: {exc}")])
    try:
        commit = template_commit(template_root, allow_dirty=True)
    except Refused as exc:
        return AcceptOutcome(exc.code, errors=exc.errors)
    if generated["template_commit"] != commit:
        return AcceptOutcome(
            5,
            errors=[("-", f"the project was generated from template commit "
                          f"{generated['template_commit']}; check out that commit to run accept")],
        )  # fmt: skip

    results: list[Result] = []
    with tempfile.TemporaryDirectory(prefix="rs-accept-") as tmp:
        copy = Path(tmp)
        _copy_tracked(target, copy)
        sync = _run(["uv", "sync", "--locked"], copy)
        synced = sync.returncode == 0
        results.append(Result("env-sync", "pass" if synced else "fail", "" if synced else _last_line(sync)))
        results.append(Result("example-build", "not-tested", "the build entry point is not implemented yet"))
        if synced:
            results.append(_render_content(copy, project))
        else:
            results.append(Result("render-content", "not-tested", "env-sync failed"))
        results.append(Result("project-checks", "not-tested", "the project checks are not implemented yet"))
        results.append(_provenance(copy, generated))

    manual = "run by hand before each release; see the compatibility file"
    results.append(Result("agent-session-start", "not-tested", manual))
    results.append(Result("agent-handoff", "not-tested", manual))
    reason = "the GitHub checks are not implemented yet" if github else "requires --github"
    results.append(Result("gh-ci", "not-tested", reason))
    results.append(Result("gh-preview", "not-tested", reason))
    code = 4 if any(r.status == "fail" for r in results) else 0
    return AcceptOutcome(code, results)
