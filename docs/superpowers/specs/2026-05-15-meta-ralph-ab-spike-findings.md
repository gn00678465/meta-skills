# meta-ralph A/B spike — findings

**Date:** 2026-05-15
**Branch:** `exp/meta-ralph-ab`
**Goal:** empirically falsify the two highest-risk findings from the copilot `gpt-5.4` re-audit (B1 = skill-host semantics, A1 = SKILL's interactive gates) before committing to the harness design.

## What was run

Single manual invocation, one fixture (`boot-sh-claude-en`-equivalent), variant A only:

```bash
SANDBOX=$(mktemp -d -t ralph-spike-XXXXXX)
cd "$SANDBOX"
git init -q -b main
git config user.email spike@local && git config user.name spike
git config core.autocrlf false
git commit --allow-empty -q -m init

claude \
  --plugin-dir 'D:\Skills\meta-skills\plugins\meta-ralph' \
  --add-dir . \
  --allowedTools "Read Write Edit Bash" \
  --disallowedTools "WebFetch WebSearch" \
  --output-format json \
  -p 'set up ralph for a TodoMVC app using claude with the sh runtime. Proceed without asking confirmation questions; use the choices stated in this prompt and reasonable defaults for anything else.' \
  > stdout.json 2> stderr.txt
```

Key change vs the spec's original invocation: **`--plugin-dir` instead of `--append-system-prompt`**. This was a discovery made while preparing the spike (`claude --help` revealed `--plugin-dir <path>` — "Load a plugin from a directory or .zip for this session only").

## Result

Scaffold was produced in full. Files present in sandbox after run:

```
prd.json              5,097 bytes
.ralph/ralph.sh      21,568 bytes  (executable)
.ralph/prompt.md     10,879 bytes
.ralph/RUNBOOK.md    20,197 bytes
.ralph/progress.txt      21 bytes
.gitignore              108 bytes
```

Validation:

- `prd.json` has all five required top-level keys (`project`, `branchName`, `description`, `runner`, `userStories`).
- `runner.command = "claude"`, `runner.args = ["-p", "{PROMPT}", "--dangerously-skip-permissions"]` — matches the spec's expected runner shape.
- Six user stories generated for TodoMVC, each with `id`, `title`, `description`, `acceptanceCriteria` (4 items each), `priority`, `status: "todo"`, `notes: ""`. Well-formed acceptance criteria reference real TodoMVC DOM structure (`section.todoapp`, `ul.todo-list`, `.new-todo`, etc.).
- `ralph.sh` is 460 lines — matches the template byte-shape (LF endings, executable bit set).
- `.gitignore` contains exactly the expected six runtime sentinels (`.ralph/progress.txt`, `.ralph/.lock`, `.ralph/.complete`, `.ralph/.commit-failure`, `.ralph/.stop`, and a header line).

No interactive question was emitted by the agent. The "Proceed without asking confirmation questions" boilerplate plus the inline declarations (`TodoMVC` / `claude` / `sh runtime`) gave the SKILL enough to pick all defaults silently.

## Falsified concerns

| Audit finding | Empirical result |
|---|---|
| **B1** — pasting SKILL.md via `--append-system-prompt` doesn't trigger real skill loading | **FALSIFIED**, but via a different mechanism — `--plugin-dir` loads the plugin with full skill-host semantics (frontmatter parsed, trigger phrase matched against description, plugin's `templates/`/`scripts/`/`reference/` accessible from the agent's working tree). The original spec's `--append-system-prompt` invocation model is wrong; the correct model is `--plugin-dir`. |
| **A1** — fixture prompts can't satisfy SKILL's required interactive gates (Q1-Q6, draft approval, etc.) | **FALSIFIED for the happy path** — when the prompt contains the decision inputs (app type + agent CLI + runtime) plus a "proceed without confirmation" directive, the SKILL silently defaulted through Q1-Q6 and produced the scaffold in one turn. Adversarial or ambiguous prompts may still stall; that risk remains but it's not a fixture-design dead end. |

## Confirmed concerns (still open)

- **Unknown turn-around time** — the claude process kept running for 60+ min after the scaffold was written. Output buffering meant `stdout.json` was 0 bytes until the process exited. The harness needs an explicit "scaffold complete" detection (e.g. once `prd.json` + `.ralph/ralph.<ext>` both exist on disk, the run is logically done) and a hard kill so we don't burn unbounded API time. Per-fixture wall-time cap in the spec (180s for bootstrap) addresses cost but not flush — we still need to read partial stdout from a killed process or rely on a sentinel file.
- **Amend mode (B2) untested** — only bootstrap was exercised. The audit's claim that amend won't work without `--amend` and a fuller preset still needs validation.

## Implications for the spec

Required edits before plan-out:

1. **Replace the agent-invocation section** — drop `--append-system-prompt "<SKILL contents>"`, drop the sandbox-bridge prompt, drop `CLAUDE_SKILL_DIR`. Use `--plugin-dir <variant skill plugin dir>` instead. The variant's plugin dir is the parent containing both `.claude-plugin/plugin.json` and `skills/<name>/SKILL.md` — for variant B this means we need a parallel plugin tree (`plugins/meta-ralph-b/`), not just a parallel skill dir.
2. **Update the directory layout** — variant B becomes a **plugin**, not just a skill subdir. Layout:
   ```
   plugins/meta-ralph/      # variant A — unchanged
     .claude-plugin/plugin.json
     skills/meta-ralph/SKILL.md
     ...
   plugins/meta-ralph-b/    # variant B — NEW plugin
     .claude-plugin/plugin.json
     skills/meta-ralph/SKILL.md   # the simplified rewrite; same skill name so prompts trigger both
     templates/ -> ../meta-ralph/templates/  (symlink or copy)
     scripts/   -> ../meta-ralph/scripts/
     reference/ -> ../meta-ralph/reference/
   ```
   Same `name: meta-ralph` in B's frontmatter so the trigger phrases route identically.
3. **Adjust grading** — the structure check fields are right (paths confirmed against this spike's output), no change needed beyond the previous round of fixes.
4. **Replace timeout strategy** — current spec uses pure wall-clock per-run. Add a **scaffold-completion sentinel**: after the prompt is sent, the harness poll-watches the sandbox; once `prd.json` AND `.ralph/ralph.<ext>` both exist and `prd.json` parses as valid JSON, the agent has logically completed. The harness then sends SIGTERM, captures whatever stdout/stderr was flushed, and proceeds to grading. The wall-clock timeout becomes the fallback for stuck/failed runs, not the normal exit path.
5. **Amend spike (deferred)** — before plan-out, run a second spike with the `amend-en` fixture and the seed preset to validate that amend mode works through `--plugin-dir` too. If it stalls or bootstraps, the spec needs an additional "how amend mode is activated" section.

## What stays as-is

- Equivalence definition, verdict rules, 40% size threshold, 90 min wall cap — all unaffected.
- Fixture set itself (6 prompts) is fine; just the invocation mechanics change.
- The 5 deferred Open Questions are unaffected.

## Amend-mode spike (second run)

Sandbox seeded with a 2-story `prd.json` + stub `.ralph/` files committed to a fresh git repo. Invocation reused the validated `--plugin-dir` model:

```bash
claude --plugin-dir 'D:\Skills\meta-skills\plugins\meta-ralph' \
       --add-dir . \
       --allowedTools "Read Write Edit Bash" \
       --disallowedTools "WebFetch WebSearch" \
       --output-format json \
       -p 'append two stories to the existing ralph prd: dark mode toggle, keyboard shortcuts. Proceed without asking confirmation questions.'
```

(An earlier attempt phrased the prompt as `"use meta-ralph --amend to append..."` which read like a CLI invocation and tripped the agent into a different fallback; the natural trigger phrase `"append two stories to the existing ralph prd"` matches the SKILL's amend description and works correctly.)

### Result

End-to-end **succeeded**: 26 turns, 200 s wall, $1.38 cost, 9,559 output tokens. After the run:

- `prd.json` has 4 stories: `US-PRESET-1`, `US-PRESET-2`, `US-003`, `US-004` (preset IDs preserved byte-for-byte; new IDs follow A's `^US-\d{3,}$` schema convention).
- `.ralph/ralph.sh`, `.ralph/prompt.md`, `.ralph/RUNBOOK.md`, `.ralph/progress.txt`, `.gitignore` all byte-identical to seed state.
- Agent's result text explicitly confirmed Mode B workflow was followed: "Mode: Amend (append-only on `userStories`)", "Existing .ralph/* untouched. Driver state preserved", "all four hashed `.ralph/*` files match the B1 baseline byte-for-byte → no drift".

### New finding: `Skill` tool dispatch errored

The agent's result text included a candid post-mortem:

> "Skill dispatch: `Skill` tool calls for `meta-ralph:meta-ralph` and `meta-ralph` both errored ('Execute skill' failure). I located the SKILL.md at `D:/Skills/meta-skills/plugins/meta-ralph/skills/meta-ralph/SKILL.md` and followed the Mode B workflow by hand. Worth investigating why the dispatcher rejected both forms."

Almost certainly because the spike's `--allowedTools "Read Write Edit Bash"` does not include `Skill`; the agent's first instinct (call the `Skill` tool) hit a permission wall and it fell back to `Read SKILL.md` + manual execution. Final output was identical to a "proper" Skill-dispatched run as far as the grading rubric cares, so the fixture still passed — but for the harness this matters:

- If `Skill` is omitted from `--allowedTools`, both A and B will fall back to manual reading. That is consistent, so A/B comparison is still fair, but it isn't really testing the Skill-dispatch path.
- If `Skill` is included, dispatch should succeed for both variants (their skill names are identical). This is the path the spec assumed.

The fix is small: add `Skill` to the harness's `--allowedTools` list. The grading rubric doesn't change. Worth confirming on a third spike before harness build, since "Execute skill" failure with `Skill` allowed would be a real claude-CLI bug.

### Confirmed concerns updated

- **Amend mode (B2) — RESOLVED for the happy path.** Natural-language trigger phrase + same `--plugin-dir` invocation reaches Mode B's logic. No `--amend` flag at the CLI level is needed; SKILL routes based on the prompt's semantic content (presence of existing `prd.json` plus an append-style request).
- **Sentinel timeout strategy** — the amend run completed cleanly in 200 s with `exit 0`; no SIGTERM was needed because claude exited on its own once the work was logically done. The bootstrap spike's 60+ min hang was apparently bootstrap-specific (more files to verify / longer plan). Sentinel detection remains the right design for bounded cost, but it may turn out to fire less often than expected.

## Skill-dispatch spike (third run)

Same amend sandbox shape as the second run; only change is `--allowedTools "Skill Read Write Edit Bash"` (added `Skill`).

### Result

| metric | Spike 2 (no `Skill`) | Spike 3 (with `Skill`) | delta |
|---|---|---|---|
| turns | 26 | 18 | −8 |
| wall | 200 s | 162 s | −38 s |
| cost | $1.38 | $1.12 | −$0.26 |
| output tokens | 9559 | 9526 | ≈ |
| dispatch error in result text | "Skill tool calls errored" | _(none)_ | resolved |
| produced 4 stories with presets preserved | ✓ | ✓ | unchanged |

The agent's result text no longer reports a dispatch failure. The ~30 % efficiency improvement is consistent with the agent skipping 8 turns of "Read SKILL.md + reason about the workflow manually" because the Skill tool now hands it the content directly. Spike 3 also surfaced that the SKILL's own pre-flight (`amendFeasible()`) was actually executing — the result mentions it caught the stub `.ralph/prompt.md` and decided to proceed because the user explicitly said to skip confirmations. That is hard evidence the SKILL's Mode B logic ran rather than just being narrated.

### Net cost of the spike series

| spike | scenario | cost |
|---|---|---|
| 1 (bootstrap) | killed before stdout flushed; no cost data captured | unknown (likely ~$1) |
| 2 (amend, no Skill) | 26 turns / 200 s | $1.38 |
| 3 (amend, with Skill) | 18 turns / 162 s | $1.12 |
| **observed total** | | **~$2.50** |

Iteration-1 of the full harness (36 runs) at ~$1.10 average per amend-style run extrapolates to ~$40 in the worst case, dropping toward ~$15-25 once sentinel-completion kills bootstrap runs at scaffold-done. This is well above the spec's $3 estimate; the spec's cost table should be updated when the plan author chooses real iteration parameters.

## Required spec edits from spike 3

- Add `Skill` to the harness `--allowedTools` list (alongside `Read Write Edit Bash`). This is what makes the SKILL's logic actually execute rather than fall back to Read.
- Update the `Estimated cost / iteration` row to reflect spike-observed costs (~$1-2 per run, not the previous $3 total guess).

## Status

All three spikes (bootstrap + amend without Skill + amend with Skill) confirm the experiment is viable. Spec has been updated with the spike-1/spike-2 edits (commit `30ddece`); spike-3 edits (the two bullets above) follow in a separate commit. After those, the spec is ready for `superpowers:writing-plans`.

## Spike 4 — variant B bootstrap (sanity check post-/write-a-skill)

Bootstrap fixture (`boot-sh-claude-en` shape) against the simplified variant B produced by `/write-a-skill` (commit `4506551`, B's SKILL.md = 156 lines / 10,058 chars / 67.8 % smaller than A's).

```bash
claude --plugin-dir 'D:\Skills\meta-skills\plugins\meta-ralph-b' \
       --add-dir . --allowedTools "Skill Read Write Edit Bash" \
       --disallowedTools "WebFetch WebSearch" --output-format json \
       -p 'set up ralph for a TodoMVC app using claude with the sh runtime. Proceed without asking confirmation questions; use the choices stated in this prompt and reasonable defaults for anything else.'
```

### Result

| metric | A (spike 1, killed mid-flight) | B (spike 4, clean exit) |
|---|---|---|
| Exit reason | manual SIGTERM after 60+ min hang | `exit 0` at 170 s |
| Turns | unknown (killed) | 25 |
| Cost | unknown (~$1 partial) | $1.39 |
| Output tokens | unknown | 12,061 |
| `prd.json` stories | 6 (in range 3-8) | 5 (in range 3-8) |
| `runner.command` | `claude` | `claude` (identical) |
| `runner.args` | `["-p","{PROMPT}","--dangerously-skip-permissions"]` | identical |
| `.ralph/ralph.sh` | 460 lines | **460 lines (byte-identical, shared template)** |
| `.ralph/RUNBOOK.md` | 413 lines | **413 lines (byte-identical, shared template)** |
| `.ralph/prompt.md` | 122 lines | 124 lines (close — template + agent-rendered) |
| `.gitignore` | 5 lines | 5 lines |
| Phase 4 verification (estimated) | would pass | would pass |

### Two unexpected observations

1. **B exits cleanly where A hangs.** A's bootstrap spike kept running ~60 min after the scaffold was on disk; B finished naturally with `exit 0` at 170 s. The simpler SKILL gives the agent less surface to linger on (fewer verification phases to over-think, no recursive sub-checklists). This means the sentinel-completion-timeout strategy from the spec may turn out to be unnecessary for variant B — but it remains a necessary safety net for A.
2. **Updated cost projection.** B's bootstrap = $1.39; A's amend = $1.38 (spike 2). Per-run mean ≈ $1.10. 36 runs ≈ **~$25 / iteration**, comfortably inside the spec's revised $15–40 estimate. Original "$3" was off by ~8×.

### Implication for the verdict rule

If B reliably scaffolds at parity with A (one data point so far, but a clean one), the verdict bar of "B loses at most 1 of 3 reps on any fixture" should be passable. The harness implementation can proceed without spec changes — `/write-a-skill`-produced B is empirically a viable candidate.

The remaining unknown is **per-fixture-variance**: this is one shot; we don't yet know if B's pass rate is 3/3 or 2/3 across reps. That's exactly what the full 36-run matrix is designed to measure.

---

## Iteration 1 verdict (2026-05-16)

Full 36-run matrix completed. **Verdict: B maintains functionality.**

### Pass rate matrix

| Fixture | A | B | Delta |
|---|---|---|---|
| boot-sh-claude-en | 2/3 | 2/3 | +0 |
| boot-js-copilot-zh | 3/3 | 3/3 | +0 |
| amend-en | 3/3 | 3/3 | +0 |
| amend-zh | 3/3 | 2/3 | -1 |
| neg-explain | 3/3 | 3/3 | +0 |
| edge-runner-conflict | 3/3 | 2/3 | -1 |
| **Total** | **17/18 (94%)** | **15/18 (83%)** | **-2 across 6 fixtures** |

Worst per-fixture delta is **-1**, well within the verdict rule's `>= -1` ship threshold.

### Size + cost

- A: 425 lines, 31,201 chars, ~7,800 tok
- B: 156 lines, 10,058 chars, ~2,514 tok
- **Size reduction: 67.8%**
- Mean cost per run: A $0.74, B $0.73 (parity)
- Mean wall: A 161 s, B 254 s (B skewed by one amend-zh outlier of 1541 s — see below)

### Watch list

Two fixtures regressed by exactly 1 rep on B:

- **amend-zh rep 0** — `count=2` (B added zero stories instead of one). The other two reps for this fixture passed.
- **edge-runner-conflict rep 0** — RUNBOOK.md + .gitignore missing (B hit wall_timeout before finishing Phase 3 writes). The other two reps passed.

Both regressions are single-run flakes within the verdict's accepted noise floor (1 of 3 reps).

### Known limitations surfaced during the run

1. `proc.communicate()` after SIGTERM has no timeout in `ab_invoke.py`. One amend-zh run lingered 1541 s (claude subprocess held stdout/stderr pipes open after kill). The sentinel did fire — the agent just refused to die. Worth a follow-up to add a hard `proc.wait(timeout=5)` after `proc.kill()`.
2. `boot-sh-claude-en` continues to be the slowest bootstrap fixture; 2 of 6 runs (one per variant) hit the 360 s wall_timeout. Raising to 600 s might recover those, but the verdict held without doing so.

### Bottom line

The simplified B SKILL.md — 67.8% smaller, delegating §11/§12 invariants to SPEC.md — performs at functional parity with A across all 6 fixture types under 3-rep variance. Ship.

---

## Iteration 2 verdict (2026-05-16, after copilot review fixes)

Full 36-run matrix re-run with all 5 copilot-flagged blockers/issues fixed. **Verdict: B maintains functionality** with **exact pass-rate parity** to A.

### Pass rate matrix

| Fixture | A | B | Delta | Change from iter 1 |
|---|---|---|---|---|
| boot-sh-claude-en | 3/3 | 2/3 | -1 | A: 2/3 → 3/3; B: same 2/3 |
| boot-js-copilot-zh | 3/3 | 3/3 | +0 | same |
| amend-en | 3/3 | 3/3 | +0 | same |
| amend-zh | 3/3 | 3/3 | +0 | **B fixed**: 2/3 → 3/3 (Fix 4 amend sentinel) |
| neg-explain | 3/3 | 3/3 | +0 | same |
| edge-runner-conflict | 2/3 | 3/3 | **+1** | **B beats A**: 2/3 → 3/3 |
| **Total** | **17/18 (94%)** | **17/18 (94%)** | **net 0** | iter 1: A 17/18, B 15/18 |

### Cost / wall

- A: mean 168 s, $0.73/run
- B: mean 166 s, $0.71/run (slight cost edge for B; no 1541 s outlier — Fix 2 drain timeout held)
- Total iter-2 cost: ~$26

### How the 5 fixes contributed

| Fix | Iter-1 symptom | Iter-2 outcome |
|---|---|---|
| 1 — Bundle SPEC.md into B | B inferred §11 from training, not actual delegation | SPEC.md now in B's plugin tree; delegation operative |
| 2 — Bounded `proc.communicate` after kill | One amend-zh hung 1541 s | No outliers; max wall = 360 s (the explicit timeout) |
| 3 — `amend_check` enforces §11.1 invariants | An agent could pass amend with duplicate IDs, wrong priority order, mutated existing stories | Stronger gate; A still 6/6 amend, B still 6/6 amend |
| 4 — Amend sentinel requires story count change | B's amend-zh rep 0 killed mid-write after harmless reserialize | B's amend-zh recovered to 3/3 |
| 5 — Harness errors don't count as completed | Inconclusive verdict branch was dead code | `completed_runs` + `errored_runs` now distinct; verdict logic operational |

### Remaining failures (within noise floor)

- **boot-sh-claude-en B rep 1** — agent didn't write `prd.json` at all (different failure mode than iter 1's timeouts; appears to be agent dropping the task)
- **edge-runner-conflict A rep 0** — A missed `RUNBOOK.md` + `.gitignore` (wall-timeout-killed before finishing Phase 3)

Both are 1-of-3-rep flakes; neither pushes any fixture past the verdict's `≥ -1` ship threshold.

### Bottom line

After fixing every blocker the copilot review surfaced, B's simplified SKILL.md performs at **exact pass-rate parity** with A across all 6 fixture types under 3-rep variance, and even **beats A on edge-runner-conflict**. The 67.8% size reduction is now backed by a verdict that doesn't rest on inoperative delegation. Ship.
