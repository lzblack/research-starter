"""The generated project's build entry point (appendix A4, A5), run on small synthetic projects."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("project_build", ROOT / "template" / "base" / "build.py")
build = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.dont_write_bytecode = True  # never leave __pycache__ inside the template tree
spec.loader.exec_module(build)
sys.dont_write_bytecode = False

HELPER = (ROOT / "template" / "base" / "notebooks" / "paper_outputs.py").read_text()
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 16


def step(body: str) -> str:
    """A producer script that uses the real output helper (run as `python notebooks/<name>.py`)."""
    return "from paper_outputs import Outputs\n" + body


FRAME = (
    "class Frame:\n"
    "    columns = ['M', 'E']\n"
    "    def itertuples(self, index=False):\n"
    "        return [('x', '0.5')]\n"
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "notebooks").mkdir(parents=True)
    (root / "notebooks" / "paper_outputs.py").write_text(HELPER)
    (root / "data").mkdir()
    (root / "data" / "input.csv").write_text("x\n1\n")
    (root / "data" / "README.md").write_text("---\ndatasets:\n  - id: remote\n    tier: public\n    license: CC0-1.0\n    raw: false\n    version: '2026-01'\n---\n")
    configure(root, analyze=["notebooks/a.py"])
    write_step(root, "a", 'o = Outputs("a")\no.input("data/input.csv")\no.variable("n_obs", "1,000")\n'
               + FRAME + 'o.table("main", Frame(), "Main")\n'
               f'(o.root / "figures").mkdir(parents=True, exist_ok=True)\n(o.root / "figures" / "fig.png").write_bytes({PNG!r})\n')
    return root


def configure(root: Path, prepare: list[str] | None = None, analyze: list[str] | None = None,
              external: dict[str, str] | None = None) -> None:  # fmt: skip
    lines = ["[project]", 'name = "demo"', "", "[tool.research-starter.build]"]
    lines.append(f"prepare = {json.dumps(prepare or [])}")
    lines.append(f"analyze = {json.dumps(analyze or [])}")
    if external:
        lines += ["", "[tool.research-starter.build.external]"]
        lines += [f'"{k}" = "{v}"' for k, v in external.items()]
    (root / "pyproject.toml").write_text("\n".join(lines) + "\n")


def write_step(root: Path, name: str, body: str) -> None:
    (root / "notebooks" / f"{name}.py").write_text(step(body))


def main(root: Path, *argv: str) -> int:
    return build.main(list(argv), root=root)


def outputs(root: Path) -> set[str]:
    base = root / "paper" / "outputs"
    return {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()}


# --- analyze -----------------------------------------------------------------------------------


def test_analyze_promotes_outputs_and_manifest(project: Path) -> None:
    assert main(project, "analyze") == 0
    assert outputs(project) == {"variables/a.yml", "tables/main.md", "figures/fig.png", "manifest.json"}
    manifest = json.loads((project / "paper" / "outputs" / "manifest.json").read_text())
    assert [a["id"] for a in manifest["artifacts"]] == ["fig", "main", "n_obs"]
    entry = manifest["artifacts"][2]
    assert entry["kind"] == "variable" and entry["producer"] == "notebooks/a.py"
    assert entry["inputs"] == [{"path": "data/input.csv", "sha256": build.sha256(project / "data" / "input.csv")}]
    assert (project / "paper" / "_variables.yml").read_text() == 'n_obs: "1,000"\n'
    assert build.check_manifest(project) == []
    assert (project / "logs" / "analyze" / "a.log").exists()


def test_failed_step_leaves_committed_outputs(project: Path) -> None:
    assert main(project, "analyze") == 0
    before = {p: (project / "paper" / "outputs" / p).read_bytes() for p in outputs(project)}
    write_step(project, "a", 'o = Outputs("a")\no.variable("n_obs", "2")\nraise SystemExit(1)\n')
    assert main(project, "analyze") == 1
    assert {p: (project / "paper" / "outputs" / p).read_bytes() for p in outputs(project)} == before
    assert (project / "paper" / "_variables.yml").read_text() == 'n_obs: "1,000"\n'


def test_outputs_no_longer_produced_are_removed(project: Path) -> None:
    assert main(project, "analyze") == 0
    write_step(project, "a", 'o = Outputs("a")\no.variable("n_obs", "7")\n')
    assert main(project, "analyze") == 0
    assert outputs(project) == {"variables/a.yml", "manifest.json"}


def test_step_exit_3_is_a_missing_prerequisite(project: Path, capsys) -> None:
    write_step(project, "a", 'print("missing: data/raw.csv (run scripts/fetch.py)")\nraise SystemExit(3)\n')
    assert main(project, "analyze") == 3
    assert "missing: data/raw.csv (run scripts/fetch.py)" in capsys.readouterr().out


def test_missing_external_output_stops_before_steps(project: Path, capsys) -> None:
    configure(project, analyze=["notebooks/a.py"], external={"data/raw/api.parquet": "scripts/fetch_api.py"})
    assert main(project, "analyze") == 3
    assert "missing: data/raw/api.parquet (run scripts/fetch_api.py)" in capsys.readouterr().out
    assert not (project / "logs" / "analyze").exists()


@pytest.mark.parametrize(
    ("second", "reason"),
    [
        ('o = Outputs("b")\no.variable("n_obs", "3")\n', "duplicate ID"),
        ('from pathlib import Path\nimport os\n(Path(os.environ["BUILD_OUTPUT_DIR"]) / "tables" / "main.md").write_text("x")\n',
         "changed a file of another producer"),
        ('o = Outputs("b")\no.variable("Bad", "3")\n', "invalid ID"),
        ('from pathlib import Path\nimport os\n(Path(os.environ["BUILD_OUTPUT_DIR"]) / "variables" / "b.yml").write_text("x: 1.5\\n")\n',
         "float variable"),
        ('from pathlib import Path\nimport os\n(Path(os.environ["BUILD_OUTPUT_DIR"]) / "notes.txt").write_text("x")\n',
         "unexpected file"),
        ('from pathlib import Path\nimport os\n(Path(os.environ["BUILD_OUTPUT_DIR"]) / "tables").mkdir(exist_ok=True)\n'
         '(Path(os.environ["BUILD_OUTPUT_DIR"]) / "tables" / "t2.md").write_text("| a |\\n|---|\\n| 1 |\\n")\n',
         "table without caption"),
        ('o = Outputs("b")\no.dataset("unknown")\n', "undeclared dataset"),
        ('o = Outputs("b")\no.input("data/absent.csv")\n', "missing input"),
    ],
)
def test_analyze_validation_failures(project: Path, second: str, reason: str) -> None:
    configure(project, analyze=["notebooks/a.py", "notebooks/b.py"])
    write_step(project, "b", second)
    assert main(project, "analyze") == 1, reason
    assert not (project / "paper" / "outputs").exists()


def test_declared_dataset_version(project: Path) -> None:
    configure(project, analyze=["notebooks/a.py", "notebooks/b.py"])
    write_step(project, "b", 'o = Outputs("b")\no.dataset("remote")\no.variable("other", 1)\n')
    assert main(project, "analyze") == 0
    manifest = json.loads((project / "paper" / "outputs" / "manifest.json").read_text())
    other = next(a for a in manifest["artifacts"] if a["id"] == "other")
    assert other["inputs"] == [{"path": "dataset:remote", "version": "2026-01"}]


def test_config_errors(project: Path) -> None:
    configure(project, analyze=["../outside.py"])
    assert main(project, "analyze") == 1
    configure(project, analyze=["notebooks/a.py", "scripts/a.py"])
    assert main(project, "analyze") == 1


# --- prepare, all, usage -------------------------------------------------------------------------


def test_prepare_runs_steps_in_order(project: Path) -> None:
    scripts = project / "scripts"
    scripts.mkdir()
    (scripts / "one.py").write_text("open('order.txt', 'a').write('one\\n')\n")
    (scripts / "two.py").write_text("open('order.txt', 'a').write('two\\n')\n")
    configure(project, prepare=["scripts/one.py", "scripts/two.py"], analyze=["notebooks/a.py"])
    assert main(project, "prepare") == 0
    assert (project / "order.txt").read_text() == "one\ntwo\n"


def test_all_stops_at_first_failure(project: Path, capsys) -> None:
    write_step(project, "a", "raise SystemExit(2)\n")
    assert main(project, "all") == 1
    out = capsys.readouterr().out
    assert "stage prepare: pass" in out and "stage analyze: fail" in out
    assert "stage paper: not-run" in out and "stage check: not-run" in out


def test_usage_error(project: Path) -> None:
    with pytest.raises(SystemExit) as info:
        main(project, "deploy")
    assert info.value.code == 2


# --- paper -------------------------------------------------------------------------------------


def fake_quarto(tmp_path: Path, produce: list[str], code: int = 0) -> str:
    script = tmp_path / "fake-quarto"
    lines = [f"#!{sys.executable}", "import sys, pathlib", "out = pathlib.Path(sys.argv[sys.argv.index('--output-dir') + 1])"]
    lines += [f"(out / {name!r}).write_text('rendered')" for name in produce]
    lines += [f"sys.exit({code})"]
    script.write_text("\n".join(lines) + "\n")
    script.chmod(0o755)
    return str(script)


def paper_project(project: Path) -> Path:
    assert main(project, "analyze") == 0
    (project / "paper" / "_quarto.yml").write_text(
        'format:\n  docx:\n    output-file: "demo.docx"\n  typst:\n    output-file: "demo.pdf"\n'
    )
    return project


def test_paper_promotes_complete_render(project: Path, tmp_path: Path, monkeypatch) -> None:
    paper_project(project)
    monkeypatch.setattr(build, "find_quarto", lambda: fake_quarto(tmp_path, ["demo.docx", "demo.pdf"]))
    assert main(project, "paper") == 0
    assert sorted(p.name for p in (project / "paper" / "_output").iterdir()) == ["demo.docx", "demo.pdf"]


@pytest.mark.parametrize(("produce", "code"), [(["demo.docx"], 0), (["demo.docx", "demo.pdf"], 1)])
def test_partial_or_failed_render_keeps_previous(project: Path, tmp_path: Path, monkeypatch, produce, code) -> None:
    paper_project(project)
    output = project / "paper" / "_output"
    output.mkdir()
    (output / "demo.pdf").write_text("previous")
    monkeypatch.setattr(build, "find_quarto", lambda: fake_quarto(tmp_path, produce, code))
    assert main(project, "paper") == 1
    assert [p.name for p in output.iterdir()] == ["demo.pdf"]
    assert (output / "demo.pdf").read_text() == "previous"


def test_paper_needs_analyze_outputs(project: Path) -> None:
    (project / "paper").mkdir()
    assert main(project, "paper") == 3


def test_unsupported_format(project: Path, tmp_path: Path, monkeypatch) -> None:
    paper_project(project)
    (project / "paper" / "_quarto.yml").write_text("format:\n  html: default\n")
    monkeypatch.setattr(build, "find_quarto", lambda: fake_quarto(tmp_path, []))
    assert main(project, "paper") == 1


# --- check -------------------------------------------------------------------------------------


def test_check_passes_after_analyze(project: Path) -> None:
    assert main(project, "analyze") == 0
    assert main(project, "check") == 0


@pytest.mark.parametrize(
    "tamper",
    [
        lambda p: (p / "paper" / "outputs" / "tables" / "main.md").write_text("edited by hand\n"),
        lambda p: (p / "paper" / "outputs" / "tables" / "extra.md").write_text("x\n"),
        lambda p: (p / "paper" / "outputs" / "figures" / "fig.png").unlink(),
        lambda p: (p / "paper" / "_variables.yml").write_text('n_obs: "999"\n'),
    ],
    ids=["edited", "unlisted", "missing", "variables"],
)
def test_manifest_check_failures(project: Path, tamper) -> None:
    assert main(project, "analyze") == 0
    tamper(project)
    assert build.check_manifest(project)
    assert main(project, "check") == 1


# --- Review fixes --------------------------------------------------------------------------------


def test_non_bmp_and_control_characters_in_variables(project: Path) -> None:
    write_step(project, "a", 'o = Outputs("a")\no.variable("beta", "\\U0001d6fd = 0.50")\no.variable("c1", "x\\x85y")\n')
    assert main(project, "analyze") == 0
    loaded = build.load_yaml((project / "paper" / "_variables.yml").read_text(encoding="utf-8"), "v")
    assert loaded == {"beta": "\U0001d6fd = 0.50", "c1": "x\x85y"}
    assert build.check_manifest(project) == []


def test_undecodable_variables_file_is_a_stage_failure(project: Path, capsys) -> None:
    write_step(project, "a", 'import os, pathlib\nd = pathlib.Path(os.environ["BUILD_OUTPUT_DIR"]) / "variables"\n'
               'd.mkdir(parents=True)\n(d / "a.yml").write_bytes(b"x: \\"\\xff\\xfe\\"\\n")\n')  # fmt: skip
    assert main(project, "analyze") == 1
    assert "stage analyze: fail" in capsys.readouterr().out


def test_quarto_format_given_as_string(project: Path, tmp_path: Path, monkeypatch) -> None:
    paper_project(project)
    (project / "paper" / "_quarto.yml").write_text("format:\n  docx: default\n")
    monkeypatch.setattr(build, "find_quarto", lambda: fake_quarto(tmp_path, ["paper.docx"]))
    assert main(project, "paper") == 0
