"""Create the synthetic example dataset, data/derived/example.parquet.

The data is generated from a fixed seed, so it is synthetic and reproducible. Replace this script
with your own preparation steps and list them in pyproject.toml.
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "derived" / "example.parquet"


def main() -> None:
    rng = np.random.default_rng(2020)
    n = 1000
    z = rng.normal(size=n)
    x = 0.6 * z + rng.normal(size=n)
    y = 1.0 + 0.5 * x + 0.3 * z + rng.normal(size=n)
    frame = pd.DataFrame({"x": x, "y": y, "z": z})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_name(f".tmp-{OUTPUT.name}")
    frame.to_parquet(tmp, index=False)
    os.replace(tmp, OUTPUT)


if __name__ == "__main__":
    main()
