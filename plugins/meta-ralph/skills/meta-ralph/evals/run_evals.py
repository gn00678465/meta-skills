#!/usr/bin/env python3
"""Runner-focused evals for meta-ralph driver templates.

Builds a fresh sandbox git repo per (scenario × runtime), points
prd.json.runner.command at evals/mock-agent.py, runs the rendered driver
with max-iter=1, then asserts on argv_dump.json + stderr + exit code.

Usage:
    python run_evals.py                       # all runtimes
    python run_evals.py --runtime sh,py       # subset
    python run_evals.py --scenario strip-long-form
    python run_evals.py --keep-sandbox        # don't rm tmpdir on exit (debug)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TEMPLATES_DIR = HERE.parent / "templates" / "ralph"
MOCK_AGENT = HERE / "mock-agent.py"
RESULTS_ROOT = HERE / "results"

RUNTIMES = ["sh", "ts", "js", "py"]


def _resolve_bash() -> str:
    """Pick a bash that has MSYS tooling on PATH (so the sh driver's `command -v jq` succeeds).

    On Windows, plain `bash` can hit the WSL App Execution Alias in WindowsApps even when
    `shutil.which('bash')` returns git-bash — the two use different resolution algorithms.
    Be explicit so the harness is deterministic.
    """
    candidates = []
    w = shutil.which("bash")
    if w and "WindowsApps" not in w:
        candidates.append(w)
    candidates += [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        "/usr/bin/bash",
        "/bin/bash",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return "bash"  # last resort; will error visibly


_BASH = _resolve_bash()

RUNTIME_CMD: dict[str, list[str]] = {
    "sh": [_BASH, ".ralph/ralph.sh"],
    "ts": ["bun", "run", ".ralph/ralph.ts"],
    "js": ["node", ".ralph/ralph.js"],
    "py": [sys.executable, ".ralph/ralph.py"],
}


@dataclass
class AssertionResult:
    text: str
    passed: bool
    evidence: str = ""


@dataclass
class RunResult:
    scenario_name: str
    runtime: str
    returncode: int
    stdout: str
    stderr: str
    argv_dump: list[str] | None
    duration_s: float
    error: str = ""
    assertions: list[AssertionResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return self.error == "" and all(a.passed for a in self.assertions)


def sh(*args: str, cwd: Path | None = None, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess synchronously, capturing stdout/stderr."""
    return subprocess.run(list(args), cwd=cwd, check=check, capture_output=True, text=True, encoding="utf-8", env=env)


def setup_sandbox(scenario: dict[str, Any], runtime: str) -> Path:
    """Create temp directory with git repo + prd.json + driver, return path."""
    sandbox = Path(tempfile.mkdtemp(prefix=f"ralph-eval-{runtime}-{scenario['name']}-"))
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    sh("git", "init", "-q", "-b", "main", cwd=sandbox, env=env)
    sh("git", "config", "user.email", "eval@test.local", cwd=sandbox)
    sh("git", "config", "user.name", "eval", cwd=sandbox)
    # disable autocrlf so the driver template's LF endings stay intact
    sh("git", "config", "core.autocrlf", "false", cwd=sandbox)
    sh("git", "commit", "--allow-empty", "-q", "-m", "init", cwd=sandbox, env=env)

    # Build prd.json
    setup = scenario.get("setup", {})
    prd: dict[str, Any] = {
        "project": "eval",
        "branchName": "main",
        "description": "eval test",
        "userStories": [
            {
                "id": "US-001",
                "title": "test story",
                "description": "test",
                "acceptanceCriteria": ["always passing"],
                "priority": 1,
                "status": "todo",
            }
        ],
    }
    if "runner_args" in setup:
        prd["runner"] = {
            "command": sys.executable,
            "args": [str(MOCK_AGENT)] + list(setup["runner_args"]),
        }
    # else: scenario explicitly tests missing-runner

    # Write prd.json in binary mode to force LF line endings (Path.write_text on Windows
    # translates \n → \r\n by default, which makes `jq -r` emit values with stray CR
    # when bash reads them — silently breaks the sh runtime parity test).
    (sandbox / "prd.json").write_bytes(
        (json.dumps(prd, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )

    # Build .ralph/
    ralph_dir = sandbox / ".ralph"
    ralph_dir.mkdir()
    prompt_content = setup.get("prompt_content", "TEST_PROMPT\n")
    (ralph_dir / "prompt.md").write_bytes(prompt_content.encode("utf-8"))
    (ralph_dir / "progress.txt").write_bytes(b"## Codebase Patterns\n")

    # Copy driver template, ensure LF endings, drop the .tpl suffix
    ext = runtime
    src = TEMPLATES_DIR / f"ralph.{ext}.tpl"
    dst = ralph_dir / f"ralph.{ext}"
    raw = src.read_bytes().replace(b"\r\n", b"\n")
    dst.write_bytes(raw)
    if ext == "sh":
        os.chmod(dst, 0o755)

    # js runtime needs .ralph/package.json pinning CommonJS
    if ext == "js":
        (ralph_dir / "package.json").write_text('{"type":"commonjs"}\n', encoding="utf-8")

    # Commit setup so working tree is clean
    sh("git", "add", "-A", cwd=sandbox, env=env)
    sh("git", "commit", "-q", "-m", "setup", cwd=sandbox, env=env)

    return sandbox


def invoke_driver(sandbox: Path, runtime: str, cli_model: str | None) -> tuple[int, str, str, float]:
    """Run the driver in the sandbox, max 1 iteration. Returns (rc, stdout, stderr, duration)."""
    cmd = list(RUNTIME_CMD[runtime]) + ["1"]
    if cli_model is not None:
        cmd += ["--model", cli_model]

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            cwd=sandbox,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env=env,
        )
        elapsed = time.monotonic() - start
        return result.returncode, result.stdout or "", result.stderr or "", elapsed
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - start
        return -1, exc.stdout or "", (exc.stderr or "") + "\n[harness] timeout after 60s", elapsed


def read_argv_dump(sandbox: Path) -> list[str] | None:
    """Return the captured argv list, or None if the mock never wrote it."""
    dump = sandbox / "argv_dump.json"
    if not dump.exists():
        return None
    try:
        return json.loads(dump.read_text(encoding="utf-8"))["argv"]
    except Exception:
        return None


def count_model_selectors(argv: list[str]) -> int:
    count = 0
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--model" or a == "-m":
            count += 1
            i += 2
            continue
        if a.startswith("--model=") or a.startswith("-m="):
            count += 1
        i += 1
    return count


# ---------------------------------------------------------------------------
# Per-scenario assertion logic
# ---------------------------------------------------------------------------

def assertions_for(scenario: dict[str, Any], runtime: str, run: RunResult) -> list[AssertionResult]:
    name = scenario["name"]
    a: list[AssertionResult] = []
    rc = run.returncode
    err = run.stderr
    argv = run.argv_dump
    setup = scenario.get("setup", {})

    def add(text: str, passed: bool, evidence: str = "") -> None:
        a.append(AssertionResult(text=text, passed=passed, evidence=evidence))

    if name == "missing-runner-aborts":
        add("driver exits non-zero", rc != 0, f"rc={rc}")
        add("stderr names the missing 'runner' field",
            "missing required 'runner'" in err or "missing required \"runner\"" in err.replace("'", "\""),
            err.splitlines()[0] if err else "(empty stderr)")
        add("argv_dump.json was NOT created (mock never spawned)",
            argv is None, f"argv={argv}")
        return a

    if name == "passthrough-no-cli-model":
        ok = argv is not None and argv[-2:] == ["--model", "opus"]
        add("argv ends with --model opus", ok, repr(argv[-4:] if argv else None))
        # prompt content should be present somewhere as a single argv element
        prompt = setup.get("prompt_content", "TEST_PROMPT\n")
        present = argv is not None and prompt in argv
        add("{PROMPT} sentinel replaced with prompt content", present,
            f"prompt={prompt!r}, found_in_argv={present}")
        return a

    if name in {"strip-long-form", "strip-equals-form", "strip-short-form", "strip-equals-short"}:
        target_model = setup.get("cli_model", "")
        forbidden_value = "opus"
        forbidden_tokens_map = {
            "strip-long-form": ["--model=opus"],
            "strip-equals-form": ["--model=opus"],
            "strip-short-form": ["-m"],
            "strip-equals-short": ["-m=opus"],
        }
        if argv is None:
            add("argv_dump.json was created", False, "mock not spawned")
            return a
        add("argv has exactly one --model selector",
            count_model_selectors(argv) == 1,
            f"argv={argv!r}, count={count_model_selectors(argv)}")
        add(f"argv ends with --model {target_model}",
            argv[-2:] == ["--model", target_model],
            repr(argv[-3:]))
        add(f"argv does NOT contain '{forbidden_value}'",
            forbidden_value not in argv,
            repr([x for x in argv if forbidden_value in x]))
        for tok in forbidden_tokens_map.get(name, []):
            add(f"argv does NOT contain the stripped token '{tok}'",
                tok not in argv,
                repr([x for x in argv if tok == x]))
        return a

    if name == "strip-duplicates":
        if argv is None:
            add("argv_dump.json was created", False, "mock not spawned")
            return a
        add("argv has exactly one --model selector",
            count_model_selectors(argv) == 1,
            f"count={count_model_selectors(argv)}, argv={argv!r}")
        add("argv ends with --model c",
            argv[-2:] == ["--model", "c"],
            repr(argv[-3:]))
        # 'a' and 'b' must not appear as standalone tokens
        add("argv does not contain stripped model values 'a' or 'b' as standalone tokens",
            "a" not in argv and "b" not in argv,
            repr([x for x in argv if x in ("a", "b")]))
        return a

    if name == "dangling-aborts":
        add("driver exits non-zero", rc != 0, f"rc={rc}")
        add("stderr mentions 'dangling' --model",
            "dangling" in err.lower(),
            err.splitlines()[0] if err else "(empty stderr)")
        add("argv_dump.json was NOT created", argv is None, f"argv={argv}")
        return a

    if name == "prompt-substitution":
        prompt = setup.get("prompt_content", "")
        if argv is None:
            add("argv_dump.json was created", False, "mock not spawned")
            return a
        # The substituted element should be the exact prompt content
        add("argv element substituted from {PROMPT} equals prompt content byte-for-byte",
            prompt in argv,
            f"prompt_repr={prompt!r}, argv={argv!r}")
        add("argv ends with --flag",
            argv[-1] == "--flag",
            repr(argv[-2:]))
        return a

    if name == "prompt-missing-sentinel":
        prompt = setup.get("prompt_content", "")
        if argv is None:
            add("argv_dump.json was created", False, "mock not spawned")
            return a
        add("argv ends with prompt content (appended after --flag)",
            argv[-1] == prompt,
            f"argv_last={argv[-1]!r}, prompt={prompt!r}")
        # warning should appear on stderr
        add("stderr contains warning about missing '{PROMPT}' sentinel",
            "{PROMPT}" in err and ("sentinel" in err.lower() or "appending" in err.lower()),
            err.splitlines()[0] if err else "(empty stderr)")
        return a

    if name == "prompt-trailing-newline-preserved":
        prompt = setup.get("prompt_content", "hello-world\n")
        if argv is None:
            add("argv_dump.json was created", False, "mock not spawned")
            return a
        # Find the substituted element. Since runner.args was ["-p","{PROMPT}"],
        # argv = [mock-path, -p, <substituted>]. We check element [-1].
        substituted = argv[-1]
        add(f"substituted element equals prompt content byte-for-byte (incl. trailing \\n)",
            substituted == prompt,
            f"got_repr={substituted!r}, want_repr={prompt!r}, "
            f"got_endswith_newline={substituted.endswith(chr(10))}")
        return a

    if name == "embedded-newline-in-args-preserved":
        prompt = setup.get("prompt_content", "TEST_PROMPT\n")
        if argv is None:
            add("argv_dump.json was created", False, "mock not spawned")
            return a
        # runner.args = ["-p", "{PROMPT}", "--note", "line1\nline2"]
        # After substitution: argv = ["-p", <prompt>, "--note", "line1\nline2"]
        add("argv has exactly 4 elements after the mock-agent.py path",
            len(argv) == 4,
            f"len={len(argv)}, argv={argv!r}")
        if len(argv) >= 4:
            add("argv[0] is '-p'", argv[0] == "-p", f"got={argv[0]!r}")
            add("argv[1] is the substituted prompt content",
                argv[1] == prompt,
                f"got={argv[1]!r}, want={prompt!r}")
            add("argv[2] is '--note'", argv[2] == "--note", f"got={argv[2]!r}")
            add("argv[3] is 'line1\\nline2' (single arg with embedded newline)",
                argv[3] == "line1\nline2",
                f"got_repr={argv[3]!r}, len={len(argv[3])}")
        return a

    add(f"(no assertions defined for scenario '{name}')", False, "")
    return a


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_one(scenario: dict[str, Any], runtime: str, keep_sandbox: bool) -> RunResult:
    sandbox: Path | None = None
    try:
        sandbox = setup_sandbox(scenario, runtime)
        setup = scenario.get("setup", {})
        rc, out, err, dur = invoke_driver(sandbox, runtime, setup.get("cli_model"))
        argv = read_argv_dump(sandbox)
        run = RunResult(
            scenario_name=scenario["name"],
            runtime=runtime,
            returncode=rc,
            stdout=out,
            stderr=err,
            argv_dump=argv,
            duration_s=dur,
        )
        run.assertions = assertions_for(scenario, runtime, run)
        return run
    except Exception as e:
        return RunResult(
            scenario_name=scenario["name"],
            runtime=runtime,
            returncode=-99,
            stdout="",
            stderr="",
            argv_dump=None,
            duration_s=0.0,
            error=f"harness error: {type(e).__name__}: {e}",
        )
    finally:
        if sandbox and sandbox.exists() and not keep_sandbox:
            shutil.rmtree(sandbox, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", default=",".join(RUNTIMES),
                        help="Comma-separated runtimes (default: sh,ts,js,py)")
    parser.add_argument("--scenario", default="",
                        help="Comma-separated scenario names (default: all)")
    parser.add_argument("--keep-sandbox", action="store_true")
    parser.add_argument("--iteration", type=int, default=1)
    args = parser.parse_args()

    runtimes = [r.strip() for r in args.runtime.split(",") if r.strip()]
    bad = [r for r in runtimes if r not in RUNTIMES]
    if bad:
        print(f"Unknown runtime(s): {bad}. Valid: {RUNTIMES}", file=sys.stderr)
        return 2

    spec = json.loads((HERE / "evals.json").read_text(encoding="utf-8"))
    all_scenarios = spec["evals"]
    if args.scenario:
        wanted = {n.strip() for n in args.scenario.split(",") if n.strip()}
        scenarios = [s for s in all_scenarios if s["name"] in wanted]
        unknown = wanted - {s["name"] for s in scenarios}
        if unknown:
            print(f"Unknown scenario(s): {unknown}", file=sys.stderr)
            return 2
    else:
        scenarios = all_scenarios

    out_dir = RESULTS_ROOT / f"iteration-{args.iteration}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running {len(scenarios)} scenario(s) across {len(runtimes)} runtime(s)...")
    print(f"Output: {out_dir}\n")

    runs: list[RunResult] = []
    for scenario in scenarios:
        for runtime in runtimes:
            print(f"  [{runtime}] {scenario['name']} ... ", end="", flush=True)
            run = run_one(scenario, runtime, args.keep_sandbox)
            runs.append(run)
            passed = run.all_passed
            print(("PASS" if passed else "FAIL") + f"  ({run.duration_s:.1f}s)")
            # write per-run grading.json (skill-creator schema)
            run_dir = out_dir / f"{scenario['id']:02d}-{scenario['name']}" / runtime
            run_dir.mkdir(parents=True, exist_ok=True)
            grading = {
                "expectations": [
                    {"text": a.text, "passed": a.passed, "evidence": a.evidence}
                    for a in run.assertions
                ],
            }
            (run_dir / "grading.json").write_text(
                json.dumps(grading, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            (run_dir / "stderr.txt").write_text(run.stderr, encoding="utf-8")
            (run_dir / "stdout.txt").write_text(run.stdout, encoding="utf-8")
            if run.argv_dump is not None:
                (run_dir / "argv_dump.json").write_text(
                    json.dumps({"argv": run.argv_dump}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

    # Aggregate
    write_markdown_report(out_dir, scenarios, runtimes, runs)
    write_json_summary(out_dir, scenarios, runtimes, runs)

    failed = [r for r in runs if not r.all_passed]
    print()
    print(f"Total: {len(runs)} runs, {len(runs) - len(failed)} pass, {len(failed)} fail")
    print(f"Report: {out_dir / 'benchmark.md'}")
    return 0 if not failed else 1


def write_markdown_report(out_dir: Path, scenarios: list[dict], runtimes: list[str], runs: list[RunResult]) -> None:
    lines: list[str] = []
    lines.append("# meta-ralph runner-focused eval — iteration results\n")
    lines.append(f"Runtimes tested: {', '.join(runtimes)}\n")
    lines.append(f"Scenarios: {len(scenarios)}\n")
    lines.append(f"Total runs: {len(runs)}\n")
    passed_runs = sum(1 for r in runs if r.all_passed)
    lines.append(f"**Overall: {passed_runs}/{len(runs)} pass**\n\n")

    # Per-runtime summary
    lines.append("## Per-runtime summary\n")
    lines.append("| Runtime | Pass | Fail | Pass rate |\n")
    lines.append("|---|---|---|---|\n")
    for rt in runtimes:
        rt_runs = [r for r in runs if r.runtime == rt]
        rt_pass = sum(1 for r in rt_runs if r.all_passed)
        rate = (rt_pass / len(rt_runs) * 100) if rt_runs else 0
        lines.append(f"| {rt} | {rt_pass} | {len(rt_runs) - rt_pass} | {rate:.0f}% |\n")
    lines.append("\n")

    # Per-scenario matrix
    lines.append("## Per-scenario × runtime matrix\n")
    lines.append("| # | Scenario | " + " | ".join(runtimes) + " |\n")
    lines.append("|---|" + "---|" * (len(runtimes) + 1) + "\n")
    for s in scenarios:
        cells = []
        for rt in runtimes:
            r = next((x for x in runs if x.scenario_name == s["name"] and x.runtime == rt), None)
            if r is None:
                cells.append("—")
            elif r.error:
                cells.append("ERR")
            elif r.all_passed:
                cells.append("✅")
            else:
                failed_count = sum(1 for a in r.assertions if not a.passed)
                cells.append(f"❌ {failed_count}")
        lines.append(f"| {s['id']:02d} | `{s['name']}` | " + " | ".join(cells) + " |\n")
    lines.append("\n")

    # Failure details
    failures = [r for r in runs if not r.all_passed]
    if failures:
        lines.append("## Failures\n")
        for r in failures:
            lines.append(f"\n### `{r.scenario_name}` on `{r.runtime}` (exit {r.returncode}, {r.duration_s:.1f}s)\n")
            if r.error:
                lines.append(f"\n**Harness error:** `{r.error}`\n")
                continue
            failed_asserts = [a for a in r.assertions if not a.passed]
            lines.append(f"\n{len(failed_asserts)} of {len(r.assertions)} assertion(s) failed:\n\n")
            for a in failed_asserts:
                lines.append(f"- ❌ {a.text}\n")
                if a.evidence:
                    lines.append(f"  - evidence: `{a.evidence}`\n")
            if r.stderr.strip():
                stderr_short = r.stderr if len(r.stderr) < 1000 else r.stderr[:1000] + "...[truncated]"
                lines.append(f"\n  stderr:\n  ```\n{stderr_short}\n  ```\n")
    else:
        lines.append("## Failures\n\n_(none — all assertions passed across all runtimes)_\n")

    (out_dir / "benchmark.md").write_text("".join(lines), encoding="utf-8")


def write_json_summary(out_dir: Path, scenarios: list[dict], runtimes: list[str], runs: list[RunResult]) -> None:
    summary = {
        "scenarios": len(scenarios),
        "runtimes": runtimes,
        "total_runs": len(runs),
        "passed": sum(1 for r in runs if r.all_passed),
        "failed": sum(1 for r in runs if not r.all_passed),
        "by_runtime": {
            rt: {
                "pass": sum(1 for r in runs if r.runtime == rt and r.all_passed),
                "fail": sum(1 for r in runs if r.runtime == rt and not r.all_passed),
            }
            for rt in runtimes
        },
        "runs": [
            {
                "scenario": r.scenario_name,
                "runtime": r.runtime,
                "returncode": r.returncode,
                "duration_s": round(r.duration_s, 2),
                "passed": r.all_passed,
                "error": r.error,
                "assertions": [
                    {"text": a.text, "passed": a.passed, "evidence": a.evidence}
                    for a in r.assertions
                ],
            }
            for r in runs
        ],
    }
    (out_dir / "results.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
