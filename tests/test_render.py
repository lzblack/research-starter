"""Template syntax (appendix A1.4): conditionals, list expansions, and scalar placeholders."""

import tomllib

import pytest
from ruamel.yaml import YAML

from starter.render import Context, TemplateError, render

NASTY = 'quote " backslash \\ newline\nnext tab\t bell \x07 @@slug@@   end'


def ctx(**scalars: str) -> Context:
    return Context(
        scalars={"slug": "demo", "name": "Demo", **scalars},
        flags={"open": True, "collaboration": False},
        lists={"authors": ['- "A"', '- "B"'], "empty": [], "includes": ["{{< include a.qmd >}}", ""]},
    )


def test_plain_text_unchanged() -> None:
    assert render("no placeholders here\n", ctx(), "t") == "no placeholders here\n"


def test_conditionals() -> None:
    text = "a\n@@if open@@\nb\n@@end@@\n@@if collaboration@@\nc\n@@end@@\n@@if not collaboration@@\nd\n@@end@@\n"
    assert render(text, ctx(), "t") == "a\nb\nd\n"


def test_nested_conditionals() -> None:
    text = "@@if open@@\nx\n  @@if collaboration@@\ny\n  @@end@@\nz\n@@end@@\n"
    assert render(text, ctx(), "t") == "x\nz\n"


@pytest.mark.parametrize(
    "text",
    ["@@if open@@\nx\n", "x\n@@end@@\n", "@@if unknown@@\nx\n@@end@@\n", "@@if open extra@@\n@@end@@\n"],
    ids=["unclosed", "stray-end", "unknown-flag", "bad-syntax"],
)
def test_conditional_errors(text: str) -> None:
    with pytest.raises(TemplateError):
        render(text, ctx(), "t")


def test_list_expansion_keeps_indentation() -> None:
    assert render("author:\n  @@list:authors@@\nend\n", ctx(), "t") == 'author:\n  - "A"\n  - "B"\nend\n'


def test_empty_list_and_blank_items() -> None:
    assert render("a\n@@list:empty@@\nb\n", ctx(), "t") == "a\nb\n"
    assert render("  @@list:includes@@\n", ctx(), "t") == "  {{< include a.qmd >}}\n\n"


def test_unknown_list() -> None:
    with pytest.raises(TemplateError):
        render("@@list:nope@@\n", ctx(), "t")


def test_bare_placeholder_is_verbatim() -> None:
    assert render("# @@name@@\n", ctx(name=NASTY), "t") == f"# {NASTY}\n"


def test_quoted_placeholder_is_valid_yaml_and_toml() -> None:
    out = render('title: "@@name@@"\n', ctx(name=NASTY), "t.yml")
    assert YAML(typ="safe", pure=True).load(out) == {"title": NASTY}
    out = render('title = "@@name@@"\n', ctx(name=NASTY), "t.toml")
    assert tomllib.loads(out) == {"title": NASTY}


def test_single_pass() -> None:
    value = "@@slug@@ and @@name@@"
    assert render("x @@name@@ y\n", ctx(name=value), "t") == f"x {value} y\n"


def test_values_never_become_conditionals() -> None:
    rules = "@@if collaboration@@\nsecret\n@@end@@"
    assert render("@@project_rules@@\n", ctx(project_rules=rules), "t") == rules + "\n"


def test_list_items_are_not_scanned() -> None:
    c = ctx()
    c.lists["authors"] = ['- "@@slug@@"']
    assert render("@@list:authors@@\n", c, "t") == '- "@@slug@@"\n'


def test_at_sign_before_placeholder() -> None:
    assert render("/docs/status.md @@@slug@@\n", ctx(), "t") == "/docs/status.md @demo\n"


def test_unknown_placeholder() -> None:
    with pytest.raises(TemplateError):
        render("@@nope@@\n", ctx(), "t")
