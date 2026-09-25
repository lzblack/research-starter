"""Regenerate the example data and paper inputs that the template ships.

The template includes the outputs of its example (appendix A4.1) so a new project renders before
any analysis runs. Their provenance manifest records hashes of the notebook and its inputs, so the
shipped files must come from an actual run. This script generates a project, runs the prepare and
analyze stages there, and copies the results back into template/base/.

    uv run tools/refresh_example.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "template" / "base"
ANSWERS = ROOT / "tests" / "fixtures" / "answers" / "minimal-defaults.yml"
COPIED_FILES = ["data/derived/example.parquet", "paper/_variables.yml"]
COPIED_TREES = ["paper/outputs"]


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd), flush=True)
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="rs-refresh-") as tmp:
        project = Path(tmp) / "project"
        project.mkdir()
        run([sys.executable, str(ROOT / "new_project.py"), "generate", "--answers", str(ANSWERS),
             "--target", str(project), "--allow-dirty"], ROOT)  # fmt: skip
        run(["uv", "sync", "--locked"], project)
        run(["uv", "run", "--locked", "build.py", "prepare"], project)
        run(["uv", "run", "--locked", "build.py", "analyze"], project)
        for rel in COPIED_FILES:
            (BASE / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(project / rel, BASE / rel)
        for rel in COPIED_TREES:
            shutil.rmtree(BASE / rel, ignore_errors=True)
            shutil.copytree(project / rel, BASE / rel)
    print("refreshed the example outputs in template/base/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
