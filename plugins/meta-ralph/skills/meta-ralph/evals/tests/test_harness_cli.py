"""CLI surface and --dry-run behaviour for ab_harness.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent / "ab_harness.py"


def test_help_lists_all_flags() -> None:
    result = subprocess.run(
        [sys.executable, str(HARNESS), "--help"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    for flag in ["--variant", "--fixture", "--reps", "--iteration", "--dry-run", "--keep-sandbox"]:
        assert flag in result.stdout, f"missing flag in --help: {flag}"


def test_dry_run_produces_report(tmp_path: Path) -> None:
    """--dry-run writes a benchmark.md + summary.json without spawning claude."""
    out_dir = tmp_path / "ab-out"
    result = subprocess.run(
        [sys.executable, str(HARNESS),
         "--dry-run",
         "--variant", "A",
         "--fixture", "boot-sh-claude-en",
         "--reps", "1",
         "--iteration", "1",
         "--output-root", str(out_dir)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    benchmark = out_dir / "iteration-1" / "ab-benchmark.md"
    summary = out_dir / "iteration-1" / "ab-summary.json"
    assert benchmark.exists(), f"benchmark.md missing under {out_dir}"
    assert summary.exists()
    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["dry_run"] is True
    assert data["verdict"] == "skipped (dry-run)"
