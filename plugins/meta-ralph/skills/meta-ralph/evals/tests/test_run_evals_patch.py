"""Verify run_evals.py accepts and honors --driver-from / --output-dir, and that
omitting both leaves behaviour identical to before the patch."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALS_DIR = HERE.parent
RUN_EVALS = EVALS_DIR / "run_evals.py"
TEMPLATES_DIR = EVALS_DIR.parent / "templates" / "ralph"


def test_help_lists_new_flags() -> None:
    """--help must mention both new flags."""
    result = subprocess.run(
        [sys.executable, str(RUN_EVALS), "--help"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert "--driver-from" in result.stdout
    assert "--output-dir" in result.stdout


def test_driver_from_reads_external_driver(tmp_path: Path) -> None:
    """When --driver-from <path> is set, run_evals copies <path>/.ralph/ralph.sh
    instead of templates/ralph/ralph.sh.tpl."""
    external = tmp_path / "ext"
    (external / ".ralph").mkdir(parents=True)
    shutil.copy(TEMPLATES_DIR / "ralph.sh.tpl", external / ".ralph" / "ralph.sh")
    out_dir = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, str(RUN_EVALS),
         "--runtime", "sh",
         "--scenario", "passthrough-no-cli-model",
         "--driver-from", str(external),
         "--output-dir", str(out_dir)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert (out_dir / "benchmark.md").exists()


def test_driver_from_missing_path_aborts(tmp_path: Path) -> None:
    """--driver-from pointing to a nonexistent .ralph/ralph.sh should error out
    with a clear message."""
    out_dir = tmp_path / "out"
    nonexistent = tmp_path / "nope"
    result = subprocess.run(
        [sys.executable, str(RUN_EVALS),
         "--runtime", "sh",
         "--scenario", "passthrough-no-cli-model",
         "--driver-from", str(nonexistent),
         "--output-dir", str(out_dir)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode != 0
    assert "driver-from" in (result.stderr + result.stdout).lower()


def test_no_flags_writes_to_default_location(tmp_path: Path) -> None:
    """With neither flag set, run_evals must still write to the default
    evals/results/iteration-N path. Verified by running with --iteration 99
    (deliberately high to avoid collision) and asserting the dir appears."""
    default_root = EVALS_DIR / "results" / "iteration-99"
    if default_root.exists():
        shutil.rmtree(default_root)
    try:
        result = subprocess.run(
            [sys.executable, str(RUN_EVALS),
             "--runtime", "sh",
             "--scenario", "passthrough-no-cli-model",
             "--iteration", "99"],
            capture_output=True, text=True, encoding="utf-8",
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert (default_root / "benchmark.md").exists()
    finally:
        if default_root.exists():
            shutil.rmtree(default_root)
