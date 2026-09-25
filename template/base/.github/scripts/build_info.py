"""Write .build/build-info.json for the preview artifact: commit, run, time, and tool versions."""

import datetime
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]


def first_line(*cmd: str) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return (result.stdout or result.stderr).strip().splitlines()[0] if result.returncode == 0 else "unknown"


def main() -> None:
    project = YAML(typ="safe", pure=True).load((ROOT / "project.yml").read_text(encoding="utf-8"))
    quarto = str(Path(sys.executable).parent / "quarto")
    info = {
        "commit": os.environ.get("GITHUB_SHA", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "time_utc": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "template_commit": project["generated"]["template_commit"],
        "versions": {
            "quarto": first_line(quarto, "--version"),
            "pandoc": first_line(quarto, "pandoc", "--version"),
            "typst": first_line(quarto, "typst", "--version"),
            "python": platform.python_version(),
            "uv": first_line("uv", "--version"),
        },
    }
    out = ROOT / ".build" / "build-info.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(info, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
