"""Public-content scan for this repository (PRD section 17, appendix A7.4).

Scans template content, fixtures, and documentation for email addresses and for the patterns in
tools/public_scan_patterns.txt. A maintainer may add private names, one per line, to the local
file .review/public-scan-local.txt, which is gitignored and never published. The scan catches
listed patterns only; review remains necessary.

    uv run tools/public_scan.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCOPE = ["template", "tests/fixtures", "docs", "README.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md",
         "CHANGELOG.md"]  # fmt: skip
PATTERNS = ROOT / "tools" / "public_scan_patterns.txt"
LOCAL = ROOT / ".review" / "public-scan-local.txt"
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
ALLOWED_DOMAINS = ("example.org", "example.com", "example.net", "noreply.github.com")


def load_patterns(path: Path) -> list[re.Pattern[str]]:
    if not path.is_file():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [re.compile(line, re.I) for line in lines if line and not line.startswith("#")]


def files(root: Path) -> list[Path]:
    found = []
    for entry in SCOPE:
        path = root / entry
        if path.is_file():
            found.append(path)
        elif path.is_dir():
            found += sorted(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    return found


def scan(root: Path, patterns: list[re.Pattern[str]], local: list[re.Pattern[str]]) -> list[str]:
    problems = []
    for path in files(root):
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            continue
        rel = path.relative_to(root).as_posix()
        for number, line in enumerate(data.decode("utf-8", "replace").splitlines(), start=1):
            for match in EMAIL.finditer(line):
                if not match.group(1).lower().endswith(ALLOWED_DOMAINS):
                    problems.append(f"{rel}:{number}: email address {match.group(0)}")
            for pattern in patterns:
                if pattern.search(line):
                    problems.append(f"{rel}:{number}: matches pattern {pattern.pattern}")
            for pattern in local:
                if pattern.search(line):
                    problems.append(f"{rel}:{number}: matches a local private pattern")
    return problems


def main() -> int:
    problems = scan(ROOT, load_patterns(PATTERNS), [re.compile(re.escape(n), re.I) for n in _local_names()])
    for problem in problems:
        print(problem)
    print(f"public-content scan: {'fail' if problems else 'pass'} ({len(files(ROOT))} files)")
    return 1 if problems else 0


def _local_names() -> list[str]:
    if not LOCAL.is_file():
        return []
    return [line.strip() for line in LOCAL.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]


if __name__ == "__main__":
    sys.exit(main())
