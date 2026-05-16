#!/usr/bin/env python3
"""ab_harness.py — regression / A/B driver for meta-ralph SKILL.

Companion to run_evals.py (driver eval suite). Defaults to a single-variant
smoke against the current `meta-ralph` SKILL.md across the fixture set in
ab_fixtures.json. A/B mode is opt-in: scaffold a sibling plugin at
plugins/meta-ralph-b/ (sharing templates/scripts/reference/docs with A) and
pass `--variant A,B` to compare a candidate against the canonical.

The A/B asset-parity check only fires when variant B is in scope.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES_PATH = HERE / "ab_fixtures.json"
DEFAULT_OUTPUT_ROOT = HERE / "ab-results"

PLUGINS_DIR = HERE.parent.parent.parent.parent


def _detect_variants() -> dict[str, Path]:
    """A is always known. B is opt-in — present only when plugins/meta-ralph-b/
    exists on disk (caller scaffolds it for an A/B comparison)."""
    result: dict[str, Path] = {"A": PLUGINS_DIR / "meta-ralph"}
    b_path = PLUGINS_DIR / "meta-ralph-b"
    if b_path.is_dir():
        result["B"] = b_path
    return result


VARIANT_PATHS = _detect_variants()


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
    p.add_argument("--variant", default="A",
                   help="Comma-separated variants to run (default: A, single-variant "
                        "smoke). Pass 'A,B' for A/B comparison; requires "
                        "plugins/meta-ralph-b/ scaffolded.")
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


def load_fixtures(path: Path = FIXTURES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def select_fixtures(doc: dict[str, Any], ids: list[str] | None) -> list[dict[str, Any]]:
    if not ids:
        return doc["fixtures"]
    by_id = {f["id"]: f for f in doc["fixtures"]}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"Unknown fixture(s): {missing}. "
                         f"Known: {list(by_id.keys())}")
    return [by_id[i] for i in ids]


def write_dry_run_report(args: HarnessArgs, fixtures: list[dict[str, Any]], reps: int) -> Path:
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


def preflight() -> dict[str, Any]:
    """Verify external tools and A/B asset parity before any runs.

    Returns a status dict with one entry per required tool plus 'asset_parity'
    and an aggregate 'ok' boolean. The harness aborts the iteration if 'ok'
    is False.
    """
    required = ("claude", "git", "python", "bash", "jq", "bun", "node")
    status: dict[str, Any] = {}
    for tool in required:
        status[tool] = shutil.which(tool) is not None
    if "B" in VARIANT_PATHS:
        import ab_lib
        a_skill = VARIANT_PATHS["A"] / "skills" / "meta-ralph"
        b_skill = VARIANT_PATHS["B"] / "skills" / "meta-ralph"
        a_root = VARIANT_PATHS["A"]
        b_root = VARIANT_PATHS["B"]
        parity = True
        for sub in ("templates", "scripts", "reference"):
            if not (a_skill / sub).exists() or not (b_skill / sub).exists():
                parity = False
                break
            if ab_lib.hash_tree(a_skill / sub) != ab_lib.hash_tree(b_skill / sub):
                parity = False
                break
        if parity:
            a_docs = a_root / "docs"
            b_docs = b_root / "docs"
            if not a_docs.exists() or not b_docs.exists():
                parity = False
            elif ab_lib.hash_tree(a_docs) != ab_lib.hash_tree(b_docs):
                parity = False
        status["asset_parity"] = parity
    else:
        status["asset_parity"] = "n/a (variant B not scaffolded)"
    status["ok"] = all(v for k, v in status.items() if k != "asset_parity") and (
        status["asset_parity"] is True or status["asset_parity"] == "n/a (variant B not scaffolded)"
    )
    return status


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


def _parse_token_usage(stdout: str) -> dict[str, Any]:
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


def _run_one(variant: str, fixture: dict[str, Any], rep_idx: int,
             iter_dir: Path, keep_sandbox: bool) -> dict[str, Any]:
    """Execute one (variant, fixture, rep) cell. Returns the per-run record
    that ab-summary.json eventually consumes."""
    import ab_lib
    import ab_grading
    import ab_invoke
    fid = fixture["id"]
    run_dir = iter_dir / variant / fid / f"rep-{rep_idx}"
    run_dir.mkdir(parents=True, exist_ok=True)
    scaffold_out = run_dir / "scaffold"
    record: dict[str, Any] = {"variant": variant, "fixture": fid, "rep": rep_idx,
                              "expectations": []}

    sandbox = ab_lib.make_sandbox(f"ab-{variant}-{fid}-{rep_idx}-")
    try:
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

        scaffold_out.mkdir(exist_ok=True)
        for rel, content in ab_lib.snapshot_files(sandbox).items():
            dst = scaffold_out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(content)

        exps: list[dict[str, Any]] = []
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


def _skill_md_stats(variant: str) -> dict[str, int]:
    """Lines / chars / approximate token count for the variant's SKILL.md.
    Returns zeros for variants that have no on-disk plugin (e.g. report rendering
    in tests with synthetic records that name an unscaffolded variant)."""
    if variant not in VARIANT_PATHS:
        return {"lines": 0, "chars": 0, "approx_tokens": 0}
    path = VARIANT_PATHS[variant] / "skills" / "meta-ralph" / "SKILL.md"
    if not path.exists():
        return {"lines": 0, "chars": 0, "approx_tokens": 0}
    text = path.read_text(encoding="utf-8")
    return {
        "lines": text.count("\n") + (0 if text.endswith("\n") else 1),
        "chars": len(text),
        "approx_tokens": len(text) // 4,
    }


def _classify_verdict(records: list[dict[str, Any]], fixtures: list[dict[str, Any]],
                      reps: int, variants: list[str]) -> tuple[str, dict[str, int]]:
    """Returns (verdict, watch_list).
    Rules from spec §"Verdict rules":
      - completed < 29 of 36 planned runs  → "inconclusive — rerun"
      - some fixture has B_pass - A_pass ≤ -2 → "B regresses"
      - else → "B maintains functionality"

    A run is "completed" only if it produced grading expectations. Harness
    errors (records carrying an `error` key, or `wall_timeout`/non-zero exit
    with no expectations) do NOT count as completed — they push the verdict
    toward inconclusive instead of being treated as silent FAILs.
    """
    def _is_completed(r: dict[str, Any]) -> bool:
        if "error" in r:
            return False
        if not r.get("expectations"):
            return False
        return "passed" in r

    expected_total = len(variants) * len(fixtures) * reps
    completed = sum(1 for r in records if _is_completed(r))
    if expected_total >= 30 and completed < 29:
        return "inconclusive — rerun", {}

    if "A" not in variants or "B" not in variants:
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


def write_real_run_report(iter_dir: Path, records: list[dict[str, Any]],
                          variants: list[str], fixtures: list[dict[str, Any]],
                          reps: int, started: str) -> None:
    """Render ab-benchmark.md + ab-summary.json from per-run records."""
    iter_dir.mkdir(parents=True, exist_ok=True)
    verdict, watch = _classify_verdict(records, fixtures, reps, variants)

    pass_count: dict[tuple[str, str], int] = {}
    for r in records:
        if not r.get("passed"):
            continue
        pass_count[(r["variant"], r["fixture"])] = pass_count.get(
            (r["variant"], r["fixture"]), 0) + 1

    stats = {v: _skill_md_stats(v) for v in variants}

    aggregates: dict[str, dict[str, Any]] = {}
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
        "completed_runs": sum(1 for r in records
                              if "error" not in r and r.get("expectations")),
        "errored_runs": sum(1 for r in records if "error" in r),
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

    lines: list[str] = []
    lines.append("# meta-ralph A/B test — iteration\n")
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    unknown_variants = [v for v in args.variants if v not in VARIANT_PATHS]
    if unknown_variants:
        print(
            f"[error] unknown variant(s): {unknown_variants}. "
            f"Known: {sorted(VARIANT_PATHS)}. "
            f"Variant B is opt-in — scaffold plugins/meta-ralph-b/ first.",
            file=sys.stderr,
        )
        return 2
    doc = load_fixtures()
    fixtures = select_fixtures(doc, args.fixture_ids)
    reps = args.reps if args.reps is not None else doc["reps_per_fixture"]
    if not args.dry_run:
        pf = preflight()
        if not pf["ok"]:
            print("[preflight] FAIL:", file=sys.stderr)
            for k, v in pf.items():
                if k == "ok":
                    continue
                print(f"  {k}: {v}", file=sys.stderr)
            return 3
    if args.dry_run:
        iter_dir = write_dry_run_report(args, fixtures, reps)
        print(f"[dry-run] report written: {iter_dir}")
        return 0
    iter_dir = args.output_root / f"iteration-{args.iteration}"
    iter_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
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


if __name__ == "__main__":
    raise SystemExit(main())
