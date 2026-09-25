"""Public-content scan (appendix A7.4)."""

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("public_scan", ROOT / "tools" / "public_scan.py")
scanner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(scanner)
sys.dont_write_bytecode = False
PATTERNS = scanner.load_patterns(ROOT / "tools" / "public_scan_patterns.txt")


def scan_text(tmp_path: Path, text: str, local: list[str] | None = None) -> list[str]:
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "note.md").write_text(text)
    return scanner.scan(tmp_path, PATTERNS, [re.compile(re.escape(n), re.I) for n in local or []])


def test_clean_text(tmp_path: Path) -> None:
    assert scan_text(tmp_path, "Researchers use synthetic data. Contact noreply@example.org.\n") == []


def test_real_email(tmp_path: Path) -> None:
    assert scan_text(tmp_path, "Write to someone@realmail.net\n")


def test_institution_and_roles(tmp_path: Path) -> None:
    assert scan_text(tmp_path, "A student at the University of Somewhere.\n")


def test_local_names(tmp_path: Path) -> None:
    assert scan_text(tmp_path, "Drafted with Pat Example.\n", local=["Pat Example"])
    assert not scan_text(tmp_path, "Drafted with Pat Example.\n")


def test_repository_is_clean() -> None:
    assert scanner.scan(ROOT, PATTERNS, []) == []
