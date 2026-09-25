"""Create a research project from this template (appendix A1).

Run from a checkout of the template repository:

    uv run new_project.py generate --answers answers.yml --target ../my-project
    uv run new_project.py accept --target ../my-project
    uv run new_project.py provision --target ../my-project --remote https://github.com/OWNER/REPO
"""

import argparse
import datetime
import sys
from pathlib import Path

from starter.accept import accept
from starter.generate import generate
from starter.github import github_checks, provision

ROOT = Path(__file__).resolve().parent


def _date(value: str) -> str:
    try:
        parsed = datetime.date.fromisoformat(value)
    except ValueError:
        parsed = None
    if parsed is None or parsed.isoformat() != value:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="new_project.py", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    gen = commands.add_parser("generate", help="create or complete a project")
    gen.add_argument("--answers", required=True, type=Path)
    gen.add_argument("--target", required=True, type=Path)
    gen.add_argument("--date", type=_date)
    gen.add_argument("--dry-run", action="store_true")
    gen.add_argument("--allow-dirty", action="store_true")

    acc = commands.add_parser("accept", help="run the acceptance checks on a generated project")
    acc.add_argument("--target", required=True, type=Path)
    acc.add_argument("--github", action="store_true")

    prov = commands.add_parser("provision", help="add the GitHub remote, push, and create the initial issues")
    prov.add_argument("--target", required=True, type=Path)
    prov.add_argument("--remote", required=True)
    prov.add_argument("--first-task", action="append", default=[], dest="first_tasks")

    args = parser.parse_args(argv)
    if args.command == "accept":
        return _accept(args)
    if args.command == "provision":
        return _provision(args)
    try:
        outcome = generate(
            args.answers,
            args.target,
            date=args.date,
            dry_run=args.dry_run,
            allow_dirty=args.allow_dirty,
            template_root=ROOT,
        )
    except Exception as exc:  # noqa: BLE001 - report any defect with the documented exit code
        print(f"error: -: internal error: {exc!r}", file=sys.stderr)
        return 1
    for line in outcome.lines:
        print(line)
    for location, message in outcome.warnings:
        print(f"warning: {location}: {message}", file=sys.stderr)
    for location, message in outcome.errors:
        print(f"error: {location}: {message}", file=sys.stderr)
    return outcome.code


def _accept(args: argparse.Namespace) -> int:
    try:
        outcome = accept(args.target.resolve(), github=args.github, template_root=ROOT)
    except Exception as exc:  # noqa: BLE001 - report any defect with the documented exit code
        print(f"error: -: internal error: {exc!r}", file=sys.stderr)
        return 1
    for result in outcome.results:
        suffix = f" ({result.reason})" if result.reason else ""
        print(f"{result.status} {result.check}{suffix}")
    for location, message in outcome.errors:
        print(f"error: {location}: {message}", file=sys.stderr)
    return outcome.code


def _provision(args: argparse.Namespace) -> int:
    target = args.target.resolve()

    def accept_local(path: Path) -> bool:
        outcome = accept(path, github=False, template_root=ROOT)
        return outcome.code == 0

    try:
        report = provision(target, args.remote, args.first_tasks, accept_local=accept_local, github_checks=github_checks)
    except Exception as exc:  # noqa: BLE001 - report any defect with the documented exit code
        print(f"error: -: internal error: {exc!r}", file=sys.stderr)
        return 1
    for line in report.lines:
        print(line)
    return report.code


if __name__ == "__main__":
    sys.exit(main())
