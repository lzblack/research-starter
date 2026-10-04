"""Markdown in this repository is written one paragraph or list item per line (docs/decisions/2026-10-04-markdown-line-breaks.md)."""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RULE_DATE = "2026-10-04"
LEAF_START = re.compile(r"(#{1,6}\s|\||<|```|~~~|(-{3,}|\*{3,}|_{3,})\s*$|\[[^\]]+\]:\s)")
ITEM_START = re.compile(r"([-*+]|\d+[.)])\s")


def body(line: str) -> str:
    """The line without blockquote markers and indentation."""
    return re.sub(r"^(\s*>)+", "", line).strip()


def is_text(line: str) -> bool:
    """A line of paragraph text, possibly the first line of a list item."""
    text = body(line)
    return bool(text) and not LEAF_START.match(text)


def hard_wraps(text: str) -> list[int]:
    """Line numbers of prose lines that continue on the next line without a hard line break."""
    lines = text.splitlines()
    start = 0
    if lines and lines[0] == "---":
        start = next((i + 1 for i, line in enumerate(lines[1:], 1) if line == "---"), 0)
    found, fenced = [], False
    for n in range(start, len(lines)):
        line = lines[n]
        if body(line).startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced or n + 1 >= len(lines) or line.endswith(("  ", "\\")):
            continue
        if is_text(line) and is_text(lines[n + 1]) and not ITEM_START.match(body(lines[n + 1])):
            found.append(n + 1)
    return found


def in_scope(path: str) -> bool:
    if path.startswith("template/"):
        return False
    name = Path(path).name
    return not (path.startswith("docs/decisions/") and name[:10] < RULE_DATE)


def tracked_markdown() -> list[str]:
    out = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if in_scope(p)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("One paragraph on one line.\n\nAnother one.\n", []),
        ("A paragraph wrapped\nat a column.\n", [1]),
        ("- An item wrapped\n  onto a second line.\n- Next item.\n", [1]),
        ("> A quote wrapped\n> onto a second line.\n", [1]),
        ("- Item.\n  - Nested item.\n- Item.\n", []),
        ("Steps:\n1. First.\n2. Second.\n", []),
        ("# Heading\nText right below.\n", []),
        ("```\ncode line one\ncode line two\n```\n", []),
        ("| a | b |\n|---|---|\n| 1 | 2 |\n", []),
        ("Hard break  \nnext line.\n\nA backslash\\\nbreak.\n", []),
        ("---\ntitle: x\nauthor: y\n---\n\nText.\n", []),
        ("Text.\n[ref]: https://example.org\n", []),
    ],
)
def test_hard_wraps(text: str, expected: list[int]) -> None:
    assert hard_wraps(text) == expected


def test_scope() -> None:
    assert in_scope("docs/design/PRD.md") and in_scope("README.md")
    assert in_scope(f"docs/decisions/{RULE_DATE}-markdown-line-breaks.md")
    assert not in_scope("docs/decisions/2026-09-24-v0-scope.md")
    assert not in_scope("template/base/README.md")


def test_repository_markdown_is_not_hard_wrapped() -> None:
    problems = [f"{p}:{n}" for p in tracked_markdown() for n in hard_wraps((ROOT / p).read_text())]
    assert problems == [], "hard-wrapped prose; write one paragraph or list item per line:\n" + "\n".join(problems)
