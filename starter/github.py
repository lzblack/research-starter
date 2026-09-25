"""GitHub provisioning and integration checks (appendix A1.7, A7.3, A10.1).

Every external action checks first whether it is already done, so an interrupted run is resumed
by running it again. The GitHub CLI is called through `run_gh`, which tests replace.
"""

import hashlib
import json
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

WORKFLOW = "paper.yml"
ARTIFACT = "paper-preview"
CI_TIMEOUT = 30 * 60
POLL_SECONDS = 20
MARKER = "<!-- research-starter:setup-issue:{key} -->"
SETUP_TITLE = "Complete project setup"
SETUP_BODY = """Finish setting up this project:

- [ ] Read README.md and AGENTS.md.
- [ ] Write the project brief in docs/brief.md.
- [ ] Declare every dataset in data/README.md.
- [ ] Replace the synthetic example with the first real analysis, or keep it until then.
- [ ] Enable the pre-commit hook in each clone: `git config core.hooksPath .githooks`.
"""

GhRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)


def _git(target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=target, capture_output=True, text=True, check=False)


@dataclass
class Report:
    code: int = 0
    lines: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    def step(self, verb: str, name: str, detail: str = "") -> None:
        self.lines.append(f"{verb} {name}" + (f" ({detail})" if detail else ""))
        if verb == "fail":
            self.code = 4


def issue_key(title: str) -> str:
    return hashlib.sha256(title.encode("utf-8")).hexdigest()[:12]


def repo_slug(remote: str, gh: GhRunner) -> str | None:
    result = gh(["repo", "view", remote, "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    return result.stdout.strip() or None if result.returncode == 0 else None


def provision(
    target: Path,
    remote: str,
    first_tasks: list[str],
    *,
    accept_local: Callable[[Path], bool],
    gh: GhRunner = run_gh,
    github_checks: Callable[[Path], list[tuple[str, str, str]]] | None = None,
) -> Report:
    report = Report()

    if _git(target, "rev-parse", "--verify", "-q", "HEAD").returncode != 0:
        report.step("fail", "confirm", "the project has no commit; make the initial commit first")
        return report
    if not accept_local(target):
        report.step("fail", "confirm", "the local acceptance checks do not pass")
        return report
    report.step("done", "confirm")

    current = _git(target, "remote", "get-url", "origin")
    if current.returncode != 0:
        if _git(target, "remote", "add", "origin", remote).returncode != 0:
            report.step("fail", "remote", f"could not add {remote}")
            return report
        report.step("done", "remote")
    elif current.stdout.strip() == remote:
        report.step("skip", "remote")
    else:
        report.step("fail", "remote", f"origin already points to {current.stdout.strip()}; not changed")
        return report

    head = _git(target, "rev-parse", "HEAD").stdout.strip()
    remote_head = _git(target, "ls-remote", "origin", "refs/heads/main").stdout.split()
    if remote_head and remote_head[0] == head:
        report.step("skip", "push")
    else:
        pushed = _git(target, "push", "-u", "origin", "main")
        if pushed.returncode != 0:
            report.step("fail", "push", pushed.stderr.strip().splitlines()[-1] if pushed.stderr.strip() else "")
            return report
        report.step("done", "push")

    slug = repo_slug(remote, gh)
    if slug is None:
        report.step("fail", "issues", "cannot resolve the GitHub repository; check `gh auth status`")
        return report
    listed = gh(["issue", "list", "--repo", slug, "--state", "all", "--limit", "1000", "--json", "body"])
    if listed.returncode != 0:
        report.step("fail", "issues", listed.stderr.strip())
        return report
    bodies = [item.get("body", "") for item in json.loads(listed.stdout or "[]")]
    wanted = [("setup", SETUP_TITLE, SETUP_BODY)] + [(issue_key(t), t, "") for t in first_tasks]
    for key, title, body in wanted:
        marker = MARKER.format(key=key)
        if any(marker in existing for existing in bodies):
            report.step("skip", f"issue {key}", title)
            continue
        created = gh(["issue", "create", "--repo", slug, "--title", title, "--body", f"{body}\n{marker}\n"])
        if created.returncode != 0:
            report.step("fail", f"issue {key}", created.stderr.strip())
            return report
        report.step("done", f"issue {key}", title)

    if github_checks is not None:
        for status, check, reason in github_checks(target):
            report.step("done" if status == "pass" else ("fail" if status == "fail" else "skip"),
                        f"check {check}", reason or status)  # fmt: skip
    return report


def github_checks(
    target: Path,
    gh: GhRunner = run_gh,
    timeout: float = CI_TIMEOUT,
    sleep: Callable[[float], None] = time.sleep,
) -> list[tuple[str, str, str]]:
    """Results of gh-ci and gh-preview as (status, check, reason)."""
    remote = _git(target, "remote", "get-url", "origin").stdout.strip()
    slug = repo_slug(remote, gh) if remote else None
    if slug is None:
        reason = "no GitHub remote, or gh is not authenticated"
        return [("not-tested", "gh-ci", reason), ("not-tested", "gh-preview", reason)]
    head = _git(target, "rev-parse", "HEAD").stdout.strip()
    waited = 0.0
    run = None
    while True:
        listed = gh(["run", "list", "--repo", slug, "--workflow", WORKFLOW, "--commit", head,
                     "--event", "push", "--json", "databaseId,status,conclusion"])  # fmt: skip
        runs = json.loads(listed.stdout or "[]") if listed.returncode == 0 else []
        run = runs[0] if runs else None
        if run is not None and run.get("status") == "completed":
            break
        if waited >= timeout:
            reason = "no CI run was found for this commit" if run is None else "the CI run did not finish in time"
            return [("not-tested", "gh-ci", reason), ("not-tested", "gh-preview", "gh-ci did not pass")]
        sleep(POLL_SECONDS)
        waited += POLL_SECONDS
    if run.get("conclusion") != "success":
        return [("fail", "gh-ci", f"CI run {run['databaseId']} concluded {run.get('conclusion')}"),
                ("not-tested", "gh-preview", "gh-ci did not pass")]  # fmt: skip
    artifacts = gh(["api", f"repos/{slug}/actions/runs/{run['databaseId']}/artifacts", "--jq", ".artifacts[].name"])
    names = artifacts.stdout.split() if artifacts.returncode == 0 else []
    preview = ("pass", "gh-preview", "") if ARTIFACT in names else ("fail", "gh-preview", f"no {ARTIFACT} artifact")
    return [("pass", "gh-ci", ""), preview]
