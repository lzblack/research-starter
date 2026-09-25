"""Scheduled compatibility checks for the external tool behaviors in docs/compatibility.md.

They need network access and download tools, so they run in a weekly workflow
(`.github/workflows/compat.yml`) and by hand with `uv run --locked pytest -m compat`.
"""

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
import urllib.request
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.compat


def env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in {"VIRTUAL_ENV", "UV_PYTHON_PREFERENCE"}}


def run(cmd: list[str], cwd: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env() | (extra_env or {}), capture_output=True, text=True, check=False)


def quarto_pin() -> str:
    pyproject = tomllib.loads((ROOT / "template" / "base" / "pyproject.toml.tmpl").read_text().replace("@@", ""))
    pin = next(d for d in pyproject["project"]["dependencies"] if d.startswith("quarto-cli=="))
    return pin.split("==")[1]


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "research-starter compat"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


@pytest.fixture(scope="module")
def project(tmp_path_factory) -> Path:
    """A generated project with its environment synced."""
    target = tmp_path_factory.mktemp("compat") / "project"
    target.mkdir()
    answers = ROOT / "tests" / "fixtures" / "answers" / "minimal-defaults.yml"
    generated = run([sys.executable, str(ROOT / "new_project.py"), "generate", "--answers", str(answers),
                     "--target", str(target), "--allow-dirty"], ROOT)  # fmt: skip
    assert generated.returncode == 0, generated.stderr
    synced = run(["uv", "sync", "--locked"], target)
    assert synced.returncode == 0, synced.stderr
    return target


def quarto(project: Path) -> str:
    return str(project / ".venv" / "bin" / "quarto")


def docx_text(path: Path) -> str:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode()
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))


def paper_copy(project: Path, tmp_path: Path, extra: str = "") -> Path:
    paper = tmp_path / "paper"
    shutil.copytree(project / "paper", paper, ignore=shutil.ignore_patterns("_output", ".quarto"))
    if extra:
        section = paper / "sections" / "introduction.qmd"
        section.write_text(section.read_text() + "\n" + extra + "\n")
    return paper


# --- E1, E2, E3: installation ------------------------------------------------------------------


def test_e1_sdist_downloads_its_own_release() -> None:
    version = quarto_pin()
    meta = json.loads(fetch(f"https://pypi.org/pypi/quarto-cli/{version}/json"))
    sdist = next(f for f in meta["urls"] if f["packagetype"] == "sdist")
    data = fetch(sdist["url"])
    assert hashlib.sha256(data).hexdigest() == sdist["digests"]["sha256"]
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        names = {m.name.split("/", 1)[1]: m for m in archive.getmembers() if "/" in m.name}
        setup = archive.extractfile(names["setup.py"]).read().decode()
        bundled = archive.extractfile(names["version.txt"]).read().decode().strip()
    assert bundled == version
    assert "releases/download/v{version}/quarto-{version}-{suffix}" in setup


def test_e3_release_publishes_checksums_for_every_platform() -> None:
    version = quarto_pin()
    base = f"https://github.com/quarto-dev/quarto-cli/releases/download/v{version}"
    checksums = fetch(f"{base}/quarto-{version}-checksums.txt").decode()
    for suffix in ["linux-amd64.tar.gz", "linux-arm64.tar.gz", "macos.tar.gz"]:
        assert f"quarto-{version}-{suffix}" in checksums


def test_e2_warm_cache_syncs_offline(project: Path, tmp_path: Path) -> None:
    copy = tmp_path / "offline"
    copy.mkdir()
    for name in ["pyproject.toml", "uv.lock", ".python-version"]:
        shutil.copy2(project / name, copy / name)
    result = run(["uv", "sync", "--locked", "--offline"], copy)
    assert result.returncode == 0, result.stderr
    assert run([str(copy / ".venv" / "bin" / "quarto"), "--version"], copy).stdout.strip() == quarto_pin()


# --- E5, E7, E8: rendering -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("extra", "rc", "marker"),
    [
        ("Value {{< var no_such_var >}}.", 0, "?var:no_such_var"),
        ("See @tbl-no-such.", 0, "?@tbl-no-such"),
        ("See @no_such_key.", 0, "no_such_key?"),
    ],
)
def test_e5_unresolved_references_do_not_fail_rendering(project, tmp_path, extra, rc, marker) -> None:
    paper = paper_copy(project, tmp_path, extra)
    result = run([quarto(project), "render", "--to", "docx"], paper)
    assert result.returncode == rc, result.stderr[-2000:]
    assert marker in docx_text(next((paper / "_output").glob("*.docx")))


def test_e5_missing_include_fails(project, tmp_path) -> None:
    paper = paper_copy(project, tmp_path, "{{< include outputs/tables/no_such.md >}}")
    assert run([quarto(project), "render", "--to", "docx"], paper).returncode != 0


def test_e5_failed_format_leaves_previous_file(project, tmp_path) -> None:
    paper = paper_copy(project, tmp_path)
    assert run([quarto(project), "render"], paper).returncode == 0
    pdf = next((paper / "_output").glob("*.pdf"))
    before = pdf.read_bytes()
    section = paper / "sections" / "introduction.qmd"
    section.write_text(section.read_text() + "\n![x](outputs/figures/no_such.png){#fig-missing}\n")
    assert run([quarto(project), "render"], paper).returncode != 0
    assert pdf.read_bytes() == before


def test_e7_syntax_probes(project, tmp_path) -> None:
    paper = paper_copy(project, tmp_path, '[“A quotation.”]{.quote status="verified"} [@example2020, p. 3]')
    bib = paper / "references.bib"
    bib.write_text(bib.read_text().replace("doi = {", "x-verification = {manager},\n  doi = {"))
    result = run([quarto(project), "render", "--to", "docx"], paper)
    assert result.returncode == 0
    assert "WARN" not in result.stderr
    text = docx_text(next((paper / "_output").glob("*.docx")))
    assert "Table 1" in text and "“A quotation.”" in text and "?@" not in text


def test_e8_execution_disabled_and_output_dir(project, tmp_path) -> None:
    paper = paper_copy(project, tmp_path, "```{python}\nopen('EXECUTED', 'w').write('x')\n```")
    staging = tmp_path / "staging"
    result = run([quarto(project), "render", "--to", "docx", "--output-dir", str(staging)], paper)
    assert result.returncode == 0, result.stderr[-2000:]
    assert not (paper / "EXECUTED").exists() and list(staging.glob("*.docx"))


# --- E6: marimo --------------------------------------------------------------------------------


def test_e6_marimo_stops_at_failing_cell(project, tmp_path) -> None:
    notebook = tmp_path / "failing.py"
    notebook.write_text(
        "import marimo\n\napp = marimo.App()\n\n\n@app.cell\ndef _():\n    open('before.txt', 'w').write('x')\n"
        "    x = 1\n    return (x,)\n\n\n@app.cell\ndef _(x):\n    raise ValueError('deliberate')\n    return\n\n\n"
        "@app.cell\ndef _():\n    open('after.txt', 'w').write('x')\n    return\n\n\nif __name__ == '__main__':\n    app.run()\n"
    )  # fmt: skip
    result = run([str(project / ".venv" / "bin" / "python"), str(notebook)], tmp_path)
    assert result.returncode == 1
    assert (tmp_path / "before.txt").exists() and not (tmp_path / "after.txt").exists()
    notebook.write_text("import marimo\n\napp = marimo.App()\n\n\n@app.cell\ndef _():\n    import sys\n"
                        "    sys.exit(3)\n    return\n\n\nif __name__ == '__main__':\n    app.run()\n")  # fmt: skip
    assert run([str(project / ".venv" / "bin" / "python"), str(notebook)], tmp_path).returncode == 3


# --- E9, E10: Python versions --------------------------------------------------------------------


def test_e9_switch_python_within_range_keeps_the_lock(project, tmp_path) -> None:
    copy = tmp_path / "switch"
    copy.mkdir()
    for name in ["pyproject.toml", "uv.lock", ".python-version"]:
        shutil.copy2(project / name, copy / name)
    lock = (copy / "uv.lock").read_bytes()
    assert run(["uv", "python", "pin", "3.12"], copy).returncode == 0
    assert run(["uv", "sync", "--locked"], copy).returncode == 0
    version = run([str(copy / ".venv" / "bin" / "python"), "--version"], copy).stdout
    assert version.startswith("Python 3.12")
    assert (copy / "uv.lock").read_bytes() == lock
    assert run(["uv", "python", "pin", "3.11"], copy).returncode != 0


def test_e10_without_a_pin_uv_uses_an_installed_interpreter(tmp_path) -> None:
    venv_bin = str(Path(sys.prefix) / "bin")
    system_path = os.pathsep.join(d for d in os.environ.get("PATH", "").split(os.pathsep) if d != venv_bin)
    system = shutil.which("python3", path=system_path)
    if system is None:
        pytest.skip("no system python3")
    system_version = run([system, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"], tmp_path).stdout.strip()
    if tuple(map(int, system_version.split("."))) < (3, 12):
        pytest.skip("system python3 is older than the template's floor")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "probe"\nversion = "0"\nrequires-python = ">=3.12"\n')
    result = run(["uv", "run", "--no-project", "--python-preference", "only-system", "python", "-c",
                  "import sys; print('%d.%d' % sys.version_info[:2])"], tmp_path)  # fmt: skip
    assert result.stdout.strip() == system_version
