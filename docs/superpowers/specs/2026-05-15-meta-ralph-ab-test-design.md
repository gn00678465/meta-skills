# meta-ralph A/B test — design

**Status:** ready for plan (3 spikes complete, all spike-driven edits applied)
**Date:** 2026-05-15
**Branch:** `exp/meta-ralph-ab` (off `fix/meta-ralph`)
**Owner:** Madao
**Companion docs:** [`2026-05-15-meta-ralph-ab-spike-findings.md`](2026-05-15-meta-ralph-ab-spike-findings.md) (bootstrap-path spike that validated `--plugin-dir` as the invocation model)

## Goal

Compare two SKILL.md implementations of `meta-ralph`:

- **A** — current `plugins/meta-ralph/skills/meta-ralph/SKILL.md` (425 lines / 31,626 chars).
- **B** — a simplified rewrite produced by `/write-a-skill`, targeting ≤ 100 lines while preserving every functional behaviour A guarantees.

The A/B test must answer **one question per dimension**, all three at once:

1. **Equivalence** — does B's SKILL.md scaffold the same artefacts A does, and do those artefacts pass the existing driver eval suite?
2. **Size** — how much smaller is B (lines / chars / estimated tokens)?
3. **Execution pass rate** — when a real agent runs each variant against a fixed fixture set, how often does each variant succeed?

If B clears the verdict bar (defined under "Verdict rules") **and** is at least 40% smaller than A by char count, B replaces A. Otherwise A stays. The 40% threshold is the operational meaning of "meaningfully smaller" for this experiment.

## Non-goals

- **Not** measuring cross-skill trigger-description routing precision/recall (i.e., would an agent pick this skill over other installed skills). Both variants share the same `description` block where possible. The one negative fixture (`neg-explain`) is an **in-skill containment** test — given the skill is already loaded, does the agent correctly refuse to scaffold when the prompt explicitly forbids it — not a routing-accuracy test.
- **Not** rewriting `templates/`, `scripts/`, or `reference/`. Only `SKILL.md` differs between A and B — material is shared so "functional equivalence" is a property of instructions, not assets.
- **Not** a CI gate. This harness runs on demand by Madao; results live in the repo for reference but do not block PRs.

## Constraints

- A's `SKILL.md`, `SPEC.md`, `templates/`, `scripts/`, `reference/`, and `evals/evals.json` remain byte-identical. The only modification to A's evals tree is **two added CLI flags** on `run_evals.py`: `--driver-from <path>` (read driver from a custom path) and `--output-dir <path>` (write results to a custom dir). Both default to current behaviour when omitted; default invocation must still produce 48/48 green on the existing driver scenarios.
- B must reuse A's `templates/`, `scripts/`, and `reference/` directories (via symlink or per-iteration copy; harness is responsible for ensuring B can find them when the agent invokes them).
- All harness file writes use LF line endings (consistency with existing eval infrastructure on Windows).
- Tests are reproducible from `pwsh` and `bash` invocations on Windows 11 (the dev environment). Linux compatibility is incidental.

## Architecture

### Git & directory layout

The 2026-05-15 spike (see `2026-05-15-meta-ralph-ab-spike-findings.md`) established that the real invocation mechanism is `claude --plugin-dir <plugin path>`, not `--append-system-prompt + paste SKILL contents`. Variant B is therefore packaged as a **sibling plugin** with its own `.claude-plugin/plugin.json`, not as a second skill directory under A's plugin. Both plugins declare the same skill `name: meta-ralph` in their SKILL.md frontmatter so the trigger phrases route identically — the harness selects which one loads by passing `--plugin-dir <A>` or `--plugin-dir <B>`.

```
exp/meta-ralph-ab branch:
  plugins/meta-ralph/             # variant A — plugin tree, unchanged
    .claude-plugin/plugin.json
    skills/meta-ralph/
      SKILL.md
      SPEC.md
      templates/
      scripts/
      reference/
      evals/                      # existing driver eval suite
        run_evals.py              # patched: +2 flags (--driver-from, --output-dir)
        evals.json
        mock-agent.py
        ab_harness.py             # NEW
        ab_fixtures.json          # NEW
        ab_lib.py                 # NEW — shared sandbox utils
        ab-results/               # NEW — output (gitignored except summary)
  plugins/meta-ralph-b/           # variant B — NEW sibling plugin
    .claude-plugin/plugin.json    # name distinct from A, skill name same
    skills/meta-ralph/
      SKILL.md                    # ≤ 100 lines, generated via /write-a-skill;
                                  # frontmatter name = "meta-ralph"
      templates  -> ../../../meta-ralph/skills/meta-ralph/templates
      scripts    -> ../../../meta-ralph/skills/meta-ralph/scripts
      reference  -> ../../../meta-ralph/skills/meta-ralph/reference
```

**Symlink portability note:** On Windows, the symlinks require either Developer Mode or admin. Fallback: B's setup script does a recursive copy at branch-init time. The harness verifies asset parity at startup (B's `templates/`, `scripts/`, `reference/` must hash-match A's) and aborts if drift is detected.

**Why two plugins with the same skill name:** claude CLI's `--plugin-dir` loads a plugin's manifest and discovers its skills. Two plugins can declare the same skill name; whichever plugin is loaded for a given invocation provides that skill's body. By passing exactly one `--plugin-dir` per harness run, the agent sees exactly one `meta-ralph` SKILL (either A's or B's) and the trigger-phrase routing stays identical.

### Harness file layout

```
evals/ab-results/iteration-<N>/
  ab-benchmark.md              # human-readable A/B report
  ab-summary.json              # machine-readable
  <variant>/<fixture>/<rep>/
    scaffold/                  # agent's actual produced files
      prd.json
      .ralph/
        ralph.<ext>
        prompt.md
        RUNBOOK.md
        progress.txt
      .gitignore
    stdout.txt
    stderr.txt
    grading.json               # skill-creator schema, one expectation per assertion
    driver-eval/               # nested run_evals output (only when driver_eval_required)
      benchmark.md
      results.json
```

`ab-results/` is gitignored except for `ab-results/iteration-*/ab-benchmark.md` and `ab-summary.json` — those two stay in git so PR reviewers can see the verdict without re-running.

## Components

### 1. `ab_fixtures.json`

Six fixtures spanning bootstrap, amend, and edge/negative cases. Single source of truth for prompts and expected outcomes.

```json
{
  "version": 1,
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
          "runner.command_contains": "claude",
          "min_user_stories": 3,
          "max_user_stories": 8,
          "runtime": "sh"
        },
        "driver_eval_required": true,
        "amend_mode": false
      }
    },
    {
      "id": "boot-ts-copilot-zh",
      "kind": "bootstrap",
      "prompt": "幫我初始化 ralph，agent 用 copilot，runtime 用 ts，專案是一個 Markdown 編輯器。請直接完成、不要問確認問題；prompt 沒講到的細節用合理預設值。",
      "wall_timeout_s": 180,
      "expected": {
        "should_trigger_skill": true,
        "files_required": ["prd.json", ".ralph/ralph.ts", ".ralph/prompt.md", ".ralph/RUNBOOK.md", ".ralph/progress.txt", ".gitignore"],
        "prd_constraints": {
          "runner.command_contains": "copilot",
          "min_user_stories": 3,
          "max_user_stories": 8,
          "runtime": "ts"
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
          "runner.command_contains": "gemini",
          "min_user_stories": 1,
          "max_user_stories": 8,
          "runtime": "py"
        },
        "driver_eval_required": true,
        "amend_mode": false
      }
    }
  ],
  "reps_per_fixture": 3,
  "rep_seed_suffix": ["", " (seed:2)", " (seed:3)"]
}
```

**Preset `seed-prd-with-2-stories`** is a fixed `prd.json` (committed under `evals/ab_presets/`) the harness drops into the sandbox before invoking the amend fixtures, so the agent actually has something to amend. The preset's two stories have ids `US-PRESET-1` and `US-PRESET-2`; the harness asserts both ids still appear in the produced `prd.json` to satisfy `preserves_initial_story_ids`.

### 2. `ab_lib.py`

New helper module used **only** by `ab_harness.py`. Public surface:

- `make_sandbox(prefix: str) -> Path` — temp dir, `git init -b main`, empty commit, `core.autocrlf=false`.
- `seed_preset(sandbox: Path, preset_name: str) -> None` — copy a preset prd.json into the sandbox before agent invocation.
- `snapshot_files(sandbox: Path) -> dict[str, bytes]` — capture all files relative to sandbox root (used for amend's `files_forbidden_to_change` check).
- `cleanup(sandbox: Path, keep: bool) -> None`.

`run_evals.py` is **not** refactored — `ab_lib.py` reimplements the minimum it needs in ~30 lines. Avoiding the refactor keeps the constraint "A's eval suite untouched" honest. The small duplication is acceptable given the harness is a self-contained sidecar.

### 3. `ab_harness.py`

Main A/B driver. CLI:

```
python ab_harness.py
    [--variant A,B]            # default: both
    [--fixture <ids>]          # default: all 6
    [--reps N]                 # default: 3
    [--iteration N]            # output dir suffix; default: auto-increment
    [--dry-run]                # skip LLM, run structure+size only
    [--keep-sandbox]
```

**Per-run flow:**

1. `make_sandbox()` → sandbox path.
2. If `fixture.preset` set → `seed_preset(sandbox, preset_name)`.
3. `invoke_agent(sandbox, variant, fixture, rep_seed_suffix)`:
   - Spawn `claude` CLI from inside `<sandbox>` (cwd = sandbox) with:
     - `--plugin-dir <plugins/meta-ralph or plugins/meta-ralph-b>` — loads the variant's plugin manifest and registers its `meta-ralph` skill. This is the spike-validated mechanism for skill-host parity.
     - `--add-dir <sandbox>` — explicit (cwd is already sandbox; this just removes any ambiguity).
     - `--allowedTools "Skill Read Write Edit Bash"` — `Skill` must be present or the agent falls back to Read + manual workflow simulation (spike 2 vs spike 3 showed a ~30% efficiency gap from this single flag).
     - `--disallowedTools "WebFetch WebSearch"`
     - `--output-format json` — single JSON result on stdout at exit; harness parses it for token usage / cost when present.
     - `-p "<fixture prompt + rep suffix>"`
   - No `--append-system-prompt`, no `CLAUDE_SKILL_DIR`, no sandbox bridge prompt. The plugin loader handles all of that. The fixture prompt itself contains the project description plus the standard "Proceed without asking confirmation questions" boilerplate.
   - **Completion detection (sentinel-based, primary path):** a watcher thread poll-checks the sandbox every 1 s; once both `prd.json` exists AND (`.ralph/ralph.<ext>` exists OR `amend_mode == true`) AND `prd.json` parses as valid JSON, the scaffold is logically complete. The watcher then sends SIGTERM to the agent process and waits up to 5 s for graceful exit before SIGKILL.
   - **Wall-clock timeout (fallback path):** `fixture.wall_timeout_s` kicks in only if the sentinel never fires (agent stuck or never started writing). The spike showed claude can run 60+ minutes after the scaffold is on disk; sentinel detection is what keeps cost bounded under normal happy-path conditions.
   - Capture stdout / stderr / exit code / wall-time / token usage (parsed from final JSON if available).
4. `snapshot_files(sandbox)` → copy produced files to `ab-results/<iter>/<variant>/<fixture>/<rep>/scaffold/`.
5. `grade(sandbox, fixture, run_artifacts)`:
   - **Structure check** — schema-validate `prd.json` against `templates/prd.schema.json`; verify `files_required` exist; verify `prd_constraints`.
   - **Amend check** (if `amend_mode == true`) — diff snapshot pre/post; assert `files_forbidden_to_change` byte-identical; assert initial story ids preserved.
   - **Negative check** (if `should_trigger_skill == false`) — assert no files added.
   - **Behaviour check** (if `driver_eval_required == true`) — invoke `run_evals.py --driver-from <scaffold>/ --output-dir <run dir>/driver-eval/ --runtime <expected.runtime>`; pass = 12/12 scenarios green.
   - Write `grading.json` (skill-creator schema: `expectations: [{text, passed, evidence}]`).
6. `cleanup(sandbox, keep=args.keep_sandbox)`.

**Safety invariants:**

- Sandbox always under `tempfile.mkdtemp()` — never reuses cwd.
- Negative fixture: sentinel detection is disabled (it expects files never to appear). Wall-clock timeout is the only exit path; if any file appears in the sandbox, fixture fails immediately and the agent is SIGTERMed.
- Negative fixture additionally asserts `git status --porcelain` is clean inside sandbox after the run.
- All exceptions caught per-run; failure of one (variant, fixture, rep) never aborts the matrix.
- 90-minute total wall-time cap on the whole `ab_harness.py` invocation; on timeout, partial report is still produced.
- Pre-flight checks before spawning runs (any failure aborts the whole iteration with a clear message): `claude --version`, `git --version`, plus tools required by the fixtures' runtime: `bash` + `jq` (sh), `bun` (ts), `node` (js if used), `python` (py).

### 4. Minimal `run_evals.py` patch — two new flags

Two flags are added, both default to `None`; behaviour with neither set is byte-identical to today.

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

Conditional logic:

- `--driver-from` unset → existing behaviour (read driver from `templates/ralph/ralph.<ext>.tpl`).
- `--driver-from <path>` set → read from `<path>/.ralph/ralph.<ext>`; abort with a clear error if the file doesn't exist.
- `--output-dir` unset → existing `RESULTS_ROOT / f"iteration-{args.iteration}"` path.
- `--output-dir <path>` set → write all `benchmark.md` / `results.json` / per-scenario subdirs there.

Validation: before-and-after the patch lands, the default invocation `python run_evals.py` must produce the same 12 × 4 = 48 green report. Verified by re-running the driver eval suite immediately after applying the patch.

## Equivalence definition

"Functional equivalence" in this spec means **statistical equivalence within tolerance**, not byte-identical output. A single run is **equivalent** (a "pass") when:

1. Structure check passes (schema + required files + prd_constraints).
2. If amend mode: preserved-files / preserved-story-ids checks pass.
3. If negative: scaffold is empty.
4. If `driver_eval_required`: nested `run_evals.py --driver-from <scaffold> --output-dir <run dir>/driver-eval/` reports 12/12 for the expected runtime.

A run **fails** if any of the above fails or the agent times out. Variance across the 3 reps is expected; the verdict rules (below) translate per-fixture pass counts into a keep/replace decision.

## Verdict rules

For each fixture, compute `(B passes) - (A passes)` across the 3 reps.

| Condition | Verdict |
|---|---|
| `min((B passes) - (A passes)) >= -1` across **all** fixtures (B loses at most 1 of 3 reps on any fixture, mirroring random LLM variance) | **B maintains functionality** |
| `min((B passes) - (A passes)) <= -2` on any fixture | **B regresses** |
| Harness completed `< 29` of the 36 planned runs (timeouts / crashes) | **inconclusive — rerun** |

Size dimension is always reported but never disqualifies — a smaller B that regresses behaviour is still a regression. Verdict scales with confidence; a borderline B (e.g. -1 on two fixtures) is flagged in the report's "watch list" even if rule classifies it as maintained.

## Report format (`ab-benchmark.md`)

```markdown
# meta-ralph A/B test — iteration <N>

## Summary
- Variant A: plugins/meta-ralph/skills/meta-ralph/SKILL.md (425 lines, 31,626 chars, ~7,907 tok)
- Variant B: plugins/meta-ralph/skills/meta-ralph-b/SKILL.md (<XXX> lines, <XXX> chars, ~<XXX> tok)
- Size reduction: <XX.X>%
- **Verdict: <B maintains functionality | B regresses | inconclusive>**

## Pass rate matrix
| Fixture | A (3 reps) | B (3 reps) | Delta |
|---|---|---|---|
| boot-sh-claude-en    | 3/3 | <X>/3 | <±N> |
| boot-ts-copilot-zh   | 3/3 | <X>/3 | <±N> |
| amend-en             | 3/3 | <X>/3 | <±N> |
| amend-zh             | 3/3 | <X>/3 | <±N> |
| neg-explain          | 3/3 | <X>/3 | <±N> |
| edge-runner-conflict | <X>/3 | <X>/3 | <±N> |

## Per-dimension breakdown
| Dimension | A | B |
|---|---|---|
| Structure pass rate | <XX>% | <XX>% |
| Behaviour (driver eval) pass rate | <XX>% | <XX>% |
| Negative containment | <XX>% | <XX>% |
| SKILL.md size (lines) | 425 | <XXX> |
| SKILL.md size (chars) | 31,626 | <XXX> |
| Mean wall-time / run (s) | <XX.X> | <XX.X> |
| Mean tokens / run (est.) | <XXX> | <XXX> |

## Watch list
<fixtures where delta == -1 across reps — borderline cases>

## Failures
### <fixture> rep <N> on variant <V>
- Failed expectations: <list>
- stderr excerpt: <first 10 lines>
- Artifact path: ab-results/iteration-<N>/<V>/<fixture>/<N>/
```

`ab-summary.json` mirrors the same data in machine form: variant metadata, per-fixture pass rates, per-dimension aggregates, verdict, and pointers into the artifact tree.

## Cost & safety

| Control | Value |
|---|---|
| Primary completion gate | Scaffold-completion sentinel (poll-watch sandbox; SIGTERM agent once `prd.json` + driver file are on disk and JSON parses) |
| Per-run wall-clock (fallback) | 60s (negative) / 90s (amend) / 180s (bootstrap) — only kicks in if sentinel never fires |
| Per-iteration total wall-clock | 90 min hard cap (worst-case sum of per-run timeouts is ~78 min for 36 runs; in practice sentinels should keep total well under this) |
| Disallowed tools | WebFetch, WebSearch |
| Sandbox location | `tempfile.mkdtemp()` only — never cwd |
| Estimated cost / iteration | **~$15–40 per 36-run iteration** based on the three spikes (one amend run observed at $1.12; bootstrap likely higher due to more turns). Original "$3" estimate was off by ≥5x. Sentinel-completion should pull bootstrap costs down toward the lower end. Re-measure after iteration 1. |
| Pre-flight | `claude --version` + `git --version` + runtime tools (`bash`+`jq`, `bun`, `node`, `python`) check before spawning runs |
| `--dry-run` mode | size + structure only; for harness development |

## Iteration plan

1. **Iteration 0** — build harness with `--dry-run` and a stub B (copy of A) to validate plumbing. No LLM calls. Verifies grading + reporting.
2. **Iteration 1** — produce B via `/write-a-skill` (interactive session, Madao + `/write-a-skill`). Commit B to `exp/meta-ralph-ab`. Run full 36-run matrix. Read verdict.
3. **If B maintains** — open PR `exp/meta-ralph-ab → main` with the benchmark.md inline. Reviewer can re-run.
4. **If B regresses** — read failure details, manually edit B to plug the gap (typically a missing phase the simplification dropped), iterate. Stop after 3 attempts; if still failing, retire the experiment.

## Open questions

Surfaced by the copilot `gpt-5.4` audit (2026-05-15) and left for resolution before or during planning:

1. **No `js` runtime fixture** — A supports `sh`/`ts`/`js`/`py` driver templates; the current fixture set only exercises `sh`, `ts`, `py`. Decide whether to (a) add a 7th fixture covering `js` (and the `.ralph/package.json` it emits), or (b) accept that `js` parity is covered transitively by the driver eval suite already.
2. **`rep_seed_suffix` semantic leakage** — appending ` (seed:2)` / ` (seed:3)` to fixture prompts may bleed into generated artefacts (branch slug, story descriptions, RUNBOOK). Decide between (a) keep current approach and tolerate cosmetic leakage, (b) switch to an out-of-band seed channel (env var, temperature override), or (c) drop reps and accept higher single-shot variance.
3. **Asset-parity machinery scope** — symlink + recursive-copy fallback + content-hash verification is heavy for an experiment where only `SKILL.md` differs. Decide whether to (a) keep all three mechanisms, (b) require symlinks and abort if unsupported (Windows Developer Mode), or (c) always copy and skip parity verification (B is rebuilt clean per iteration).
4. **Token / cost metrics' value** — `mean tokens per run` and `~$3 cost estimate` are in the report but never enter the verdict. Decide whether to (a) keep as observability, (b) drop entirely to simplify the harness, or (c) promote into a fourth verdict dimension (only if claude CLI emits token counts reliably).
5. **Committing `ab-results/iteration-*/` summaries** — currently the plan keeps `ab-benchmark.md` and `ab-summary.json` per iteration in git. Decide whether to (a) keep all iterations (history of attempts), (b) keep only the final accepted iteration, or (c) gitignore everything and rely on PR description for the verdict.

These do not block writing the implementation plan — each has a defensible default. They are surfaced so the plan author chooses explicitly rather than implicitly.

## Out of scope (deferred)

- Multi-agent comparison (copilot / gemini variants).
- Trigger-accuracy precision/recall harness across many skills (vs the single in-skill containment fixture this spec includes).
- Cached-scaffold two-stage pipeline (Section 3, option 3 from brainstorming).
- Variance analysis beyond 3 reps (skill-creator's full variance protocol).

Any of these can be added later as separate specs without changing this one.
