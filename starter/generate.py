"""`generate`: create or complete a project (appendix A1.1, A1.2, A1.5, A3.2)."""

import datetime
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from starter.answers import AnswersError, load_answers, load_yaml_strict
from starter.plan import FileSpec, Plan, build_plan
from starter.render import TemplateError

TEMP_PREFIX = ".rs-tmp-"
TOLERATED = {".git", ".DS_Store"}
TEMPLATE_PATHS = ["template", "starter", "new_project.py"]


@dataclass
class Outcome:
    code: int
    lines: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[tuple[str, str]] = field(default_factory=list)


class Refused(Exception):
    def __init__(self, code: int, errors: list[tuple[str, str]]) -> None:
        super().__init__(errors)
        self.code = code
        self.errors = errors


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def template_commit(root: Path, allow_dirty: bool) -> str:
    head = _git(root, "rev-parse", "HEAD", check=False)
    if head.returncode != 0:
        raise Refused(5, [("-", f"the template directory is not a git checkout: {root}")])
    dirty = _git(root, "status", "--porcelain", "--", *TEMPLATE_PATHS).stdout.strip()
    if dirty and not allow_dirty:
        raise Refused(
            5, [("-", "the template checkout has uncommitted changes; commit them or pass --allow-dirty")]
        )
    return head.stdout.strip() + ("-dirty" if dirty else "")


def template_files(root: Path) -> set[str]:
    """Template files git would track: committed or untracked, never ignored (A1.5, A3.1)."""
    listed = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "template").stdout
    return {path for path in listed.split("\0") if path}


def _is_inside(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _recorded(target: Path, normalized: dict[str, Any]) -> dict[str, str] | None:
    """Return the `generated` block of an existing project.yml, or None on a first run."""
    path = target / "project.yml"
    if not os.path.lexists(path):
        return None
    if path.is_symlink() or not path.is_file():
        raise Refused(5, [("project.yml", "exists but is not a regular file")])
    try:
        data = load_yaml_strict(path.read_text(encoding="utf-8"), "project.yml")
    except (AnswersError, UnicodeDecodeError, OSError) as exc:
        raise Refused(5, [("project.yml", f"exists but cannot be read: {exc}")]) from exc
    generated = data.pop("generated", None) if isinstance(data, dict) else None
    if not (
        isinstance(generated, dict)
        and set(generated) == {"date", "template_commit"}
        and all(isinstance(v, str) for v in generated.values())
    ):
        raise Refused(5, [("project.yml", "has no valid 'generated' block")])
    if data != normalized:
        raise Refused(
            5,
            [("project.yml", "the answers differ from the recorded ones; change configuration by hand")],
        )
    return generated


def _check_first_run(target: Path) -> None:
    extra = sorted(
        entry.name
        for entry in target.iterdir()
        if entry.name not in TOLERATED and not entry.name.startswith(TEMP_PREFIX)
    )
    if extra:
        raise Refused(
            5,
            [("-", f"the target is not empty ({', '.join(extra[:5])}); adoption of an existing "
                   "project is not supported")],
        )  # fmt: skip
    if (target / ".git").exists() and _git(target, "rev-parse", "--verify", "-q", "HEAD", check=False).returncode == 0:
        raise Refused(5, [("-", "the target's git repository already has commits")])


def _classify(target: Path, path: str, spec: FileSpec) -> str:
    current = target
    for part in Path(path).parts[:-1]:
        current = current / part
        if os.path.lexists(current) and (current.is_symlink() or not current.is_dir()):
            return "conflict"
    dest = target / path
    if not os.path.lexists(dest):
        return "create"
    if spec.link is not None:
        return "same" if dest.is_symlink() and os.readlink(dest) == spec.link else "conflict"
    if dest.is_symlink() or not dest.is_file():
        return "conflict"
    same_bytes = dest.read_bytes() == spec.content
    same_mode = bool(dest.stat().st_mode & 0o111) == spec.executable
    return "same" if same_bytes and same_mode else "conflict"


def _remove_leftovers(target: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(target):
        for name in [d for d in dirnames if d.startswith(TEMP_PREFIX)]:
            if os.path.islink(os.path.join(dirpath, name)):
                os.unlink(os.path.join(dirpath, name))
        dirnames[:] = [d for d in dirnames if d != ".git" and not d.startswith(TEMP_PREFIX)]
        for name in filenames:
            if name.startswith(TEMP_PREFIX):
                os.unlink(os.path.join(dirpath, name))


def _write_atomic(dest: Path, spec: FileSpec) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if spec.link is not None:
        tmp = dest.with_name(f"{TEMP_PREFIX}{dest.name}")
        if os.path.lexists(tmp):
            os.unlink(tmp)
        os.symlink(spec.link, tmp)
        os.replace(tmp, dest)
        return
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=TEMP_PREFIX)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(spec.content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o755 if spec.executable else 0o644)
        os.replace(tmp, dest)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def _setup_git(target: Path, paths: list[str]) -> None:
    if not (target / ".git").exists():
        _git(target, "init", "-q", "-b", "main")
    elif _git(target, "rev-parse", "--verify", "-q", "HEAD", check=False).returncode != 0:
        _git(target, "symbolic-ref", "HEAD", "refs/heads/main")
    current = _git(target, "config", "--get", "core.hooksPath", check=False).stdout.strip()
    if current != ".githooks":
        _git(target, "config", "core.hooksPath", ".githooks")
    if paths:
        # A user's global excludes (for example `.claude/`) must not drop generated files.
        _git(target, "-c", "core.excludesFile=/dev/null", "add", "--", *paths)


def generate(
    answers_path: Path,
    target: Path,
    *,
    date: str | None,
    dry_run: bool,
    allow_dirty: bool,
    template_root: Path,
) -> Outcome:
    try:
        return _generate(answers_path, target, date, dry_run, allow_dirty, template_root)
    except Refused as refused:
        return Outcome(code=refused.code, errors=refused.errors)


def _generate(
    answers_path: Path, target: Path, date: str | None, dry_run: bool, allow_dirty: bool, root: Path
) -> Outcome:
    for tool in ["git", "uv"]:
        if shutil.which(tool) is None:
            raise Refused(5, [("-", f"{tool} is not installed or not on PATH")])
    commit = template_commit(root, allow_dirty)

    try:
        answers = load_answers(answers_path)
    except AnswersError as exc:
        raise Refused(3, [(i.location, i.message) for i in exc.issues]) from exc

    if not target.is_dir():
        raise Refused(5, [("-", f"the target directory does not exist: {target}")])
    target = target.resolve()
    if _is_inside(target, root.resolve()):
        raise Refused(5, [("-", "the target must not be inside the template checkout")])
    store = answers.normalized["data"]["large_store"]
    if store.startswith("~/") and _is_inside(Path(store).expanduser().resolve(), target):
        raise Refused(3, [("data.large_store", "must not be inside the project directory")])

    recorded = _recorded(target, answers.normalized)
    if recorded is None:
        _check_first_run(target)
        generated = {"date": date or datetime.date.today().isoformat(), "template_commit": commit}
    else:
        if recorded["template_commit"] != commit:
            raise Refused(
                5,
                [("project.yml", f"was generated from template commit {recorded['template_commit']}, "
                                 f"but this checkout is at {commit}; template updates follow the "
                                 "manual migration notes")],
            )  # fmt: skip
        if date is not None and date != recorded["date"]:
            raise Refused(5, [("-", f"--date differs from the recorded date {recorded['date']}")])
        generated = recorded

    try:
        plan: Plan = build_plan(answers, generated, root / "template", include=template_files(root))
    except TemplateError as exc:
        raise Refused(1, [("template", str(exc))]) from exc

    status = {path: _classify(target, path, spec) for path, spec in plan.files.items()}
    outcome = Outcome(
        code=4 if "conflict" in status.values() else 0,
        lines=[f"{verb} {path}" for path, verb in status.items()],
        warnings=plan.warnings,
    )
    if dry_run:
        return outcome

    _remove_leftovers(target)
    order = sorted(plan.files, key=lambda p: p != "project.yml")
    for path in order:
        if status[path] == "create":
            _write_atomic(target / path, plan.files[path])
    _setup_git(target, [p for p, verb in status.items() if verb != "conflict"])
    return outcome
