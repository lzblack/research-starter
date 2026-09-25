"""File plan from answers and a template tree (appendix A1.4, A2, A3.1, A6.3, A9.3)."""

import os
from pathlib import Path

import pytest

from starter.answers import validate
from starter.plan import build_plan
from starter.render import TemplateError

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GENERATED = {"date": "2026-01-15", "template_commit": "abc123"}


def write(path: Path, text: str | bytes, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text)
    if executable:
        path.chmod(0o755)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    t = tmp_path / "template"
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


def answers(**changes: object) -> dict:
    data = {
        "schema": 1,
        "name": "Synthetic Project",
        "slug": "synthetic-project",
        "mode": "solo",
        "visibility": "closed",
        "people": [{"name": "Researcher A", "github": "researcher-a", "role": "lead"}],
        "writing": {"sections": ["intro", "data-work"], "human_drafted": ["data-work"]},
    }
    data.update(changes)
    return data


def plan_for(tree: Path, **changes: object):
    return build_plan(validate(answers(**changes), FIXTURES / "answers"), GENERATED, tree)


def test_solo_closed(tree: Path) -> None:
    plan = plan_for(tree)
    assert list(plan.files) == sorted(plan.files)
    assert set(plan.files) == {
        "project.yml",
        "README.md",
        "static.txt",
        "image.png",
        "hook",
        "CLOSED.md",
        "paper/sections/intro.qmd",
        "paper/sections/data-work.qmd",
        "docs/decisions/2026-01-15-template-provenance-0000.md",
    }
    assert plan.files["README.md"].content == b"# Synthetic Project\nprivate\n"
    assert plan.files["image.png"].content == b"\x89PNG\r\n\x1a\n@@name@@"
    assert plan.files["hook"].executable
    assert not plan.files["README.md"].executable
    assert plan.files["paper/sections/intro.qmd"].content == b"# Intro\nfirst\n"
    assert plan.files["paper/sections/data-work.qmd"].content == b"# Data work\nhuman\n"
    assert plan.files["docs/decisions/2026-01-15-template-provenance-0000.md"].content == b"commit abc123\n"
    assert b'template_commit: "abc123"' in plan.files["project.yml"].content


def test_team_open_with_codeowners(tree: Path) -> None:
    people = [
        {"name": "Researcher A", "github": "researcher-a", "role": "lead", "consent_open": True,
         "reviews": ["paper/sections/"]},
        {"name": "Researcher B", "github": "researcher-b", "role": "contributor", "consent_open": True,
         "reviews": ["paper/sections/intro.qmd", "paper/sections/"]},
    ]  # fmt: skip
    plan = plan_for(tree, mode="team", visibility="open", people=people)
    assert "OPEN.md" in plan.files and "CLOSED.md" not in plan.files
    assert plan.files[".github/CODEOWNERS"].content == (
        b"paper/sections/ @researcher-a @researcher-b\n"
        b"paper/sections/intro.qmd @researcher-b\n"
        b"/docs/status.md @researcher-a\n"
    )
    assert len(plan.warnings) == 1
    location, message = plan.warnings[0]
    assert location == "CODEOWNERS" and "paper/sections/intro.qmd" in message


def test_csl_copied(tree: Path) -> None:
    plan = plan_for(tree, writing={"csl": "../styles/minimal-test.csl"})
    assert plan.files["paper/minimal-test.csl"].content == (FIXTURES / "styles" / "minimal-test.csl").read_bytes()


def test_collision_is_template_error(tree: Path) -> None:
    write(tree / "if-not-open" / "README.md", "clash\n")
    with pytest.raises(TemplateError):
        plan_for(tree)


def test_unexpected_template_directory(tree: Path) -> None:
    (tree / "if-bogus").mkdir()
    with pytest.raises(TemplateError):
        plan_for(tree)


def test_symlink_in_template_rejected(tree: Path) -> None:
    os.symlink(tree / "base" / "hook", tree / "base" / "link")
    with pytest.raises(TemplateError):
        plan_for(tree)


def test_same_inputs_same_plan(tree: Path) -> None:
    assert plan_for(tree).files == plan_for(tree).files
