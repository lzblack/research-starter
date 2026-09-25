"""Answers file: strict loading, validation, normalization, and serialization.

Implements appendix A1.3 (schema), A1.4 (path patterns), A2.3 (default sections), A2.5 (invalid
combinations), and A3.1 (normalization). All problems are collected and reported together.
"""

import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.events import AliasEvent, CollectionStartEvent, ScalarEvent

from starter.patterns import matches, pattern_error

SCHEMA_VERSION = 1

DEFAULT_SECTIONS = {
    "paper": ["introduction", "data", "methods", "results", "conclusion"],
    "report": ["summary", "background", "methods", "findings", "conclusion"],
}

DEFAULT_PERSONA = (
    "A careful reviewer in the project's field who checks whether each claim is supported by "
    "the evidence it cites and reports numbered concerns by severity, without rewriting the text."
)

FORMATS = ["docx", "pdf"]
CSL_NAMESPACE = "{http://purl.org/net/xbiblio/csl}style"
CSL_MAX_BYTES = 1_000_000

SLUG = re.compile(r"^[a-z][a-z0-9-]{1,48}[a-z0-9]$")
LANGUAGE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
IDENT = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
GITHUB = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
URI = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*)://\S+$")
CSL_NAME = re.compile(r"^[A-Za-z0-9._-]+\.csl$")

TOP_FIELDS = [
    "schema", "name", "slug", "description", "language", "type", "mode", "visibility", "people",
    "modules", "writing", "reviewer_persona", "data", "review_gates", "project_rules",
]  # fmt: skip
WRITING_FIELDS = ["formats", "csl", "sections", "human_drafted"]
DATA_FIELDS = ["large_store"]
PERSON_FIELDS = ["name", "github", "role", "owns", "reviews", "consent_open"]
ROLES = ["lead", "contributor", "reader"]


@dataclass(frozen=True)
class Issue:
    location: str
    message: str


class AnswersError(Exception):
    def __init__(self, issues: list[Issue]) -> None:
        super().__init__("; ".join(f"{i.location}: {i.message}" for i in issues))
        self.issues = issues


@dataclass(frozen=True)
class Answers:
    normalized: dict[str, Any]
    csl_source: Path | None


# --- Strict YAML -------------------------------------------------------------------------------


def load_yaml_strict(text: str, source: str) -> Any:
    """Parse YAML 1.2 with a safe loader, rejecting anchors, aliases, tags, and duplicate keys."""
    yaml = YAML(typ="safe", pure=True)
    try:
        for event in yaml.parse(text):
            if isinstance(event, AliasEvent):
                raise AnswersError([Issue(source, "aliases are not allowed")])
            if isinstance(event, ScalarEvent | CollectionStartEvent):
                if event.anchor:
                    raise AnswersError([Issue(source, "anchors are not allowed")])
                if event.tag is not None:
                    raise AnswersError([Issue(source, f"tags are not allowed ({event.tag})")])
        return yaml.load(text)
    except YAMLError as exc:
        message = " ".join(str(exc).split("To suppress this check")[0].split())
        raise AnswersError([Issue(source, f"invalid YAML: {message}")]) from exc


def load_answers(path: Path) -> Answers:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AnswersError([Issue(str(path), f"cannot read answers file: {exc}")]) from exc
    return validate(load_yaml_strict(text, str(path)), path.parent)


# --- Validation --------------------------------------------------------------------------------


class _Checker:
    def __init__(self) -> None:
        self.issues: list[Issue] = []

    def fail(self, location: str, message: str) -> None:
        self.issues.append(Issue(location, message))

    def string(
        self,
        value: Any,
        loc: str,
        *,
        max_len: int,
        min_len: int = 0,
        one_line: bool = True,
        pattern: re.Pattern[str] | None = None,
    ) -> str | None:
        if not isinstance(value, str):
            self.fail(loc, f"must be a string, not {_type_name(value)}; quote the value")
            return None
        value = unicodedata.normalize("NFC", value)
        allowed = set() if one_line else {"\n", "\t"}
        if any(unicodedata.category(ch) == "Cc" and ch not in allowed for ch in value):
            self.fail(loc, "must be a single line" if one_line else "contains control characters")
            return None
        if not min_len <= len(value) <= max_len:
            self.fail(loc, f"must have {min_len}-{max_len} characters")
            return None
        if pattern is not None and not pattern.match(value):
            self.fail(loc, f"must match {pattern.pattern}")
            return None
        return value

    def choice(self, value: Any, loc: str, options: list[str]) -> str | None:
        if not isinstance(value, str) or value not in options:
            self.fail(loc, f"must be one of: {', '.join(options)}")
            return None
        return value

    def mapping(self, value: Any, loc: str, fields: list[str]) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            self.fail(loc, f"must be a mapping, not {_type_name(value)}")
            return None
        for key in value:
            if key not in fields:
                where = f"{loc}.{key}" if loc else str(key)
                self.fail(where, "unknown field")
        return value

    def string_list(
        self,
        value: Any,
        loc: str,
        *,
        pattern: re.Pattern[str] | None = None,
        non_empty: bool = False,
        unique: bool = True,
    ) -> list[str] | None:
        if not isinstance(value, list):
            self.fail(loc, f"must be a list, not {_type_name(value)}")
            return None
        if non_empty and not value:
            self.fail(loc, "must not be empty")
            return None
        items = []
        ok = True
        for i, item in enumerate(value):
            checked = self.string(item, f"{loc}[{i}]", max_len=200, min_len=1, pattern=pattern)
            ok = ok and checked is not None
            items.append(checked)
        if not ok:
            return None
        if unique and len(set(items)) != len(items):
            self.fail(loc, "entries must be unique")
            return None
        return items


def _type_name(value: Any) -> str:
    return {bool: "a boolean", int: "an integer", float: "a number", list: "a list", dict: "a mapping",
            type(None): "empty"}.get(type(value), type(value).__name__)  # fmt: skip


def validate(data: Any, base_dir: Path) -> Answers:
    """Validate parsed answers and return them normalized. `base_dir` resolves `writing.csl`."""
    c = _Checker()
    top = c.mapping(data, "", TOP_FIELDS + ["generated"])
    if top is None:
        raise AnswersError(c.issues)
    if "generated" in top:
        c.fail("generated", "is written by setup and must not appear in the answers file")

    for field in ["schema", "name", "slug", "mode", "visibility", "people"]:
        if field not in top:
            c.fail(field, "is required")

    schema = top.get("schema")
    if "schema" in top and (type(schema) is not int or schema != SCHEMA_VERSION):
        c.fail("schema", f"must be the integer {SCHEMA_VERSION}")

    n: dict[str, Any] = {"schema": SCHEMA_VERSION}
    n["name"] = c.string(top.get("name"), "name", min_len=1, max_len=120) if "name" in top else None
    slug = c.string(top["slug"], "slug", max_len=50, pattern=SLUG) if "slug" in top else None
    if slug is not None and "--" in slug:
        c.fail("slug", "must not contain '--'")
    n["slug"] = slug
    n["description"] = c.string(top.get("description", ""), "description", max_len=500)
    n["language"] = c.string(top.get("language", "en"), "language", max_len=35, pattern=LANGUAGE)
    n["type"] = c.choice(top.get("type", "paper"), "type", ["paper", "report"])
    n["mode"] = c.choice(top["mode"], "mode", ["solo", "team"]) if "mode" in top else None
    n["visibility"] = (
        c.choice(top["visibility"], "visibility", ["open", "closed"]) if "visibility" in top else None
    )

    modules = top.get("modules", {})
    if not isinstance(modules, dict):
        c.fail("modules", "must be a mapping")
    elif modules:
        c.fail("modules", "must be empty in schema 1; the collaboration module follows mode")
    n["people"] = None
    n["modules"] = {}

    n["writing"] = _writing(c, top.get("writing", {}), n["type"], base_dir)
    n["reviewer_persona"] = c.string(
        top.get("reviewer_persona", DEFAULT_PERSONA), "reviewer_persona", max_len=2000, one_line=False
    )
    n["data"] = _data(c, top.get("data", {}))
    n["review_gates"] = c.string_list(top.get("review_gates", []), "review_gates", pattern=IDENT)
    n["project_rules"] = c.string(
        top.get("project_rules", ""), "project_rules", max_len=10000, one_line=False
    )

    sections = (n["writing"] or {}).get("sections")
    if "people" in top:
        n["people"] = _people(c, top["people"], n["mode"], n["visibility"], sections)

    csl_source = (n["writing"] or {}).pop("_csl_source", None)
    if c.issues:
        raise AnswersError(c.issues)
    return Answers(normalized=n, csl_source=csl_source)


def _writing(c: _Checker, value: Any, doc_type: str | None, base_dir: Path) -> dict[str, Any] | None:
    w = c.mapping(value, "writing", WRITING_FIELDS)
    if w is None:
        return None
    out: dict[str, Any] = {}
    formats = c.string_list(w.get("formats", FORMATS), "writing.formats", non_empty=True)
    if formats is not None:
        bad = [i for i, f in enumerate(formats) if f not in FORMATS]
        for i in bad:
            c.fail(f"writing.formats[{i}]", f"must be one of: {', '.join(FORMATS)}")
        formats = None if bad else [f for f in FORMATS if f in formats]
    out["formats"] = formats

    out["csl"], out["_csl_source"] = _csl(c, w.get("csl", ""), base_dir)

    default_sections = DEFAULT_SECTIONS.get(doc_type or "paper")
    sections = c.string_list(
        w.get("sections", default_sections), "writing.sections", pattern=IDENT, non_empty=True
    )
    out["sections"] = sections
    human = c.string_list(w.get("human_drafted", []), "writing.human_drafted", pattern=IDENT)
    if human is not None and sections is not None:
        for i, section in enumerate(human):
            if section not in sections:
                c.fail(f"writing.human_drafted[{i}]", f"'{section}' is not in writing.sections")
    out["human_drafted"] = human
    return out


def _csl(c: _Checker, value: Any, base_dir: Path) -> tuple[str | None, Path | None]:
    text = c.string(value, "writing.csl", max_len=500)
    if not text:
        return text, None
    source = (base_dir / text).resolve()
    if not CSL_NAME.match(source.name):
        c.fail("writing.csl", "must name a file ending in .csl, using letters, digits, '.', '_', '-'")
        return None, None
    if not source.is_file():
        c.fail("writing.csl", f"file not found: {text}")
        return None, None
    if source.stat().st_size > CSL_MAX_BYTES:
        c.fail("writing.csl", "must be at most 1 MB")
        return None, None
    try:
        root = ET.parse(source).getroot()
    except ET.ParseError as exc:
        c.fail("writing.csl", f"is not valid XML: {exc}")
        return None, None
    if root.tag != CSL_NAMESPACE:
        c.fail("writing.csl", "must have a CSL style root element")
        return None, None
    return source.name, source


def _data(c: _Checker, value: Any) -> dict[str, Any] | None:
    d = c.mapping(value, "data", DATA_FIELDS)
    if d is None:
        return None
    store = c.string(d.get("large_store", ""), "data.large_store", max_len=500)
    if store:
        uri = URI.match(store)
        if store.startswith("~/"):
            pass
        elif uri is None:
            c.fail(
                "data.large_store",
                "must be empty, a path starting with ~/, or a URI; absolute paths are not allowed "
                "because they often contain a user name",
            )
            store = None
        elif uri.group(1).lower() == "file":
            c.fail("data.large_store", "file URIs are not allowed; use a path starting with ~/")
            store = None
    return {"large_store": store}


def _people(
    c: _Checker, value: Any, mode: str | None, visibility: str | None, sections: list[str] | None
) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or not value:
        c.fail("people", "must be a non-empty list")
        return None
    people: list[dict[str, Any] | None] = []
    for i, raw in enumerate(value):
        people.append(_person(c, raw, f"people[{i}]", visibility))
    if any(p is None for p in people):
        return None
    valid: list[dict[str, Any]] = [p for p in people if p is not None]

    if valid[0]["role"] != "lead":
        c.fail("people[0].role", "the first person must be the lead")
    for i, p in enumerate(valid[1:], start=1):
        if p["role"] == "lead":
            c.fail(f"people[{i}].role", "there must be exactly one lead, listed first")

    non_readers = sum(p["role"] != "reader" for p in valid)
    if mode == "solo" and non_readers != 1:
        c.fail("people", "solo mode requires exactly one person who is not a reader")
    if mode == "team" and non_readers < 2:
        c.fail("people", "team mode requires the lead and at least one contributor")

    names: dict[str, int] = {}
    handles: dict[str, int] = {}
    for i, p in enumerate(valid):
        key = unicodedata.normalize("NFC", p["name"]).casefold()
        if key in names:
            c.fail(f"people[{i}].name", f"duplicates the name of people[{names[key]}]")
        names.setdefault(key, i)
        if "github" in p:
            handle = p["github"].lower()
            if handle in handles:
                c.fail(f"people[{i}].github", f"duplicates the handle of people[{handles[handle]}]")
            handles.setdefault(handle, i)
        if mode == "team" and p["role"] != "reader" and "github" not in p:
            c.fail(f"people[{i}].github", "is required for the lead and contributors in team mode")

    if sections is not None:
        _ownership(c, valid, sections)
    return valid


def _person(c: _Checker, raw: Any, loc: str, visibility: str | None) -> dict[str, Any] | None:
    p = c.mapping(raw, loc, PERSON_FIELDS)
    if p is None:
        return None
    before = len(c.issues)
    out: dict[str, Any] = {}
    out["name"] = c.string(p.get("name"), f"{loc}.name", min_len=1, max_len=120)
    if "name" not in p:
        c.fail(f"{loc}.name", "is required")
    if "github" in p:
        out["github"] = c.string(p["github"], f"{loc}.github", max_len=39, pattern=GITHUB)
    out["role"] = c.choice(p.get("role"), f"{loc}.role", ROLES)
    for field in ["owns", "reviews"]:
        patterns = c.string_list(p.get(field, []), f"{loc}.{field}")
        if patterns is not None:
            for j, pattern in enumerate(patterns):
                problem = pattern_error(pattern)
                if problem:
                    c.fail(f"{loc}.{field}[{j}]", problem)
        out[field] = patterns
    if out["role"] == "reader":
        for field in ["github", "owns", "reviews"]:
            if p.get(field):
                c.fail(f"{loc}.{field}", "is not allowed for a reader")
    if out["reviews"] and "github" not in p:
        c.fail(f"{loc}.reviews", "requires github, because reviews become CODEOWNERS entries")
    if visibility == "open":
        consent = p.get("consent_open")
        if type(consent) is not bool:
            c.fail(f"{loc}.consent_open", "must be true or false and is required for open projects")
        elif not consent:
            c.fail(f"{loc}.consent_open", "an open project needs every person's consent")
        else:
            out["consent_open"] = True
    elif "consent_open" in p and type(p["consent_open"]) is not bool:
        c.fail(f"{loc}.consent_open", "must be true or false")
    if len(c.issues) > before:
        return None
    return out


def _ownership(c: _Checker, people: list[dict[str, Any]], sections: list[str]) -> None:
    owner: dict[str, int] = {}
    for i, p in enumerate(people):
        for j, pattern in enumerate(p["owns"]):
            files = [f"paper/sections/{s}.qmd" for s in sections]
            hit = [f for f in files if matches(pattern, f)]
            if not hit:
                c.fail(f"people[{i}].owns[{j}]", "matches no section file")
            for f in hit:
                if f in owner and owner[f] != i:
                    c.fail(f"people[{i}].owns[{j}]", f"{f} is already owned by people[{owner[f]}]")
                owner.setdefault(f, i)


# --- Serialization -----------------------------------------------------------------------------

_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}


def quote(value: str) -> str:
    """A double-quoted string valid in both YAML 1.2 and TOML."""
    out = []
    for ch in value:
        if ch in _ESCAPES:
            out.append(_ESCAPES[ch])
        elif unicodedata.category(ch) in {"Cc", "Zl", "Zp"} or ch == "\ufeff":
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _literal_ok(value: str) -> bool:
    if "\n" not in value or not value.strip("\n"):
        return False
    if any(unicodedata.category(ch) in {"Cc", "Zl", "Zp"} and ch != "\n" for ch in value):
        return False
    lines = value.split("\n")
    if any(line and not line.strip() for line in lines):
        return False
    first = next(line for line in lines if line)
    return not first.startswith(" ") and "\ufeff" not in value


def _scalar_lines(value: Any, indent: int) -> tuple[str, list[str]]:
    """Return the text after `key:` and any following lines, for a scalar value."""
    if type(value) is bool:
        return " true" if value else " false", []
    if type(value) is int:
        return f" {value}", []
    if not isinstance(value, str):
        raise TypeError(f"cannot serialize {type(value).__name__}")
    if not _literal_ok(value):
        return " " + quote(value), []
    trailing = len(value) - len(value.rstrip("\n"))
    chomp = "-" if trailing == 0 else ("" if trailing == 1 else "+")
    body = value[: len(value) - trailing] if trailing else value
    pad = " " * (indent + 2)
    lines = [pad + line if line else "" for line in body.split("\n")]
    lines += [""] * (trailing - 1 if trailing > 1 else 0)
    return f" |{chomp}", lines


def _emit(obj: Any, indent: int) -> list[str]:
    pad = " " * indent
    lines: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, dict) and value:
                lines.append(f"{pad}{key}:")
                lines.extend(_emit(value, indent + 2))
            elif isinstance(value, list) and value:
                lines.append(f"{pad}{key}:")
                lines.extend(_emit(value, indent + 2))
            elif isinstance(value, dict | list):
                lines.append(f"{pad}{key}: {'{}' if isinstance(value, dict) else '[]'}")
            else:
                head, rest = _scalar_lines(value, indent)
                lines.append(f"{pad}{key}:{head}")
                lines.extend(rest)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict) and item:
                inner = _emit(item, indent + 2)
                inner[0] = f"{pad}- " + inner[0][indent + 2 :]
                lines.extend(inner)
            elif isinstance(item, dict | list):
                lines.append(f"{pad}- {'{}' if isinstance(item, dict) else '[]'}")
            else:
                head, rest = _scalar_lines(item, indent)
                lines.append(f"{pad}-{head}")
                lines.extend(rest)
    else:
        raise TypeError("top level must be a mapping or list")
    return lines


def dump_yaml(obj: dict[str, Any]) -> str:
    """Deterministic block-style YAML for mappings, lists, strings, integers, and booleans."""
    return "\n".join(_emit(obj, 0)) + "\n"
