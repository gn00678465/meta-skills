"""Tests for ab_lib.py — sandbox utilities and asset-tree hashing."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALS_DIR = HERE.parent
if str(EVALS_DIR) not in sys.path:
    sys.path.insert(0, str(EVALS_DIR))

import ab_lib  # type: ignore  # noqa: E402


def test_make_sandbox_initializes_git_repo() -> None:
    box = ab_lib.make_sandbox("test-")
    try:
        assert box.exists()
        assert (box / ".git").is_dir()
        cfg = subprocess.run(["git", "config", "core.autocrlf"], cwd=box,
                             capture_output=True, text=True).stdout.strip()
        assert cfg == "false"
        log = subprocess.run(["git", "log", "--oneline"], cwd=box,
                             capture_output=True, text=True).stdout
        assert log.count("\n") == 1
    finally:
        ab_lib.cleanup(box, keep=False)


def test_make_sandbox_temp_location_not_cwd(tmp_path: Path, monkeypatch) -> None:
    """Sandbox must be under tempfile.mkdtemp, never the current working dir."""
    monkeypatch.chdir(tmp_path)
    box = ab_lib.make_sandbox("test-")
    try:
        assert tmp_path not in box.parents and box != tmp_path
    finally:
        ab_lib.cleanup(box, keep=False)


def test_seed_preset_writes_prd_and_stub_ralph() -> None:
    box = ab_lib.make_sandbox("test-")
    try:
        ab_lib.seed_preset(box, "seed-prd-with-2-stories")
        prd = box / "prd.json"
        assert prd.exists()
        data = json.loads(prd.read_text(encoding="utf-8"))
        ids = [s["id"] for s in data["userStories"]]
        assert ids == ["US-PRESET-1", "US-PRESET-2"]
        assert (box / ".ralph" / "ralph.sh").exists()
        assert (box / ".ralph" / "prompt.md").exists()
        assert (box / ".ralph" / "progress.txt").exists()
    finally:
        ab_lib.cleanup(box, keep=False)


def test_snapshot_files_captures_everything_under_root() -> None:
    box = ab_lib.make_sandbox("test-")
    try:
        (box / "a.txt").write_bytes(b"hello")
        (box / "sub").mkdir()
        (box / "sub" / "b.txt").write_bytes(b"world")
        snap = ab_lib.snapshot_files(box)
        assert "a.txt" in snap
        assert snap["a.txt"] == b"hello"
        assert "sub/b.txt" in snap or "sub\\b.txt" in snap
        assert not any(k.startswith(".git/") or k.startswith(".git\\") for k in snap)
    finally:
        ab_lib.cleanup(box, keep=False)


def test_hash_tree_detects_drift(tmp_path: Path) -> None:
    """hash_tree returns a stable sha256 over (relative path, content) pairs;
    any byte change in any file must alter the hash."""
    a = tmp_path / "a"; a.mkdir()
    (a / "x.txt").write_bytes(b"abc")
    (a / "y.txt").write_bytes(b"def")
    h1 = ab_lib.hash_tree(a)
    b = tmp_path / "b"; b.mkdir()
    (b / "x.txt").write_bytes(b"abc")
    (b / "y.txt").write_bytes(b"def")
    h2 = ab_lib.hash_tree(b)
    assert h1 == h2
    (b / "y.txt").write_bytes(b"def!")
    h3 = ab_lib.hash_tree(b)
    assert h1 != h3
