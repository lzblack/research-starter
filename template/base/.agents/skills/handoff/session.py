"""Session helpers for the handoff skill.

    uv run python .agents/skills/handoff/session.py new [--at 2026-01-15T09:30Z]
    uv run python .agents/skills/handoff/session.py decision-id <slug> [--date YYYY-MM-DD]
    uv run python .agents/skills/handoff/session.py uncovered

`new` prints a session ID and its journal path. `uncovered` lists your commits that no journal
entry covers, and uncommitted changes. A commit is covered when it is a handoff commit (its
`Session:` trailer names a journal file present here) or an ancestor of one.
"""

import argparse
import datetime
import re
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else ""


def new(at: str | None) -> None:
    when = datetime.datetime.now(datetime.UTC)
    if at:
        when = datetime.datetime.strptime(at, "%Y-%m-%dT%H:%MZ").replace(tzinfo=datetime.UTC)
    session = f"{when:%Y-%m-%dT%H%M}Z-{secrets.token_hex(3)}"
    print(session)
    print(f"journal/{session}.md")


def decision_id(slug: str, date: str | None) -> None:
    if not SLUG.match(slug) or len(slug) > 50:
        sys.exit("error: the slug must be lowercase words joined by hyphens, at most 50 characters")
    day = date or datetime.date.today().isoformat()
    print(f"{day}-{slug}-{secrets.token_hex(2)}")


def uncovered() -> None:
    if not git("rev-parse", "--verify", "-q", "HEAD"):
        print("No commits yet.")
        return
    journal = {p.stem for p in (ROOT / "journal").glob("*.md")}
    handoffs = []
    for line in git("log", "--format=%H%x00%(trailers:key=Session,valueonly,separator=%x2C)").splitlines():
        commit, _, sessions = line.partition("\0")
        if any(s.strip() in journal for s in sessions.split(",") if s.strip()):
            handoffs.append(commit)
    covered = set(git("rev-list", *handoffs).split()) if handoffs else set()
    email = git("config", "user.email").strip().lower()
    missed = []
    for line in git("log", "--format=%H%x00%ae%x00%h %s").splitlines():
        commit, author, summary = line.split("\0", 2)
        if author.lower() == email and commit not in covered:
            missed.append(summary)
    changes = git("status", "--porcelain").strip()
    if not missed and not changes:
        print("No missed handoff.")
        return
    if missed:
        print("Commits not covered by a journal entry:")
        print("\n".join(f"  {s}" for s in missed))
    if changes:
        print("Uncommitted changes:")
        print("\n".join(f"  {line}" for line in changes.splitlines()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    n = sub.add_parser("new")
    n.add_argument("--at", help="session start in UTC, e.g. 2026-01-15T09:30Z")
    d = sub.add_parser("decision-id")
    d.add_argument("slug")
    d.add_argument("--date")
    sub.add_parser("uncovered")
    args = parser.parse_args()
    if args.command == "new":
        new(args.at)
    elif args.command == "decision-id":
        decision_id(args.slug, args.date)
    else:
        uncovered()


if __name__ == "__main__":
    main()
