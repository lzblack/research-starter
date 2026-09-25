"""Write paper inputs (variables, tables, figures) for the build.

Notebooks write through this module so that `uv run build.py analyze` can collect, check, and
promote their outputs. When the build runs a notebook, it sets BUILD_OUTPUT_DIR; in an interactive
session the outputs go to .build/scratch/outputs/, and the committed paper inputs stay unchanged.

    from paper_outputs import Outputs

    outputs = Outputs("example")            # the notebook's file name without .py
    data = pd.read_parquet(outputs.input("data/derived/example.parquet"))
    outputs.variable("n_obs", f"{len(data):,}")
    outputs.table("main_results", frame, "Main estimates")
    outputs.figure("scatter", fig)
"""

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _output_root() -> Path:
    configured = os.environ.get("BUILD_OUTPUT_DIR")
    return Path(configured) if configured else ROOT / ".build" / "scratch" / "outputs"


def _quote(value: str) -> str:
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


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


class Outputs:
    def __init__(self, producer: str) -> None:
        self.producer = producer
        self.root = _output_root()
        self._variables: dict[str, str | int | bool] = {}
        self._inputs: list[str] = []

    @staticmethod
    def _check_id(artifact_id: str) -> None:
        if not ARTIFACT_ID.match(artifact_id):
            raise ValueError(f"artifact ID {artifact_id!r} must match {ARTIFACT_ID.pattern}")

    def _write(self, rel: str, data: bytes) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".tmp-{path.name}")
        tmp.write_bytes(data)
        os.replace(tmp, path)

    def input(self, path: str) -> Path:
        """Declare a repository file this notebook reads, and return its absolute path."""
        if path not in self._inputs:
            self._inputs.append(path)
            self._write(f"inputs/{self.producer}.json", json.dumps(self._inputs, indent=2).encode() + b"\n")
        return ROOT / path

    def dataset(self, dataset_id: str) -> None:
        """Declare a dataset from data/README.md that lives outside the repository."""
        self.input(f"dataset:{dataset_id}")

    def variable(self, artifact_id: str, value: str | int | bool) -> None:
        """A value for `{{< var id >}}`. Format numbers as strings, for example f"{x:.2f}"."""
        self._check_id(artifact_id)
        if type(value) not in (str, int, bool):
            raise TypeError(f"{artifact_id}: use a string, integer, or boolean; format numbers as strings")
        self._variables[artifact_id] = value
        lines = []
        for key in sorted(self._variables):
            v = self._variables[key]
            text = _quote(v) if isinstance(v, str) else str(v).lower() if isinstance(v, bool) else str(v)
            lines.append(f"{key}: {text}")
        self._write(f"variables/{self.producer}.yml", ("\n".join(lines) + "\n").encode())

    def table(self, artifact_id: str, frame: Any, caption: str) -> None:
        """A table for `{{< include outputs/tables/id.md >}}`, cited as @tbl-id.

        `frame` is a pandas DataFrame whose cells are already formatted as text.
        """
        self._check_id(artifact_id)
        header = [_cell(c) for c in frame.columns]
        rows = [[_cell(v) for v in row] for row in frame.itertuples(index=False)]
        lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        lines += ["| " + " | ".join(row) + " |" for row in rows]
        lines += ["", f": {caption} {{#tbl-{artifact_id}}}"]
        self._write(f"tables/{artifact_id}.md", ("\n".join(lines) + "\n").encode())

    def figure(self, artifact_id: str, figure: Any, dpi: int = 200) -> None:
        """A PNG figure for `![caption](outputs/figures/id.png){#fig-id}`."""
        self._check_id(artifact_id)
        path = self.root / "figures" / f"{artifact_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".tmp-{path.name}")
        figure.savefig(tmp, format="png", dpi=dpi, metadata={"Software": None})
        os.replace(tmp, path)
