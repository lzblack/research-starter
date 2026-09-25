"""Project checks, run by `uv run build.py check` (and by the pre-commit hook with --staged).

Each check reports pass, fail, warn, or not-tested, and states only what it establishes: the
data-exposure checks together mean "configured checks passed", not "no sensitive data exists".
"""

import fnmatch
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

PASS, FAIL, WARN, NOT_TESTED = "pass", "fail", "warn", "not-tested"
STATUS_LIMIT = 8000
SIZE_LIMIT = 10_000_000
YEARS = range(1800, 2101)
CLAUDE_IMPORT = "@AGENTS.md\n"
FORBIDDEN = ["*.duckdb", "*.duckdb.wal"]
CITE_KEY = r"[A-Za-z][A-Za-z0-9_-]*"
XREF = re.compile(r"(?<![\w@])@(tbl|fig|sec|eq)-([A-Za-z0-9_-]*[A-Za-z0-9_])")
LABEL = re.compile(r"\{#(tbl|fig|sec|eq)-([A-Za-z0-9_-]*[A-Za-z0-9_])[\s}]")
VAR = re.compile(r"\{\{<\s*var\s+([^\s>]+)\s*>\}\}")
INCLUDE = re.compile(r"\{\{<\s*include\s+([^\s>]+)\s*>\}\}")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
CITATION = re.compile(rf"(?<![\w@/.])-?@({CITE_KEY})")
QUOTE_SPAN = re.compile(r"\[([^\]]*)\]\{\.quote([^}]*)\}")
LOCATED_CITATION = re.compile(rf"^\s*\[-?@{CITE_KEY},[^\]]*\d[^\]]*\]")
BIB_ENTRY = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")
ABBREVIATIONS = {"e.g.", "i.e.", "al.", "Fig.", "fig.", "Eq.", "eq.", "vs.", "etc.", "Dr.", "Mr.", "Ms.",
                 "No.", "no.", "p.", "pp.", "Tab.", "cf.", "ca.", "approx.", "Sec.", "sec."}  # fmt: skip
SECRET_PATTERNS = {
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "AWS access key ID": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "Anthropic API key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    "OpenAI project API key": re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "secret assignment": re.compile(r"^\s*(?:export\s+)?[A-Z0-9_]*(?:_API_KEY|_SECRET|_TOKEN)\s*=\s*['\"]?[^\s'\"#]{8,}", re.M),
}  # fmt: skip
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
EXEMPT_DOMAINS = ("example.org", "example.com", "example.net", "noreply.github.com")
PHONE = re.compile(r"(?<![\w.])(?:\+\d{1,3}[\s-]\d{1,4}[\s-]\d{3,4}[\s-]\d{3,4}|\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b)")


@dataclass
class Result:
    check: str
    status: str
    problems: list[str] = field(default_factory=list)


def _yaml(text: str) -> Any:
    return YAML(typ="safe", pure=True).load(text)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blank(text: str, pattern: re.Pattern[str]) -> str:
    """Replace matches with spaces, keeping newlines, so line numbers stay correct."""
    return pattern.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


CODE_FENCE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.M | re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")
COMMENT = re.compile(r"<!--.*?-->", re.S)


def prose(text: str) -> str:
    return blank(blank(blank(text, CODE_FENCE), COMMENT), INLINE_CODE)


def pattern_matches(pattern: str, path: str) -> bool:
    """CODEOWNERS-style anchored pattern (the same rules as setup's path patterns)."""
    body = pattern.rstrip("/")
    out, i = [], 0
    while i < len(body):
        if body.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif body.startswith("**", i):
            out.append(".*")
            i += 2
        elif body[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(body[i]))
            i += 1
    last = body.rsplit("/", 1)[-1]
    below = "" if "*" in last and last != "**" else "(?:/.*)?"
    return re.match("^" + "".join(out) + below + "$", path) is not None


def pattern_error(pattern: Any) -> str | None:
    """Why a dataset path pattern is invalid (the setup rules for path patterns), or None."""
    if not isinstance(pattern, str) or not pattern:
        return "must be a non-empty string"
    if not re.fullmatch(r"[A-Za-z0-9._/*-]+", pattern):
        return "may contain only letters, digits, '.', '_', '-', '/', and '*'"
    if pattern.startswith("/"):
        return "must be relative (no leading '/')"
    if ".." in pattern.split("/"):
        return "must not contain a '..' segment"
    if "/" not in pattern[:-1]:
        return "must contain a '/' before its last character"
    return None


class Project:
    """Read access to the project, either as tracked files or as the staged index."""

    def __init__(self, root: Path, staged: bool = False) -> None:
        self.root = root
        self.staged = staged

    def _git(self, *args: str) -> str | None:
        try:
            result = subprocess.run(["git", *args], cwd=self.root, capture_output=True, check=False)
        except OSError:
            return None
        return result.stdout.decode("utf-8", "replace") if result.returncode == 0 else None

    @cached_property
    def tracked(self) -> list[str] | None:
        if self.staged:
            out = self._git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
        else:
            out = self._git("ls-files", "-z")
        return None if out is None else [p for p in out.split("\0") if p]

    def content(self, rel: str) -> bytes:
        if self.staged:
            result = subprocess.run(["git", "show", f":{rel}"], cwd=self.root, capture_output=True, check=False)
            return result.stdout
        path = self.root / rel
        return path.read_bytes() if path.is_file() and not path.is_symlink() else b""

    def text(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def exists(self, rel: str) -> bool:
        return (self.root / rel).is_file()

    @cached_property
    def sources(self) -> dict[str, str]:
        """Paper sources: .qmd files under paper/ and the files they include, as prose."""
        paper = self.root / "paper"
        found: dict[str, str] = {}
        pending = sorted(
            p.relative_to(self.root).as_posix()
            for p in paper.rglob("*.qmd")
            if not {"_output", ".quarto"} & set(p.relative_to(paper).parts)
        ) if paper.is_dir() else []  # fmt: skip
        while pending:
            rel = pending.pop(0)
            if rel in found or not self.exists(rel):
                continue
            found[rel] = prose(self.text(rel))
            for match in INCLUDE.finditer(found[rel]):
                pending.append(f"paper/{match.group(1)}")
        return found

    @cached_property
    def variables(self) -> dict[str, Any]:
        if not self.exists("paper/_variables.yml"):
            return {}
        return _yaml(self.text("paper/_variables.yml")) or {}

    @cached_property
    def manifest(self) -> dict[str, Any] | None:
        path = "paper/outputs/manifest.json"
        return json.loads(self.text(path)) if self.exists(path) else None

    @cached_property
    def project(self) -> dict[str, Any]:
        return _yaml(self.text("project.yml")) if self.exists("project.yml") else {}

    @cached_property
    def datasets(self) -> list[dict[str, Any]]:
        if not self.exists("data/README.md"):
            return []
        match = re.match(r"^---\n(.*?)\n---\n", self.text("data/README.md"), re.S)
        front = _yaml(match.group(1)) if match else {}
        return (front or {}).get("datasets") or []

    @cached_property
    def bibliography(self) -> list[dict[str, str]]:
        """Entries of paper/references.bib as {key, type, fields...}, fields in lower case."""
        if not self.exists("paper/references.bib"):
            return []
        text = self.text("paper/references.bib")
        entries = []
        starts = list(BIB_ENTRY.finditer(text))
        for i, match in enumerate(starts):
            if match.group(1).lower() in {"comment", "string", "preamble"}:
                continue
            body = text[match.end() : starts[i + 1].start() if i + 1 < len(starts) else len(text)]
            fields = {k.lower(): v.strip() for k, v in re.findall(r"(\w[\w-]*)\s*=\s*[{\"]([^}\"]*)[}\"]", body)}
            entries.append({"key": match.group(2), "type": match.group(1).lower(), **fields})
        return entries

    def lines(self, rel: str) -> list[tuple[int, str]]:
        return list(enumerate(self.sources[rel].splitlines(), start=1))


Check = Callable[[Project], Result]
REGISTRY: list[tuple[str, Check, bool]] = []


def check(name: str, hook: bool = False) -> Callable[[Check], Check]:
    def register(func: Check) -> Check:
        REGISTRY.append((name, func, hook))
        return func

    return register


def result(name: str, problems: list[str], severity: str = FAIL) -> Result:
    return Result(name, severity if problems else PASS, problems)


# --- References --------------------------------------------------------------------------------


@check("var-resolve")
def var_resolve(p: Project) -> Result:
    problems = [
        f"{rel}:{n}: variable '{m.group(1)}' is not in paper/_variables.yml"
        for rel in p.sources for n, line in p.lines(rel) for m in VAR.finditer(line)
        if m.group(1) not in p.variables
    ]  # fmt: skip
    return result("var-resolve", problems)


@check("var-unused")
def var_unused(p: Project) -> Result:
    used = {m.group(1) for text in p.sources.values() for m in VAR.finditer(text)}
    return result("var-unused", [f"variable '{k}' is never used" for k in p.variables if k not in used], WARN)


@check("xref-resolve")
def xref_resolve(p: Project) -> Result:
    labels = {(m.group(1), m.group(2)) for text in p.sources.values() for m in LABEL.finditer(text + "\n")}
    problems = [
        f"{rel}:{n}: @{m.group(1)}-{m.group(2)} has no matching label"
        for rel in p.sources for n, line in p.lines(rel) for m in XREF.finditer(line)
        if (m.group(1), m.group(2)) not in labels
    ]  # fmt: skip
    return result("xref-resolve", problems)


def citations(p: Project) -> list[tuple[str, int, str]]:
    found = []
    for rel in p.sources:
        for n, line in p.lines(rel):
            cleaned = XREF.sub(" ", VAR.sub(" ", line))
            found += [(rel, n, m.group(1)) for m in CITATION.finditer(cleaned)]
    return found


@check("cite-resolve")
def cite_resolve(p: Project) -> Result:
    keys = {e["key"] for e in p.bibliography}
    problems = [f"{rel}:{n}: citation key '{key}' is not in paper/references.bib"
                for rel, n, key in citations(p) if key not in keys]  # fmt: skip
    return result("cite-resolve", problems)


@check("include-resolve")
def include_resolve(p: Project) -> Result:
    problems = [
        f"{rel}:{n}: included file paper/{m.group(1)} does not exist"
        for rel in p.sources for n, line in p.lines(rel) for m in INCLUDE.finditer(line)
        if not p.exists(f"paper/{m.group(1)}")
    ]  # fmt: skip
    return result("include-resolve", problems)


@check("figure-resolve")
def figure_resolve(p: Project) -> Result:
    problems = [
        f"{rel}:{n}: image paper/{m.group(1)} does not exist"
        for rel in p.sources for n, line in p.lines(rel) for m in IMAGE.finditer(line)
        if "://" not in m.group(1) and not p.exists(f"paper/{m.group(1)}")
    ]  # fmt: skip
    return result("figure-resolve", problems)


# --- Outputs -----------------------------------------------------------------------------------


@check("output-freshness")
def output_freshness(p: Project) -> Result:
    if p.manifest is None:
        return Result("output-freshness", NOT_TESTED, ["no manifest"])
    versions = {d.get("id"): d.get("version") for d in p.datasets if isinstance(d, dict)}
    stale, untested = set(), set()
    for artifact in p.manifest.get("artifacts", []):
        producer = artifact.get("producer", "")
        if not p.exists(producer):
            stale.add(f"{producer} no longer exists")
        elif sha256(p.content(producer)) != artifact.get("producer_sha256"):
            stale.add(f"{producer} changed since the last analyze")
        for item in artifact.get("inputs", []):
            path = item.get("path", "")
            if path.startswith("dataset:"):
                version = item.get("version")
                if version is None:
                    untested.add(f"{path} has no declared version")
                elif versions.get(path.removeprefix("dataset:")) != version:
                    stale.add(f"{path} version changed since the last analyze")
            elif not p.exists(path):
                untested.add(f"{path} is not available here")
            elif sha256(p.content(path)) != item.get("sha256"):
                stale.add(f"{path} changed since the last analyze")
    if stale:
        return Result("output-freshness", WARN, sorted(stale) + sorted(untested))
    return Result("output-freshness", NOT_TESTED if untested else PASS, sorted(untested))


# --- Writing -----------------------------------------------------------------------------------


def section_files(p: Project) -> list[str]:
    return sorted(rel for rel in p.sources if rel.startswith("paper/sections/"))


def strip_references(line: str) -> str:
    for pattern in (VAR, INCLUDE, XREF, LABEL, QUOTE_SPAN, IMAGE):
        line = pattern.sub(" ", line)
    line = re.sub(r"\[[^\]]*@[^\]]*\]", " ", line)
    return CITATION.sub(" ", line)


@check("typed-number")
def typed_number(p: Project) -> Result:
    problems = []
    for rel in section_files(p):
        for n, line in p.lines(rel):
            if line.lstrip().startswith(("#", "|", ":")):
                continue
            for m in re.finditer(r"(?<![\w.])\d+(?:[.,]\d+)*%?(?![\w])", strip_references(line)):
                digits = m.group(0).rstrip("%")
                if digits.isdigit() and int(digits) in YEARS:
                    continue
                problems.append(f"{rel}:{n}: number '{m.group(0)}' typed in the text; use {{{{< var id >}}}}")
    return result("typed-number", problems, WARN)


@check("quote-marked")
def quote_marked(p: Project) -> Result:
    problems = []
    for rel in p.sources:
        text = p.sources[rel]
        for m in QUOTE_SPAN.finditer(text):
            n = text.count("\n", 0, m.start()) + 1
            status = re.search(r'status\s*=\s*"([^"]*)"', m.group(2))
            if status is None or status.group(1) not in {"verified", "unverifiable"}:
                problems.append(f'{rel}:{n}: quotation needs status="verified" or status="unverifiable"')
            if not LOCATED_CITATION.match(text[m.end() :]):
                problems.append(f"{rel}:{n}: quotation needs a following citation with a locator, e.g. [@key, p. 12]")
    return result("quote-marked", problems)


@check("sentence-per-line")
def sentence_per_line(p: Project) -> Result:
    problems = []
    for rel in section_files(p):
        for n, line in p.lines(rel):
            if line.lstrip().startswith(("#", "|", ":", "!", "{{<")):
                continue
            for m in re.finditer(r"(\S+[.!?])[\"')\]]*\s+[A-Z]", line):
                if m.group(1).split("(")[-1] not in ABBREVIATIONS:
                    problems.append(f"{rel}:{n}: more than one sentence on this line")
                    break
    return result("sentence-per-line", problems, WARN)


# --- Bibliography ------------------------------------------------------------------------------


def normalized_doi(value: str) -> str:
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", value.strip().lower())


@check("bib-keys")
def bib_keys(p: Project) -> Result:
    problems, keys, dois = [], {}, {}
    for entry in p.bibliography:
        key = entry["key"]
        if not re.fullmatch(CITE_KEY, key):
            problems.append(f"citation key '{key}' must match {CITE_KEY}")
        folded = key.lower()
        if folded in keys:
            problems.append(f"citation key '{key}' duplicates '{keys[folded]}'")
        keys.setdefault(folded, key)
        if entry.get("doi"):
            doi = normalized_doi(entry["doi"])
            if doi in dois:
                problems.append(f"'{key}' and '{dois[doi]}' have the same DOI")
            dois.setdefault(doi, key)
    return result("bib-keys", problems)


@check("bib-unverified")
def bib_unverified(p: Project) -> Result:
    problems = [
        f"'{e['key']}' has no DOI and is not marked x-verification = {{manager}}"
        for e in p.bibliography if not e.get("doi") and e.get("x-verification") != "manager"
    ]  # fmt: skip
    return result("bib-unverified", problems, WARN)


# --- Records and ownership ---------------------------------------------------------------------


@check("status-size")
def status_size(p: Project) -> Result:
    if not p.exists("docs/status.md"):
        return Result("status-size", NOT_TESTED, ["docs/status.md does not exist"])
    size = len(p.content("docs/status.md"))
    problems = [f"docs/status.md has {size} bytes; the limit is {STATUS_LIMIT}"] if size > STATUS_LIMIT else []
    return result("status-size", problems)


@check("owners")
def owners(p: Project) -> Result:
    people = p.project.get("people") or []
    problems = []
    sections = sorted(q.relative_to(p.root).as_posix() for q in (p.root / "paper" / "sections").glob("*.qmd"))
    for section in sections:
        claimed = [person.get("name", "?") for person in people
                   if any(pattern_matches(pat, section) for pat in person.get("owns") or [])]  # fmt: skip
        if len(claimed) > 1:
            problems.append(f"{section} is owned by more than one person: {', '.join(claimed)}")
    return result("owners", problems)


@check("datasets")
def datasets(p: Project) -> Result:
    try:
        entries = p.datasets
    except YAMLError as exc:
        return Result("datasets", FAIL, [f"data/README.md front matter is not valid YAML: {exc}"])
    if not isinstance(entries, list):
        return Result("datasets", FAIL, ["datasets must be a list"])
    problems, seen = [], set()
    tiers = {"public", "licensed", "confidential", "restricted"}
    for i, d in enumerate(entries):
        where = f"datasets[{i}]"
        if not isinstance(d, dict):
            problems.append(f"{where} must be a mapping")
            continue
        unknown = set(d) - {"id", "tier", "license", "raw", "paths", "location", "version"}
        problems += [f"{where}: unknown field '{k}'" for k in sorted(unknown)]
        if not isinstance(d.get("id"), str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", d["id"]):
            problems.append(f"{where}: id must match [a-z][a-z0-9_-]{{0,63}}")
        elif d["id"] in seen:
            problems.append(f"{where}: duplicate id '{d['id']}'")
        else:
            seen.add(d["id"])
        if d.get("tier") not in tiers:
            problems.append(f"{where}: tier must be one of {', '.join(sorted(tiers))}")
        if not isinstance(d.get("license"), str) or not d["license"]:
            problems.append(f"{where}: license is required (use 'unknown' if it is not known)")
        if type(d.get("raw")) is not bool:
            problems.append(f"{where}: raw must be true or false")
        paths = d.get("paths", [])
        if not isinstance(paths, list):
            problems.append(f"{where}: paths must be a list of repository path patterns")
        else:
            problems += [f"{where}: path {x!r} {pattern_error(x)}" for x in paths if pattern_error(x)]
        for key in ["location", "version"]:
            if key in d and not isinstance(d[key], str):
                problems.append(f"{where}: {key} must be a string")
    return result("datasets", problems)


# --- Data exposure (also run by the pre-commit hook) -------------------------------------------


def tracked_or_untested(p: Project, name: str) -> list[str] | Result:
    if p.tracked is None:
        return Result(name, NOT_TESTED, ["not a git repository"])
    return p.tracked


def is_text(data: bytes) -> bool:
    return b"\0" not in data[:8192]


@check("declared-paths", hook=True)
def declared_paths(p: Project) -> Result:
    files = tracked_or_untested(p, "declared-paths")
    if isinstance(files, Result):
        return files
    problems, guarded = [], []
    for d in p.datasets if isinstance(p.datasets, list) else [None]:
        if not isinstance(d, dict):
            problems.append("data/README.md: a dataset declaration is not a mapping")
            continue
        name, paths = d.get("id"), d.get("paths", [])
        # Fail closed: a declaration this check cannot interpret must not let files through.
        if type(d.get("raw")) is not bool:
            problems.append(f"dataset '{name}': raw must be true or false")
        if not isinstance(paths, list):
            problems.append(f"dataset '{name}': paths must be a list")
            continue
        for pattern in paths:
            if pattern_error(pattern):
                problems.append(f"dataset '{name}': path {pattern!r} {pattern_error(pattern)}")
            elif d.get("raw") is not False or d.get("tier") != "public":
                guarded.append((name, pattern))
    problems += [f"{f} is at a path of dataset '{i}', which must not be committed"
                 for f in files for i, pattern in guarded if pattern_matches(pattern, f)]  # fmt: skip
    return result("declared-paths", problems)


@check("forbidden-types", hook=True)
def forbidden_types(p: Project) -> Result:
    files = tracked_or_untested(p, "forbidden-types")
    if isinstance(files, Result):
        return files
    problems = [
        f"{f} must not be committed"
        for f in files
        if Path(f).name == ".env" or any(fnmatch.fnmatch(Path(f).name, pat) for pat in FORBIDDEN)
    ]
    return result("forbidden-types", problems)


@check("file-size", hook=True)
def file_size(p: Project) -> Result:
    files = tracked_or_untested(p, "file-size")
    if isinstance(files, Result):
        return files
    problems = [f"{f} is larger than 10 MB; keep it in the configured large-data store"
                for f in files if len(p.content(f)) > SIZE_LIMIT]  # fmt: skip
    return result("file-size", problems)


@check("secret-patterns", hook=True)
def secret_patterns(p: Project) -> Result:
    files = tracked_or_untested(p, "secret-patterns")
    if isinstance(files, Result):
        return files
    problems = []
    for f in files:
        data = p.content(f)
        if not is_text(data):
            continue
        text = data.decode("utf-8", "replace")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                problems.append(f"{f}: matches the pattern for a {label}")
    return result("secret-patterns", problems)


@check("pii-scan", hook=True)
def pii_scan(p: Project) -> Result:
    files = tracked_or_untested(p, "pii-scan")
    if isinstance(files, Result):
        return files
    problems = []
    for f in files:
        if f in {"paper/references.bib", "project.yml"}:
            continue
        data = p.content(f)
        if not is_text(data):
            continue
        text = data.decode("utf-8", "replace")
        for label, pattern in [("email address", EMAIL), ("phone number", PHONE)]:
            for m in pattern.finditer(text):
                domain = m.group(0).rsplit("@", 1)[-1].lower()
                if label == "email address" and any(domain == d or domain.endswith("." + d) for d in EXEMPT_DOMAINS):
                    continue
                problems.append(f"{f}:{text.count(chr(10), 0, m.start()) + 1}: possible {label}")
    return result("pii-scan", problems, WARN)


# --- Configuration -----------------------------------------------------------------------------


@check("hook-enabled")
def hook_enabled(p: Project) -> Result:
    if os.environ.get("CI") == "true":
        return Result("hook-enabled", NOT_TESTED, ["local git configuration is not available in CI"])
    value = (p._git("config", "--get", "core.hooksPath") or "").strip()
    if value != ".githooks":
        return Result("hook-enabled", WARN, ["enable the hook: git config core.hooksPath .githooks"])
    return Result("hook-enabled", PASS)


@check("no-claude-md")
def no_claude_md(p: Project) -> Result:
    files = tracked_or_untested(p, "no-claude-md")
    if isinstance(files, Result):
        return files
    problems = [
        f"{f}: AGENTS.md is the only instruction file"
        for f in files
        if Path(f).name == "CLAUDE.md" and not (f == "CLAUDE.md" and p.content(f).decode("utf-8", "replace") == CLAUDE_IMPORT)
    ]
    return result("no-claude-md", problems)


# --- Running -----------------------------------------------------------------------------------


def run(root: Path, staged: bool = False, extra: dict[str, Check] | None = None) -> list[Result]:
    project = Project(root, staged)
    checks = [(n, f) for n, f, hook in REGISTRY if hook or not staged]
    if extra and not staged:
        checks = list(extra.items()) + checks
    results = []
    for name, func in checks:
        try:
            results.append(func(project))
        except (OSError, UnicodeDecodeError, ValueError, YAMLError, KeyError, TypeError, AttributeError) as exc:
            results.append(Result(name, FAIL, [f"could not run: {exc}"]))
    return results


def crosswalk(root: Path) -> list[dict[str, str]]:
    """Rows of .build/reports/crosswalk.csv (appendix A4.4)."""
    project = Project(root)
    artifacts = {a["id"]: a for a in (project.manifest or {}).get("artifacts", [])}
    rows = []
    for rel in project.sources:
        for n, line in project.lines(rel):
            refs = [(m.group(0), m.group(1)) for m in VAR.finditer(line)]
            refs += [(m.group(0), m.group(2)) for m in XREF.finditer(line) if m.group(1) in {"tbl", "fig"}]
            for written, artifact_id in refs:
                artifact = artifacts.get(artifact_id, {})
                rows.append({"location": f"{rel}:{n}", "reference": written, "artifact_id": artifact_id,
                             "kind": artifact.get("kind", ""), "producer": artifact.get("producer", "")})  # fmt: skip
    return rows
