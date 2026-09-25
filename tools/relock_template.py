"""Regenerate template/base/uv.lock.tmpl from template/base/pyproject.toml.tmpl.

A lockfile containing a placeholder cannot be produced by `uv lock` directly. This script locks
a copy of the template's pyproject with the sentinel project name, then puts the placeholder
back in. The fixture acceptance check `env-sync` (`uv sync --locked`) is its regression test.

    uv run tools/relock_template.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "template" / "base"
SENTINEL = "template-slug"
PLACEHOLDER = '"@@slug@@"'


def main() -> int:
    pyproject = (BASE / "pyproject.toml.tmpl").read_text()
    if pyproject.count(PLACEHOLDER) != 1:
        print(f"error: expected one {PLACEHOLDER} in pyproject.toml.tmpl", file=sys.stderr)
        return 1
    concrete = pyproject.replace(PLACEHOLDER, f'"{SENTINEL}"').replace('"@@description@@"', '""')
    if "@@" in concrete:
        print("error: pyproject.toml.tmpl has placeholders this script does not handle", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "pyproject.toml").write_text(concrete)
        (work / ".python-version").write_text((BASE / ".python-version").read_text())
        subprocess.run(["uv", "lock"], cwd=work, check=True)
        lock = (work / "uv.lock").read_text()
    line = f'name = "{SENTINEL}"'
    if lock.count(line) != 1 or lock.count(SENTINEL) != 1:
        print("error: the sentinel name does not appear exactly once in uv.lock", file=sys.stderr)
        return 1
    (BASE / "uv.lock.tmpl").write_text(lock.replace(line, f"name = {PLACEHOLDER}"))
    print("wrote template/base/uv.lock.tmpl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
