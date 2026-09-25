"""`accept` preconditions and the render-content text rules (appendix A7.3)."""

from pathlib import Path

import pytest

from starter.accept import accept, render_problems

GOOD = "Title 1. Introduction This reports 1,000 observations (Table 1 and Figure 1), following Example (2020)."


def test_good_text() -> None:
    assert render_problems(GOOD, value="1,000", first_title="Introduction", english=True) == []


def test_pdf_heading_style() -> None:
    text = GOOD.replace("1. Introduction", "1 Introduction")
    assert render_problems(text, value="1,000", first_title="Introduction", english=True) == []


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        (GOOD.replace("1,000", "?var:example_n_obs"), "value"),
        (GOOD.replace("1. Introduction", "Introduction"), "heading"),
        (GOOD.replace("Table 1", "?@tbl-example_table"), "Table 1"),
        (GOOD.replace("Example (2020)", "(example2020?)"), "unresolved"),
    ],
)
def test_problems(text: str, fragment: str) -> None:
    problems = render_problems(text, value="1,000", first_title="Introduction", english=True)
    assert any(fragment in p for p in problems), problems


def test_table_label_not_required_outside_english() -> None:
    text = GOOD.replace("Table 1", "Tabelle 1")
    assert render_problems(text, value="1,000", first_title="Introduction", english=False) == []


def test_not_a_project(tmp_path: Path) -> None:
    outcome = accept(tmp_path, github=False, template_root=tmp_path)
    assert outcome.code == 5


def test_unreadable_project_yml(tmp_path: Path) -> None:
    (tmp_path / "project.yml").write_text("schema: 1\n")
    assert accept(tmp_path, github=False, template_root=tmp_path).code == 5


def test_copy_uses_the_index_not_the_working_tree(tmp_path: Path) -> None:
    import subprocess

    from starter.accept import _copy_tracked

    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
    (source / "kept.txt").write_text("staged\n")
    (source / "deleted.txt").write_text("gone\n")
    subprocess.run(["git", "add", "-A"], cwd=source, check=True)
    (source / "kept.txt").write_text("edited but not staged\n")
    (source / "deleted.txt").unlink()
    copy = tmp_path / "copy"
    copy.mkdir()
    _copy_tracked(source, copy)
    assert (copy / "kept.txt").read_text() == "staged\n"
    assert (copy / "deleted.txt").read_text() == "gone\n"
