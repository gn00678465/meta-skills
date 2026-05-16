"""Tests for write_real_run_report — verdict logic and report shape."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EVALS_DIR = HERE.parent
if str(EVALS_DIR) not in sys.path:
    sys.path.insert(0, str(EVALS_DIR))

import ab_harness  # type: ignore  # noqa: E402


def _record(variant: str, fixture: str, rep: int, passed: bool, wall_s: float = 30.0,
            usage: dict[str, Any] | None = None) -> dict[str, Any]:
    # Non-empty expectations: real grading always produces at least one check;
    # _classify_verdict treats empty-expectations records as "not completed"
    return {"variant": variant, "fixture": fixture, "rep": rep,
            "passed": passed, "wall_s": wall_s, "exit_reason": "sentinel",
            "exit_code": 0, "usage": usage or {},
            "expectations": [{"text": "ok", "passed": passed, "evidence": ""}]}


def test_verdict_maintains_when_b_loses_at_most_one_per_fixture(tmp_path: Path) -> None:
    fixtures = [{"id": "f1"}, {"id": "f2"}]
    records = (
        [_record("A", "f1", r, True) for r in range(3)] +
        [_record("A", "f2", r, True) for r in range(3)] +
        [_record("B", "f1", r, True) for r in range(3)] +
        [_record("B", "f2", 0, False), _record("B", "f2", 1, True), _record("B", "f2", 2, True)]
    )
    ab_harness.write_real_run_report(tmp_path, records, ["A", "B"], fixtures, 3, "now")
    summary = json.loads((tmp_path / "ab-summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] == "B maintains functionality"


def test_verdict_regresses_when_b_loses_two_on_any_fixture(tmp_path: Path) -> None:
    fixtures = [{"id": "f1"}]
    records = (
        [_record("A", "f1", r, True) for r in range(3)] +
        [_record("B", "f1", 0, False), _record("B", "f1", 1, False), _record("B", "f1", 2, True)]
    )
    ab_harness.write_real_run_report(tmp_path, records, ["A", "B"], fixtures, 3, "now")
    summary = json.loads((tmp_path / "ab-summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] == "B regresses"


def test_verdict_inconclusive_when_fewer_than_29_runs_completed(tmp_path: Path) -> None:
    fixtures = [{"id": f"f{i}"} for i in range(6)]
    records = [_record("A", "f0", 0, True) for _ in range(28)]
    ab_harness.write_real_run_report(tmp_path, records, ["A", "B"], fixtures, 3, "now")
    summary = json.loads((tmp_path / "ab-summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] == "inconclusive — rerun"


def test_verdict_inconclusive_when_harness_errors_push_completed_below_29(tmp_path: Path) -> None:
    """Records with `error` key (harness exceptions) must not count as completed."""
    fixtures = [{"id": f"f{i}"} for i in range(6)]
    records: list[dict[str, Any]] = []
    # 32 records total — but 28 have errors, only 4 actually completed
    for i in range(28):
        r = _record("A", "f0", i, False)
        r["error"] = "RuntimeError: sandbox failed"
        # error records have empty expectations
        records.append(r)
    for i in range(4):
        r = _record("B", "f1", i, True)
        r["expectations"] = [{"text": "ok", "passed": True, "evidence": ""}]
        records.append(r)
    ab_harness.write_real_run_report(tmp_path, records, ["A", "B"], fixtures, 3, "now")
    summary = json.loads((tmp_path / "ab-summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] == "inconclusive — rerun"
    assert summary["completed_runs"] == 4
    assert summary["errored_runs"] == 28


def test_benchmark_md_has_pass_rate_matrix(tmp_path: Path) -> None:
    fixtures = [{"id": "f1"}, {"id": "f2"}]
    records = (
        [_record("A", "f1", r, True) for r in range(3)] +
        [_record("A", "f2", r, True) for r in range(3)] +
        [_record("B", "f1", r, True) for r in range(3)] +
        [_record("B", "f2", r, True) for r in range(3)]
    )
    ab_harness.write_real_run_report(tmp_path, records, ["A", "B"], fixtures, 3, "now")
    md = (tmp_path / "ab-benchmark.md").read_text(encoding="utf-8")
    assert "## Pass rate matrix" in md
    assert "| f1 |" in md
    assert "| f2 |" in md
    assert "## Summary" in md
