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
EVALS_DIR = HERE.parent
if str(EVALS_DIR) not in sys.path:
    sys.path.insert(0, str(EVALS_DIR))

import ab_invoke  # type: ignore  # noqa: E402


def _write_fake_agent(script_path: Path, sandbox: Path, delay_s: float = 0.5,
                      linger_s: float = 30.0) -> None:
    """Write a python script that simulates claude: writes prd.json + .ralph/ralph.sh
    after `delay_s`, then sleeps for `linger_s` (to test the SIGTERM path)."""
    script_path.write_text(textwrap.dedent(f"""
        import json, time, sys
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
        (sandbox / ".ralph" / "prompt.md").write_text("p\\n", encoding="utf-8")
        (sandbox / ".ralph" / "RUNBOOK.md").write_text("r\\n", encoding="utf-8")
        (sandbox / ".ralph" / "progress.txt").write_text("## p\\n", encoding="utf-8")
        (sandbox / ".gitignore").write_text(".ralph/.lock\\n", encoding="utf-8")
        (sandbox / ".ralph" / "ralph.sh").write_text("#!/bin/sh\\n", encoding="utf-8")
        time.sleep({linger_s})
        print('{{"result":"ok"}}')
    """).strip(), encoding="utf-8")


def test_sentinel_terminates_when_scaffold_complete(tmp_path: Path) -> None:
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    fake_agent = tmp_path / "fake_agent.py"
    _write_fake_agent(fake_agent, sandbox, delay_s=0.3, linger_s=15.0)
    cmd = [sys.executable, str(fake_agent)]
    result = ab_invoke.run_agent(
        cmd=cmd, sandbox=sandbox,
        wall_timeout_s=20,
        amend_mode=False, runtime="sh",
    )
    assert result.exit_reason in ("sentinel", "exited"), result.exit_reason
    assert result.wall_s < 8.0, f"sentinel did not fire quickly: {result.wall_s}s"
    assert (sandbox / "prd.json").exists()


def test_wall_timeout_kicks_in_when_sentinel_never_fires(tmp_path: Path) -> None:
    """Agent never writes the scaffold — wall_timeout_s must fire."""
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    fake_agent = tmp_path / "fake_agent.py"
    fake_agent.write_text(
        "import time, sys\ntime.sleep(20)\n",
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


def test_amend_sentinel_ignores_harmless_reserialize(tmp_path: Path) -> None:
    """Amend sentinel must NOT fire on a no-op rewrite of prd.json (whitespace
    or key-order changes without adding a story). Iteration 1's amend-zh rep 0
    failure was consistent with a premature SIGTERM after a harmless reserialize."""
    sandbox = tmp_path / "sb"; sandbox.mkdir()
    initial_doc = {"userStories": [{"id": "US-PRESET-1"}, {"id": "US-PRESET-2"}]}
    import json as _json
    (sandbox / "prd.json").write_text(_json.dumps(initial_doc, indent=2), encoding="utf-8")
    fake_agent = tmp_path / "fake_agent.py"
    fake_agent.write_text(textwrap.dedent(f"""
        import json, time
        from pathlib import Path
        sandbox = Path(r'{sandbox}')
        time.sleep(0.5)
        # Re-serialize prd.json with different formatting — count unchanged
        doc = json.loads((sandbox / "prd.json").read_text(encoding="utf-8"))
        (sandbox / "prd.json").write_text(
            json.dumps(doc, indent=4, sort_keys=True), encoding="utf-8"
        )
        time.sleep(10)
    """).strip(), encoding="utf-8")
    cmd = [sys.executable, str(fake_agent)]
    result = ab_invoke.run_agent(
        cmd=cmd, sandbox=sandbox,
        wall_timeout_s=4,
        amend_mode=True, runtime="sh",
    )
    # Sentinel must NOT have fired (count didn't change) — wall_timeout instead
    assert result.exit_reason == "wall_timeout", \
        f"sentinel false-positive on reserialize: {result.exit_reason}"


def test_amend_sentinel_fires_on_count_increase(tmp_path: Path) -> None:
    """Amend sentinel SHOULD fire once a new story is appended."""
    sandbox = tmp_path / "sb"; sandbox.mkdir()
    initial_doc = {"userStories": [{"id": "US-PRESET-1"}, {"id": "US-PRESET-2"}]}
    import json as _json
    (sandbox / "prd.json").write_text(_json.dumps(initial_doc, indent=2), encoding="utf-8")
    fake_agent = tmp_path / "fake_agent.py"
    fake_agent.write_text(textwrap.dedent(f"""
        import json, time
        from pathlib import Path
        sandbox = Path(r'{sandbox}')
        time.sleep(0.5)
        doc = json.loads((sandbox / "prd.json").read_text(encoding="utf-8"))
        doc["userStories"].append({{"id": "US-003"}})
        (sandbox / "prd.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
        time.sleep(10)
    """).strip(), encoding="utf-8")
    cmd = [sys.executable, str(fake_agent)]
    result = ab_invoke.run_agent(
        cmd=cmd, sandbox=sandbox,
        wall_timeout_s=15,
        amend_mode=True, runtime="sh",
    )
    assert result.exit_reason == "sentinel"
    assert result.wall_s < 5.0


def test_drain_after_kill_is_bounded(tmp_path: Path) -> None:
    """If a grandchild process holds the pipes open after proc.kill(),
    _bounded_drain must return within drain_timeout_s instead of blocking forever.

    Simulates the iteration-1 amend-zh outlier (1541 s) where claude spawned a
    helper that inherited stdout/stderr handles.
    """
    sandbox = tmp_path / "sb"
    sandbox.mkdir()
    fake_agent = tmp_path / "fake_agent.py"
    # Parent prints something, then spawns a detached child that lingers with the
    # pipe still inherited, then parent waits for SIGTERM but the child keeps the
    # pipe open.
    fake_agent.write_text(textwrap.dedent("""
        import os, sys, time, subprocess
        if os.environ.get('IS_CHILD') == '1':
            time.sleep(30)
            sys.exit(0)
        env = dict(os.environ); env['IS_CHILD'] = '1'
        # Spawn a child that inherits stdout/stderr by default
        subprocess.Popen([sys.executable, __file__], env=env)
        time.sleep(60)
    """).strip(), encoding="utf-8")
    cmd = [sys.executable, str(fake_agent)]
    started = __import__("time").monotonic()
    result = ab_invoke.run_agent(
        cmd=cmd, sandbox=sandbox,
        wall_timeout_s=2,
        amend_mode=False, runtime="sh",
    )
    elapsed = __import__("time").monotonic() - started
    assert result.exit_reason == "wall_timeout"
    # Must return within wall_timeout + drain_timeout (10) + slack, not 30s+
    assert elapsed < 18.0, f"drain not bounded: {elapsed:.1f}s"
