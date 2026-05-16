"""Grading checks for ab_harness.

Each check returns a list of expectation records:
    [{"text": str, "passed": bool, "evidence": str}, ...]

The list is the skill-creator grading.json schema. ab_harness aggregates these
across the four checks (structure / amend / negative / behaviour) into one
grading.json per run.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

Expectation = dict[str, Any]

_HERE = Path(__file__).resolve().parent
_RUN_EVALS = _HERE / "run_evals.py"

_US_ID_PATTERN = re.compile(r"^US-\d{3,}$")

_RUNTIME_TO_DRIVER = {"sh": "ralph.sh", "ts": "ralph.ts", "js": "ralph.js", "py": "ralph.py"}


def structure_check(scaffold: Path, fixture: dict[str, Any]) -> list[Expectation]:
    """Validate prd.json schema + required files + prd_constraints."""
    out: list[Expectation] = []
    exp = fixture["expected"]

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

    required_top = ("project", "branchName", "description", "runner", "userStories")
    for k in required_top:
        ok = k in prd
        out.append({
            "text": f"prd.json has '{k}'",
            "passed": ok,
            "evidence": "" if ok else f"keys: {sorted(prd.keys())}",
        })

    for rel in exp.get("files_required", []):
        ok = (scaffold / rel).exists()
        out.append({
            "text": f"file exists: {rel}",
            "passed": ok,
            "evidence": "" if ok else "missing",
        })

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


def amend_check(scaffold: Path,
                pre_snapshot: dict[str, bytes],
                fixture: dict[str, Any]) -> list[Expectation]:
    """Verify amend invariants:
      - files in expected.files_forbidden_to_change are byte-identical pre vs post
      - presets ids US-PRESET-N still appear in post prd.json (if requested)
    """
    out: list[Expectation] = []
    exp = fixture["expected"]
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
        out.extend(_check_spec_11_1(pre_prd, post_prd, pc))
    return out


def _check_spec_11_1(pre_prd: dict[str, Any], post_prd: dict[str, Any],
                     pc: dict[str, Any]) -> list[Expectation]:
    """SPEC §11.1 append-only invariants:
      1. length === N_old + N_new
      2. existing stories deep-equal (first N_old indices)
      3. new stories: status=='todo', id matches ^US-\\d{3,}$, ≥1 acceptanceCriteria
      4. new priorities strictly greater than every pre-amend priority
      5. ids unique across the full post array
      6. at most 1 status=='in_progress' (B4-6)
    """
    out: list[Expectation] = []
    pre_stories = pre_prd.get("userStories", [])
    post_stories = post_prd.get("userStories", [])
    n_old = len(pre_stories)
    expected_total = pc.get("min_user_stories")
    if expected_total is not None and pc.get("max_user_stories") == expected_total:
        n_new = expected_total - n_old
        out.append({
            "text": f"§11.1 length invariant: userStories.length == {n_old} + {n_new}",
            "passed": len(post_stories) == expected_total,
            "evidence": "" if len(post_stories) == expected_total
                        else f"got {len(post_stories)}, want {expected_total}",
        })

    for i, pre_story in enumerate(pre_stories):
        if i >= len(post_stories):
            out.append({
                "text": f"§11.1 deep-equal: existing story idx {i} preserved",
                "passed": False, "evidence": "post array too short",
            })
            continue
        same = pre_story == post_stories[i]
        out.append({
            "text": f"§11.1 deep-equal: existing story idx {i} ({pre_story.get('id', '?')}) preserved",
            "passed": same,
            "evidence": "" if same else f"diff at idx {i}",
        })

    pre_priorities = [s.get("priority") for s in pre_stories
                      if isinstance(s.get("priority"), (int, float))]
    max_pre_priority = max(pre_priorities) if pre_priorities else 0
    new_stories = post_stories[n_old:]
    for j, ns in enumerate(new_stories):
        idx = n_old + j
        sid = ns.get("id", "")
        out.append({
            "text": f"§11.1 new story idx {idx} id matches '^US-\\d{{3,}}$'",
            "passed": bool(_US_ID_PATTERN.match(sid)),
            "evidence": "" if _US_ID_PATTERN.match(sid) else f"id={sid!r}",
        })
        out.append({
            "text": f"§11.1 new story idx {idx} status=='todo'",
            "passed": ns.get("status") == "todo",
            "evidence": "" if ns.get("status") == "todo" else f"status={ns.get('status')!r}",
        })
        ac = ns.get("acceptanceCriteria", [])
        out.append({
            "text": f"§11.1 new story idx {idx} has ≥1 acceptanceCriteria",
            "passed": isinstance(ac, list) and len(ac) >= 1,
            "evidence": "" if isinstance(ac, list) and ac else f"got {ac!r}",
        })
        p = ns.get("priority")
        ok = isinstance(p, (int, float)) and p > max_pre_priority
        out.append({
            "text": f"§11.1 append-to-tail: new story idx {idx} priority > {max_pre_priority}",
            "passed": ok,
            "evidence": "" if ok else f"priority={p!r}, max_pre={max_pre_priority}",
        })

    all_ids = [s.get("id") for s in post_stories]
    out.append({
        "text": "§11.1 ids unique across post.userStories",
        "passed": len(all_ids) == len(set(all_ids)),
        "evidence": "" if len(all_ids) == len(set(all_ids))
                    else f"duplicates in {all_ids}",
    })

    in_progress_count = sum(1 for s in post_stories if s.get("status") == "in_progress")
    out.append({
        "text": "§11.1 at most 1 story has status=='in_progress'",
        "passed": in_progress_count <= 1,
        "evidence": "" if in_progress_count <= 1 else f"count={in_progress_count}",
    })
    return out


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
