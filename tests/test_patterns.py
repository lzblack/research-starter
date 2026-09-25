"""Path pattern syntax and matching (appendix A1.4)."""

import pytest

from starter.patterns import matches, pattern_error


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("paper/sections/data.qmd", "paper/sections/data.qmd", True),
        ("paper/sections/data.qmd", "paper/sections/data.qmd.bak", False),
        ("paper/sections/", "paper/sections/data.qmd", True),
        ("paper/sections", "paper/sections/data.qmd", True),
        ("paper/sections/", "paper/sections-old/data.qmd", False),
        ("paper/sections/*.qmd", "paper/sections/data.qmd", True),
        ("paper/sections/*.qmd", "paper/sections/sub/data.qmd", False),
        ("paper/**/data.qmd", "paper/data.qmd", True),
        ("paper/**/data.qmd", "paper/a/b/data.qmd", True),
        ("paper/**", "paper/a/b/c.qmd", True),
        ("docs/status.md", "sub/docs/status.md", False),
        ("paper/a.b", "paper/aXb", False),
    ],
)
def test_matches(pattern: str, path: str, expected: bool) -> None:
    assert pattern_error(pattern) is None
    assert matches(pattern, path) is expected


@pytest.mark.parametrize("pattern", ["", "/a/b", "a/../b", "a b/c", "name", "dir/", "a/[x]"])
def test_invalid(pattern: str) -> None:
    assert pattern_error(pattern) is not None


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("paper/*", "paper/paper.qmd", True),
        ("paper/*", "paper/sections/intro.qmd", False),
        ("paper/sections/*.qmd", "paper/sections/intro.qmd", True),
        ("paper/**", "paper/sections/intro.qmd", True),
    ],
)
def test_codeowners_star_semantics(pattern: str, path: str, expected: bool) -> None:
    assert matches(pattern, path) is expected
