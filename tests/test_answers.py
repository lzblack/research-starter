"""Answers file loading, validation, and normalization (appendix A1.3, A1.4, A2, A3.1)."""

import copy
import textwrap
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from starter.answers import AnswersError, dump_yaml, load_answers, load_yaml_strict, validate

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ANSWERS = sorted((FIXTURES / "answers").glob("*.yml"))
CSL = FIXTURES / "styles" / "minimal-test.csl"


def base() -> dict:
    return {
        "schema": 1,
        "name": "Synthetic Project",
        "slug": "synthetic-project",
        "mode": "solo",
        "visibility": "closed",
        "people": [{"name": "Researcher A", "role": "lead"}],
    }


def team() -> dict:
    data = base()
    data["mode"] = "team"
    data["people"] = [
        {"name": "Researcher A", "github": "researcher-a", "role": "lead"},
        {"name": "Researcher B", "github": "researcher-b", "role": "contributor"},
    ]
    return data


def errors(data: dict, base_dir: Path = FIXTURES / "answers") -> dict[str, str]:
    with pytest.raises(AnswersError) as info:
        validate(data, base_dir)
    return {issue.location: issue.message for issue in info.value.issues}


def load_text(text: str) -> object:
    return load_yaml_strict(textwrap.dedent(text), "answers.yml")


# --- Strict YAML -------------------------------------------------------------------------------


def test_yaml_12_keeps_no_as_string() -> None:
    assert load_text("language: no\n") == {"language": "no"}


@pytest.mark.parametrize(
    "text",
    [
        "a: 1\na: 2\n",
        "a: &x [1]\nb: *x\n",
        "a: !!python/object:os.system x\n",
        "a: !custom x\n",
        "a: [1\n",
    ],
    ids=["duplicate-key", "alias", "python-tag", "custom-tag", "syntax"],
)
def test_yaml_rejects(text: str) -> None:
    with pytest.raises(AnswersError):
        load_text(text)


# --- Valid inputs ------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ANSWERS, ids=lambda p: p.stem)
def test_fixtures_are_valid(path: Path) -> None:
    load_answers(path)


def test_defaults_applied() -> None:
    result = validate(base(), FIXTURES)
    n = result.normalized
    assert n["language"] == "en"
    assert n["type"] == "paper"
    assert n["description"] == ""
    assert n["modules"] == {}
    assert n["writing"]["formats"] == ["docx", "pdf"]
    assert n["writing"]["sections"] == ["introduction", "data", "methods", "results", "conclusion"]
    assert n["writing"]["human_drafted"] == []
    assert n["writing"]["csl"] == ""
    assert n["reviewer_persona"]
    assert n["data"]["large_store"] == ""
    assert n["review_gates"] == []
    assert n["project_rules"] == ""
    assert result.csl_source is None


def test_report_type_default_sections() -> None:
    data = base()
    data["type"] = "report"
    sections = validate(data, FIXTURES).normalized["writing"]["sections"]
    assert sections == ["summary", "background", "methods", "findings", "conclusion"]


def test_explicit_sections_win_over_type() -> None:
    data = base()
    data["type"] = "report"
    data["writing"] = {"sections": ["one", "two"]}
    assert validate(data, FIXTURES).normalized["writing"]["sections"] == ["one", "two"]


def test_language_no_is_accepted_as_a_tag() -> None:
    data = base()
    data["language"] = "no"
    assert validate(data, FIXTURES).normalized["language"] == "no"


# --- Normalization and serialization (A3.1) ----------------------------------------------------


def test_normalization_ignores_format_order_defaults_and_key_order() -> None:
    a = base()
    a["writing"] = {"formats": ["pdf", "docx"]}
    b = {key: base()[key] for key in reversed(list(base()))}
    b["language"] = "en"
    b["writing"] = {"formats": ["docx", "pdf"], "human_drafted": []}
    assert dump_yaml(validate(a, FIXTURES).normalized) == dump_yaml(validate(b, FIXTURES).normalized)


def test_csl_reduced_to_file_name(tmp_path: Path) -> None:
    other = tmp_path / "styles"
    other.mkdir()
    (other / "minimal-test.csl").write_bytes(CSL.read_bytes())
    a = base()
    a["writing"] = {"csl": "../styles/minimal-test.csl"}
    b = base()
    b["writing"] = {"csl": "styles/minimal-test.csl"}
    ra = validate(a, FIXTURES / "answers")
    rb = validate(b, tmp_path)
    assert ra.normalized == rb.normalized
    assert ra.normalized["writing"]["csl"] == "minimal-test.csl"
    assert ra.csl_source == CSL.resolve()


def test_nfc_normalization() -> None:
    data = base()
    data["name"] = "Cafe\u0301 study"
    assert validate(data, FIXTURES).normalized["name"] == "Caf\u00e9 study"


@pytest.mark.parametrize(
    "value",
    [
        "plain",
        "",
        "yes",
        "no",
        "123",
        "2026-01-31",
        'with "quotes" and \\ backslash',
        "line one\nline two\n",
        "line one\nline two",
        "trailing blank lines\n\n\n",
        "  leading spaces\nsecond",
        "tab\there",
        "a: colon and # hash",
        "unicode \u00e9\u4e2d\U0001f600",
        "control \x07 char",
        "carriage\r\nreturn",
        "@@name@@ placeholder text",
    ],
)
def test_dump_round_trips(value: str) -> None:
    obj = {"text": value, "items": [value], "flag": True, "count": 1, "empty": [], "map": {}}
    text = dump_yaml(obj)
    assert YAML(typ="safe", pure=True).load(text) == obj
    assert load_yaml_strict(text, "dump") == obj


def test_dump_is_block_style_in_given_order() -> None:
    text = dump_yaml({"b": 1, "a": {"y": ["x"], "x": []}})
    assert text == 'b: 1\na:\n  y:\n    - "x"\n  x: []\n'


# --- Type and field errors ---------------------------------------------------------------------


def test_unknown_field() -> None:
    data = base()
    data["colour"] = "blue"
    assert "colour" in errors(data)


def test_generated_block_not_allowed_in_answers() -> None:
    data = base()
    data["generated"] = {"date": "2026-01-01"}
    assert "generated" in errors(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", 2),
        ("schema", "1"),
        ("schema", True),
        ("slug", 2024),
        ("slug", "Bad_Slug"),
        ("slug", "a--b"),
        ("slug", "ab"),
        ("slug", "x" * 51),
        ("slug", "ends-with-"),
        ("name", ""),
        ("name", "x" * 121),
        ("name", "two\nlines"),
        ("description", "x" * 501),
        ("language", "english"),
        ("language", False),
        ("type", "thesis"),
        ("mode", "duo"),
        ("visibility", "public"),
        ("reviewer_persona", "x" * 2001),
        ("project_rules", "x" * 10001),
        ("modules", {"collaboration": True}),
        ("modules", []),
    ],
)
def test_field_errors(field: str, value: object) -> None:
    data = base()
    data[field] = value
    assert field in errors(data)


def test_missing_required_fields() -> None:
    found = errors({"schema": 1})
    for field in ["name", "slug", "mode", "visibility", "people"]:
        assert field in found


def test_date_scalar_in_string_field() -> None:
    data = load_text(
        """\
        schema: 1
        name: 2026-01-31
        slug: synthetic-project
        mode: solo
        visibility: closed
        people:
          - name: Researcher A
            role: lead
        """
    )
    assert "name" in errors(data)


@pytest.mark.parametrize(
    ("section", "value", "location"),
    [
        ("writing", {"formats": []}, "writing.formats"),
        ("writing", {"formats": ["docx", "docx"]}, "writing.formats"),
        ("writing", {"formats": ["html"]}, "writing.formats[0]"),
        ("writing", {"sections": []}, "writing.sections"),
        ("writing", {"sections": ["a", "a"]}, "writing.sections"),
        ("writing", {"sections": ["Bad"]}, "writing.sections[0]"),
        ("writing", {"human_drafted": ["unknown"]}, "writing.human_drafted[0]"),
        ("writing", {"csl": "missing.csl"}, "writing.csl"),
        ("writing", {"csl": "style.txt"}, "writing.csl"),
        ("writing", {"unknown": 1}, "writing.unknown"),
        ("data", {"large_store": "/home/someone/data"}, "data.large_store"),
        ("data", {"large_store": "file:///tmp/x"}, "data.large_store"),
        ("data", {"large_store": "relative/path"}, "data.large_store"),
        ("review_gates", ["a", "a"], "review_gates"),
        ("review_gates", ["Bad Gate"], "review_gates[0]"),
    ],
)
def test_nested_errors(section: str, value: object, location: str) -> None:
    data = base()
    data[section] = value
    assert location in errors(data)


def test_csl_with_wrong_root(tmp_path: Path) -> None:
    (tmp_path / "bad.csl").write_text("<?xml version='1.0'?><html/>")
    data = base()
    data["writing"] = {"csl": "bad.csl"}
    assert "writing.csl" in errors(data, tmp_path)


@pytest.mark.parametrize("store", ["", "~/store", "s3://bucket/path", "https://example.org/data"])
def test_large_store_accepted(store: str) -> None:
    data = base()
    data["data"] = {"large_store": store}
    assert validate(data, FIXTURES).normalized["data"]["large_store"] == store


# --- People and cross-field rules (A1.3, A2.5) -------------------------------------------------


def test_first_person_must_be_lead() -> None:
    data = team()
    data["people"].reverse()
    assert "people[0].role" in errors(data)


def test_exactly_one_lead() -> None:
    data = team()
    data["people"][1]["role"] = "lead"
    assert "people[1].role" in errors(data)


def test_solo_with_two_non_readers() -> None:
    data = team()
    data["mode"] = "solo"
    assert "people" in errors(data)


def test_team_with_one_non_reader() -> None:
    data = base()
    data["mode"] = "team"
    data["people"][0]["github"] = "researcher-a"
    assert "people" in errors(data)


def test_team_requires_github() -> None:
    data = team()
    del data["people"][1]["github"]
    assert "people[1].github" in errors(data)


def test_reader_rules() -> None:
    data = base()
    data["people"].append(
        {"name": "Reader B", "role": "reader", "github": "reader-b", "owns": ["paper/sections/data.qmd"]}
    )
    found = errors(data)
    assert "people[1].github" in found
    assert "people[1].owns" in found


def test_reviews_require_github() -> None:
    data = base()
    data["people"][0]["reviews"] = ["paper/sections/"]
    assert "people[0].reviews" in errors(data)


def test_open_requires_everyone_to_consent() -> None:
    data = base()
    data["visibility"] = "open"
    data["people"][0]["consent_open"] = True
    data["people"].append({"name": "Reader B", "role": "reader"})
    assert "people[1].consent_open" in errors(data)
    data["people"][1]["consent_open"] = False
    assert "people[1].consent_open" in errors(data)


def test_consent_type() -> None:
    data = base()
    data["visibility"] = "open"
    data["people"][0]["consent_open"] = "yes"
    assert "people[0].consent_open" in errors(data)


def test_duplicate_names_and_handles() -> None:
    data = team()
    data["people"][1]["name"] = "researcher a"
    data["people"][1]["github"] = "Researcher-A"
    found = errors(data)
    assert "people[1].name" in found
    assert "people[1].github" in found


@pytest.mark.parametrize("handle", ["-bad", "bad-", "a--b", "x" * 40, "under_score"])
def test_bad_github_handle(handle: str) -> None:
    data = base()
    data["people"][0]["github"] = handle
    assert "people[0].github" in errors(data)


@pytest.mark.parametrize(
    "pattern",
    ["", "/paper/sections/data.qmd", "paper/../x.qmd", "paper\\sections", "data.qmd", "paper/", "paper/[a].qmd"],
)
def test_bad_path_patterns(pattern: str) -> None:
    data = base()
    data["people"][0]["owns"] = [pattern]
    assert "people[0].owns[0]" in errors(data)


def test_owns_must_match_a_section() -> None:
    data = base()
    data["people"][0]["owns"] = ["notebooks/main.py"]
    assert "people[0].owns[0]" in errors(data)


def test_section_owned_twice() -> None:
    data = team()
    data["people"][0]["owns"] = ["paper/sections/"]
    data["people"][1]["owns"] = ["paper/sections/data.qmd"]
    assert "people[1].owns[0]" in errors(data)


def test_owns_with_globs() -> None:
    data = team()
    data["people"][1]["owns"] = ["paper/sections/*.qmd"]
    validate(data, FIXTURES)


def test_errors_do_not_mutate_input() -> None:
    data = team()
    before = copy.deepcopy(data)
    validate(data, FIXTURES)
    assert data == before
