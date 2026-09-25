"""The real template tree renders valid files for every fixture, even with hostile values."""

import tomllib
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from starter.answers import load_answers, validate
from starter.plan import build_plan

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = sorted((ROOT / "tests" / "fixtures" / "answers").glob("*.yml"))
GENERATED = {"date": "2026-01-15", "template_commit": "0" * 40}
HOSTILE = 'Name "quoted" \\ back @@slug@@ é'


def plans(path: Path, hostile: bool):
    answers = load_answers(path)
    if hostile:
        data = dict(answers.normalized, name=HOSTILE, description='a "b" \\ c')
        data["writing"] = dict(data["writing"], csl="")
        answers = validate(data, path.parent)
    return build_plan(answers, GENERATED, ROOT / "template")


@pytest.mark.parametrize("hostile", [False, True], ids=["plain", "hostile"])
@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_structured_files_parse(path: Path, hostile: bool) -> None:
    plan = plans(path, hostile)
    yaml = YAML(typ="safe", pure=True)
    for name, spec in plan.files.items():
        text = spec.content.decode() if not name.endswith(".png") else ""
        if name.endswith((".yml", ".yaml")):
            yaml.load(text)
        elif name.endswith(".toml") or name == "uv.lock":
            tomllib.loads(text)
    quarto = yaml.load(plan.files["paper/_quarto.yml"].content)
    if hostile:
        assert quarto["title"] == HOSTILE
        assert tomllib.loads(plan.files["pyproject.toml"].content.decode())["project"]["description"] == 'a "b" \\ c'


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_no_placeholder_left(path: Path) -> None:
    for name, spec in plans(path, hostile=False).files.items():
        if not name.endswith(".png"):
            assert b"@@" not in spec.content, name


def test_lock_names_the_project() -> None:
    plan = plans(FIXTURES[0], hostile=False)
    lock = tomllib.loads(plan.files["uv.lock"].content.decode())
    slug = load_answers(FIXTURES[0]).normalized["slug"]
    assert any(p["name"] == slug for p in lock["package"])
