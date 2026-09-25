"""Skill helpers shipped in the template: session IDs, coverage, and add-paper."""

import importlib.util
import re
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "template" / "base" / ".agents" / "skills"


def load(name: str, path: Path):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    sys.dont_write_bytecode = False
    return module


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=Researcher A", "-c", "user.email=a@example.org", *args],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / ".agents" / "skills" / "handoff").mkdir(parents=True)
    git(tmp_path, "init", "-q", "-b", "main", str(root))
    git(root, "config", "user.email", "a@example.org")
    return root


def run_session(repo: Path, capsys, *args: str) -> str:
    module = load("session_under_test", SKILLS / "handoff" / "session.py")
    module.ROOT = repo
    sys.argv = ["session.py", *args]
    module.main()
    return capsys.readouterr().out


def test_new_session_id(repo: Path, capsys) -> None:
    out = run_session(repo, capsys, "new", "--at", "2026-01-15T09:30Z").split()
    assert re.fullmatch(r"2026-01-15T0930Z-[0-9a-f]{6}", out[0])
    assert out[1] == f"journal/{out[0]}.md"


def test_decision_id(repo: Path, capsys) -> None:
    out = run_session(repo, capsys, "decision-id", "use-synthetic-data", "--date", "2026-01-15").strip()
    assert re.fullmatch(r"2026-01-15-use-synthetic-data-[0-9a-f]{4}", out)
    with pytest.raises(SystemExit):
        run_session(repo, capsys, "decision-id", "Bad Slug")


def commit(repo: Path, message: str, session_id: str | None = None) -> None:
    body = f"{message}\n\nSession: {session_id}\n" if session_id else message
    git(repo, "commit", "-q", "--allow-empty", "-m", body)


def test_uncovered_commits(repo: Path, capsys) -> None:
    commit(repo, "first work")
    assert "first work" in run_session(repo, capsys, "uncovered")
    (repo / "journal").mkdir()
    (repo / "journal" / "2026-01-15T0930Z-abcdef.md").write_text("entry\n")
    commit(repo, "handoff", "2026-01-15T0930Z-abcdef")
    commit(repo, "later work")
    out = run_session(repo, capsys, "uncovered")
    assert "later work" in out and "first work" not in out and "handoff" not in out.split("covered")[-1]


def test_merged_branch_is_covered(repo: Path, capsys) -> None:
    commit(repo, "base")
    git(repo, "switch", "-q", "-c", "feature")
    commit(repo, "feature work")
    (repo / "journal").mkdir()
    (repo / "journal" / "2026-01-15T0930Z-aaaaaa.md").write_text("entry\n")
    commit(repo, "feature handoff", "2026-01-15T0930Z-aaaaaa")
    git(repo, "switch", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "feature", "-m", "merge feature")
    out = run_session(repo, capsys, "uncovered")
    assert "feature work" not in out and "base" not in out
    assert "merge feature" in out


def test_other_authors_are_not_reported(repo: Path, capsys) -> None:
    subprocess.run(["git", "-c", "user.name=B", "-c", "user.email=b@example.org", "commit", "-q",
                    "--allow-empty", "-m", "their work"], cwd=repo, check=True)  # fmt: skip
    assert "No missed handoff." in run_session(repo, capsys, "uncovered")


def test_uncommitted_changes(repo: Path, capsys) -> None:
    commit(repo, "base", None)
    (repo / "journal").mkdir()
    (repo / "journal" / "2026-01-15T0930Z-bbbbbb.md").write_text("entry\n")
    git(repo, "add", "-A")
    commit(repo, "handoff", "2026-01-15T0930Z-bbbbbb")
    (repo / "notes.md").write_text("draft\n")
    assert "notes.md" in run_session(repo, capsys, "uncovered")


# --- add-paper -----------------------------------------------------------------------------------

BIBTEX = (
    "@article{Doe_2020, title={A {Synthetic} Study of Examples}, volume={3}, "
    "DOI={10.1000/xyz123}, journal={Journal of Examples}, author={Doe, Jane and Roe, Richard}, year={2020}}"
)


@pytest.fixture
def paper(tmp_path: Path):
    module = load("add_paper_under_test", SKILLS / "add-paper" / "add_paper.py")
    module.BIB = tmp_path / "paper" / "references.bib"
    module.LIT = tmp_path / "lit"
    module.BIB.parent.mkdir()
    module.BIB.write_text("@article{example2020,\n  title = {Existing},\n  doi = {10.0000/existing}\n}\n")
    return module


def test_add_paper(paper) -> None:
    code, message = paper.add("https://doi.org/10.1000/XYZ123", fetcher=lambda doi: BIBTEX)
    assert code == 0 and message == "added doe2020synthetic"
    text = paper.BIB.read_text()
    assert "@article{doe2020synthetic," in text and "@article{example2020," in text
    assert paper.fields(text[text.index("@article{doe2020synthetic"):])["doi"] == "10.1000/xyz123"
    assert (paper.LIT / "doe2020synthetic.md").read_text().startswith("---\nkey: doe2020synthetic\n")


def test_add_paper_duplicate_doi(paper) -> None:
    before = paper.BIB.read_text()
    code, message = paper.add("10.0000/EXISTING", fetcher=lambda doi: pytest.fail("no fetch expected"))
    assert code == 0 and "example2020" in message
    assert paper.BIB.read_text() == before


def test_add_paper_key_collision(paper) -> None:
    paper.add("10.1000/xyz123", fetcher=lambda doi: BIBTEX)
    code, message = paper.add("10.1000/other", fetcher=lambda doi: BIBTEX.replace("10.1000/xyz123", "10.1000/other"))
    assert message == "added doe2020synthetica"


@pytest.mark.parametrize("failure", [urllib.error.URLError("offline"), TimeoutError("slow")])
def test_add_paper_failure_writes_nothing(paper, failure) -> None:
    before = paper.BIB.read_text()

    def fail(doi: str) -> str:
        raise failure

    code, message = paper.add("10.1000/xyz123", fetcher=fail)
    assert code == 1 and "nothing written" in message
    assert paper.BIB.read_text() == before and not paper.LIT.exists()


def test_add_paper_rejects_non_doi(paper) -> None:
    assert paper.add("not-a-doi", fetcher=lambda doi: BIBTEX)[0] == 1
