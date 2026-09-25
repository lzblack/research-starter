"""`accept`: acceptance checks on a generated project (appendix A1.6, A7.3).

Local checks run in a temporary git repository holding a copy of the target's tracked files, so
the target is never changed. Checks whose prerequisites are missing report `not-tested`.
"""

import json
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
from starter.github import github_checks
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
    """Copy the index content (A1.6), so unstaged edits and deletions do not change the result."""
    prefix = str(dest.resolve()) + os.sep
    subprocess.run(["git", "checkout-index", "--all", f"--prefix={prefix}"], cwd=target, check=True)
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


def _example_build(copy: Path, project: dict[str, Any]) -> Result:
    check = "example-build"
    for stage in ["analyze", "paper"]:
        result = _run(["uv", "run", "--locked", "build.py", stage], copy)
        if result.returncode != 0:
            return Result(check, "fail", f"build.py {stage} failed: {_last_line(result)}")
    manifest = json.loads((copy / "paper" / "outputs" / "manifest.json").read_text(encoding="utf-8"))
    kinds = {artifact["kind"] for artifact in manifest["artifacts"]}
    lacking = sorted({"variable", "table", "figure"} - kinds)
    if lacking:
        return Result(check, "fail", f"analyze produced no {', '.join(lacking)}")
    absent = [
        name for name in _rendered(project) if not (copy / "paper" / "_output" / name).is_file()
    ]
    if absent:
        return Result(check, "fail", f"paper did not produce {', '.join(absent)}")
    return Result(check, "pass")


def _rendered(project: dict[str, Any]) -> list[str]:
    return [f"{project['slug']}.{EXTENSIONS[fmt]}" for fmt in project["writing"]["formats"]]


def _render_content(copy: Path, project: dict[str, Any]) -> Result:
    check = "render-content"
    variables = load_yaml_strict((copy / "paper" / "_variables.yml").read_text(), "_variables.yml")
    if not isinstance(variables, dict) or EXAMPLE_VARIABLE not in variables:
        return Result(check, "fail", f"paper/_variables.yml has no {EXAMPLE_VARIABLE}")
    value = str(variables[EXAMPLE_VARIABLE])
    first = section_title(project["writing"]["sections"][0])
    english = project["language"].split("-")[0] == "en"
    problems = []
    for name in _rendered(project):
        path = copy / "paper" / "_output" / name
        problems += [f"{name}: {p}" for p in render_problems(
            extract_text(path), value=value, first_title=first, english=english
        )]  # fmt: skip
    if problems:
        return Result(check, "fail", "; ".join(problems))
    return Result(check, "pass")


def _project_checks(copy: Path) -> Result:
    result = _run(["uv", "run", "--locked", "build.py", "check"], copy)
    if result.returncode != 0:
        failed = [line for line in result.stdout.splitlines() if line.startswith("fail ")]
        return Result("project-checks", "fail", "; ".join(failed) or _last_line(result))
    return Result("project-checks", "pass")


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
        if synced:
            built = _example_build(copy, project)
            results.append(built)
            if built.status == "pass":
                results.append(_render_content(copy, project))
            else:
                results.append(Result("render-content", "not-tested", "example-build failed"))
            results.append(_project_checks(copy))
        else:
            for check in ["example-build", "render-content", "project-checks"]:
                results.append(Result(check, "not-tested", "env-sync failed"))
        results.append(_provenance(copy, generated))

    manual = "run by hand before each release; see the compatibility file"
    results.append(Result("agent-session-start", "not-tested", manual))
    results.append(Result("agent-handoff", "not-tested", manual))
    if github:
        results += [Result(check, status, reason) for status, check, reason in github_checks(target)]
    else:
        results += [Result(check, "not-tested", "requires --github") for check in ["gh-ci", "gh-preview"]]
    code = 4 if any(r.status == "fail" for r in results) else 0
    return AcceptOutcome(code, results)
