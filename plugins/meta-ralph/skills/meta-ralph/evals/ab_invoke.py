"""Spawn the agent subprocess and watch for scaffold completion.

Two completion paths:
  1. Sentinel — sandbox poll-checks every 1 s; once prd.json + driver-file
     (or just prd.json in amend mode) are on disk and prd.json parses, SIGTERM.
  2. Wall-clock — fallback if sentinel never fires.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path


_RUNTIME_TO_DRIVER = {"sh": "ralph.sh", "ts": "ralph.ts", "js": "ralph.js", "py": "ralph.py"}

# All files SKILL §11 Phase 3 writes for bootstrap. Sentinel waits for the
# full set — firing on just (prd.json + driver) cuts off the agent before
# RUNBOOK.md / progress.txt / .gitignore are written.
_BOOTSTRAP_REQUIRED_RELS = (
    "prd.json",
    ".ralph/prompt.md",
    ".ralph/RUNBOOK.md",
    ".ralph/progress.txt",
    ".gitignore",
)


@dataclass
class AgentRunResult:
    exit_code: int
    stdout: str
    stderr: str
    wall_s: float
    exit_reason: str
    sentinel_fired_at: float | None


def _scaffold_complete(sandbox: Path, amend_mode: bool, runtime: str,
                       initial_prd_bytes: bytes | None) -> bool:
    """Return True once prd.json exists + parses, and (if bootstrap) all SPEC
    §11 Phase-3 outputs are on disk (driver, RUNBOOK, progress, .gitignore,
    prompt.md). In amend mode, requires prd.json userStories count to be
    strictly greater than the pre-run count — any harmless reserialize
    (whitespace/key-order/Unicode normalization) that doesn't actually add a
    story must not trip the sentinel."""
    prd = sandbox / "prd.json"
    if not prd.exists():
        return False
    try:
        current_bytes = prd.read_bytes()
        current_doc = json.loads(current_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return False
    if amend_mode:
        if initial_prd_bytes is None:
            return False
        try:
            initial_doc = json.loads(initial_prd_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False
        return (len(current_doc.get("userStories", []))
                > len(initial_doc.get("userStories", [])))
    driver = _RUNTIME_TO_DRIVER.get(runtime)
    if driver is None:
        return False
    if not (sandbox / ".ralph" / driver).exists():
        return False
    return all((sandbox / rel).exists() for rel in _BOOTSTRAP_REQUIRED_RELS)


def run_agent(cmd: list[str], sandbox: Path, wall_timeout_s: float,
              amend_mode: bool, runtime: str,
              poll_interval_s: float = 1.0) -> AgentRunResult:
    """Spawn `cmd` with cwd=sandbox; watch for scaffold completion or timeout."""
    initial_prd_bytes: bytes | None = None
    if amend_mode:
        prd_path = sandbox / "prd.json"
        if prd_path.exists():
            initial_prd_bytes = prd_path.read_bytes()
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
                return
            if _scaffold_complete(sandbox, amend_mode, runtime, initial_prd_bytes):
                sentinel_fired_at = time.monotonic() - started
                try:
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
        out, err = _bounded_drain(proc, drain_timeout_s=10.0)
        wall_s = time.monotonic() - started
        return AgentRunResult(
            exit_code=-1, stdout=out, stderr=err + "\n[wall_timeout]",
            wall_s=wall_s, exit_reason="wall_timeout", sentinel_fired_at=None,
        )
    finally:
        stop_event.set()
        if proc.poll() is None:
            proc.kill()


def _bounded_drain(proc: subprocess.Popen, drain_timeout_s: float) -> tuple[str, str]:
    """Read stdout/stderr after proc.kill() with a hard upper bound.

    On Windows, claude can spawn grandchild processes that inherit the parent's
    pipe write-handles. proc.kill() (TerminateProcess) hits the direct child
    only; grandchildren keep the pipes open and an unbounded proc.communicate()
    blocks until they exit. The 1541 s amend-zh outlier in iteration 1 was
    exactly this case.

    Strategy: try communicate(timeout=drain_timeout_s). On second TimeoutExpired,
    discard whatever the pipes still hold and return an empty marker."""
    try:
        out, err = proc.communicate(timeout=drain_timeout_s)
        return (out or ""), (err or "")
    except subprocess.TimeoutExpired:
        return "", "[drain_timeout — orphaned grandchild process held pipes]"
