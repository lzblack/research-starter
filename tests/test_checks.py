"""Project checks (appendix A7.2), run against small synthetic projects."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("project_checks", ROOT / "template" / "base" / "checks.py")
checks = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(checks)
sys.dont_write_bytecode = False

SECTION = """# Introduction {#sec-introduction}

We use {{< var n_obs >}} observations (@tbl-main, @fig-plot), following @doe2020.

{{< include outputs/tables/main.md >}}

![A figure.](outputs/figures/plot.png){#fig-plot}

See @sec-introduction.
"""


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def write(root: Path, rel: str, text: str | bytes) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text if isinstance(text, bytes) else text.encode())


@pytest.fixture
def project(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.delenv("CI", raising=False)
    root = tmp_path / "p"
    write(root, "paper/paper.qmd", "{{< include sections/introduction.qmd >}}\n")
    write(root, "paper/sections/introduction.qmd", SECTION)
    write(root, "paper/_variables.yml", 'n_obs: "1,000"\n')
    write(root, "paper/outputs/tables/main.md", "| a |\n|---|\n| 1 |\n\n: Main {#tbl-main}\n")
    write(root, "paper/outputs/figures/plot.png", b"\x89PNG\r\n\x1a\n")
    write(root, "paper/references.bib", "@article{doe2020,\n  title = {A Title},\n  doi = {10.1/abc}\n}\n")
    write(root, "docs/status.md", "# Status\n")
    write(root, "data/README.md", "---\ndatasets:\n  - id: raw_survey\n    tier: public\n    license: CC0-1.0\n"
          "    raw: true\n    paths:\n      - data/raw/\n---\n# Data\n")
    write(root, "project.yml", "people:\n  - name: A\n    owns: []\n")
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "core.hooksPath", ".githooks")
    git(root, "add", "-A")
    return root


def results(root: Path, staged: bool = False) -> dict[str, "checks.Result"]:
    return {r.check: r for r in checks.run(root, staged=staged)}


def status(root: Path, name: str, staged: bool = False) -> str:
    return results(root, staged)[name].status


def test_clean_project_passes(project: Path) -> None:
    found = results(project)
    assert {r.status for r in found.values()} <= {"pass", "not-tested"}, {
        n: (r.status, r.problems) for n, r in found.items() if r.status not in {"pass", "not-tested"}
    }


@pytest.mark.parametrize(
    ("name", "edit", "expected"),
    [
        ("var-resolve", lambda r: write(r, "paper/_variables.yml", 'other: "1"\n'), "fail"),
        ("var-unused", lambda r: write(r, "paper/_variables.yml", 'n_obs: "1"\nextra: "2"\n'), "warn"),
        ("xref-resolve", lambda r: write(r, "paper/outputs/tables/main.md", "| a |\n|---|\n| 1 |\n"), "fail"),
        ("cite-resolve", lambda r: write(r, "paper/references.bib", ""), "fail"),
        ("include-resolve", lambda r: (r / "paper/outputs/tables/main.md").unlink(), "fail"),
        ("figure-resolve", lambda r: (r / "paper/outputs/figures/plot.png").unlink(), "fail"),
        ("typed-number", lambda r: write(r, "paper/sections/introduction.qmd", SECTION + "\nThe effect is 0.42.\n"), "warn"),
        ("sentence-per-line", lambda r: write(r, "paper/sections/introduction.qmd", SECTION + "\nOne sentence. Two sentences.\n"), "warn"),
        ("bib-keys", lambda r: write(r, "paper/references.bib", "@article{doe2020, doi = {10.1/abc}}\n@book{Doe2020, title={x}}\n"), "fail"),
        ("bib-keys", lambda r: write(r, "paper/references.bib", "@article{doe2020, doi = {10.1/ABC}}\n@article{roe2021, doi = {https://doi.org/10.1/abc}}\n"), "fail"),
        ("bib-unverified", lambda r: write(r, "paper/references.bib", "@article{doe2020, title = {x}}\n"), "warn"),
        ("status-size", lambda r: write(r, "docs/status.md", "x" * 8001), "fail"),
        ("datasets", lambda r: write(r, "data/README.md", "---\ndatasets:\n  - id: Bad Id\n    tier: secret\n---\n"), "fail"),
        ("owners", lambda r: write(r, "project.yml", "people:\n  - name: A\n    owns: [paper/sections/]\n"
                                   "  - name: B\n    owns: [paper/sections/introduction.qmd]\n"), "fail"),
    ],
)
def test_detects(project: Path, name: str, edit, expected: str) -> None:
    edit(project)
    assert status(project, name) == expected, results(project)[name].problems


def test_numbers_that_are_not_flagged(project: Path) -> None:
    write(project, "paper/sections/introduction.qmd",
          "# Results in 2024 {#sec-r}\n\nData from 2019 to 2021 [@doe2020, p. 12], see @tbl-main.\n")  # fmt: skip
    assert status(project, "typed-number") == "pass", results(project)["typed-number"].problems


def test_abbreviations_are_not_sentence_ends(project: Path) -> None:
    write(project, "paper/sections/introduction.qmd", "# I {#sec-i}\n\nAs shown by Doe et al. Results hold, e.g. The x.\n")
    assert status(project, "sentence-per-line") == "pass", results(project)["sentence-per-line"].problems


def test_code_and_comments_are_ignored(project: Path) -> None:
    write(project, "paper/sections/introduction.qmd",
          "# I {#sec-i}\n\n<!-- @missing {{< var nope >}} -->\n\n```python\nx = @absent 42\n```\n\nText with `@code 7`.\n")  # fmt: skip
    found = results(project)
    for name in ["cite-resolve", "var-resolve", "typed-number"]:
        assert found[name].status in {"pass", "warn"} and not [p for p in found[name].problems if "nope" in p or "absent" in p or "missing" in p]


@pytest.mark.parametrize(
    ("span", "ok"),
    [
        ('[“A quote.”]{.quote status="verified"} [@doe2020, p. 3]', True),
        ('[“A quote.”]{.quote status="unverifiable"} [@doe2020, pp. 3-4]', True),
        ('[“A quote.”]{.quote} [@doe2020, p. 3]', False),
        ('[“A quote.”]{.quote status="maybe"} [@doe2020, p. 3]', False),
        ('[“A quote.”]{.quote status="verified"} [@doe2020]', False),
        ('[“A quote.”]{.quote status="verified"}', False),
    ],
)
def test_quote_marked(project: Path, span: str, ok: bool) -> None:
    write(project, "paper/sections/introduction.qmd", SECTION + "\n" + span + "\n")
    assert (status(project, "quote-marked") == "pass") is ok


# --- Data exposure -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rel", "content", "name"),
    [
        ("data/raw/survey.csv", "id\n1\n", "declared-paths"),
        ("local.duckdb", "x", "forbidden-types"),
        ("config/.env", "A=1\n", "forbidden-types"),
        ("notes.md", "key: -----BEGIN RSA PRIVATE KEY-----\n", "secret-patterns"),
        ("notes.md", "token ghp_" + "a" * 36 + "\n", "secret-patterns"),
        ("notes.md", "export SERVICE_API_KEY=abcdefgh12345\n", "secret-patterns"),
    ],
)
def test_data_exposure_failures(project: Path, rel: str, content: str, name: str) -> None:
    write(project, rel, content)
    git(project, "add", "-f", rel)
    assert status(project, name) == "fail"
    assert status(project, name, staged=True) == "fail"


def test_env_example_is_allowed(project: Path) -> None:
    write(project, ".env.example", "SERVICE_API_KEY=\n")
    git(project, "add", ".env.example")
    assert status(project, "forbidden-types") == "pass"
    assert status(project, "secret-patterns") == "pass"


def test_untracked_files_are_not_checked(project: Path) -> None:
    write(project, "data/raw/survey.csv", "id\n1\n")
    assert status(project, "declared-paths") == "pass"


def test_large_file(project: Path) -> None:
    write(project, "big.bin", b"\0" * 10_000_001)
    git(project, "add", "big.bin")
    assert status(project, "file-size") == "fail"


def test_pii_scan_warns(project: Path) -> None:
    write(project, "notes.md", "Contact person@university-mail.net or +1 617 555 0100.\nSee test@example.org.\n")
    git(project, "add", "notes.md")
    found = results(project)["pii-scan"]
    assert found.status == "warn"
    assert len(found.problems) == 2


def test_staged_mode_runs_only_hook_checks(project: Path) -> None:
    names = set(results(project, staged=True))
    assert names == {"declared-paths", "forbidden-types", "file-size", "secret-patterns", "pii-scan"}


def test_staged_mode_reads_the_index(project: Path) -> None:
    write(project, "notes.md", "clean\n")
    git(project, "add", "notes.md")
    write(project, "notes.md", "export SERVICE_API_KEY=abcdefgh12345\n")  # not staged
    assert status(project, "secret-patterns", staged=True) == "pass"


def test_hook_enabled(project: Path, monkeypatch) -> None:
    assert status(project, "hook-enabled") == "pass"
    git(project, "config", "--unset", "core.hooksPath")
    assert status(project, "hook-enabled") == "warn"
    monkeypatch.setenv("CI", "true")
    assert status(project, "hook-enabled") == "not-tested"


@pytest.mark.parametrize(("rel", "content", "expected"), [
    ("CLAUDE.md", "@AGENTS.md\n", "pass"),
    ("CLAUDE.md", "# Rules\n", "fail"),
    ("paper/CLAUDE.md", "@AGENTS.md\n", "fail"),
])  # fmt: skip
def test_no_claude_md(project: Path, rel: str, content: str, expected: str) -> None:
    write(project, rel, content)
    git(project, "add", rel)
    assert status(project, "no-claude-md") == expected


def test_not_a_git_repository(project: Path) -> None:
    import shutil

    shutil.rmtree(project / ".git")
    assert status(project, "declared-paths") == "not-tested"


# --- Freshness and crosswalk ----------------------------------------------------------------------


def manifest(project: Path, producer_sha: str, input_sha: str) -> None:
    import json

    write(project, "notebooks/a.py", "print(1)\n")
    write(project, "data/x.csv", "x\n")
    entry = {"id": "n_obs", "kind": "variable", "file": "paper/outputs/variables/a.yml",
             "producer": "notebooks/a.py", "producer_sha256": producer_sha,
             "inputs": [{"path": "data/x.csv", "sha256": input_sha}, {"path": "data/absent.csv", "sha256": "0"}],
             "sha256": "0"}  # fmt: skip
    write(project, "paper/outputs/manifest.json", json.dumps({"schema": 1, "artifacts": [entry]}))


def test_output_freshness(project: Path) -> None:
    current = checks.sha256(b"print(1)\n"), checks.sha256(b"x\n")
    manifest(project, *current)
    fresh = results(project)["output-freshness"]
    assert fresh.status == "not-tested" and "data/absent.csv is not available here" in fresh.problems
    manifest(project, "stale", current[1])
    assert status(project, "output-freshness") == "warn"


def test_crosswalk_rows(project: Path) -> None:
    manifest(project, "x", "y")
    rows = checks.crosswalk(project)
    refs = {(r["reference"], r["artifact_id"], r["kind"]) for r in rows}
    assert ("{{< var n_obs >}}", "n_obs", "variable") in refs
    assert ("@tbl-main", "main", "") in refs
    assert all(r["location"].startswith("paper/sections/introduction.qmd:") for r in rows)


# --- Review fixes --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "declaration",
    [
        "  - id: raw_survey\n    tier: confidential\n    license: x\n    raw: true\n    paths:\n      - /data/raw/**\n",
        "  - id: raw_survey\n    tier: confidential\n    license: x\n    raw: true\n    paths: data/raw/\n",
        "  - id: raw_survey\n    tier: public\n    license: x\n    raw: 'true'\n    paths:\n      - data/raw/\n",
    ],
    ids=["leading-slash", "paths-string", "raw-string"],
)
def test_declared_paths_fails_closed_on_malformed_declarations(project: Path, declaration: str) -> None:
    write(project, "data/README.md", "---\ndatasets:\n" + declaration + "---\n")
    write(project, "data/raw/responses.csv", "id\n1\n")
    git(project, "add", "-A")
    assert status(project, "declared-paths", staged=True) == "fail"
    assert status(project, "declared-paths") == "fail"
    assert status(project, "datasets") == "fail"


def test_email_exemption_matches_whole_domain(project: Path) -> None:
    write(project, "notes.md", "a@notexample.com b@sub.example.org\n")
    git(project, "add", "notes.md")
    problems = results(project)["pii-scan"].problems
    assert len(problems) == 1 and "possible email address" in problems[0]


def test_malformed_project_yml_is_a_failure_not_a_crash(project: Path) -> None:
    write(project, "project.yml", "- just\n- a list\n")
    assert status(project, "owners") == "fail"


def test_single_star_does_not_match_nested(project: Path) -> None:
    assert not checks.pattern_matches("paper/*", "paper/sections/intro.qmd")
    assert checks.pattern_matches("paper/*", "paper/paper.qmd")
    assert checks.pattern_matches("paper/**", "paper/sections/intro.qmd")
