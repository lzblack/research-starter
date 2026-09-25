"""End-to-end runs over the fixture answer files (appendix A3.1, A3.2, A7.3, A7.4)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = sorted((ROOT / "tests" / "fixtures" / "answers").glob("*.yml"))
DATE = "2026-01-15"

pytestmark = pytest.mark.fixtures


def run(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "new_project.py"), *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


def generate(answers: Path, target: Path) -> subprocess.CompletedProcess[str]:
    target.mkdir(exist_ok=True)
    return run("generate", "--answers", answers, "--target", target, "--date", DATE, "--allow-dirty")


def reported(stdout: str) -> dict[str, str]:
    """Map each reported path to its verb (create, same, conflict)."""
    result = {}
    for line in stdout.splitlines():
        verb, _, path = line.partition(" ")
        result[path] = verb
    return result


def snapshot(target: Path, paths: list[str]) -> dict[str, tuple[bytes, bool]]:
    return {
        path: ((target / path).read_bytes(), os.access(target / path, os.X_OK))
        for path in paths
    }


@pytest.mark.parametrize("answers", FIXTURES, ids=lambda p: p.stem)
def test_fixture(answers: Path, tmp_path: Path) -> None:
    first = generate(answers, tmp_path / "a")
    assert first.returncode == 0, first.stderr
    paths = sorted(reported(first.stdout))
    assert set(reported(first.stdout).values()) == {"create"}

    # Determinism (A3.1): a second run into a new directory gives identical files.
    second = generate(answers, tmp_path / "b")
    assert second.returncode == 0, second.stderr
    assert sorted(reported(second.stdout)) == paths
    assert snapshot(tmp_path / "a", paths) == snapshot(tmp_path / "b", paths)

    # Rerun on a complete, unedited project reports only `same` (A3.2).
    rerun = run("generate", "--answers", answers, "--target", tmp_path / "a", "--allow-dirty")
    assert rerun.returncode == 0, rerun.stderr
    assert set(reported(rerun.stdout).values()) == {"same"}

    # Local acceptance checks (A7.3): nothing fails.
    accept = run("accept", "--target", tmp_path / "a")
    assert accept.returncode == 0, accept.stdout + accept.stderr
    statuses = {line.split(" ")[1]: line.split(" ")[0] for line in accept.stdout.splitlines()}
    for check in ["env-sync", "render-content", "template-provenance"]:
        assert statuses[check] == "pass", accept.stdout
    assert "fail" not in statuses.values(), accept.stdout
