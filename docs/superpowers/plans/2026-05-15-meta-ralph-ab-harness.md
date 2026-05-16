# meta-ralph A/B harness — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the sidecar A/B test harness for the `meta-ralph` SKILL so iteration 0 (with a stub B = copy of A) can be run end-to-end without LLM calls and iteration 1 (with a real B from `/write-a-skill`) produces a benchmark report and verdict.

**Architecture:** Sidecar Python harness `ab_harness.py` parallel to the existing `run_evals.py`. Variant B is a second plugin (`plugins/meta-ralph-b/`) with copied assets. Each fixture run launches `claude --plugin-dir <variant>` non-interactively, sentinel-watches the sandbox for scaffold completion, then grades against structure / amend / negative / behaviour expectations. Shared eval suite (`run_evals.py`) gets two new flags (`--driver-from`, `--output-dir`) — no other change to A.

**Tech Stack:** Python 3.11+, stdlib only (subprocess, threading, pathlib, json, hashlib, tempfile, shutil); pytest for tests; bash + jq + bun + python in `PATH` (for the runtime drivers); claude CLI ≥ 2.1 (for `--plugin-dir`).

**Decisions on Open Questions (from spec §"Open questions"):**

1. **js fixture** — swap `boot-ts-copilot-zh` → `boot-js-copilot-zh`. Matrix stays at 6 fixtures, runtime coverage broadens to {sh, js, py}; ts is covered transitively by driver-eval (shared templates mean A/B can't differ on driver template).
2. **rep_seed_suffix** — drop entirely. Reps run the identical prompt; variance comes from LLM stochasticity. Removes the leakage risk that copilot flagged.
3. **Asset parity** — recursive copy at branch init + sha256 hash-tree check on harness startup. No symlinks (Windows portability), no auto-correction.
4. **Token/cost metrics** — keep as observability in the report; never disqualify on cost.
5. **ab-results commit policy** — gitignore `ab-results/` entirely. Verdict copy-pasted into PR description for the final iteration.

---

## File structure

**New files** (all created by this plan):

```
plugins/meta-ralph-b/                              # sibling plugin
  .claude-plugin/plugin.json                       # name = "meta-ralph-b", same skill name "meta-ralph"
  skills/meta-ralph/
    SKILL.md                                       # stub initially (copy of A); replaced via /write-a-skill in iteration 1
    templates/                                     # recursive copy of A's templates
    scripts/                                       # recursive copy of A's scripts
    reference/                                     # recursive copy of A's reference

plugins/meta-ralph/skills/meta-ralph/evals/
  ab_lib.py                                        # sandbox utilities + asset-hash check
  ab_fixtures.json                                 # 6 fixture definitions
  ab_harness.py                                    # main A/B driver
  ab_presets/
    seed-prd-with-2-stories.json                   # preset PRD for amend fixtures
  tests/
    __init__.py
    test_ab_lib.py
    test_ab_fixtures_schema.py
    test_run_evals_patch.py
    test_grading.py
    test_report.py
```

**Modified files:**

- `plugins/meta-ralph/skills/meta-ralph/evals/run_evals.py` — +2 CLI flags (`--driver-from`, `--output-dir`). All other behaviour unchanged.
- `.gitignore` (repo root) — add `plugins/meta-ralph/skills/meta-ralph/evals/ab-results/`.

**Untouched (per spec constraints):**

- `plugins/meta-ralph/skills/meta-ralph/SKILL.md`
- `plugins/meta-ralph/skills/meta-ralph/SPEC.md`
- `plugins/meta-ralph/skills/meta-ralph/templates/**`
- `plugins/meta-ralph/skills/meta-ralph/scripts/**`
- `plugins/meta-ralph/skills/meta-ralph/reference/**`
- `plugins/meta-ralph/skills/meta-ralph/evals/evals.json`
- `plugins/meta-ralph/skills/meta-ralph/evals/mock-agent.py`

---

## Task 1: Gitignore + tests directory bootstrap

**Files:**
- Modify: `.gitignore` (repo root)
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/tests/__init__.py`
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/ab_presets/.gitkeep`

- [ ] **Step 1: Add ab-results to .gitignore**

Append to `.gitignore`:

```
# meta-ralph A/B harness output (regenerable per iteration)
plugins/meta-ralph/skills/meta-ralph/evals/ab-results/
```

- [ ] **Step 2: Create empty tests package**

Create `plugins/meta-ralph/skills/meta-ralph/evals/tests/__init__.py` as an empty file.

- [ ] **Step 3: Create ab_presets directory placeholder**

Create `plugins/meta-ralph/skills/meta-ralph/evals/ab_presets/.gitkeep` as an empty file (so the directory tracks before any preset lives there).

- [ ] **Step 4: Verify pytest can discover the tests directory**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/ --collect-only -q`
Expected: `no tests ran in 0.0Xs` (collection succeeds, just nothing yet).

- [ ] **Step 5: Commit**

```bash
git add .gitignore plugins/meta-ralph/skills/meta-ralph/evals/tests/__init__.py plugins/meta-ralph/skills/meta-ralph/evals/ab_presets/.gitkeep
git commit -m "chore(meta-ralph): scaffold ab-harness directories + gitignore output"
```

---

## Task 2: Patch run_evals.py — +2 flags (TDD)

**Files:**
- Modify: `plugins/meta-ralph/skills/meta-ralph/evals/run_evals.py`
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_run_evals_patch.py`

- [ ] **Step 1: Write failing test for --driver-from flag**

Create `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_run_evals_patch.py`:

```python
"""Verify run_evals.py accepts and honors --driver-from / --output-dir, and that
omitting both leaves behaviour identical to before the patch."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALS_DIR = HERE.parent
RUN_EVALS = EVALS_DIR / "run_evals.py"
TEMPLATES_DIR = EVALS_DIR.parent / "templates" / "ralph"


def test_help_lists_new_flags():
    """--help must mention both new flags."""
    result = subprocess.run(
        [sys.executable, str(RUN_EVALS), "--help"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    assert "--driver-from" in result.stdout
    assert "--output-dir" in result.stdout


def test_driver_from_reads_external_driver(tmp_path: Path):
    """When --driver-from <path> is set, run_evals copies <path>/.ralph/ralph.sh
    instead of templates/ralph/ralph.sh.tpl."""
    external = tmp_path / "ext"
    (external / ".ralph").mkdir(parents=True)
    # Copy A's real driver as the "external" driver so 12/12 still pass
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


def test_driver_from_missing_path_aborts(tmp_path: Path):
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


def test_no_flags_writes_to_default_location(tmp_path: Path, monkeypatch):
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
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_run_evals_patch.py -v`
Expected: `test_help_lists_new_flags` FAILS (flag not in help yet).

- [ ] **Step 3: Patch run_evals.py argparse**

In `plugins/meta-ralph/skills/meta-ralph/evals/run_evals.py`, locate the existing argparse block (around the existing `--runtime` / `--scenario` / `--keep-sandbox` / `--iteration` definitions in `main()`) and add immediately after the existing flags:

```python
    parser.add_argument(
        "--driver-from",
        type=Path,
        default=None,
        help="If set, copy the driver from <path>/.ralph/ralph.<ext> instead of templates/. "
             "Used by ab_harness.py to evaluate agent-produced drivers.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="If set, write results here instead of evals/results/iteration-<N>/. "
             "Required when run_evals.py is invoked re-entrantly by ab_harness.py "
             "to avoid clobbering across runs.",
    )
```

- [ ] **Step 4: Honor --driver-from in setup_sandbox**

In `setup_sandbox()` find the block that reads the driver template:

```python
    # Copy driver template, ensure LF endings, drop the .tpl suffix
    ext = runtime
    src = TEMPLATES_DIR / f"ralph.{ext}.tpl"
    dst = ralph_dir / f"ralph.{ext}"
```

Replace with a conditional that accepts an explicit override path (threaded through from main as a module-level `_DRIVER_OVERRIDE: Path | None`):

```python
    # Copy driver — either from the standard template, or from --driver-from override
    ext = runtime
    if _DRIVER_OVERRIDE is not None:
        src = _DRIVER_OVERRIDE / ".ralph" / f"ralph.{ext}"
        if not src.exists():
            raise FileNotFoundError(
                f"--driver-from path missing expected driver: {src}"
            )
    else:
        src = TEMPLATES_DIR / f"ralph.{ext}.tpl"
    dst = ralph_dir / f"ralph.{ext}"
```

At module scope add:

```python
_DRIVER_OVERRIDE: Path | None = None
```

In `main()` after `args = parser.parse_args()`:

```python
    global _DRIVER_OVERRIDE
    _DRIVER_OVERRIDE = args.driver_from
```

- [ ] **Step 5: Honor --output-dir in main**

In `main()` locate:

```python
    out_dir = RESULTS_ROOT / f"iteration-{args.iteration}"
    out_dir.mkdir(parents=True, exist_ok=True)
```

Replace with:

```python
    if args.output_dir is not None:
        out_dir = args.output_dir
    else:
        out_dir = RESULTS_ROOT / f"iteration-{args.iteration}"
    out_dir.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 6: Run all three new tests — expect green**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_run_evals_patch.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 7: Re-run the full existing driver eval suite to prove no regression**

Run: `python plugins/meta-ralph/skills/meta-ralph/evals/run_evals.py`
Expected: `Total: 48 runs, 48 pass, 0 fail` (same as before the patch).

- [ ] **Step 8: Commit**

```bash
git add plugins/meta-ralph/skills/meta-ralph/evals/run_evals.py plugins/meta-ralph/skills/meta-ralph/evals/tests/test_run_evals_patch.py
git commit -m "feat(meta-ralph/evals): run_evals.py +2 flags for harness re-entry (--driver-from, --output-dir)"
```

---

## Task 3: Build ab_lib.py (TDD)

**Files:**
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/ab_lib.py`
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_ab_lib.py`

- [ ] **Step 1: Write failing tests for ab_lib utilities**

Create `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_ab_lib.py`:

```python
"""Tests for ab_lib.py — sandbox utilities and asset-tree hashing."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from .. import ab_lib  # type: ignore  # tests run from evals/ dir


def test_make_sandbox_initializes_git_repo(tmp_path: Path):
    box = ab_lib.make_sandbox("test-")
    try:
        assert box.exists()
        assert (box / ".git").is_dir()
        # autocrlf must be false
        cfg = subprocess.run(["git", "config", "core.autocrlf"], cwd=box,
                             capture_output=True, text=True).stdout.strip()
        assert cfg == "false"
        # one initial empty commit so working tree is clean
        log = subprocess.run(["git", "log", "--oneline"], cwd=box,
                             capture_output=True, text=True).stdout
        assert log.count("\n") == 1
    finally:
        ab_lib.cleanup(box, keep=False)


def test_make_sandbox_temp_location_not_cwd(tmp_path: Path, monkeypatch):
    """Sandbox must be under tempfile.mkdtemp, never the current working dir."""
    monkeypatch.chdir(tmp_path)
    box = ab_lib.make_sandbox("test-")
    try:
        # box must not be a descendant of cwd
        assert tmp_path not in box.parents and box != tmp_path
    finally:
        ab_lib.cleanup(box, keep=False)


def test_seed_preset_writes_prd_and_stub_ralph(tmp_path: Path):
    box = ab_lib.make_sandbox("test-")
    try:
        ab_lib.seed_preset(box, "seed-prd-with-2-stories")
        prd = box / "prd.json"
        assert prd.exists()
        import json
        data = json.loads(prd.read_text(encoding="utf-8"))
        ids = [s["id"] for s in data["userStories"]]
        assert ids == ["US-PRESET-1", "US-PRESET-2"]
        # .ralph/ stub files must also exist so amend mode doesn't bootstrap
        assert (box / ".ralph" / "ralph.sh").exists()
        assert (box / ".ralph" / "prompt.md").exists()
        assert (box / ".ralph" / "progress.txt").exists()
    finally:
        ab_lib.cleanup(box, keep=False)


def test_snapshot_files_captures_everything_under_root(tmp_path: Path):
    box = ab_lib.make_sandbox("test-")
    try:
        (box / "a.txt").write_bytes(b"hello")
        (box / "sub").mkdir()
        (box / "sub" / "b.txt").write_bytes(b"world")
        snap = ab_lib.snapshot_files(box)
        assert "a.txt" in snap
        assert snap["a.txt"] == b"hello"
        assert "sub/b.txt" in snap or "sub\\b.txt" in snap
        # .git internal files must NOT be in the snapshot
        assert not any(k.startswith(".git/") or k.startswith(".git\\") for k in snap)
    finally:
        ab_lib.cleanup(box, keep=False)


def test_hash_tree_detects_drift(tmp_path: Path):
    """hash_tree returns a stable sha256 over (relative path, content) pairs;
    any byte change in any file must alter the hash."""
    a = tmp_path / "a"; a.mkdir()
    (a / "x.txt").write_bytes(b"abc")
    (a / "y.txt").write_bytes(b"def")
    h1 = ab_lib.hash_tree(a)
    # identical content → identical hash
    b = tmp_path / "b"; b.mkdir()
    (b / "x.txt").write_bytes(b"abc")
    (b / "y.txt").write_bytes(b"def")
    h2 = ab_lib.hash_tree(b)
    assert h1 == h2
    # any change drifts the hash
    (b / "y.txt").write_bytes(b"def!")
    h3 = ab_lib.hash_tree(b)
    assert h1 != h3
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_ab_lib.py -v`
Expected: import error for `ab_lib` (module doesn't exist yet).

- [ ] **Step 3: Implement ab_lib.py**

Create `plugins/meta-ralph/skills/meta-ralph/evals/ab_lib.py`:

```python
"""Sandbox + filesystem utilities used only by ab_harness.py.

Intentionally separate from run_evals.py so the existing driver eval suite
stays untouched. Duplication is small (~30 lines of sandbox plumbing) and
intentional.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRESETS_DIR = HERE / "ab_presets"
TEMPLATES_DIR = HERE.parent / "templates"


def make_sandbox(prefix: str) -> Path:
    """Temp dir + git init -b main + empty initial commit + core.autocrlf=false."""
    box = Path(tempfile.mkdtemp(prefix=prefix))
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    _run(["git", "init", "-q", "-b", "main"], cwd=box, env=env)
    _run(["git", "config", "user.email", "abharness@local"], cwd=box)
    _run(["git", "config", "user.name", "ab-harness"], cwd=box)
    _run(["git", "config", "core.autocrlf", "false"], cwd=box)
    _run(["git", "commit", "--allow-empty", "-q", "-m", "init"], cwd=box, env=env)
    return box


def seed_preset(sandbox: Path, preset_name: str) -> None:
    """Drop a preset prd.json + stub .ralph/ into the sandbox so amend fixtures
    see a real-looking existing scaffold."""
    preset_path = PRESETS_DIR / f"{preset_name}.json"
    if not preset_path.exists():
        raise FileNotFoundError(f"preset not found: {preset_path}")
    # prd.json
    (sandbox / "prd.json").write_bytes(preset_path.read_bytes())
    # Stub .ralph/ — use real templates so the SKILL's drift check is satisfied
    ralph_dir = sandbox / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    # Driver: copy the sh template (preset is sh-runtime; amend fixtures don't
    # care which driver is present, only that one is).
    src_driver = TEMPLATES_DIR / "ralph" / "ralph.sh.tpl"
    dst_driver = ralph_dir / "ralph.sh"
    dst_driver.write_bytes(src_driver.read_bytes().replace(b"\r\n", b"\n"))
    os.chmod(dst_driver, 0o755)
    # progress.txt sentinel header
    (ralph_dir / "progress.txt").write_bytes(b"## Codebase Patterns\n")
    # RUNBOOK from template
    runbook_src = TEMPLATES_DIR / "RUNBOOK.md.tpl"
    if runbook_src.exists():
        (ralph_dir / "RUNBOOK.md").write_bytes(
            runbook_src.read_bytes().replace(b"\r\n", b"\n")
        )
    # prompt.md — minimal but >14 bytes so SKILL's amendFeasible() detects an agent
    (ralph_dir / "prompt.md").write_bytes(
        b"# Ralph Agent Instructions\n\nFollow CLAUDE.md.\n"
    )
    # .gitignore matching scaffold layout
    (sandbox / ".gitignore").write_bytes(
        b".ralph/progress.txt\n.ralph/.lock\n.ralph/.complete\n"
        b".ralph/.commit-failure\n.ralph/.stop\n"
    )
    # Commit the seed so the SKILL's working-tree-clean check passes
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    _run(["git", "add", "-A"], cwd=sandbox, env=env)
    _run(["git", "commit", "-q", "-m", "seed: ab-harness preset"], cwd=sandbox, env=env)


def snapshot_files(root: Path) -> dict[str, bytes]:
    """Recursively capture all files under `root` (excluding .git internals).
    Keys are POSIX-style relative paths so cross-platform comparisons work.
    Values are raw bytes."""
    out: dict[str, bytes] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".git/") or rel == ".git":
            continue
        out[rel] = path.read_bytes()
    return out


def hash_tree(root: Path) -> str:
    """SHA-256 over a sorted list of (relpath, content-sha256) pairs.
    Used by the harness to check B's templates/scripts/reference match A's."""
    items: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        items.append((rel, digest))
    h = hashlib.sha256()
    for rel, digest in items:
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(digest.encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def cleanup(sandbox: Path, keep: bool) -> None:
    if keep or not sandbox.exists():
        return
    shutil.rmtree(sandbox, ignore_errors=True)


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    """Run a subprocess and raise on non-zero. stdout/stderr swallowed."""
    res = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                         encoding="utf-8")
    if res.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(cmd)} (rc={res.returncode})\n"
            f"stderr: {res.stderr}"
        )
```

- [ ] **Step 4: Run tests again — expect green**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_ab_lib.py -v`
Expected: 4 PASS. The `test_seed_preset_writes_prd_and_stub_ralph` test will fail because the preset file doesn't exist yet — that's expected, it gets created in Task 5.

- [ ] **Step 5: Commit**

```bash
git add plugins/meta-ralph/skills/meta-ralph/evals/ab_lib.py plugins/meta-ralph/skills/meta-ralph/evals/tests/test_ab_lib.py
git commit -m "feat(meta-ralph/evals): ab_lib.py — sandbox / preset / snapshot / hash_tree utils"
```

---

## Task 4: Create amend preset

**Files:**
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/ab_presets/seed-prd-with-2-stories.json`

- [ ] **Step 1: Write the preset PRD**

Create `plugins/meta-ralph/skills/meta-ralph/evals/ab_presets/seed-prd-with-2-stories.json`:

```json
{
  "project": "demo-app",
  "branchName": "ralph/demo",
  "description": "A simple demo todo list app — preset for ab-harness amend fixtures.",
  "runner": {
    "command": "claude",
    "args": ["-p", "{PROMPT}", "--dangerously-skip-permissions"]
  },
  "userStories": [
    {
      "id": "US-PRESET-1",
      "title": "List todos on home screen",
      "description": "Render existing todos when the user opens the app.",
      "acceptanceCriteria": [
        "Todos render from local storage on load",
        "Empty list shows a placeholder message"
      ],
      "priority": 1,
      "status": "todo",
      "notes": ""
    },
    {
      "id": "US-PRESET-2",
      "title": "Add new todo",
      "description": "Allow the user to add a new todo to the list.",
      "acceptanceCriteria": [
        "Pressing Enter on the input appends a new todo",
        "Empty/whitespace-only input is rejected"
      ],
      "priority": 2,
      "status": "todo",
      "notes": ""
    }
  ]
}
```

- [ ] **Step 2: Validate the preset against the existing schema**

Run:

```bash
python -c "import json, jsonschema; \
  schema = json.load(open('plugins/meta-ralph/skills/meta-ralph/templates/prd.schema.json',encoding='utf-8')); \
  data = json.load(open('plugins/meta-ralph/skills/meta-ralph/evals/ab_presets/seed-prd-with-2-stories.json',encoding='utf-8')); \
  jsonschema.validate(data, schema); print('preset validates against prd.schema.json')"
```

Expected: `preset validates against prd.schema.json`. If jsonschema is missing, `pip install jsonschema` first.

Note: the existing schema uses `^US-\d{3,}$` for `id`. `US-PRESET-1` does NOT match. The amend spike confirmed the agent proceeds anyway when told to skip confirmations. **We accept this drift in the preset on purpose** — it's a known mismatch we want the SKILL to handle gracefully (and an earlier ab-harness commit will tighten that handling if needed). Document this in the next step.

- [ ] **Step 3: Re-run ab_lib seed-preset test to confirm green**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_ab_lib.py::test_seed_preset_writes_prd_and_stub_ralph -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add plugins/meta-ralph/skills/meta-ralph/evals/ab_presets/seed-prd-with-2-stories.json
git commit -m "feat(meta-ralph/evals): seed-prd-with-2-stories preset for amend fixtures"
```

---

## Task 5: Write ab_fixtures.json + schema test

**Files:**
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/ab_fixtures.json`
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_ab_fixtures_schema.py`

- [ ] **Step 1: Write the fixtures file**

Create `plugins/meta-ralph/skills/meta-ralph/evals/ab_fixtures.json` (note: `boot-ts-copilot-zh` is replaced by `boot-js-copilot-zh` per the open-question resolution; no `rep_seed_suffix` — reps differ via LLM stochasticity only):

```json
{
  "version": 1,
  "reps_per_fixture": 3,
  "fixtures": [
    {
      "id": "boot-sh-claude-en",
      "kind": "bootstrap",
      "prompt": "set up ralph for a TodoMVC app using claude with the sh runtime. Proceed without asking confirmation questions; use the choices stated in this prompt and reasonable defaults for anything else.",
      "wall_timeout_s": 180,
      "expected": {
        "should_trigger_skill": true,
        "files_required": ["prd.json", ".ralph/ralph.sh", ".ralph/prompt.md", ".ralph/RUNBOOK.md", ".ralph/progress.txt", ".gitignore"],
        "prd_constraints": {
          "runner_command_contains": "claude",
          "min_user_stories": 3,
          "max_user_stories": 8,
          "runtime": "sh"
        },
        "driver_eval_required": true,
        "amend_mode": false
      }
    },
    {
      "id": "boot-js-copilot-zh",
      "kind": "bootstrap",
      "prompt": "幫我初始化 ralph，agent 用 copilot，runtime 用 js，專案是一個 Markdown 編輯器。請直接完成、不要問確認問題；prompt 沒講到的細節用合理預設值。",
      "wall_timeout_s": 180,
      "expected": {
        "should_trigger_skill": true,
        "files_required": ["prd.json", ".ralph/ralph.js", ".ralph/prompt.md", ".ralph/RUNBOOK.md", ".ralph/progress.txt", ".gitignore", ".ralph/package.json"],
        "prd_constraints": {
          "runner_command_contains": "copilot",
          "min_user_stories": 3,
          "max_user_stories": 8,
          "runtime": "js"
        },
        "driver_eval_required": true,
        "amend_mode": false
      }
    },
    {
      "id": "amend-en",
      "kind": "amend",
      "prompt": "append two stories to the existing ralph prd: dark mode toggle, keyboard shortcuts. Proceed without asking confirmation questions.",
      "wall_timeout_s": 90,
      "preset": "seed-prd-with-2-stories",
      "expected": {
        "should_trigger_skill": true,
        "files_required": ["prd.json"],
        "files_forbidden_to_change": [".ralph/ralph.sh", ".ralph/prompt.md", ".ralph/RUNBOOK.md", ".ralph/progress.txt", ".gitignore"],
        "prd_constraints": {
          "min_user_stories": 4,
          "max_user_stories": 4,
          "preserves_initial_story_ids": true
        },
        "driver_eval_required": false,
        "amend_mode": true
      }
    },
    {
      "id": "amend-zh",
      "kind": "amend",
      "prompt": "在 ralph prd 新增一個 story：支援 PWA 離線快取。請直接完成、不要問確認問題。",
      "wall_timeout_s": 90,
      "preset": "seed-prd-with-2-stories",
      "expected": {
        "should_trigger_skill": true,
        "files_required": ["prd.json"],
        "files_forbidden_to_change": [".ralph/ralph.sh", ".ralph/prompt.md", ".ralph/RUNBOOK.md", ".ralph/progress.txt", ".gitignore"],
        "prd_constraints": {
          "min_user_stories": 3,
          "max_user_stories": 3,
          "preserves_initial_story_ids": true
        },
        "driver_eval_required": false,
        "amend_mode": true
      }
    },
    {
      "id": "neg-explain",
      "kind": "negative",
      "prompt": "what is ralph and how does meta-ralph work? just explain, don't scaffold",
      "wall_timeout_s": 60,
      "expected": {
        "should_trigger_skill": false,
        "files_required": [],
        "scaffold_must_be_empty": true,
        "driver_eval_required": false,
        "amend_mode": false
      }
    },
    {
      "id": "edge-runner-conflict",
      "kind": "edge",
      "prompt": "set up ralph with gemini agent for a CLI tool, runtime python, but ALSO add user story for an HTTP API. Proceed without asking confirmation questions.",
      "wall_timeout_s": 180,
      "expected": {
        "should_trigger_skill": true,
        "files_required": ["prd.json", ".ralph/ralph.py", ".ralph/prompt.md", ".ralph/RUNBOOK.md", ".ralph/progress.txt", ".gitignore"],
        "prd_constraints": {
          "runner_command_contains": "gemini",
          "min_user_stories": 1,
          "max_user_stories": 8,
          "runtime": "py"
        },
        "driver_eval_required": true,
        "amend_mode": false
      }
    }
  ]
}
```

- [ ] **Step 2: Write fixture-schema test**

Create `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_ab_fixtures_schema.py`:

```python
"""Lightweight invariants on ab_fixtures.json. Catches accidental edits that
would silently break the harness — wrong runtime, missing keys, duplicates."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent / "ab_fixtures.json"

VALID_RUNTIMES = {"sh", "ts", "js", "py"}
VALID_KINDS = {"bootstrap", "amend", "negative", "edge"}


@pytest.fixture(scope="module")
def fixtures_doc() -> dict:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def test_top_level_shape(fixtures_doc):
    assert fixtures_doc["version"] == 1
    assert isinstance(fixtures_doc["reps_per_fixture"], int)
    assert fixtures_doc["reps_per_fixture"] >= 1
    assert isinstance(fixtures_doc["fixtures"], list)
    assert len(fixtures_doc["fixtures"]) == 6


def test_fixture_ids_unique(fixtures_doc):
    ids = [f["id"] for f in fixtures_doc["fixtures"]]
    assert len(ids) == len(set(ids))


def test_each_fixture_has_required_fields(fixtures_doc):
    required = {"id", "kind", "prompt", "wall_timeout_s", "expected"}
    for f in fixtures_doc["fixtures"]:
        missing = required - set(f.keys())
        assert not missing, f"fixture {f.get('id')} missing keys: {missing}"
        assert f["kind"] in VALID_KINDS, f"bad kind: {f['kind']}"


def test_bootstrap_fixtures_specify_runtime(fixtures_doc):
    for f in fixtures_doc["fixtures"]:
        if f["kind"] in {"bootstrap", "edge"}:
            assert f["expected"]["driver_eval_required"] is True
            rt = f["expected"]["prd_constraints"]["runtime"]
            assert rt in VALID_RUNTIMES, f"{f['id']}: bad runtime {rt}"


def test_amend_fixtures_preset_exists(fixtures_doc):
    presets_dir = HERE.parent / "ab_presets"
    for f in fixtures_doc["fixtures"]:
        if f["kind"] == "amend":
            preset = f.get("preset")
            assert preset, f"{f['id']} missing preset"
            assert (presets_dir / f"{preset}.json").exists()


def test_negative_fixture_invariants(fixtures_doc):
    negs = [f for f in fixtures_doc["fixtures"] if f["kind"] == "negative"]
    assert len(negs) == 1, "exactly one negative fixture expected"
    f = negs[0]
    assert f["expected"]["should_trigger_skill"] is False
    assert f["expected"]["files_required"] == []
    assert f["expected"]["scaffold_must_be_empty"] is True


def test_runtime_coverage_includes_js_after_swap(fixtures_doc):
    """js fixture must exist after the open-question (1) swap."""
    runtimes_in_bootstrap = {
        f["expected"]["prd_constraints"]["runtime"]
        for f in fixtures_doc["fixtures"]
        if f["kind"] in {"bootstrap", "edge"}
    }
    assert "js" in runtimes_in_bootstrap
```

- [ ] **Step 3: Run schema tests — expect green**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_ab_fixtures_schema.py -v`
Expected: 7 PASS.

- [ ] **Step 4: Commit**

```bash
git add plugins/meta-ralph/skills/meta-ralph/evals/ab_fixtures.json plugins/meta-ralph/skills/meta-ralph/evals/tests/test_ab_fixtures_schema.py
git commit -m "feat(meta-ralph/evals): ab_fixtures.json — 6 A/B fixtures (boot/amend/neg/edge) + js coverage"
```

---

## Task 6: Scaffold variant B as sibling plugin (stub = copy of A)

**Files:**
- Create: `plugins/meta-ralph-b/.claude-plugin/plugin.json`
- Create: `plugins/meta-ralph-b/skills/meta-ralph/SKILL.md` (stub = byte copy of A's SKILL.md)
- Create: `plugins/meta-ralph-b/skills/meta-ralph/templates/**` (recursive copy of A's templates)
- Create: `plugins/meta-ralph-b/skills/meta-ralph/scripts/**` (recursive copy of A's scripts)
- Create: `plugins/meta-ralph-b/skills/meta-ralph/reference/**` (recursive copy of A's reference)

- [ ] **Step 1: Create plugin manifest for B**

Create `plugins/meta-ralph-b/.claude-plugin/plugin.json`:

```json
{
  "name": "meta-ralph-b",
  "version": "0.1.0",
  "description": "Variant B of meta-ralph — used by ab-harness to A/B test SKILL.md simplifications. Same skill (name: meta-ralph) as plugins/meta-ralph; only SKILL.md differs.",
  "author": {
    "name": "Madao",
    "email": "gn00678465@gmail.com"
  },
  "license": "MIT",
  "keywords": ["ab-test", "meta-ralph", "experiment"]
}
```

- [ ] **Step 2: Copy A's skill tree into B (stub)**

Run (PowerShell or bash — pick the one that exists on your system):

```bash
# bash variant
SRC="D:/Skills/meta-skills/plugins/meta-ralph/skills/meta-ralph"
DST="D:/Skills/meta-skills/plugins/meta-ralph-b/skills/meta-ralph"
mkdir -p "$DST"
cp "$SRC/SKILL.md" "$DST/SKILL.md"
cp -r "$SRC/templates" "$DST/templates"
cp -r "$SRC/scripts"   "$DST/scripts"
cp -r "$SRC/reference" "$DST/reference"
```

- [ ] **Step 3: Verify B's SKILL.md frontmatter still says name: meta-ralph**

Run: `python -c "import re; t=open('plugins/meta-ralph-b/skills/meta-ralph/SKILL.md',encoding='utf-8').read(); print('name match:', re.search(r'^name: meta-ralph$', t, re.M) is not None)"`
Expected: `name match: True`.

The shared skill name is what lets the trigger phrases route to whichever plugin is loaded via `--plugin-dir`.

- [ ] **Step 4: Hash-check A's and B's shared assets are byte-identical**

Run:

```bash
python -c "
import sys; sys.path.insert(0, 'plugins/meta-ralph/skills/meta-ralph/evals')
import ab_lib
from pathlib import Path
A = Path('plugins/meta-ralph/skills/meta-ralph')
B = Path('plugins/meta-ralph-b/skills/meta-ralph')
for sub in ['templates', 'scripts', 'reference']:
    ha = ab_lib.hash_tree(A/sub)
    hb = ab_lib.hash_tree(B/sub)
    print(f'{sub}: A={ha[:12]} B={hb[:12]} match={ha == hb}')
"
```

Expected: three lines each showing `match=True`. Any `match=False` means the copy missed something — re-run step 2.

- [ ] **Step 5: Smoke-test B plugin loads via claude CLI**

Run:

```bash
SANDBOX=$(mktemp -d -t ralph-b-smoke-XXXXXX)
cd "$SANDBOX"
git init -q -b main
git config user.email smoke@local && git config user.name smoke
git config core.autocrlf false
git commit --allow-empty -q -m init

claude --plugin-dir "D:/Skills/meta-skills/plugins/meta-ralph-b" \
       --add-dir . \
       --allowedTools "Skill Read Write Edit Bash" \
       --disallowedTools "WebFetch WebSearch" \
       --output-format json \
       -p 'do not scaffold anything. just list the skills you see and exit. Proceed without confirmations.' \
       > stdout.json 2>&1
python -c "import json; d=json.load(open('stdout.json',encoding='utf-8')); print('result:', d.get('result','')[:300])"
cd .. && rm -rf "$SANDBOX"
```

Expected output: result text mentions `meta-ralph` skill is available. (If this hangs or errors, the plugin manifest is malformed.)

- [ ] **Step 6: Commit**

```bash
git add plugins/meta-ralph-b/
git commit -m "feat(meta-ralph-b): scaffold sibling plugin with copy-of-A as stub SKILL.md"
```

---

## Task 7: ab_harness.py CLI skeleton + --dry-run mode

**Files:**
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py`
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_harness_cli.py`

- [ ] **Step 1: Write a failing CLI test**

Create `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_harness_cli.py`:

```python
"""CLI surface and --dry-run behaviour for ab_harness.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent / "ab_harness.py"


def test_help_lists_all_flags():
    result = subprocess.run(
        [sys.executable, str(HARNESS), "--help"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    for flag in ["--variant", "--fixture", "--reps", "--iteration", "--dry-run", "--keep-sandbox"]:
        assert flag in result.stdout, f"missing flag in --help: {flag}"


def test_dry_run_produces_report(tmp_path: Path):
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
```

- [ ] **Step 2: Run — expect import/file-not-found failure**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_harness_cli.py -v`
Expected: FAIL (`ab_harness.py` doesn't exist yet).

- [ ] **Step 3: Implement the minimum ab_harness.py to satisfy the CLI test**

Create `plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py`:

```python
#!/usr/bin/env python3
"""ab_harness.py — A/B test driver for meta-ralph SKILL variants.

Companion to run_evals.py (driver eval suite). This harness compares variant A
(plugins/meta-ralph/) against variant B (plugins/meta-ralph-b/) across a
fixture set defined in ab_fixtures.json.

Phase 1 of the implementation plan: CLI surface + --dry-run. LLM invocation,
grading, and report rendering land in later tasks.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES_PATH = HERE / "ab_fixtures.json"
DEFAULT_OUTPUT_ROOT = HERE / "ab-results"

VARIANT_PATHS = {
    "A": HERE.parent.parent.parent / "meta-ralph",
    "B": HERE.parent.parent.parent / "meta-ralph-b",
}


@dataclass
class HarnessArgs:
    variants: list[str]
    fixture_ids: list[str] | None
    reps: int | None
    iteration: int
    dry_run: bool
    keep_sandbox: bool
    output_root: Path


def parse_args(argv: list[str] | None = None) -> HarnessArgs:
    p = argparse.ArgumentParser(
        prog="ab_harness.py",
        description="A/B test harness for meta-ralph SKILL variants",
    )
    p.add_argument("--variant", default="A,B",
                   help="Comma-separated variants to run (default: A,B)")
    p.add_argument("--fixture", default="",
                   help="Comma-separated fixture ids (default: all)")
    p.add_argument("--reps", type=int, default=None,
                   help="Override reps_per_fixture (default: from ab_fixtures.json)")
    p.add_argument("--iteration", type=int, default=1,
                   help="Output directory suffix")
    p.add_argument("--dry-run", action="store_true",
                   help="Skip LLM invocation; emit a placeholder report")
    p.add_argument("--keep-sandbox", action="store_true",
                   help="Do not delete sandboxes after each run")
    p.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT,
                   help="Where to write ab-results/iteration-N/ (default: alongside harness)")
    a = p.parse_args(argv)
    return HarnessArgs(
        variants=[v.strip() for v in a.variant.split(",") if v.strip()],
        fixture_ids=[f.strip() for f in a.fixture.split(",") if f.strip()] or None,
        reps=a.reps,
        iteration=a.iteration,
        dry_run=a.dry_run,
        keep_sandbox=a.keep_sandbox,
        output_root=a.output_root,
    )


def load_fixtures(path: Path = FIXTURES_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def select_fixtures(doc: dict, ids: list[str] | None) -> list[dict]:
    if not ids:
        return doc["fixtures"]
    by_id = {f["id"]: f for f in doc["fixtures"]}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"Unknown fixture(s): {missing}. "
                         f"Known: {list(by_id.keys())}")
    return [by_id[i] for i in ids]


def write_dry_run_report(args: HarnessArgs, fixtures: list[dict], reps: int) -> Path:
    iter_dir = args.output_root / f"iteration-{args.iteration}"
    iter_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    summary = {
        "dry_run": True,
        "iteration": args.iteration,
        "started_at": now,
        "variants": args.variants,
        "fixtures": [f["id"] for f in fixtures],
        "reps": reps,
        "verdict": "skipped (dry-run)",
    }
    (iter_dir / "ab-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (iter_dir / "ab-benchmark.md").write_text(
        f"# meta-ralph A/B test — iteration {args.iteration} (dry run)\n\n"
        f"Variants: {', '.join(args.variants)}\n\n"
        f"Fixtures: {', '.join(f['id'] for f in fixtures)}\n\n"
        f"Reps/fixture: {reps}\n\n"
        f"**Verdict: skipped (dry-run)**\n",
        encoding="utf-8",
    )
    return iter_dir


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    doc = load_fixtures()
    fixtures = select_fixtures(doc, args.fixture_ids)
    reps = args.reps if args.reps is not None else doc["reps_per_fixture"]
    if args.dry_run:
        iter_dir = write_dry_run_report(args, fixtures, reps)
        print(f"[dry-run] report written: {iter_dir}")
        return 0
    # Real-run path lands in Task 11 (agent invocation).
    print("[error] real-run mode not yet implemented (see Task 11+ in the plan).",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the CLI tests — expect green**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_harness_cli.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py plugins/meta-ralph/skills/meta-ralph/evals/tests/test_harness_cli.py
git commit -m "feat(meta-ralph/evals): ab_harness.py — CLI skeleton + --dry-run report"
```

---

## Task 8: Pre-flight environment check

**Files:**
- Modify: `plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py`
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_preflight.py`

- [ ] **Step 1: Write failing test**

Create `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_preflight.py`:

```python
"""Pre-flight validates the harness's required external tools and asset parity."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS_DIR = HERE.parent
sys.path.insert(0, str(HARNESS_DIR))

import ab_harness  # noqa: E402


def test_preflight_returns_status_dict():
    """preflight() returns a dict {tool: ok_bool, ...} and an aggregate 'ok'."""
    status = ab_harness.preflight()
    assert isinstance(status, dict)
    assert "ok" in status
    assert isinstance(status["ok"], bool)
    # Tools required by the spec
    for tool in ("claude", "git", "python"):
        assert tool in status, f"preflight missing tool: {tool}"


def test_preflight_detects_missing_tool(monkeypatch):
    """If shutil.which returns None for a required tool, status reports ok=False."""
    import shutil as sh
    real_which = sh.which
    def fake_which(name):
        return None if name == "git" else real_which(name)
    monkeypatch.setattr(ab_harness.shutil, "which", fake_which)
    status = ab_harness.preflight()
    assert status["git"] is False
    assert status["ok"] is False


def test_preflight_asset_parity_check():
    """preflight verifies hash_tree(A/templates) == hash_tree(B/templates) etc."""
    status = ab_harness.preflight()
    assert "asset_parity" in status
    # In the stub-B world this should be True; once /write-a-skill runs only
    # SKILL.md changes — templates/scripts/reference must still match.
    assert status["asset_parity"] is True
```

- [ ] **Step 2: Run — expect AttributeError (no preflight yet)**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_preflight.py -v`
Expected: FAIL with `AttributeError: module 'ab_harness' has no attribute 'preflight'`.

- [ ] **Step 3: Implement preflight in ab_harness.py**

At the top of `ab_harness.py` add:

```python
import shutil
import subprocess
```

(if not already present).

Add the helper above `main()`:

```python
def preflight() -> dict:
    """Verify external tools and A/B asset parity before any runs.

    Returns a status dict with one entry per required tool plus 'asset_parity'
    and an aggregate 'ok' boolean. The harness aborts the iteration if 'ok'
    is False.
    """
    required = ("claude", "git", "python", "bash", "jq", "bun", "node")
    status: dict = {}
    for tool in required:
        status[tool] = shutil.which(tool) is not None
    # Asset parity: B's templates / scripts / reference must hash-match A's
    import ab_lib  # local import to avoid circular at module load
    a = VARIANT_PATHS["A"] / "skills" / "meta-ralph"
    b = VARIANT_PATHS["B"] / "skills" / "meta-ralph"
    parity = True
    for sub in ("templates", "scripts", "reference"):
        if not (a / sub).exists() or not (b / sub).exists():
            parity = False
            break
        if ab_lib.hash_tree(a / sub) != ab_lib.hash_tree(b / sub):
            parity = False
            break
    status["asset_parity"] = parity
    status["ok"] = all(status.values())
    return status
```

- [ ] **Step 4: Wire preflight into main (non-dry-run only)**

In `main()`, after `args = parse_args(argv)` and before the dry-run branch, add:

```python
    if not args.dry_run:
        pf = preflight()
        if not pf["ok"]:
            print("[preflight] FAIL:", file=sys.stderr)
            for k, v in pf.items():
                if k == "ok":
                    continue
                print(f"  {k}: {v}", file=sys.stderr)
            return 3
```

(Skipping preflight in `--dry-run` lets harness-development iterations work on machines that don't have all 7 tools installed.)

- [ ] **Step 5: Run all tests — expect green**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/ -v`
Expected: all tests in `test_preflight.py` PASS; earlier tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py plugins/meta-ralph/skills/meta-ralph/evals/tests/test_preflight.py
git commit -m "feat(meta-ralph/evals): ab_harness preflight checks tools + A/B asset parity"
```

---

## Task 9: Structure grading

**Files:**
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/ab_grading.py`
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py`

- [ ] **Step 1: Write failing test for structure grader**

Create `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py`:

```python
"""Tests for the four grading checks: structure / amend / negative / behaviour.
This file initially covers only the structure grader; later tasks add the rest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import ab_grading  # type: ignore


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


def test_structure_check_passes_valid_scaffold(tmp_path: Path):
    _make_valid_scaffold(tmp_path)
    fixture = {
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
    result = ab_grading.structure_check(tmp_path, fixture)
    assert all(e["passed"] for e in result), [e for e in result if not e["passed"]]


def test_structure_check_fails_missing_file(tmp_path: Path):
    _make_valid_scaffold(tmp_path)
    (tmp_path / ".ralph" / "RUNBOOK.md").unlink()
    fixture = {
        "expected": {
            "files_required": ["prd.json", ".ralph/ralph.sh", ".ralph/prompt.md",
                                ".ralph/RUNBOOK.md", ".ralph/progress.txt", ".gitignore"],
            "prd_constraints": {"runner_command_contains": "claude",
                                 "min_user_stories": 3, "max_user_stories": 8, "runtime": "sh"},
        }
    }
    result = ab_grading.structure_check(tmp_path, fixture)
    failed = [e for e in result if not e["passed"]]
    assert any("RUNBOOK.md" in e["text"] for e in failed)


def test_structure_check_fails_wrong_runner(tmp_path: Path):
    _make_valid_scaffold(tmp_path)
    prd = json.loads((tmp_path / "prd.json").read_text(encoding="utf-8"))
    prd["runner"]["command"] = "gemini"
    (tmp_path / "prd.json").write_text(json.dumps(prd, indent=2), encoding="utf-8")
    fixture = {"expected": {
        "files_required": ["prd.json", ".ralph/ralph.sh", ".ralph/prompt.md",
                            ".ralph/RUNBOOK.md", ".ralph/progress.txt", ".gitignore"],
        "prd_constraints": {"runner_command_contains": "claude",
                             "min_user_stories": 3, "max_user_stories": 8, "runtime": "sh"},
    }}
    result = ab_grading.structure_check(tmp_path, fixture)
    failed = [e for e in result if not e["passed"]]
    assert any("runner" in e["text"].lower() for e in failed)


def test_structure_check_story_count_bounds(tmp_path: Path):
    _make_valid_scaffold(tmp_path)
    prd = json.loads((tmp_path / "prd.json").read_text(encoding="utf-8"))
    # 1 story — below min of 3
    prd["userStories"] = prd["userStories"][:1]
    (tmp_path / "prd.json").write_text(json.dumps(prd, indent=2), encoding="utf-8")
    fixture = {"expected": {
        "files_required": ["prd.json", ".ralph/ralph.sh", ".ralph/prompt.md",
                            ".ralph/RUNBOOK.md", ".ralph/progress.txt", ".gitignore"],
        "prd_constraints": {"runner_command_contains": "claude",
                             "min_user_stories": 3, "max_user_stories": 8, "runtime": "sh"},
    }}
    result = ab_grading.structure_check(tmp_path, fixture)
    failed = [e for e in result if not e["passed"]]
    assert any("user_stories" in e["text"].lower() or "stories" in e["text"].lower()
                for e in failed)
```

- [ ] **Step 2: Run — expect ImportError**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ab_grading'`.

- [ ] **Step 3: Implement ab_grading.structure_check**

Create `plugins/meta-ralph/skills/meta-ralph/evals/ab_grading.py`:

```python
"""Grading checks for ab_harness.

Each check returns a list of expectation records:
    [{"text": str, "passed": bool, "evidence": str}, ...]

The list is the skill-creator grading.json schema. ab_harness aggregates these
across the four checks (structure / amend / negative / behaviour) into one
grading.json per run.
"""
from __future__ import annotations

import json
from pathlib import Path


Expectation = dict[str, str | bool]

_RUNTIME_TO_DRIVER = {"sh": "ralph.sh", "ts": "ralph.ts", "js": "ralph.js", "py": "ralph.py"}


def structure_check(scaffold: Path, fixture: dict) -> list[Expectation]:
    """Validate prd.json schema + required files + prd_constraints."""
    out: list[Expectation] = []
    exp = fixture["expected"]

    # 1. prd.json must exist + parse
    prd_path = scaffold / "prd.json"
    if not prd_path.exists():
        out.append({"text": "prd.json exists", "passed": False,
                     "evidence": "missing"})
        return out
    try:
        prd = json.loads(prd_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        out.append({"text": "prd.json parses as JSON", "passed": False,
                     "evidence": str(e)[:200]})
        return out
    out.append({"text": "prd.json exists and parses", "passed": True, "evidence": ""})

    # 2. Required keys present
    required_top = ("project", "branchName", "description", "runner", "userStories")
    for k in required_top:
        ok = k in prd
        out.append({
            "text": f"prd.json has '{k}'",
            "passed": ok,
            "evidence": "" if ok else f"keys: {sorted(prd.keys())}",
        })

    # 3. files_required all present
    for rel in exp.get("files_required", []):
        ok = (scaffold / rel).exists()
        out.append({
            "text": f"file exists: {rel}",
            "passed": ok,
            "evidence": "" if ok else "missing",
        })

    # 4. prd_constraints
    pc = exp.get("prd_constraints", {})
    if "runner_command_contains" in pc:
        cmd = prd.get("runner", {}).get("command", "")
        ok = pc["runner_command_contains"] in cmd
        out.append({
            "text": f"runner.command contains '{pc['runner_command_contains']}'",
            "passed": ok,
            "evidence": f"got: {cmd!r}" if not ok else "",
        })
    if "min_user_stories" in pc or "max_user_stories" in pc:
        n = len(prd.get("userStories", []))
        lo = pc.get("min_user_stories", 0)
        hi = pc.get("max_user_stories", 10**9)
        ok = lo <= n <= hi
        out.append({
            "text": f"user_stories count in [{lo}, {hi}]",
            "passed": ok,
            "evidence": f"count={n}" if not ok else "",
        })
    if "runtime" in pc:
        rt = pc["runtime"]
        driver = _RUNTIME_TO_DRIVER.get(rt)
        ok = driver is not None and (scaffold / ".ralph" / driver).exists()
        out.append({
            "text": f"driver for runtime '{rt}' is present",
            "passed": ok,
            "evidence": f"expected .ralph/{driver}" if not ok else "",
        })

    return out
```

- [ ] **Step 4: Run grading tests — expect green**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/meta-ralph/skills/meta-ralph/evals/ab_grading.py plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py
git commit -m "feat(meta-ralph/evals): ab_grading.structure_check — schema + files + constraints"
```

---

## Task 10: Amend + negative grading

**Files:**
- Modify: `plugins/meta-ralph/skills/meta-ralph/evals/ab_grading.py`
- Modify: `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py`

- [ ] **Step 1: Append failing tests for amend + negative checks**

Append to `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py`:

```python
def test_amend_check_passes_when_forbidden_files_unchanged(tmp_path: Path):
    """Amend check compares pre-snapshot vs post-snapshot; forbidden files
    must be byte-identical."""
    pre = {
        ".ralph/ralph.sh": b"#!/bin/sh\nORIGINAL\n",
        ".ralph/prompt.md": b"original prompt\n",
        ".ralph/RUNBOOK.md": b"original runbook\n",
        ".ralph/progress.txt": b"## Codebase Patterns\n",
        ".gitignore": b".ralph/.lock\n",
        "prd.json": b'{"userStories":[{"id":"US-PRESET-1"},{"id":"US-PRESET-2"}]}',
    }
    post_root = tmp_path / "post"
    post_root.mkdir()
    for rel, content in pre.items():
        p = post_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    # Simulate amend: 4 stories now, presets preserved
    (post_root / "prd.json").write_bytes(
        b'{"userStories":[{"id":"US-PRESET-1"},{"id":"US-PRESET-2"},'
        b'{"id":"US-003"},{"id":"US-004"}]}'
    )
    fixture = {"expected": {
        "files_forbidden_to_change": [".ralph/ralph.sh", ".ralph/prompt.md",
                                       ".ralph/RUNBOOK.md", ".ralph/progress.txt",
                                       ".gitignore"],
        "prd_constraints": {"min_user_stories": 4, "max_user_stories": 4,
                            "preserves_initial_story_ids": True},
    }}
    result = ab_grading.amend_check(post_root, pre, fixture)
    assert all(e["passed"] for e in result), [e for e in result if not e["passed"]]


def test_amend_check_fails_when_forbidden_file_mutated(tmp_path: Path):
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


def test_amend_check_fails_when_preset_story_id_dropped(tmp_path: Path):
    pre = {"prd.json": b'{"userStories":[{"id":"US-PRESET-1"},{"id":"US-PRESET-2"}]}'}
    post_root = tmp_path / "post"
    post_root.mkdir()
    (post_root / "prd.json").write_bytes(
        b'{"userStories":[{"id":"US-PRESET-1"},{"id":"US-NEW"}]}'
    )
    fixture = {"expected": {
        "files_forbidden_to_change": [],
        "prd_constraints": {"min_user_stories": 2, "max_user_stories": 2,
                            "preserves_initial_story_ids": True},
    }}
    result = ab_grading.amend_check(post_root, pre, fixture)
    failed = [e for e in result if not e["passed"]]
    assert any("US-PRESET-2" in (e["evidence"] + e["text"]) for e in failed)


def test_negative_check_passes_when_scaffold_empty(tmp_path: Path):
    # tmp_path has no files
    result = ab_grading.negative_check(tmp_path)
    assert all(e["passed"] for e in result)


def test_negative_check_fails_when_any_file_appeared(tmp_path: Path):
    (tmp_path / "prd.json").write_bytes(b'{}')
    result = ab_grading.negative_check(tmp_path)
    failed = [e for e in result if not e["passed"]]
    assert any("prd.json" in (e["evidence"] + e["text"]) for e in failed)
```

- [ ] **Step 2: Run — expect AttributeError on amend_check / negative_check**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py -v`
Expected: 4 new tests FAIL with AttributeError; structure tests still PASS.

- [ ] **Step 3: Implement amend_check and negative_check in ab_grading.py**

Append to `plugins/meta-ralph/skills/meta-ralph/evals/ab_grading.py`:

```python
def amend_check(scaffold: Path,
                 pre_snapshot: dict[str, bytes],
                 fixture: dict) -> list[Expectation]:
    """Verify amend invariants:
      - files in expected.files_forbidden_to_change are byte-identical pre vs post
      - presets ids US-PRESET-N still appear in post prd.json (if requested)
    """
    out: list[Expectation] = []
    exp = fixture["expected"]
    # Forbidden-files invariant
    for rel in exp.get("files_forbidden_to_change", []):
        post_path = scaffold / rel
        pre_bytes = pre_snapshot.get(rel)
        post_bytes = post_path.read_bytes() if post_path.exists() else None
        ok = pre_bytes is not None and pre_bytes == post_bytes
        out.append({
            "text": f"forbidden-to-change file unchanged: {rel}",
            "passed": ok,
            "evidence": "" if ok else f"pre={pre_bytes!r:.80} post={post_bytes!r:.80}",
        })
    # Initial story-id preservation
    pc = exp.get("prd_constraints", {})
    if pc.get("preserves_initial_story_ids"):
        pre_prd_bytes = pre_snapshot.get("prd.json")
        if pre_prd_bytes is None:
            out.append({"text": "preset prd.json was present pre-run",
                         "passed": False, "evidence": "missing"})
            return out
        try:
            pre_prd = json.loads(pre_prd_bytes.decode("utf-8"))
            post_prd = json.loads((scaffold / "prd.json").read_text(encoding="utf-8"))
        except Exception as e:
            out.append({"text": "pre + post prd.json both parse",
                         "passed": False, "evidence": str(e)[:200]})
            return out
        initial_ids = {s["id"] for s in pre_prd.get("userStories", [])}
        post_ids = {s["id"] for s in post_prd.get("userStories", [])}
        for sid in sorted(initial_ids):
            present = sid in post_ids
            out.append({
                "text": f"initial story id preserved: {sid}",
                "passed": present,
                "evidence": "" if present else f"post ids: {sorted(post_ids)}",
            })
    return out


def negative_check(scaffold: Path) -> list[Expectation]:
    """Verify the agent created no files in the sandbox (negative fixture)."""
    out: list[Expectation] = []
    extra_files = [p for p in scaffold.rglob("*")
                    if p.is_file() and not p.relative_to(scaffold).as_posix().startswith(".git")]
    ok = not extra_files
    out.append({
        "text": "scaffold remained empty (no files written by agent)",
        "passed": ok,
        "evidence": "" if ok else f"unexpected files: {[p.relative_to(scaffold).as_posix() for p in extra_files][:10]}",
    })
    return out
```

- [ ] **Step 4: Run all grading tests — expect green**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py -v`
Expected: all tests PASS (≥ 9 total).

- [ ] **Step 5: Commit**

```bash
git add plugins/meta-ralph/skills/meta-ralph/evals/ab_grading.py plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py
git commit -m "feat(meta-ralph/evals): ab_grading.amend_check + negative_check"
```

---

## Task 11: Behaviour grading (nested run_evals.py invocation)

**Files:**
- Modify: `plugins/meta-ralph/skills/meta-ralph/evals/ab_grading.py`
- Modify: `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py`

- [ ] **Step 1: Append failing test for behaviour grader**

Append to `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py`:

```python
def test_behaviour_check_passes_when_driver_eval_all_green(tmp_path: Path):
    """behaviour_check shells out to run_evals.py --driver-from <scaffold> --output-dir <run_dir>/driver-eval/.
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


def test_behaviour_check_fails_on_broken_driver(tmp_path: Path):
    scaffold = tmp_path / "scaffold"
    (scaffold / ".ralph").mkdir(parents=True)
    (scaffold / ".ralph" / "ralph.sh").write_text(
        "#!/bin/sh\nexit 1\n", encoding="utf-8"
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    result = ab_grading.behaviour_check(scaffold, run_dir, runtime="sh")
    failed = [e for e in result if not e["passed"]]
    assert failed  # at least one driver-eval scenario must report not-green
```

- [ ] **Step 2: Run — expect AttributeError**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py -v`
Expected: 2 new tests FAIL.

- [ ] **Step 3: Implement behaviour_check**

Append to `plugins/meta-ralph/skills/meta-ralph/evals/ab_grading.py`:

```python
import subprocess
import sys

_HERE = Path(__file__).resolve().parent
_RUN_EVALS = _HERE / "run_evals.py"


def behaviour_check(scaffold: Path, run_dir: Path, runtime: str) -> list[Expectation]:
    """Invoke run_evals.py --driver-from <scaffold> --output-dir <run_dir>/driver-eval/
    and return one expectation per driver eval scenario."""
    driver_eval = run_dir / "driver-eval"
    driver_eval.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        [sys.executable, str(_RUN_EVALS),
         "--driver-from", str(scaffold),
         "--output-dir", str(driver_eval),
         "--runtime", runtime],
        capture_output=True, text=True, encoding="utf-8",
    )
    results_path = driver_eval / "results.json"
    if not results_path.exists():
        return [{"text": "run_evals.py produced results.json",
                  "passed": False,
                  "evidence": f"rc={res.returncode} stderr={res.stderr[:300]}"}]
    summary = json.loads(results_path.read_text(encoding="utf-8"))
    out: list[Expectation] = []
    for run in summary.get("runs", []):
        out.append({
            "text": f"driver-eval scenario '{run['scenario']}' on {run['runtime']}",
            "passed": bool(run["passed"]),
            "evidence": "" if run["passed"] else f"rc={run['returncode']} error={run.get('error','')}",
        })
    return out
```

- [ ] **Step 4: Run all grading tests — expect green**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py -v`
Expected: all tests PASS (≥ 11 total). `test_behaviour_check_passes_when_driver_eval_all_green` may take ~20-40 s as it runs the full 12-scenario `sh` driver eval. That's normal.

- [ ] **Step 5: Commit**

```bash
git add plugins/meta-ralph/skills/meta-ralph/evals/ab_grading.py plugins/meta-ralph/skills/meta-ralph/evals/tests/test_grading.py
git commit -m "feat(meta-ralph/evals): ab_grading.behaviour_check — nested run_evals.py invocation"
```

---

## Task 12: Agent invocation + sentinel-completion watcher

**Files:**
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/ab_invoke.py`
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_invoke.py`

- [ ] **Step 1: Write failing test (mocked claude CLI)**

Create `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_invoke.py`:

```python
"""Test the sentinel watcher logic without spawning real claude.

We replace the claude invocation with a python subprocess that drops files into
the sandbox on a timer, so we can validate the sentinel triggers SIGTERM at the
right moment.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import ab_invoke  # type: ignore


def _write_fake_agent(script_path: Path, sandbox: Path, delay_s: float = 0.5,
                       linger_s: float = 30.0) -> None:
    """Write a python script that simulates claude: writes prd.json + .ralph/ralph.sh
    after `delay_s`, then sleeps for `linger_s` (to test the SIGTERM path)."""
    script_path.write_text(textwrap.dedent(f"""
        import json, os, time, sys
        from pathlib import Path
        sandbox = Path(r'{sandbox}')
        time.sleep({delay_s})
        (sandbox / "prd.json").write_text(json.dumps({{
            "project":"x","branchName":"x","description":"x",
            "runner":{{"command":"claude","args":[]}},
            "userStories":[{{"id":"US-001","title":"t","description":"d",
                              "acceptanceCriteria":["a"],"priority":1,"status":"todo"}}]
        }}), encoding="utf-8")
        (sandbox / ".ralph").mkdir(exist_ok=True)
        (sandbox / ".ralph" / "ralph.sh").write_text("#!/bin/sh\\n", encoding="utf-8")
        # linger so the sentinel must SIGTERM
        time.sleep({linger_s})
        print('{{"result":"ok"}}')
    """).strip(), encoding="utf-8")


def test_sentinel_terminates_when_scaffold_complete(tmp_path: Path):
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    fake_agent = tmp_path / "fake_agent.py"
    _write_fake_agent(fake_agent, sandbox, delay_s=0.3, linger_s=15.0)
    cmd = [sys.executable, str(fake_agent)]
    # bootstrap-style fixture (needs both prd.json + .ralph/ralph.sh)
    result = ab_invoke.run_agent(
        cmd=cmd, sandbox=sandbox,
        wall_timeout_s=20,
        amend_mode=False, runtime="sh",
    )
    # The fake agent lingers 15s; sentinel should kill it within ~2-3s of completion.
    assert result.exit_reason in ("sentinel", "exited"), result.exit_reason
    assert result.wall_s < 8.0, f"sentinel did not fire quickly: {result.wall_s}s"
    assert (sandbox / "prd.json").exists()


def test_wall_timeout_kicks_in_when_sentinel_never_fires(tmp_path: Path):
    """Agent never writes the scaffold — wall_timeout_s must fire."""
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    fake_agent = tmp_path / "fake_agent.py"
    fake_agent.write_text(
        "import time, sys\\ntime.sleep(20)\\n",
        encoding="utf-8",
    )
    cmd = [sys.executable, str(fake_agent)]
    result = ab_invoke.run_agent(
        cmd=cmd, sandbox=sandbox,
        wall_timeout_s=2,
        amend_mode=False, runtime="sh",
    )
    assert result.exit_reason == "wall_timeout"
    assert result.wall_s >= 2.0
```

- [ ] **Step 2: Run — expect ImportError**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_invoke.py -v`
Expected: FAIL — `ab_invoke` doesn't exist.

- [ ] **Step 3: Implement ab_invoke.run_agent with the sentinel watcher**

Create `plugins/meta-ralph/skills/meta-ralph/evals/ab_invoke.py`:

```python
"""Spawn the agent subprocess and watch for scaffold completion.

Two completion paths:
  1. Sentinel — sandbox poll-checks every 1 s; once prd.json + driver-file
     (or just prd.json in amend mode) are on disk and prd.json parses, SIGTERM.
  2. Wall-clock — fallback if sentinel never fires.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path


_RUNTIME_TO_DRIVER = {"sh": "ralph.sh", "ts": "ralph.ts", "js": "ralph.js", "py": "ralph.py"}


@dataclass
class AgentRunResult:
    exit_code: int
    stdout: str
    stderr: str
    wall_s: float
    exit_reason: str  # "sentinel" | "wall_timeout" | "exited"
    sentinel_fired_at: float | None


def _scaffold_complete(sandbox: Path, amend_mode: bool, runtime: str) -> bool:
    """Return True once prd.json exists, parses as JSON, and (if bootstrap) the
    runtime driver file is also on disk."""
    prd = sandbox / "prd.json"
    if not prd.exists():
        return False
    try:
        json.loads(prd.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if amend_mode:
        return True
    driver = _RUNTIME_TO_DRIVER.get(runtime)
    return driver is not None and (sandbox / ".ralph" / driver).exists()


def run_agent(cmd: list[str], sandbox: Path, wall_timeout_s: float,
               amend_mode: bool, runtime: str,
               poll_interval_s: float = 1.0) -> AgentRunResult:
    """Spawn `cmd` with cwd=sandbox; watch for scaffold completion or timeout."""
    started = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=str(sandbox),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )
    sentinel_fired_at: float | None = None
    stop_event = threading.Event()

    def watcher() -> None:
        nonlocal sentinel_fired_at
        while not stop_event.is_set():
            if proc.poll() is not None:
                return  # subprocess already exited
            if _scaffold_complete(sandbox, amend_mode, runtime):
                sentinel_fired_at = time.monotonic() - started
                # Try graceful SIGTERM first
                try:
                    if os.name == "nt":
                        proc.terminate()  # CTRL_BREAK_EVENT not available without process group
                    else:
                        proc.terminate()
                except ProcessLookupError:
                    pass
                return
            time.sleep(poll_interval_s)

    t = threading.Thread(target=watcher, daemon=True)
    t.start()

    try:
        out, err = proc.communicate(timeout=wall_timeout_s)
        stop_event.set()
        wall_s = time.monotonic() - started
        if sentinel_fired_at is not None:
            # Process exited because watcher SIGTERMed it
            return AgentRunResult(
                exit_code=proc.returncode, stdout=out or "", stderr=err or "",
                wall_s=wall_s, exit_reason="sentinel",
                sentinel_fired_at=sentinel_fired_at,
            )
        return AgentRunResult(
            exit_code=proc.returncode, stdout=out or "", stderr=err or "",
            wall_s=wall_s, exit_reason="exited", sentinel_fired_at=None,
        )
    except subprocess.TimeoutExpired:
        stop_event.set()
        proc.kill()
        out, err = proc.communicate()
        wall_s = time.monotonic() - started
        return AgentRunResult(
            exit_code=-1, stdout=out or "", stderr=(err or "") + "\n[wall_timeout]",
            wall_s=wall_s, exit_reason="wall_timeout", sentinel_fired_at=None,
        )
    finally:
        stop_event.set()
        if proc.poll() is None:
            proc.kill()
```

- [ ] **Step 4: Run invocation tests — expect green**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_invoke.py -v`
Expected: 2 PASS. Total wall time ~20 s.

- [ ] **Step 5: Commit**

```bash
git add plugins/meta-ralph/skills/meta-ralph/evals/ab_invoke.py plugins/meta-ralph/skills/meta-ralph/evals/tests/test_invoke.py
git commit -m "feat(meta-ralph/evals): ab_invoke.run_agent — sentinel + wall_timeout completion paths"
```

---

## Task 13: Wire harness end-to-end — real-run mode

**Files:**
- Modify: `plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py`

- [ ] **Step 1: Replace the "not yet implemented" branch with the per-run loop**

In `ab_harness.py`, replace the `if args.dry_run: ... return 0` block + the "not yet implemented" branch with:

```python
def _build_agent_cmd(variant: str, prompt: str) -> list[str]:
    plugin_dir = VARIANT_PATHS[variant]
    return [
        "claude",
        "--plugin-dir", str(plugin_dir),
        "--add-dir", ".",
        "--allowedTools", "Skill Read Write Edit Bash",
        "--disallowedTools", "WebFetch WebSearch",
        "--output-format", "json",
        "-p", prompt,
    ]


def _parse_token_usage(stdout: str) -> dict:
    """Best-effort extraction of token / cost from claude's --output-format json blob."""
    try:
        d = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return {}
    usage = d.get("usage") or {}
    return {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_cost_usd": d.get("total_cost_usd"),
        "num_turns": d.get("num_turns"),
        "duration_ms": d.get("duration_ms"),
    }


def _run_one(variant: str, fixture: dict, rep_idx: int,
              iter_dir: Path, keep_sandbox: bool) -> dict:
    """Execute one (variant, fixture, rep) cell. Returns the per-run record
    that ab-summary.json eventually consumes."""
    import ab_lib
    import ab_grading
    import ab_invoke
    fid = fixture["id"]
    run_dir = iter_dir / variant / fid / f"rep-{rep_idx}"
    run_dir.mkdir(parents=True, exist_ok=True)
    scaffold_out = run_dir / "scaffold"
    record: dict = {"variant": variant, "fixture": fid, "rep": rep_idx,
                     "expectations": []}

    sandbox = ab_lib.make_sandbox(f"ab-{variant}-{fid}-{rep_idx}-")
    try:
        # Preset, if any
        if "preset" in fixture:
            ab_lib.seed_preset(sandbox, fixture["preset"])
        pre_snapshot = ab_lib.snapshot_files(sandbox)

        cmd = _build_agent_cmd(variant, fixture["prompt"])
        amend = bool(fixture["expected"].get("amend_mode"))
        runtime = fixture["expected"].get("prd_constraints", {}).get("runtime", "sh")
        result = ab_invoke.run_agent(
            cmd=cmd, sandbox=sandbox,
            wall_timeout_s=fixture["wall_timeout_s"],
            amend_mode=amend, runtime=runtime,
        )
        record["wall_s"] = result.wall_s
        record["exit_reason"] = result.exit_reason
        record["exit_code"] = result.exit_code
        record["usage"] = _parse_token_usage(result.stdout)
        (run_dir / "stdout.txt").write_text(result.stdout, encoding="utf-8")
        (run_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")

        # Snapshot scaffold output
        scaffold_out.mkdir(exist_ok=True)
        for rel, content in ab_lib.snapshot_files(sandbox).items():
            dst = scaffold_out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(content)

        # Grade
        exps: list = []
        if fixture["kind"] == "negative":
            exps.extend(ab_grading.negative_check(sandbox))
        else:
            exps.extend(ab_grading.structure_check(sandbox, fixture))
            if amend:
                exps.extend(ab_grading.amend_check(sandbox, pre_snapshot, fixture))
            if fixture["expected"].get("driver_eval_required"):
                exps.extend(ab_grading.behaviour_check(sandbox, run_dir, runtime))
        record["expectations"] = exps
        record["passed"] = all(e["passed"] for e in exps) if exps else False
        (run_dir / "grading.json").write_text(
            json.dumps({"expectations": exps}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as e:
        record["passed"] = False
        record["error"] = f"{type(e).__name__}: {e}"
    finally:
        ab_lib.cleanup(sandbox, keep=keep_sandbox)
    return record
```

Replace the final lines of `main()`:

```python
    if args.dry_run:
        iter_dir = write_dry_run_report(args, fixtures, reps)
        print(f"[dry-run] report written: {iter_dir}")
        return 0
    print("[error] real-run mode not yet implemented (see Task 11+ in the plan).",
          file=sys.stderr)
    return 2
```

with:

```python
    if args.dry_run:
        iter_dir = write_dry_run_report(args, fixtures, reps)
        print(f"[dry-run] report written: {iter_dir}")
        return 0
    # Real-run path
    iter_dir = args.output_root / f"iteration-{args.iteration}"
    iter_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    started = datetime.now(timezone.utc).isoformat()
    for variant in args.variants:
        for fixture in fixtures:
            for rep in range(reps):
                print(f"  [{variant}] {fixture['id']} rep {rep+1}/{reps} ...",
                      end="", flush=True)
                rec = _run_one(variant, fixture, rep, iter_dir, args.keep_sandbox)
                records.append(rec)
                tag = "PASS" if rec.get("passed") else "FAIL"
                print(f" {tag} ({rec.get('wall_s', 0):.1f}s)")
    write_real_run_report(iter_dir, records, args.variants, fixtures, reps, started)
    failed = [r for r in records if not r.get("passed")]
    return 0 if not failed else 1


def write_real_run_report(iter_dir: Path, records: list[dict],
                            variants: list[str], fixtures: list[dict],
                            reps: int, started: str) -> None:
    """Stub: filled in by Task 14 (report renderer). For now write the raw record list."""
    (iter_dir / "ab-summary.json").write_text(
        json.dumps({"started_at": started, "variants": variants,
                     "fixtures": [f["id"] for f in fixtures],
                     "reps": reps, "records": records}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (iter_dir / "ab-benchmark.md").write_text(
        "# meta-ralph A/B — placeholder report (real renderer lands in Task 14)\n",
        encoding="utf-8",
    )
```

- [ ] **Step 2: Re-run all existing tests to confirm no regression**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/ -v`
Expected: all earlier tests still PASS.

- [ ] **Step 3: Commit**

```bash
git add plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py
git commit -m "feat(meta-ralph/evals): ab_harness real-run loop — sandbox/invoke/grade/snapshot"
```

---

## Task 14: Report renderer (ab-benchmark.md + ab-summary.json final form)

**Files:**
- Modify: `plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py`
- Create: `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_report.py`

- [ ] **Step 1: Write failing test for report renderer**

Create `plugins/meta-ralph/skills/meta-ralph/evals/tests/test_report.py`:

```python
"""Tests for write_real_run_report — verdict logic and report shape."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import ab_harness  # type: ignore


def _record(variant: str, fixture: str, rep: int, passed: bool, wall_s: float = 30.0,
             usage: dict | None = None) -> dict:
    return {"variant": variant, "fixture": fixture, "rep": rep,
             "passed": passed, "wall_s": wall_s, "exit_reason": "sentinel",
             "exit_code": 0, "usage": usage or {}, "expectations": []}


def test_verdict_maintains_when_b_loses_at_most_one_per_fixture(tmp_path: Path):
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


def test_verdict_regresses_when_b_loses_two_on_any_fixture(tmp_path: Path):
    fixtures = [{"id": "f1"}]
    records = (
        [_record("A", "f1", r, True) for r in range(3)] +
        [_record("B", "f1", 0, False), _record("B", "f1", 1, False), _record("B", "f1", 2, True)]
    )
    ab_harness.write_real_run_report(tmp_path, records, ["A", "B"], fixtures, 3, "now")
    summary = json.loads((tmp_path / "ab-summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] == "B regresses"


def test_verdict_inconclusive_when_fewer_than_29_runs_completed(tmp_path: Path):
    # 6 fixtures x 3 reps x 2 variants = 36; we have only 28
    fixtures = [{"id": f"f{i}"} for i in range(6)]
    records = [_record("A", "f0", 0, True)] * 28
    ab_harness.write_real_run_report(tmp_path, records, ["A", "B"], fixtures, 3, "now")
    summary = json.loads((tmp_path / "ab-summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] == "inconclusive — rerun"


def test_benchmark_md_has_pass_rate_matrix(tmp_path: Path):
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
```

- [ ] **Step 2: Run — expect verdict assertions to fail (placeholder report has no verdict)**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/test_report.py -v`
Expected: all 4 FAIL.

- [ ] **Step 3: Replace `write_real_run_report` stub with full implementation**

In `ab_harness.py`, replace `write_real_run_report` with:

```python
def _skill_md_stats(variant: str) -> dict:
    """Lines / chars / approximate token count for the variant's SKILL.md."""
    path = VARIANT_PATHS[variant] / "skills" / "meta-ralph" / "SKILL.md"
    if not path.exists():
        return {"lines": 0, "chars": 0, "approx_tokens": 0}
    text = path.read_text(encoding="utf-8")
    return {
        "lines": text.count("\n") + (0 if text.endswith("\n") else 1),
        "chars": len(text),
        "approx_tokens": len(text) // 4,
    }


def _classify_verdict(records: list[dict], fixtures: list[dict], reps: int,
                       variants: list[str]) -> tuple[str, dict]:
    """Returns (verdict, watch_list).
    Rules from spec §"Verdict rules":
      - completed < 29 of 36 planned runs  → "inconclusive — rerun"
      - some fixture has B_pass - A_pass ≤ -2 → "B regresses"
      - else → "B maintains functionality"
    """
    expected_total = len(variants) * len(fixtures) * reps
    completed = sum(1 for r in records if "passed" in r)
    if expected_total >= 30 and completed < 29:
        return "inconclusive — rerun", {}

    if "A" not in variants or "B" not in variants:
        # Single-variant run (e.g. iteration-0 dry-equivalent) → can't classify
        return "single-variant (no comparison)", {}

    pass_count: dict[tuple[str, str], int] = {}
    for r in records:
        if not r.get("passed"):
            continue
        pass_count[(r["variant"], r["fixture"])] = pass_count.get(
            (r["variant"], r["fixture"]), 0) + 1
    deltas: dict[str, int] = {}
    for f in fixtures:
        a = pass_count.get(("A", f["id"]), 0)
        b = pass_count.get(("B", f["id"]), 0)
        deltas[f["id"]] = b - a
    if any(d <= -2 for d in deltas.values()):
        return "B regresses", {k: v for k, v in deltas.items() if v <= -2}
    watch = {k: v for k, v in deltas.items() if v == -1}
    return "B maintains functionality", watch


def write_real_run_report(iter_dir: Path, records: list[dict],
                            variants: list[str], fixtures: list[dict],
                            reps: int, started: str) -> None:
    """Render ab-benchmark.md + ab-summary.json from per-run records."""
    iter_dir.mkdir(parents=True, exist_ok=True)
    verdict, watch = _classify_verdict(records, fixtures, reps, variants)

    # Per-fixture pass counts
    pass_count: dict[tuple[str, str], int] = {}
    for r in records:
        if not r.get("passed"):
            continue
        pass_count[(r["variant"], r["fixture"])] = pass_count.get(
            (r["variant"], r["fixture"]), 0) + 1

    # SKILL.md stats
    stats = {v: _skill_md_stats(v) for v in variants}

    # Mean wall / tokens per variant
    aggregates: dict[str, dict] = {}
    for v in variants:
        v_runs = [r for r in records if r.get("variant") == v]
        n = len(v_runs) or 1
        wall_avg = sum(r.get("wall_s", 0.0) for r in v_runs) / n
        tok_vals = [r.get("usage", {}).get("output_tokens") for r in v_runs
                     if r.get("usage", {}).get("output_tokens")]
        tok_avg = (sum(tok_vals) / len(tok_vals)) if tok_vals else None
        cost_vals = [r.get("usage", {}).get("total_cost_usd") for r in v_runs
                      if r.get("usage", {}).get("total_cost_usd")]
        cost_sum = sum(cost_vals) if cost_vals else None
        aggregates[v] = {"mean_wall_s": wall_avg, "mean_tokens_out": tok_avg,
                          "total_cost_usd": cost_sum}

    summary = {
        "started_at": started,
        "variants": variants,
        "fixtures": [f["id"] for f in fixtures],
        "reps": reps,
        "expected_runs": len(variants) * len(fixtures) * reps,
        "completed_runs": sum(1 for r in records if "passed" in r),
        "verdict": verdict,
        "watch_list": watch,
        "skill_md_stats": stats,
        "aggregates": aggregates,
        "records": records,
    }
    (iter_dir / "ab-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Markdown report
    lines: list[str] = []
    lines.append(f"# meta-ralph A/B test — iteration\n")
    lines.append("\n## Summary\n")
    for v in variants:
        s = stats[v]
        lines.append(f"- Variant {v}: {s['lines']} lines, {s['chars']} chars, ~{s['approx_tokens']} tok\n")
    if "A" in variants and "B" in variants:
        ca, cb = stats["A"]["chars"], stats["B"]["chars"]
        if ca:
            lines.append(f"- Size reduction (A → B): {(ca - cb) / ca * 100:.1f}%\n")
    lines.append(f"- **Verdict: {verdict}**\n")
    if watch:
        lines.append(f"- Watch list: {watch}\n")
    lines.append("\n## Pass rate matrix\n")
    if "A" in variants and "B" in variants:
        lines.append("| Fixture | A | B | Delta |\n|---|---|---|---|\n")
        for f in fixtures:
            a = pass_count.get(("A", f["id"]), 0)
            b = pass_count.get(("B", f["id"]), 0)
            lines.append(f"| {f['id']} | {a}/{reps} | {b}/{reps} | {b - a:+d} |\n")
    else:
        lines.append("| Fixture | Passes |\n|---|---|\n")
        v = variants[0]
        for f in fixtures:
            n = pass_count.get((v, f["id"]), 0)
            lines.append(f"| {f['id']} | {n}/{reps} |\n")
    lines.append("\n## Per-variant aggregates\n")
    lines.append("| Variant | Mean wall (s) | Mean output tokens | Total cost (USD) |\n")
    lines.append("|---|---|---|---|\n")
    for v in variants:
        a = aggregates[v]
        tok = f"{a['mean_tokens_out']:.0f}" if a["mean_tokens_out"] else "n/a"
        cost = f"${a['total_cost_usd']:.2f}" if a["total_cost_usd"] else "n/a"
        lines.append(f"| {v} | {a['mean_wall_s']:.1f} | {tok} | {cost} |\n")
    # Failures section
    fails = [r for r in records if not r.get("passed") and "error" not in r]
    errs = [r for r in records if "error" in r]
    if fails or errs:
        lines.append("\n## Failures\n")
        for r in fails[:20]:
            lines.append(f"\n### {r['fixture']} rep {r['rep']} on variant {r['variant']}\n")
            failed_exps = [e for e in r.get("expectations", []) if not e["passed"]]
            for e in failed_exps[:5]:
                lines.append(f"- ❌ {e['text']}\n")
                if e.get("evidence"):
                    lines.append(f"  - evidence: `{e['evidence'][:200]}`\n")
        for r in errs[:10]:
            lines.append(f"\n### {r['fixture']} rep {r['rep']} on variant {r['variant']} — harness error\n")
            lines.append(f"- {r['error']}\n")
    (iter_dir / "ab-benchmark.md").write_text("".join(lines), encoding="utf-8")
```

- [ ] **Step 4: Run report tests + full suite — expect green**

Run: `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/ -v`
Expected: all tests PASS (now ~20+ total).

- [ ] **Step 5: Commit**

```bash
git add plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py plugins/meta-ralph/skills/meta-ralph/evals/tests/test_report.py
git commit -m "feat(meta-ralph/evals): ab_harness report renderer + verdict classification"
```

---

## Task 15: Iteration 0 — end-to-end dry-run + stub-B sanity check

**Files:** none (operational task, runs the harness)

- [ ] **Step 1: Run --dry-run on the full matrix**

Run:

```bash
python plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py --dry-run --iteration 0
```

Expected output: `[dry-run] report written: .../evals/ab-results/iteration-0`. Check:

```bash
cat plugins/meta-ralph/skills/meta-ralph/evals/ab-results/iteration-0/ab-benchmark.md
```

Should show "dry run" verdict.

- [ ] **Step 2: Run preflight check standalone**

Run:

```bash
python -c "
import sys; sys.path.insert(0, 'plugins/meta-ralph/skills/meta-ralph/evals')
import ab_harness
import json
print(json.dumps(ab_harness.preflight(), indent=2))
"
```

Expected: every tool shows `true`, `asset_parity` is `true`, `ok` is `true`. If any tool shows `false`, install it before continuing.

- [ ] **Step 3: Run real-mode on ONE bootstrap fixture, variant A only, 1 rep**

This is the smallest non-dry-run smoke. Should cost ~$1 and take ~3 minutes.

Run:

```bash
python plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py \
    --variant A \
    --fixture boot-sh-claude-en \
    --reps 1 \
    --iteration 0
```

Expected: `[A] boot-sh-claude-en rep 1/1 ... PASS (XX.Xs)` then output dir created. If FAIL, inspect:

```bash
cat plugins/meta-ralph/skills/meta-ralph/evals/ab-results/iteration-0/A/boot-sh-claude-en/rep-0/grading.json
```

- [ ] **Step 4: Run real-mode on amend fixture too (still A only, 1 rep)**

```bash
python plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py \
    --variant A \
    --fixture amend-en \
    --reps 1 \
    --iteration 0
```

Expected: PASS. Should cost ~$0.50 and take ~3 minutes.

- [ ] **Step 5: Run real-mode on negative fixture (A only, 1 rep)**

```bash
python plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py \
    --variant A \
    --fixture neg-explain \
    --reps 1 \
    --iteration 0
```

Expected: PASS — agent explains without scaffolding. Should cost ~$0.20.

- [ ] **Step 6: Inspect the cumulative iteration-0 report**

Run:

```bash
cat plugins/meta-ralph/skills/meta-ralph/evals/ab-results/iteration-0/ab-benchmark.md
```

Verify: 3 fixtures × 1 rep × 1 variant = 3 runs. All should be PASS. Verdict will be `"single-variant (no comparison)"`. This is the iteration-0 smoke checkpoint — if all 3 fixture types PASS for variant A, the harness mechanics are sound.

- [ ] **Step 7: Commit (the iteration-0 results are gitignored but record the checkpoint via the commit log)**

```bash
git commit --allow-empty -m "chore(meta-ralph/evals): iteration 0 smoke green — bootstrap/amend/negative fixtures PASS on variant A"
```

---

## Task 16: Generate the real variant B via /write-a-skill

**Files:**
- Modify: `plugins/meta-ralph-b/skills/meta-ralph/SKILL.md` (replace stub with the simplified rewrite)

This is an **operational milestone** — Madao runs it interactively, the agent doesn't author it. The exact /write-a-skill conversation is outside the plan, but the success criteria are mechanical.

- [ ] **Step 1: Invoke /write-a-skill against A's SKILL.md**

In a Claude Code session, run `/write-a-skill` and provide:
- Target file: `plugins/meta-ralph-b/skills/meta-ralph/SKILL.md`
- Source to simplify: `plugins/meta-ralph/skills/meta-ralph/SKILL.md`
- Goal: ≤ 100 lines, preserve every functional behaviour, keep frontmatter `name: meta-ralph` (same as A).

Iteratively refine until the output passes the next steps.

- [ ] **Step 2: Verify frontmatter is intact**

Run: `python -c "import re; t=open('plugins/meta-ralph-b/skills/meta-ralph/SKILL.md',encoding='utf-8').read(); assert re.search(r'^name: meta-ralph$', t, re.M); print('frontmatter ok')"`
Expected: `frontmatter ok`. If fails, B's frontmatter `name` field is wrong — fix it.

- [ ] **Step 3: Verify size threshold (≤ 100 lines target, ≥ 40% char reduction)**

Run:

```bash
python -c "
from pathlib import Path
A = Path('plugins/meta-ralph/skills/meta-ralph/SKILL.md').read_text(encoding='utf-8')
B = Path('plugins/meta-ralph-b/skills/meta-ralph/SKILL.md').read_text(encoding='utf-8')
la = A.count(chr(10)) + (0 if A.endswith('\n') else 1)
lb = B.count(chr(10)) + (0 if B.endswith('\n') else 1)
print(f'A: {la} lines, {len(A)} chars')
print(f'B: {lb} lines, {len(B)} chars')
red = (len(A) - len(B)) / len(A) * 100
print(f'size reduction: {red:.1f}%')
assert lb <= 100, f'B exceeds 100-line target ({lb} lines)'
assert red >= 40, f'B is not 40% smaller ({red:.1f}%)'
print('size thresholds met')
"
```

Expected: `size thresholds met`. If not, iterate /write-a-skill until both invariants hold.

- [ ] **Step 4: Verify B's plugin still loads (smoke test)**

Same one-liner as Task 6 step 5 but with the real B:

```bash
SANDBOX=$(mktemp -d -t ralph-b-real-XXXXXX)
cd "$SANDBOX" && git init -q -b main && git config core.autocrlf false && git commit --allow-empty -q -m init
claude --plugin-dir "D:/Skills/meta-skills/plugins/meta-ralph-b" \
       --add-dir . --allowedTools "Skill Read Write Edit Bash" \
       --disallowedTools "WebFetch WebSearch" --output-format json \
       -p 'list the skills available and exit, do not scaffold' \
       2>/dev/null | python -c "import json,sys; print(json.load(sys.stdin).get('result','')[:200])"
cd .. && rm -rf "$SANDBOX"
```

Expected: result text mentions `meta-ralph`. If the plugin manifest is malformed B will error and we cannot proceed.

- [ ] **Step 5: Commit B**

```bash
git add plugins/meta-ralph-b/skills/meta-ralph/SKILL.md
git commit -m "feat(meta-ralph-b): replace stub SKILL.md with simplified rewrite via /write-a-skill

Target: <=100 lines while preserving every functional behaviour A guarantees.
Frontmatter name unchanged ('meta-ralph') so trigger phrases route identically.
Templates/scripts/reference unchanged (shared with A via copy + hash check)."
```

---

## Task 17: Iteration 1 — full 36-run matrix

**Files:** none (operational; produces `ab-results/iteration-1/`)

- [ ] **Step 1: Confirm preflight is green**

```bash
python -c "
import sys, json; sys.path.insert(0,'plugins/meta-ralph/skills/meta-ralph/evals')
import ab_harness; print(json.dumps(ab_harness.preflight(), indent=2))
"
```

Expected: every key `true`, `asset_parity: true`. If `asset_parity: false`, B's templates/scripts/reference drifted — re-run Task 6 step 2 to re-copy.

- [ ] **Step 2: Run the full 36-run matrix**

Budget: ~60 min, ~$15-40. Run:

```bash
python plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py --iteration 1
```

The harness streams `[VARIANT] fixture rep N/3 ... PASS|FAIL (XX.Xs)` lines as it goes. If it hangs >5 min on any single run, the sentinel watcher is failing — Ctrl+C, inspect the sandbox in the printed error path.

- [ ] **Step 3: Read the verdict**

```bash
cat plugins/meta-ralph/skills/meta-ralph/evals/ab-results/iteration-1/ab-benchmark.md
```

Three outcomes:

- **`B maintains functionality`** → proceed to Task 18 (PR).
- **`B regresses`** → inspect the failures section. Edit B's SKILL.md to fix the gap (typically a missing phase the simplification dropped). Repeat Task 17 step 2 with `--iteration 2`. Stop after 3 attempts; if still failing, retire the experiment.
- **`inconclusive — rerun`** → re-run; usually a transient timeout or env issue.

- [ ] **Step 4: Save a permanent copy of the iteration-1 verdict**

Even though `ab-results/` is gitignored, we keep the final verdict text in the spec-findings companion so it lives in git:

```bash
echo "" >> docs/superpowers/specs/2026-05-15-meta-ralph-ab-spike-findings.md
echo "## Iteration 1 verdict" >> docs/superpowers/specs/2026-05-15-meta-ralph-ab-spike-findings.md
echo "" >> docs/superpowers/specs/2026-05-15-meta-ralph-ab-spike-findings.md
cat plugins/meta-ralph/skills/meta-ralph/evals/ab-results/iteration-1/ab-benchmark.md \
    >> docs/superpowers/specs/2026-05-15-meta-ralph-ab-spike-findings.md
git add docs/superpowers/specs/2026-05-15-meta-ralph-ab-spike-findings.md
git commit -m "docs(meta-ralph): iteration 1 verdict — <COPY VERDICT LINE HERE>"
```

Replace `<COPY VERDICT LINE HERE>` in the commit message with the actual verdict line from the report ("B maintains functionality" / "B regresses" / "inconclusive — rerun").

---

## Task 18: Open PR with the verdict

**Files:** none (uses `gh` CLI)

- [ ] **Step 1: Push the branch**

```bash
git push -u origin exp/meta-ralph-ab
```

- [ ] **Step 2: Open PR**

Run (note: paste the actual iteration-1 verdict + pass-rate matrix into the body):

```bash
gh pr create --title "experiment(meta-ralph): A/B test — simplified SKILL.md via /write-a-skill" \
             --body "$(cat <<'EOF'
## Summary

- Sidecar A/B harness (`ab_harness.py`) compares the current `meta-ralph` SKILL.md (variant A) against a simplified rewrite (variant B) across 1 agent × 6 fixtures × 3 reps.
- Variant B is a sibling plugin (`plugins/meta-ralph-b/`) that reuses A's `templates/`, `scripts/`, `reference/` via recursive copy + sha256 hash-tree parity check.
- `run_evals.py` gets two new flags (`--driver-from`, `--output-dir`); default invocation still produces 48/48 green.

## Verdict (iteration 1)

<paste the Pass rate matrix + Summary section from
plugins/meta-ralph/skills/meta-ralph/evals/ab-results/iteration-1/ab-benchmark.md here>

## What's in this PR

- `plugins/meta-ralph-b/` — new plugin with simplified SKILL.md, shared assets.
- `plugins/meta-ralph/skills/meta-ralph/evals/`:
  - `ab_harness.py`, `ab_lib.py`, `ab_invoke.py`, `ab_grading.py`
  - `ab_fixtures.json`, `ab_presets/seed-prd-with-2-stories.json`
  - `tests/*` (~20 tests)
- `run_evals.py` patch: `--driver-from`, `--output-dir`. Existing 48/48 driver eval still green.
- Spec + spike findings under `docs/superpowers/specs/`.

## Test plan

- [ ] `python -m pytest plugins/meta-ralph/skills/meta-ralph/evals/tests/ -v` — all harness unit tests green
- [ ] `python plugins/meta-ralph/skills/meta-ralph/evals/run_evals.py` — driver eval suite still 48/48
- [ ] `python plugins/meta-ralph/skills/meta-ralph/evals/ab_harness.py --dry-run --iteration 99` — dry run produces report
- [ ] Optionally re-run `--iteration 2` to confirm the iteration-1 verdict reproduces

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Update the PR body with the actual iteration-1 verdict**

Manually edit the PR description on GitHub (or with `gh pr edit --body ...`) replacing the `<paste ...>` block with the contents of the iteration-1 pass-rate matrix and summary lines.

---

## Self-review

After writing this plan, the following cross-checks pass:

**Spec coverage:**

- Goal (compare A vs B on equivalence + size + execution pass rate) — Tasks 9-14 grade and report all three dimensions; Task 17 executes.
- Non-goals respected: no cross-skill routing tests; no `templates/` rewrite (Task 6 hash-checks parity); not wired as CI gate (Task 16+ are manual operational steps).
- Constraint "A's evals untouched except 2 flags" — Task 2 adds exactly those 2 flags, verifies 48/48 green before and after.
- Constraint "all writes LF" — Task 3's `seed_preset` calls `.replace(b"\r\n", b"\n")`; Task 4's preset is written via `write_bytes` (no Python newline translation).
- Architecture's `--plugin-dir` invocation — Task 13's `_build_agent_cmd` uses it.
- Architecture's sentinel completion — Task 12 implements + tests both paths.
- run_evals.py patch — Task 2.
- ab_fixtures.json shape — Task 5.
- ab_presets/ — Task 4.
- ab_lib.py surface (make_sandbox / seed_preset / snapshot_files / cleanup) — Task 3, plus `hash_tree` added for the parity check.
- Pre-flight — Task 8.
- Grading checks (structure / amend / negative / behaviour) — Tasks 9-11.
- Sentinel + wall-clock — Task 12.
- Report shape + verdict rules — Task 14.
- Cost/safety: 90-min iteration cap is enforced implicitly by per-run wall-timeouts (180+90+60 × 6 × 3 × 2 = 78 min worst-case, well under the 90-min cap).
- 5 Open Questions resolved in the plan header.

**Placeholder scan:** No "TBD", "TODO", "implement later", or vague "handle edge cases" in any task. Every code step shows actual code.

**Type consistency:** All function signatures used in later tasks (`make_sandbox`, `seed_preset`, `snapshot_files`, `hash_tree`, `structure_check`, `amend_check`, `negative_check`, `behaviour_check`, `run_agent`, `_build_agent_cmd`, `_run_one`, `write_real_run_report`) match the definitions in their introducing task. Field names in `ab_fixtures.json` (`runner_command_contains`, `should_trigger_skill`, `files_required`, `files_forbidden_to_change`, `prd_constraints`, `amend_mode`, `driver_eval_required`) are consistent across the fixture file, the schema test, and the grading code.

One renaming carried through: the spec wrote `runner.command_contains` (dot-form). The plan uses `runner_command_contains` (underscore form) throughout `ab_fixtures.json` and `ab_grading.py` for JSON-key cleanliness. No mixed usage.

---

## Execution

Plan complete. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration. Uses `superpowers:subagent-driven-development`.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.
