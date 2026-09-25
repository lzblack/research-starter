"""Shared test fixtures: a synthetic template tree and a git checkout that contains it."""

import subprocess
from pathlib import Path

import pytest


def write(path: Path, text: str | bytes, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text)
    if executable:
        path.chmod(0o755)


def build_tree(t: Path) -> Path:
    write(t / "base" / "README.md.tmpl", "# @@name@@\n@@if not open@@\nprivate\n@@end@@\n")
    write(t / "base" / "static.txt.tmpl", "unchanged @@slug@@\n")
    write(t / "base" / "image.png", b"\x89PNG\r\n\x1a\n@@name@@")
    write(t / "base" / "hook", "#!/bin/sh\n", executable=True)
    write(t / "if-collaboration" / ".github" / "CODEOWNERS.tmpl", "@@list:codeowners@@\n/docs/status.md @@@lead.github@@\n")
    write(t / "if-open" / "OPEN.md", "open\n")
    write(t / "if-not-open" / "CLOSED.md", "closed\n")
    write(t / "parts" / "section.qmd.tmpl", "# @@section.title@@\n@@if section.first@@\nfirst\n@@end@@\n@@if section.human_drafted@@\nhuman\n@@end@@\n")
    write(t / "parts" / "template-provenance.md.tmpl", "commit @@generated.template_commit@@\n")
    return t


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    return build_tree(tmp_path / "template")


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.org", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def template_repo(tmp_path: Path) -> Path:
    """A template checkout with one commit, as `generate` expects."""
    root = tmp_path / "starter-checkout"
    build_tree(root / "template")
    git(root.parent, "init", "-q", "-b", "main", str(root))
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "template")
    return root
