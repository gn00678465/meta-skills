"""Lightweight invariants on ab_fixtures.json. Catches accidental edits that
would silently break the harness — wrong runtime, missing keys, duplicates."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent / "ab_fixtures.json"

VALID_RUNTIMES = {"sh", "ts", "js", "py"}
VALID_KINDS = {"bootstrap", "amend", "negative", "edge"}


@pytest.fixture(scope="module")
def fixtures_doc() -> dict[str, Any]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def test_top_level_shape(fixtures_doc: dict[str, Any]) -> None:
    assert fixtures_doc["version"] == 1
    assert isinstance(fixtures_doc["reps_per_fixture"], int)
    assert fixtures_doc["reps_per_fixture"] >= 1
    assert isinstance(fixtures_doc["fixtures"], list)
    assert len(fixtures_doc["fixtures"]) == 6


def test_fixture_ids_unique(fixtures_doc: dict[str, Any]) -> None:
    ids = [f["id"] for f in fixtures_doc["fixtures"]]
    assert len(ids) == len(set(ids))


def test_each_fixture_has_required_fields(fixtures_doc: dict[str, Any]) -> None:
    required = {"id", "kind", "prompt", "wall_timeout_s", "expected"}
    for f in fixtures_doc["fixtures"]:
        missing = required - set(f.keys())
        assert not missing, f"fixture {f.get('id')} missing keys: {missing}"
        assert f["kind"] in VALID_KINDS, f"bad kind: {f['kind']}"


def test_bootstrap_fixtures_specify_runtime(fixtures_doc: dict[str, Any]) -> None:
    for f in fixtures_doc["fixtures"]:
        if f["kind"] in {"bootstrap", "edge"}:
            assert f["expected"]["driver_eval_required"] is True
            rt = f["expected"]["prd_constraints"]["runtime"]
            assert rt in VALID_RUNTIMES, f"{f['id']}: bad runtime {rt}"


def test_amend_fixtures_preset_exists(fixtures_doc: dict[str, Any]) -> None:
    presets_dir = HERE.parent / "ab_presets"
    for f in fixtures_doc["fixtures"]:
        if f["kind"] == "amend":
            preset = f.get("preset")
            assert preset, f"{f['id']} missing preset"
            assert (presets_dir / f"{preset}.json").exists()


def test_negative_fixture_invariants(fixtures_doc: dict[str, Any]) -> None:
    negs = [f for f in fixtures_doc["fixtures"] if f["kind"] == "negative"]
    assert len(negs) == 1, "exactly one negative fixture expected"
    f = negs[0]
    assert f["expected"]["should_trigger_skill"] is False
    assert f["expected"]["files_required"] == []
    assert f["expected"]["scaffold_must_be_empty"] is True


def test_runtime_coverage_includes_js_after_swap(fixtures_doc: dict[str, Any]) -> None:
    """js fixture must exist after the open-question (1) swap."""
    runtimes_in_bootstrap = {
        f["expected"]["prd_constraints"]["runtime"]
        for f in fixtures_doc["fixtures"]
        if f["kind"] in {"bootstrap", "edge"}
    }
    assert "js" in runtimes_in_bootstrap
