"""`generate`: preconditions, writes, reruns, and git setup (appendix A1.2, A1.5, A3.2)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from starter.generate import Outcome, generate
from tests.conftest import git, write

ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-01-15"
ANSWERS = """\
schema: 1
name: Synthetic Project
slug: synthetic-project
mode: solo
visibility: closed
people:
  - name: Researcher A
    github: researcher-a
    role: lead
"""


@pytest.fixture
def answers(tmp_path: Path) -> Path:
    path = tmp_path / "answers.yml"
    path.write_text(ANSWERS)
    return path


@pytest.fixture
def target(tmp_path: Path) -> Path:
    path = tmp_path / "project"
    path.mkdir()
    return path


def run(template_repo: Path, answers: Path, target: Path, **kwargs: object) -> Outcome:
    options = {"date": DATE, "dry_run": False, "allow_dirty": False} | kwargs
    return generate(answers, target, template_root=template_repo, **options)  # type: ignore[arg-type]


def verbs(outcome: Outcome) -> dict[str, str]:
    return {line.split(" ", 1)[1]: line.split(" ", 1)[0] for line in outcome.lines}


def files_in(target: Path) -> set[str]:
    return {
        p.relative_to(target).as_posix()
        for p in target.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(target).parts
    }


# --- First run -------------------------------------------------------------------------------


def test_first_run(template_repo: Path, answers: Path, target: Path) -> None:
    outcome = run(template_repo, answers, target)
    assert outcome.code == 0, outcome.errors
    assert set(verbs(outcome).values()) == {"create"}
    assert files_in(target) == set(verbs(outcome))
    assert (target / "hook").stat().st_mode & 0o111
    assert not (target / "README.md").stat().st_mode & 0o111
    assert git(target, "symbolic-ref", "HEAD") == "refs/heads/main"
    assert git(target, "config", "--get", "core.hooksPath") == ".githooks"
    assert set(git(target, "ls-files").splitlines()) == set(verbs(outcome))
    commit = git(template_repo, "rev-parse", "HEAD")
    assert f'template_commit: "{commit}"' in (target / "project.yml").read_text()
    assert f'date: "{DATE}"' in (target / "project.yml").read_text()


def test_dry_run_writes_nothing(template_repo: Path, answers: Path, target: Path) -> None:
    dry = run(template_repo, answers, target, dry_run=True)
    assert dry.code == 0
    assert list(target.iterdir()) == []
    real = run(template_repo, answers, target)
    assert dry.lines == real.lines


def test_existing_unborn_repository_is_moved_to_main(template_repo: Path, answers: Path, target: Path) -> None:
    git(target, "init", "-q", "-b", "master")
    assert run(template_repo, answers, target).code == 0
    assert git(target, "symbolic-ref", "HEAD") == "refs/heads/main"


def test_ds_store_is_tolerated(template_repo: Path, answers: Path, target: Path) -> None:
    (target / ".DS_Store").write_bytes(b"\0")
    assert run(template_repo, answers, target).code == 0


# --- Reruns ----------------------------------------------------------------------------------


def test_rerun_unchanged(template_repo: Path, answers: Path, target: Path) -> None:
    run(template_repo, answers, target)
    again = run(template_repo, answers, target, date=None)
    assert again.code == 0
    assert set(verbs(again).values()) == {"same"}


def test_rerun_reports_conflict_and_restores_missing(template_repo: Path, answers: Path, target: Path) -> None:
    run(template_repo, answers, target)
    (target / "README.md").write_text("edited by the user\n")
    (target / "static.txt").unlink()
    again = run(template_repo, answers, target)
    assert again.code == 4
    assert verbs(again)["README.md"] == "conflict"
    assert verbs(again)["static.txt"] == "create"
    assert (target / "README.md").read_text() == "edited by the user\n"
    assert (target / "static.txt").exists()


def test_executable_bit_difference_is_a_conflict(template_repo: Path, answers: Path, target: Path) -> None:
    run(template_repo, answers, target)
    (target / "hook").chmod(0o644)
    assert verbs(run(template_repo, answers, target))["hook"] == "conflict"


def test_rerun_completes_interrupted_run(template_repo: Path, answers: Path, target: Path) -> None:
    run(template_repo, answers, target)
    (target / "static.txt").unlink()
    (target / "paper" / "sections" / ".rs-tmp-leftover").write_text("partial")
    again = run(template_repo, answers, target)
    assert again.code == 0
    assert (target / "static.txt").exists()
    assert not (target / "paper" / "sections" / ".rs-tmp-leftover").exists()


def test_interruption_before_project_yml(template_repo: Path, answers: Path, target: Path) -> None:
    (target / ".rs-tmp-project").write_text("partial")
    assert run(template_repo, answers, target).code == 0
    assert not (target / ".rs-tmp-project").exists()


def test_directory_or_symlink_at_a_path_is_a_conflict(
    template_repo: Path, answers: Path, target: Path, tmp_path: Path
) -> None:
    run(template_repo, answers, target)
    (target / "static.txt").unlink()
    (target / "static.txt").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    for f in (target / "paper" / "sections").iterdir():
        f.unlink()
    (target / "paper" / "sections").rmdir()
    os.symlink(outside, target / "paper" / "sections")
    again = run(template_repo, answers, target)
    assert again.code == 4
    assert verbs(again)["static.txt"] == "conflict"
    assert verbs(again)["paper/sections/introduction.qmd"] == "conflict"
    assert list(outside.iterdir()) == []


def test_dry_run_with_conflicts(template_repo: Path, answers: Path, target: Path) -> None:
    run(template_repo, answers, target)
    (target / "README.md").write_text("edited\n")
    (target / "static.txt").unlink()
    dry = run(template_repo, answers, target, dry_run=True)
    assert dry.code == 4
    assert not (target / "static.txt").exists()


# --- Preconditions (code 5, nothing written) ---------------------------------------------------


def assert_refused(outcome: Outcome, target: Path, before: set[str]) -> None:
    assert outcome.code == 5, outcome
    assert outcome.errors
    assert files_in(target) == before


def test_target_missing(template_repo: Path, answers: Path, tmp_path: Path) -> None:
    outcome = run(template_repo, answers, tmp_path / "absent")
    assert outcome.code == 5


def test_target_with_other_files(template_repo: Path, answers: Path, target: Path) -> None:
    (target / "notes.txt").write_text("existing work\n")
    assert_refused(run(template_repo, answers, target), target, {"notes.txt"})


def test_target_repository_with_commits(template_repo: Path, answers: Path, target: Path) -> None:
    git(target, "init", "-q", "-b", "main")
    git(target, "commit", "-q", "--allow-empty", "-m", "existing")
    assert_refused(run(template_repo, answers, target), target, set())


def test_target_inside_template_checkout(template_repo: Path, answers: Path) -> None:
    inside = template_repo / "generated"
    inside.mkdir()
    assert run(template_repo, answers, inside).code == 5


def test_answers_differ_on_rerun(template_repo: Path, answers: Path, target: Path) -> None:
    run(template_repo, answers, target)
    before = files_in(target)
    answers.write_text(ANSWERS.replace("Synthetic Project", "Renamed Project"))
    assert_refused(run(template_repo, answers, target), target, before)


def test_explicit_date_differs_on_rerun(template_repo: Path, answers: Path, target: Path) -> None:
    run(template_repo, answers, target)
    before = files_in(target)
    assert_refused(run(template_repo, answers, target, date="2026-02-01"), target, before)


def test_template_commit_differs_on_rerun(template_repo: Path, answers: Path, target: Path) -> None:
    run(template_repo, answers, target)
    before = files_in(target)
    write(template_repo / "template" / "base" / "NEW.md", "new\n")
    git(template_repo, "add", "-A")
    git(template_repo, "commit", "-q", "-m", "change")
    assert_refused(run(template_repo, answers, target), target, before)


def test_unreadable_project_yml(template_repo: Path, answers: Path, target: Path) -> None:
    (target / "project.yml").write_text("not: [valid\n")
    assert_refused(run(template_repo, answers, target), target, {"project.yml"})


def test_dirty_template(template_repo: Path, answers: Path, target: Path) -> None:
    write(template_repo / "template" / "base" / "EXTRA.md", "uncommitted\n")
    assert_refused(run(template_repo, answers, target), target, set())
    allowed = run(template_repo, answers, target, allow_dirty=True)
    assert allowed.code == 0
    assert "-dirty" in (target / "project.yml").read_text()


def test_invalid_answers(template_repo: Path, answers: Path, target: Path) -> None:
    answers.write_text(ANSWERS.replace("mode: solo", "mode: duo"))
    outcome = run(template_repo, answers, target)
    assert outcome.code == 3
    assert ("mode", "must be one of: solo, team") in outcome.errors
    assert files_in(target) == set()


def test_large_store_inside_target(template_repo: Path, answers: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "project"
    target.mkdir()
    answers.write_text(ANSWERS + "data:\n  large_store: ~/project/store\n")
    outcome = run(template_repo, answers, target)
    assert outcome.code == 3
    assert outcome.errors[0][0] == "data.large_store"


# --- Command line ----------------------------------------------------------------------------


def cli(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "new_project.py"), *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_usage_error() -> None:
    assert cli("frobnicate").returncode == 2
    assert cli("generate", "--answers", "x.yml").returncode == 2


def test_cli_bad_date(answers: Path, target: Path) -> None:
    assert cli("generate", "--answers", answers, "--target", target, "--date", "2026-13-01").returncode == 2


def test_cli_invalid_answers(answers: Path, target: Path) -> None:
    answers.write_text(ANSWERS.replace("mode: solo", "mode: duo"))
    result = cli("generate", "--answers", answers, "--target", target, "--allow-dirty")
    assert result.returncode == 3
    assert "error: mode: must be one of: solo, team" in result.stderr


def test_symlinks_are_created_and_compared(template_repo: Path, answers: Path, target: Path) -> None:
    write(template_repo / "template" / "base" / ".claude" / "skills.symlink", "../.agents/skills\n")
    write(template_repo / "template" / "base" / ".agents" / "skills" / "x" / "SKILL.md", "x\n")
    git(template_repo, "add", "-A")
    git(template_repo, "commit", "-q", "-m", "link")
    first = run(template_repo, answers, target)
    assert first.code == 0 and verbs(first)[".claude/skills"] == "create"
    link = target / ".claude" / "skills"
    assert link.is_symlink() and os.readlink(link) == "../.agents/skills"
    assert (link / "x" / "SKILL.md").read_text() == "x\n"
    assert verbs(run(template_repo, answers, target))[".claude/skills"] == "same"
    link.unlink()
    link.mkdir()
    assert verbs(run(template_repo, answers, target))[".claude/skills"] == "conflict"


def test_leftover_temporary_link_is_removed(template_repo: Path, answers: Path, target: Path) -> None:
    run(template_repo, answers, target)
    os.symlink("..", target / ".rs-tmp-link")
    assert run(template_repo, answers, target).code == 0
    assert not os.path.lexists(target / ".rs-tmp-link")


def test_global_excludes_do_not_break_generate(
    template_repo: Path, answers: Path, target: Path, tmp_path: Path, monkeypatch
) -> None:
    excludes = tmp_path / "global-excludes"
    excludes.write_text("static.txt\n")
    config = tmp_path / "gitconfig"
    config.write_text(f"[core]\n\texcludesFile = {excludes}\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    outcome = run(template_repo, answers, target)
    assert outcome.code == 0, outcome.errors
    assert "static.txt" in git(target, "ls-files").splitlines()
    assert run(template_repo, answers, target).code == 0


def test_ignored_template_files_are_not_copied(template_repo: Path, answers: Path, target: Path) -> None:
    write(template_repo / "template" / "base" / ".gitignore", "*.env\nprivate/\n")
    git(template_repo, "add", "-A")
    git(template_repo, "commit", "-q", "-m", "ignore rules")
    write(template_repo / "template" / "base" / "local.env", "SECRET=1\n")
    write(template_repo / "template" / "base" / "private" / "people.md", "names\n")
    outcome = run(template_repo, answers, target)
    assert outcome.code == 0, outcome.errors
    assert not (target / "local.env").exists() and not (target / "private").exists()
