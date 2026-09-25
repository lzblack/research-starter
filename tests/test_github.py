"""GitHub provisioning and integration checks (appendix A1.7, A7.3), with a fake GitHub CLI."""

import json
import subprocess
from pathlib import Path

import pytest

from starter.github import MARKER, github_checks, issue_key, provision
from tests.conftest import git


class FakeGh:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.issues: list[dict[str, str]] = []
        self.runs: list[list[dict]] = [[{"databaseId": 7, "status": "completed", "conclusion": "success"}]]
        self.artifacts = ["paper-preview"]
        self.slug: str | None = "example/demo"

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        out, code = "", 0
        if args[:2] == ["repo", "view"]:
            out, code = (self.slug or "", 0) if self.slug else ("", 1)
        elif args[:2] == ["issue", "list"]:
            out = json.dumps([{"body": i["body"]} for i in self.issues])
        elif args[:2] == ["issue", "create"]:
            self.issues.append({"title": args[args.index("--title") + 1], "body": args[args.index("--body") + 1]})
        elif args[:2] == ["run", "list"]:
            out = json.dumps(self.runs.pop(0) if len(self.runs) > 1 else self.runs[0])
        elif args[0] == "api":
            out = "\n".join(self.artifacts)
        return subprocess.CompletedProcess(["gh", *args], code, out, "")


@pytest.fixture
def project(tmp_path: Path) -> tuple[Path, str]:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    target = tmp_path / "project"
    target.mkdir()
    git(target, "init", "-q", "-b", "main")
    (target / "project.yml").write_text("schema: 1\n")
    git(target, "add", "-A")
    git(target, "commit", "-q", "-m", "initial")
    return target, str(remote)


def test_first_run(project) -> None:
    target, remote = project
    gh = FakeGh()
    report = provision(target, remote, ["Collect the first dataset"], accept_local=lambda t: True, gh=gh)
    assert report.code == 0, report.lines
    assert [line.split(" (")[0] for line in report.lines] == [
        "done confirm", "done remote", "done push", "done issue setup", f"done issue {issue_key('Collect the first dataset')}",
    ]  # fmt: skip
    assert git(target, "remote", "get-url", "origin") == remote
    assert git(Path(remote), "rev-parse", "main") == git(target, "rev-parse", "HEAD")
    assert MARKER.format(key="setup") in gh.issues[0]["body"]


def test_rerun_skips_everything(project) -> None:
    target, remote = project
    gh = FakeGh()
    provision(target, remote, ["Collect the first dataset"], accept_local=lambda t: True, gh=gh)
    again = provision(target, remote, ["Collect the first dataset"], accept_local=lambda t: True, gh=gh)
    assert again.code == 0
    assert all(line.startswith(("done confirm", "skip")) for line in again.lines), again.lines
    assert len(gh.issues) == 2


def test_new_first_task_on_rerun(project) -> None:
    target, remote = project
    gh = FakeGh()
    provision(target, remote, [], accept_local=lambda t: True, gh=gh)
    provision(target, remote, ["Second task"], accept_local=lambda t: True, gh=gh)
    assert [i["title"] for i in gh.issues] == ["Complete project setup", "Second task"]


def test_closed_issue_counts_as_existing(project) -> None:
    target, remote = project
    gh = FakeGh()
    gh.issues.append({"title": "old", "body": "done\n" + MARKER.format(key="setup")})
    provision(target, remote, [], accept_local=lambda t: True, gh=gh)
    assert len(gh.issues) == 1


def test_different_origin_is_not_overwritten(project, tmp_path: Path) -> None:
    target, remote = project
    git(target, "remote", "add", "origin", str(tmp_path / "elsewhere.git"))
    report = provision(target, remote, [], accept_local=lambda t: True, gh=FakeGh())
    assert report.code == 4 and report.lines[-1].startswith("fail remote")
    assert git(target, "remote", "get-url", "origin") == str(tmp_path / "elsewhere.git")


def test_refuses_without_commit(tmp_path: Path) -> None:
    target = tmp_path / "empty"
    target.mkdir()
    git(target, "init", "-q", "-b", "main")
    report = provision(target, "x", [], accept_local=lambda t: True, gh=FakeGh())
    assert report.code == 4 and report.lines == ["fail confirm (the project has no commit; make the initial commit first)"]


def test_refuses_when_local_acceptance_fails(project) -> None:
    target, remote = project
    report = provision(target, remote, [], accept_local=lambda t: False, gh=FakeGh())
    assert report.code == 4 and report.lines[0].startswith("fail confirm")


def test_unresolvable_repository(project) -> None:
    target, remote = project
    gh = FakeGh()
    gh.slug = None
    report = provision(target, remote, [], accept_local=lambda t: True, gh=gh)
    assert report.lines[-1].startswith("fail issues")


# --- gh-ci and gh-preview ------------------------------------------------------------------------


def with_remote(project) -> Path:
    target, remote = project
    git(target, "remote", "add", "origin", remote)
    return target


def statuses(results) -> dict[str, str]:
    return {check: status for status, check, _ in results}


def test_checks_pass(project) -> None:
    assert statuses(github_checks(with_remote(project), FakeGh(), sleep=lambda s: None)) == {
        "gh-ci": "pass", "gh-preview": "pass"}  # fmt: skip


def test_waits_for_a_running_ci(project) -> None:
    gh = FakeGh()
    gh.runs = [[{"databaseId": 7, "status": "in_progress", "conclusion": ""}],
               [{"databaseId": 7, "status": "completed", "conclusion": "success"}]]  # fmt: skip
    slept = []
    assert statuses(github_checks(with_remote(project), gh, sleep=slept.append))["gh-ci"] == "pass"
    assert slept


def test_failed_ci(project) -> None:
    gh = FakeGh()
    gh.runs = [[{"databaseId": 7, "status": "completed", "conclusion": "failure"}]]
    assert statuses(github_checks(with_remote(project), gh, sleep=lambda s: None)) == {
        "gh-ci": "fail", "gh-preview": "not-tested"}  # fmt: skip


def test_missing_preview(project) -> None:
    gh = FakeGh()
    gh.artifacts = []
    assert statuses(github_checks(with_remote(project), gh, sleep=lambda s: None))["gh-preview"] == "fail"


def test_timeout_is_not_tested(project) -> None:
    gh = FakeGh()
    gh.runs = [[]]
    result = statuses(github_checks(with_remote(project), gh, timeout=40, sleep=lambda s: None))
    assert result == {"gh-ci": "not-tested", "gh-preview": "not-tested"}


def test_no_remote_is_not_tested(project) -> None:
    target, _ = project
    assert statuses(github_checks(target, FakeGh(), sleep=lambda s: None)) == {
        "gh-ci": "not-tested", "gh-preview": "not-tested"}  # fmt: skip
