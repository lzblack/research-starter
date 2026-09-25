"""Build entry point: regenerate every number, table, figure, and the paper.

    uv run build.py all | prepare | analyze | paper | check

Stages run in the order prepare, analyze, paper, check. `all` stops at the first stage that does
not pass. Exit codes: 0 every requested stage passed, 1 a stage failed, 2 usage error,
3 a prerequisite is missing.

Steps are listed in pyproject.toml under [tool.research-starter.build]. Each step runs as its own
process from the repository root; its output goes to logs/<stage>/<step>.log.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import unicodedata
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

ROOT = Path(__file__).resolve().parent
STAGES = ["prepare", "analyze", "paper", "check"]
PASS, FAIL, MISSING, NOT_RUN = "pass", "fail", "missing-prerequisite", "not-run"
EXIT_CODES = {PASS: 0, FAIL: 1, MISSING: 3}
ARTIFACT_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
FORMAT_EXTENSIONS = {"docx": "docx", "typst": "pdf"}


class StageError(Exception):
    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


# --- Helpers -----------------------------------------------------------------------------------


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quote(value: str) -> str:
    """A double-quoted YAML string; control and line-separator characters are escaped."""
    escapes = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}
    out = []
    for ch in value:
        if ch in escapes:
            out.append(escapes[ch])
        elif unicodedata.category(ch) in {"Cc", "Cs", "Zl", "Zp"} or ch == "\ufeff":
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def load_yaml(text: str, where: str) -> Any:
    try:
        return YAML(typ="safe", pure=True).load(text)
    except YAMLError as exc:
        raise StageError(FAIL, f"{where}: invalid YAML: {' '.join(str(exc).split())}") from exc


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".tmp-{path.name}")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def fresh_dir(path: Path) -> Path:
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def relative_path(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value or value.startswith("/") or ".." in value.split("/"):
        raise StageError(FAIL, f"{where}: {value!r} must be a relative path inside the repository")
    return value


# --- Configuration -----------------------------------------------------------------------------


def load_config(root: Path) -> dict[str, Any]:
    try:
        pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise StageError(FAIL, f"pyproject.toml: {exc}") from exc
    table = pyproject.get("tool", {}).get("research-starter", {}).get("build", {})
    where = "pyproject.toml [tool.research-starter.build]"
    config: dict[str, Any] = {}
    for key in ["prepare", "analyze"]:
        steps = table.get(key, [])
        if not isinstance(steps, list):
            raise StageError(FAIL, f"{where}: {key} must be a list of paths")
        config[key] = [relative_path(s, f"{where} {key}") for s in steps]
    stems = [Path(s).stem for s in config["analyze"]]
    if len(set(stems)) != len(stems):
        raise StageError(FAIL, f"{where}: analyze steps must have distinct file names")
    external = table.get("external", {})
    if not isinstance(external, dict):
        raise StageError(FAIL, f"{where}: external must map output paths to scripts")
    config["external"] = {
        relative_path(k, f"{where} external"): relative_path(v, f"{where} external") for k, v in external.items()
    }
    return config


def check_external(root: Path, config: dict[str, Any]) -> None:
    missing = [(path, script) for path, script in config["external"].items() if not (root / path).exists()]
    for path, script in missing:
        print(f"missing: {path} (run {script})")
    if missing:
        raise StageError(MISSING, "outputs of external jobs are missing")


def run_step(root: Path, stage: str, step: str, env: dict[str, str] | None = None) -> None:
    if not (root / step).is_file():
        raise StageError(FAIL, f"step not found: {step}")
    log = root / "logs" / stage / f"{Path(step).stem}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as handle:
        code = subprocess.run(
            [sys.executable, str(root / step)], cwd=root, env=env, stdout=handle, stderr=subprocess.STDOUT
        ).returncode
    if code == 0:
        return
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("missing: "):
            print(line)
    status = MISSING if code == 3 else FAIL
    raise StageError(status, f"{step} exited with code {code}; see {log.relative_to(root)}")


# --- prepare -----------------------------------------------------------------------------------


def stage_prepare(root: Path, config: dict[str, Any]) -> None:
    check_external(root, config)
    for step in config["prepare"]:
        run_step(root, "prepare", step)


# --- analyze -----------------------------------------------------------------------------------


def snapshot(directory: Path) -> dict[str, str]:
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise StageError(FAIL, f"symbolic links are not allowed in outputs: {path.relative_to(directory)}")
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = sha256(path)
    return files


def dataset_versions(root: Path) -> dict[str, str | None]:
    readme = root / "data" / "README.md"
    if not readme.is_file():
        return {}
    match = re.match(r"^---\n(.*?)\n---\n", readme.read_text(encoding="utf-8"), re.DOTALL)
    front = load_yaml(match.group(1), "data/README.md") if match else None
    datasets = (front or {}).get("datasets") or []
    if not isinstance(datasets, list):
        raise StageError(FAIL, "data/README.md: datasets must be a list")
    return {d["id"]: d.get("version") for d in datasets if isinstance(d, dict) and "id" in d}


def merged_variables(variables: dict[str, Any]) -> bytes:
    lines = []
    for key in sorted(variables):
        value = variables[key]
        text = quote(value) if isinstance(value, str) else ("true" if value is True else "false" if value is False else str(value))
        lines.append(f"{key}: {text}")
    return ("\n".join(lines) + "\n").encode() if lines else b"{}\n"


def build_manifest(root: Path, staging: Path, owner: dict[str, str], producers: dict[str, str]) -> tuple[dict, bytes]:
    variables: dict[str, Any] = {}
    artifacts: list[dict[str, Any]] = []
    inputs: dict[str, list[dict[str, Any]]] = {pid: [] for pid in producers}
    seen: dict[str, str] = {}
    versions = dataset_versions(root)

    def claim(artifact_id: str, where: str) -> None:
        if not ARTIFACT_ID.match(artifact_id):
            raise StageError(FAIL, f"{where}: artifact ID {artifact_id!r} must match {ARTIFACT_ID.pattern}")
        if artifact_id in seen:
            raise StageError(FAIL, f"{where}: artifact ID {artifact_id!r} is also produced in {seen[artifact_id]}")
        seen[artifact_id] = where

    for rel, pid in sorted(owner.items()):
        if rel.startswith("inputs/") and rel == f"inputs/{pid}.json":
            declared = json.loads((staging / rel).read_text(encoding="utf-8"))
            if not isinstance(declared, list) or not all(isinstance(i, str) for i in declared):
                raise StageError(FAIL, f"{rel}: must be a JSON list of strings")
            for item in declared:
                if item.startswith("dataset:"):
                    name = item.removeprefix("dataset:")
                    if name not in versions:
                        raise StageError(FAIL, f"{rel}: dataset {name!r} is not declared in data/README.md")
                    inputs[pid].append({"path": item, "version": versions[name]})
                else:
                    path = root / relative_path(item, rel)
                    if not path.is_file():
                        raise StageError(FAIL, f"{rel}: declared input not found: {item}")
                    inputs[pid].append({"path": item, "sha256": sha256(path)})

    for rel, pid in sorted(owner.items()):
        folder, _, name = rel.partition("/")
        path = staging / rel
        if "/" in name:
            raise StageError(FAIL, f"unexpected output path: {rel}")
        if folder == "inputs" and rel == f"inputs/{pid}.json":
            continue
        if folder == "variables" and name == f"{pid}.yml":
            data = load_yaml(path.read_text(encoding="utf-8"), rel)
            if not isinstance(data, dict):
                raise StageError(FAIL, f"{rel}: must be a mapping of variable IDs to values")
            for key, value in data.items():
                claim(str(key), rel)
                if type(value) not in (str, int, bool):
                    raise StageError(FAIL, f"{rel}: {key} must be a string, integer, or boolean (format numbers as strings)")
                variables[key] = value
                artifacts.append({"id": key, "kind": "variable", "file": f"paper/outputs/{rel}"})
        elif folder == "tables" and name.endswith(".md"):
            artifact_id = name.removesuffix(".md")
            claim(artifact_id, rel)
            if not re.search(rf"^: .*\{{#tbl-{re.escape(artifact_id)}\}}\s*$", path.read_text(encoding="utf-8"), re.M):
                raise StageError(FAIL, f"{rel}: needs a caption line ': <caption> {{#tbl-{artifact_id}}}'")
            artifacts.append({"id": artifact_id, "kind": "table", "file": f"paper/outputs/{rel}"})
        elif folder == "figures" and name.endswith(".png"):
            artifact_id = name.removesuffix(".png")
            claim(artifact_id, rel)
            if not path.read_bytes().startswith(PNG_MAGIC):
                raise StageError(FAIL, f"{rel}: is not a PNG file")
            artifacts.append({"id": artifact_id, "kind": "figure", "file": f"paper/outputs/{rel}"})
        else:
            raise StageError(FAIL, f"unexpected output from {producers[pid]}: {rel}")
        for entry in artifacts:
            if "producer" not in entry:
                entry.update(
                    producer=producers[pid],
                    producer_sha256=sha256(root / producers[pid]),
                    inputs=inputs[pid],
                    sha256=sha256(path),
                )

    merged = merged_variables(variables)
    manifest = {
        "artifacts": sorted(artifacts, key=lambda a: a["id"]),
        "schema": 1,
        "variables_sha256": hashlib.sha256(merged).hexdigest(),
    }
    return manifest, merged


def manifest_bytes(manifest: dict) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def stage_analyze(root: Path, config: dict[str, Any]) -> None:
    check_external(root, config)
    staging = fresh_dir(root / ".build" / "analyze")
    producers = {Path(step).stem: step for step in config["analyze"]}
    owner: dict[str, str] = {}
    before: dict[str, str] = {}
    for pid, step in producers.items():
        env = dict(os.environ, BUILD_OUTPUT_DIR=str(staging))
        run_step(root, "analyze", step, env)
        after = snapshot(staging)
        for rel in before.keys() - after.keys():
            raise StageError(FAIL, f"{step} removed {rel}, written by {producers[owner[rel]]}")
        for rel, digest in after.items():
            if before.get(rel) != digest:
                if rel in owner and owner[rel] != pid:
                    raise StageError(FAIL, f"{step} changed {rel}, written by {producers[owner[rel]]}")
                owner[rel] = pid
        before = after

    try:
        manifest, merged = build_manifest(root, staging, owner, producers)
    except (UnicodeError, ValueError) as exc:
        raise StageError(FAIL, f"an output file could not be read: {exc}") from exc
    promote = fresh_dir(root / ".build" / "promote")
    for rel in owner:
        if not rel.startswith("inputs/"):
            (promote / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staging / rel, promote / rel)
    (promote / "manifest.json").write_bytes(manifest_bytes(manifest))

    outputs = root / "paper" / "outputs"
    previous = root / ".build" / "previous-outputs"
    shutil.rmtree(previous, ignore_errors=True)
    outputs.parent.mkdir(parents=True, exist_ok=True)
    if outputs.exists():
        os.replace(outputs, previous)
    os.replace(promote, outputs)
    write_atomic(root / "paper" / "_variables.yml", merged)
    shutil.rmtree(previous, ignore_errors=True)


# --- paper -------------------------------------------------------------------------------------


def find_quarto() -> str:
    beside = Path(sys.executable).parent / "quarto"
    if beside.exists():
        return str(beside)
    found = shutil.which("quarto")
    if found is None:
        raise StageError(FAIL, "quarto not found; run `uv sync`")
    return found


def expected_outputs(root: Path) -> list[str]:
    config = load_yaml((root / "paper" / "_quarto.yml").read_text(encoding="utf-8"), "paper/_quarto.yml")
    formats = (config or {}).get("format") or {}
    if not isinstance(formats, dict) or not formats:
        raise StageError(FAIL, "paper/_quarto.yml: no output formats configured")
    names = []
    for key, options in formats.items():
        if key not in FORMAT_EXTENSIONS:
            raise StageError(FAIL, f"paper/_quarto.yml: format {key!r} is not supported (docx, typst)")
        extension = FORMAT_EXTENSIONS[key]
        name = (options.get("output-file") if isinstance(options, dict) else None) or f"paper.{extension}"
        names.append(name if name.endswith(f".{extension}") else f"{name}.{extension}")
    return names


def stage_paper(root: Path) -> None:
    for required in ["paper/_variables.yml", "paper/outputs/manifest.json"]:
        if not (root / required).is_file():
            print(f"missing: {required} (run `uv run build.py analyze`)")
            raise StageError(MISSING, f"{required} is missing")
    expected = expected_outputs(root)
    staging = fresh_dir(root / ".build" / "render")
    log = root / "logs" / "paper" / "quarto.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as handle:
        code = subprocess.run(
            [find_quarto(), "render", "--output-dir", str(staging)],
            cwd=root / "paper",
            stdout=handle,
            stderr=subprocess.STDOUT,
        ).returncode
    if code != 0:
        raise StageError(FAIL, f"quarto render exited with code {code}; see logs/paper/quarto.log")
    absent = [name for name in expected if not (staging / name).is_file()]
    if absent:
        raise StageError(FAIL, f"quarto did not produce {', '.join(absent)}; see logs/paper/quarto.log")
    output = root / "paper" / "_output"
    previous = root / ".build" / "previous-render"
    shutil.rmtree(previous, ignore_errors=True)
    if output.exists():
        os.replace(output, previous)
    os.replace(staging, output)
    shutil.rmtree(previous, ignore_errors=True)


# --- check -------------------------------------------------------------------------------------


def check_manifest(root: Path) -> list[str]:
    """Problems with the outputs against the manifest (check `manifest`)."""
    outputs = root / "paper" / "outputs"
    path = outputs / "manifest.json"
    if not path.is_file():
        return ["paper/outputs/manifest.json is missing"]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        artifacts = manifest["artifacts"]
        ids = [a["id"] for a in artifacts]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        return [f"paper/outputs/manifest.json is malformed: {exc}"]
    problems = []
    if manifest.get("schema") != 1:
        problems.append("manifest schema must be 1")
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        problems.append(f"duplicate artifact IDs: {', '.join(duplicates)}")
    listed = {a["file"] for a in artifacts}
    present = {p.relative_to(root).as_posix() for p in outputs.rglob("*") if p.is_file() and p != path}
    for missing in sorted(listed - present):
        problems.append(f"{missing} is listed in the manifest but missing")
    for extra in sorted(present - listed):
        problems.append(f"{extra} is not in the manifest")
    for artifact in artifacts:
        file = root / artifact["file"]
        if file.is_file() and sha256(file) != artifact.get("sha256"):
            problems.append(f"{artifact['file']} changed after it was produced")
    variables: dict[str, Any] = {}
    for file in sorted((outputs / "variables").glob("*.yml")):
        data = load_yaml(file.read_text(encoding="utf-8"), file.relative_to(root).as_posix())
        variables.update(data or {})
    merged = merged_variables(variables)
    current = root / "paper" / "_variables.yml"
    if not current.is_file() or current.read_bytes() != merged:
        problems.append("paper/_variables.yml does not match the variables files")
    elif hashlib.sha256(merged).hexdigest() != manifest.get("variables_sha256"):
        problems.append("paper/_variables.yml does not match variables_sha256 in the manifest")
    return problems


def load_checks() -> Any:
    """Load checks.py from beside this file (it is not an installed package)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("project_checks", Path(__file__).resolve().parent / "checks.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def stage_check(root: Path, staged: bool = False) -> None:
    checks = load_checks()

    def manifest(project: Any) -> Any:
        return checks.result("manifest", check_manifest(project.root))

    results = checks.run(root, staged=staged, extra={"manifest": manifest})
    for item in results:
        print(f"{item.status} {item.check}")
        for problem in item.problems:
            print(f"  {problem}")
    print("Data checks: configured checks passed only if none failed above. They cannot establish")
    print("that no sensitive data exists; the owner reviews outputs before any release.")
    if not staged:
        write_crosswalk(root, checks.crosswalk(root))
    if any(item.status == "fail" for item in results):
        raise StageError(FAIL, "one or more checks failed")


def write_crosswalk(root: Path, rows: list[dict[str, str]]) -> None:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, ["location", "reference", "artifact_id", "kind", "producer"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    write_atomic(root / ".build" / "reports" / "crosswalk.csv", buffer.getvalue().encode())


# --- main --------------------------------------------------------------------------------------


def run_stage(root: Path, stage: str, staged: bool = False) -> None:
    if stage == "paper":
        stage_paper(root)
    elif stage == "check":
        stage_check(root, staged)
    else:
        config = load_config(root)
        (stage_prepare if stage == "prepare" else stage_analyze)(root, config)


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(prog="build.py", description="Regenerate results and the paper.")
    parser.add_argument("stage", choices=["all", *STAGES])
    parser.add_argument("--staged", action="store_true", help="check: only the data-exposure checks, on staged files")
    args = parser.parse_args(argv)
    if args.staged and args.stage != "check":
        parser.error("--staged applies only to the check stage")
    stages = STAGES if args.stage == "all" else [args.stage]
    code = 0
    for index, stage in enumerate(stages):
        try:
            run_stage(root, stage, args.staged)
            print(f"stage {stage}: {PASS}")
        except StageError as exc:
            print(f"error: {exc}", file=sys.stderr)
            print(f"stage {stage}: {exc.status}")
            for rest in stages[index + 1 :]:
                print(f"stage {rest}: {NOT_RUN}")
            code = EXIT_CODES[exc.status]
            break
    return code


if __name__ == "__main__":
    sys.exit(main())
