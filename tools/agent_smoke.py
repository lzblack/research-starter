"""Agent smoke checks (appendix A7.3), run by hand before each release.

    uv run tools/agent_smoke.py claude
    uv run tools/agent_smoke.py codex

Generates a project in a temporary directory, runs the agent there, and checks the results
mechanically:
- agent-session-start: the agent answers a question only AGENTS.md answers;
- agent-handoff: a handoff given one decision writes a journal entry and a decision file in the
  appendix A6 formats, and commits with the Session and AI-Assisted trailers.

Record the results in docs/compatibility.md. The agent runs without its own sandbox or approval
prompts, but only inside the temporary project.
"""

import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parent.parent
ANSWERS = ROOT / "tests" / "fixtures" / "answers" / "minimal-defaults.yml"
HOOK_COMMAND = "git config core.hooksPath .githooks"
SESSION_QUESTION = (
    "According to your project instructions, what command enables the pre-commit hook in each "
    "clone? Reply with the command only."
)
DECISION = "The project uses only synthetic data until the data agreement is signed."
HANDOFF_BRIEF = (
    "This session added notes.md with a first research question. Decision to record: "
    f"{DECISION} There is no remote: do not push and do not create issues. Do not ask questions; "
    "complete the handoff."
)


def agent_command(agent: str, prompt: str) -> list[str]:
    if agent == "claude":
        return ["claude", "-p", prompt, "--permission-mode", "bypassPermissions"]
    if agent == "codex":
        return ["codex", "exec", "--skip-git-repo-check", "-s", "danger-full-access", prompt]
    raise SystemExit(f"unknown agent {agent!r}; use claude or codex")


def invocation(agent: str, skill: str, text: str) -> str:
    return f"/{skill} {text}" if agent == "claude" else f"${skill} {text}"


def run(cmd: list[str], cwd: Path, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False)


def git(project: Path, *args: str) -> str:
    return run(["git", *args], project).stdout


def front_matter(text: str) -> dict:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    data = YAML(typ="safe", pure=True).load(match.group(1))
    return {k: str(v) if isinstance(v, datetime.date) else v for k, v in (data or {}).items()}


def check_handoff(project: Path) -> list[str]:
    problems = []
    journals = sorted((project / "journal").glob("*.md"))
    if len(journals) != 1:
        return [f"expected one journal entry, found {len(journals)}"]
    journal = journals[0]
    session = journal.stem
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{4}Z-[0-9a-f]{6}", session):
        problems.append(f"journal name {journal.name} does not follow A6.2")
    text = journal.read_text(encoding="utf-8")
    front = front_matter(text)
    if front.get("session") != session:
        problems.append(f"journal front matter session {front.get('session')!r} does not match the file name")
    for key in ["author", "agent", "model"]:
        if not front.get(key):
            problems.append(f"journal front matter lacks '{key}'")
    for needed in ["## Done", "## Decisions", "## Open", "## Next", "## AI use"]:
        if needed not in text:
            problems.append(f"journal entry lacks '{needed}'")
    decisions = [p for p in (project / "docs" / "decisions").glob("*.md") if "template-provenance" not in p.name]
    if len(decisions) != 1:
        problems.append(f"expected one new decision file, found {len(decisions)}")
    else:
        decision = decisions[0]
        body = decision.read_text(encoding="utf-8")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-[a-z0-9]+(-[a-z0-9]+)*-[0-9a-f]{4}\.md", decision.name):
            problems.append(f"decision name {decision.name} does not follow A6.3")
        front = front_matter(body)
        if front.get("id") != decision.stem:
            problems.append(f"decision front matter id {front.get('id')!r} does not match the file name")
        for key in ["date", "decided_by", "supersedes"]:
            if key not in front:
                problems.append(f"decision front matter lacks '{key}'")
        for needed in ["## Decision", "## Reason", "## Alternatives considered", "synthetic"]:
            if needed not in body:
                problems.append(f"decision file lacks '{needed}'")
    trailers = git(project, "log", "-1", "--format=%(trailers)")
    if f"Session: {session}" not in trailers:
        problems.append("the last commit has no Session trailer naming the journal entry")
    if "AI-Assisted:" not in trailers:
        problems.append("the last commit has no AI-Assisted trailer")
    if git(project, "status", "--porcelain", "--", "journal", "docs").strip():
        problems.append("the handoff left journal or decision files uncommitted")
    return problems


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    agent = sys.argv[1]
    if shutil.which(agent) is None:
        print(f"not-tested agent-session-start ({agent} is not installed)")
        print(f"not-tested agent-handoff ({agent} is not installed)")
        return 0
    version = run([agent, "--version"], ROOT).stdout.strip().splitlines()[0]
    print(f"agent: {version}")
    failed = False
    with tempfile.TemporaryDirectory(prefix="rs-smoke-") as tmp:
        project = Path(tmp) / "project"
        project.mkdir()
        generated = run([sys.executable, str(ROOT / "new_project.py"), "generate", "--answers", str(ANSWERS),
                         "--target", str(project), "--allow-dirty"], ROOT)  # fmt: skip
        if generated.returncode != 0:
            print(generated.stderr, file=sys.stderr)
            return 1
        run(["uv", "sync", "--locked", "-q"], project)
        git(project, "-c", "user.name=Researcher A", "-c", "user.email=a@example.org", "commit", "-q",
            "-m", "Initial commit")  # fmt: skip
        git(project, "config", "user.name", "Researcher A")
        git(project, "config", "user.email", "a@example.org")

        answer = run(agent_command(agent, SESSION_QUESTION), project)
        ok = HOOK_COMMAND in answer.stdout
        failed |= not ok
        print(f"{'pass' if ok else 'fail'} agent-session-start")

        (project / "notes.md").write_text("# Notes\n\nFirst research question: a synthetic example.\n")
        handoff = run(agent_command(agent, invocation(agent, "handoff", HANDOFF_BRIEF)), project, timeout=1800)
        problems = check_handoff(project)
        failed |= bool(problems)
        print(f"{'fail' if problems else 'pass'} agent-handoff")
        for problem in problems:
            print(f"  {problem}")
        if problems:
            print(handoff.stdout[-3000:], file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
