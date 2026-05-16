"""Pre-flight validates the harness's required external tools and asset parity."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS_DIR = HERE.parent
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))

import ab_harness  # type: ignore  # noqa: E402


def test_preflight_returns_status_dict() -> None:
    """preflight() returns a dict {tool: ok_bool, ...} and an aggregate 'ok'."""
    status = ab_harness.preflight()
    assert isinstance(status, dict)
    assert "ok" in status
    assert isinstance(status["ok"], bool)
    for tool in ("claude", "git", "python"):
        assert tool in status, f"preflight missing tool: {tool}"


def test_preflight_detects_missing_tool(monkeypatch) -> None:
    """If shutil.which returns None for a required tool, status reports ok=False."""
    import shutil as sh
    real_which = sh.which

    def fake_which(name: str) -> str | None:
        return None if name == "git" else real_which(name)

    monkeypatch.setattr(ab_harness.shutil, "which", fake_which)
    status = ab_harness.preflight()
    assert status["git"] is False
    assert status["ok"] is False


def test_preflight_asset_parity_check_when_b_absent() -> None:
    """When plugins/meta-ralph-b/ is not scaffolded, asset_parity is reported
    as 'n/a' (informational) and does NOT block ok=True."""
    status = ab_harness.preflight()
    assert "asset_parity" in status
    if "B" in ab_harness.VARIANT_PATHS:
        assert status["asset_parity"] is True
    else:
        assert status["asset_parity"] == "n/a (variant B not scaffolded)"


def test_preflight_asset_parity_check_when_b_present(tmp_path: Path, monkeypatch) -> None:
    """When plugins/meta-ralph-b/ exists and its templates/scripts/reference/docs
    match A's, asset_parity is True. Use a tmp B with the same hash tree as A."""
    import shutil
    a_path = ab_harness.VARIANT_PATHS["A"]
    b_path = tmp_path / "meta-ralph-b"
    shutil.copytree(a_path / "skills", b_path / "skills")
    shutil.copytree(a_path / "docs", b_path / "docs")
    monkeypatch.setitem(ab_harness.VARIANT_PATHS, "B", b_path)
    status = ab_harness.preflight()
    assert status["asset_parity"] is True
