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


def test_preflight_asset_parity_check() -> None:
    """preflight verifies hash_tree(A/templates) == hash_tree(B/templates) etc."""
    status = ab_harness.preflight()
    assert "asset_parity" in status
    assert status["asset_parity"] is True
