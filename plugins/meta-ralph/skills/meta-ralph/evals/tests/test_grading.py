"""Tests for the four grading checks: structure / amend / negative / behaviour.
This file initially covers only the structure grader; later tasks add the rest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALS_DIR = HERE.parent
if str(EVALS_DIR) not in sys.path:
    sys.path.insert(0, str(EVALS_DIR))

import ab_grading  # type: ignore  # noqa: E402


def _make_valid_scaffold(root: Path) -> None:
    """Write a minimal-but-valid scaffold layout the structure check accepts."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "prd.json").write_text(json.dumps({
        "project": "x",
        "branchName": "x",
        "description": "x" * 10,
        "runner": {"command": "claude", "args": ["-p", "{PROMPT}"]},
        "userStories": [
            {"id": "US-001", "title": "t", "description": "d",
             "acceptanceCriteria": ["ok"], "priority": 1, "status": "todo"},
            {"id": "US-002", "title": "t2", "description": "d",
             "acceptanceCriteria": ["ok"], "priority": 2, "status": "todo"},
            {"id": "US-003", "title": "t3", "description": "d",
             "acceptanceCriteria": ["ok"], "priority": 3, "status": "todo"},
        ],
    }, indent=2), encoding="utf-8")
    (root / ".ralph").mkdir(exist_ok=True)
    (root / ".ralph" / "ralph.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (root / ".ralph" / "prompt.md").write_text("# stub\n", encoding="utf-8")
    (root / ".ralph" / "RUNBOOK.md").write_text("# runbook\n", encoding="utf-8")
    (root / ".ralph" / "progress.txt").write_text("## Codebase Patterns\n", encoding="utf-8")
    (root / ".gitignore").write_text(".ralph/.lock\n", encoding="utf-8")


_FIXTURE_BOOT_SH = {
    "expected": {
        "files_required": ["prd.json", ".ralph/ralph.sh", ".ralph/prompt.md",
                           ".ralph/RUNBOOK.md", ".ralph/progress.txt", ".gitignore"],
        "prd_constraints": {
            "runner_command_contains": "claude",
            "min_user_stories": 3,
            "max_user_stories": 8,
            "runtime": "sh",
        },
    }
}


def test_structure_check_passes_valid_scaffold(tmp_path: Path) -> None:
    _make_valid_scaffold(tmp_path)
    result = ab_grading.structure_check(tmp_path, _FIXTURE_BOOT_SH)
    assert all(e["passed"] for e in result), [e for e in result if not e["passed"]]


def test_structure_check_fails_missing_file(tmp_path: Path) -> None:
    _make_valid_scaffold(tmp_path)
    (tmp_path / ".ralph" / "RUNBOOK.md").unlink()
    result = ab_grading.structure_check(tmp_path, _FIXTURE_BOOT_SH)
    failed = [e for e in result if not e["passed"]]
    assert any("RUNBOOK.md" in e["text"] for e in failed)


def test_structure_check_fails_wrong_runner(tmp_path: Path) -> None:
    _make_valid_scaffold(tmp_path)
    prd = json.loads((tmp_path / "prd.json").read_text(encoding="utf-8"))
    prd["runner"]["command"] = "gemini"
    (tmp_path / "prd.json").write_text(json.dumps(prd, indent=2), encoding="utf-8")
    result = ab_grading.structure_check(tmp_path, _FIXTURE_BOOT_SH)
    failed = [e for e in result if not e["passed"]]
    assert any("runner" in e["text"].lower() for e in failed)


def test_structure_check_story_count_bounds(tmp_path: Path) -> None:
    _make_valid_scaffold(tmp_path)
    prd = json.loads((tmp_path / "prd.json").read_text(encoding="utf-8"))
    prd["userStories"] = prd["userStories"][:1]
    (tmp_path / "prd.json").write_text(json.dumps(prd, indent=2), encoding="utf-8")
    result = ab_grading.structure_check(tmp_path, _FIXTURE_BOOT_SH)
    failed = [e for e in result if not e["passed"]]
    assert any("user_stories" in e["text"].lower() or "stories" in e["text"].lower()
               for e in failed)


def _make_story(sid: str, priority: int, status: str = "todo") -> dict[str, Any]:
    return {
        "id": sid, "title": f"t-{sid}", "description": f"d-{sid}",
        "acceptanceCriteria": ["ok"], "priority": priority, "status": status,
    }


def test_amend_check_passes_when_forbidden_files_unchanged(tmp_path: Path) -> None:
    """Amend check compares pre-snapshot vs post-snapshot; forbidden files
    must be byte-identical."""
    pre_prd = {"userStories": [_make_story("US-PRESET-1", 1),
                               _make_story("US-PRESET-2", 2)]}
    post_prd = {"userStories": [_make_story("US-PRESET-1", 1),
                                _make_story("US-PRESET-2", 2),
                                _make_story("US-003", 3),
                                _make_story("US-004", 4)]}
    pre = {
        ".ralph/ralph.sh": b"#!/bin/sh\nORIGINAL\n",
        ".ralph/prompt.md": b"original prompt\n",
        ".ralph/RUNBOOK.md": b"original runbook\n",
        ".ralph/progress.txt": b"## Codebase Patterns\n",
        ".gitignore": b".ralph/.lock\n",
        "prd.json": json.dumps(pre_prd).encode("utf-8"),
    }
    post_root = tmp_path / "post"
    post_root.mkdir()
    for rel, content in pre.items():
        p = post_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    (post_root / "prd.json").write_bytes(json.dumps(post_prd).encode("utf-8"))
    fixture = {"expected": {
        "files_forbidden_to_change": [".ralph/ralph.sh", ".ralph/prompt.md",
                                      ".ralph/RUNBOOK.md", ".ralph/progress.txt",
                                      ".gitignore"],
        "prd_constraints": {"min_user_stories": 4, "max_user_stories": 4,
                            "preserves_initial_story_ids": True},
    }}
    result = ab_grading.amend_check(post_root, pre, fixture)
    assert all(e["passed"] for e in result), [e for e in result if not e["passed"]]


def test_amend_check_fails_when_forbidden_file_mutated(tmp_path: Path) -> None:
    pre = {".ralph/ralph.sh": b"ORIGINAL\n"}
    post_root = tmp_path / "post"
    post_root.mkdir()
    (post_root / ".ralph").mkdir()
    (post_root / ".ralph" / "ralph.sh").write_bytes(b"MUTATED\n")
    (post_root / "prd.json").write_bytes(b'{"userStories":[]}')
    fixture = {"expected": {
        "files_forbidden_to_change": [".ralph/ralph.sh"],
        "prd_constraints": {"min_user_stories": 0, "max_user_stories": 0,
                            "preserves_initial_story_ids": False},
    }}
    result = ab_grading.amend_check(post_root, pre, fixture)
    failed = [e for e in result if not e["passed"]]
    assert any("ralph.sh" in e["text"] for e in failed)


def test_amend_check_fails_when_preset_story_id_dropped(tmp_path: Path) -> None:
    pre_prd = {"userStories": [_make_story("US-PRESET-1", 1),
                               _make_story("US-PRESET-2", 2)]}
    post_prd = {"userStories": [_make_story("US-PRESET-1", 1),
                                _make_story("US-NEW", 3)]}
    pre = {"prd.json": json.dumps(pre_prd).encode("utf-8")}
    post_root = tmp_path / "post"
    post_root.mkdir()
    (post_root / "prd.json").write_bytes(json.dumps(post_prd).encode("utf-8"))
    fixture = {"expected": {
        "files_forbidden_to_change": [],
        "prd_constraints": {"min_user_stories": 2, "max_user_stories": 2,
                            "preserves_initial_story_ids": True},
    }}
    result = ab_grading.amend_check(post_root, pre, fixture)
    failed = [e for e in result if not e["passed"]]
    assert any("US-PRESET-2" in (e["evidence"] + e["text"]) for e in failed)


def test_amend_check_fails_when_priority_not_appended(tmp_path: Path) -> None:
    """SPEC §11.1: new priority must be strictly > all pre priorities."""
    pre_prd = {"userStories": [_make_story("US-PRESET-1", 5),
                               _make_story("US-PRESET-2", 6)]}
    post_prd = {"userStories": [_make_story("US-PRESET-1", 5),
                                _make_story("US-PRESET-2", 6),
                                _make_story("US-003", 1)]}  # priority 1 < 6 — violates append-to-tail
    pre = {"prd.json": json.dumps(pre_prd).encode("utf-8")}
    post_root = tmp_path / "post"; post_root.mkdir()
    (post_root / "prd.json").write_bytes(json.dumps(post_prd).encode("utf-8"))
    fixture = {"expected": {"files_forbidden_to_change": [],
                            "prd_constraints": {"min_user_stories": 3, "max_user_stories": 3,
                                                "preserves_initial_story_ids": True}}}
    result = ab_grading.amend_check(post_root, pre, fixture)
    failed = [e for e in result if not e["passed"]]
    assert any("append-to-tail" in e["text"] for e in failed)


def test_amend_check_fails_when_existing_story_mutated(tmp_path: Path) -> None:
    """SPEC §11.1: existing stories must deep-equal pre-amend snapshot."""
    pre_prd = {"userStories": [_make_story("US-PRESET-1", 1),
                               _make_story("US-PRESET-2", 2)]}
    mutated = _make_story("US-PRESET-1", 1)
    mutated["title"] = "MUTATED"  # changed an existing story
    post_prd = {"userStories": [mutated,
                                _make_story("US-PRESET-2", 2),
                                _make_story("US-003", 3)]}
    pre = {"prd.json": json.dumps(pre_prd).encode("utf-8")}
    post_root = tmp_path / "post"; post_root.mkdir()
    (post_root / "prd.json").write_bytes(json.dumps(post_prd).encode("utf-8"))
    fixture = {"expected": {"files_forbidden_to_change": [],
                            "prd_constraints": {"min_user_stories": 3, "max_user_stories": 3,
                                                "preserves_initial_story_ids": True}}}
    result = ab_grading.amend_check(post_root, pre, fixture)
    failed = [e for e in result if not e["passed"]]
    assert any("deep-equal" in e["text"] for e in failed)


def test_amend_check_fails_when_new_story_id_format_invalid(tmp_path: Path) -> None:
    """SPEC §11.1: new story id must match ^US-\\d{3,}$."""
    pre_prd = {"userStories": [_make_story("US-PRESET-1", 1)]}
    bad = _make_story("FEATURE-X", 2)
    post_prd = {"userStories": [_make_story("US-PRESET-1", 1), bad]}
    pre = {"prd.json": json.dumps(pre_prd).encode("utf-8")}
    post_root = tmp_path / "post"; post_root.mkdir()
    (post_root / "prd.json").write_bytes(json.dumps(post_prd).encode("utf-8"))
    fixture = {"expected": {"files_forbidden_to_change": [],
                            "prd_constraints": {"min_user_stories": 2, "max_user_stories": 2,
                                                "preserves_initial_story_ids": True}}}
    result = ab_grading.amend_check(post_root, pre, fixture)
    failed = [e for e in result if not e["passed"]]
    assert any("id matches" in e["text"] for e in failed)


def test_negative_check_passes_when_scaffold_empty(tmp_path: Path) -> None:
    result = ab_grading.negative_check(tmp_path)
    assert all(e["passed"] for e in result)


def test_negative_check_fails_when_any_file_appeared(tmp_path: Path) -> None:
    (tmp_path / "prd.json").write_bytes(b'{}')
    result = ab_grading.negative_check(tmp_path)
    failed = [e for e in result if not e["passed"]]
    assert any("prd.json" in (e["evidence"] + e["text"]) for e in failed)


def test_behaviour_check_passes_when_driver_eval_all_green(tmp_path: Path) -> None:
    """behaviour_check shells out to run_evals.py --driver-from <scaffold>.
    For this test, copy A's real driver into the scaffold and confirm 12/12 green."""
    import shutil
    eval_dir = Path(__file__).resolve().parent.parent
    a_template = eval_dir.parent / "templates" / "ralph" / "ralph.sh.tpl"
    scaffold = tmp_path / "scaffold"
    (scaffold / ".ralph").mkdir(parents=True)
    shutil.copy(a_template, scaffold / ".ralph" / "ralph.sh")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    result = ab_grading.behaviour_check(scaffold, run_dir, runtime="sh")
    failed = [e for e in result if not e["passed"]]
    assert not failed, failed


def test_behaviour_check_fails_on_broken_driver(tmp_path: Path) -> None:
    scaffold = tmp_path / "scaffold"
    (scaffold / ".ralph").mkdir(parents=True)
    (scaffold / ".ralph" / "ralph.sh").write_text(
        "#!/bin/sh\nexit 1\n", encoding="utf-8"
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    result = ab_grading.behaviour_check(scaffold, run_dir, runtime="sh")
    failed = [e for e in result if not e["passed"]]
    assert failed
