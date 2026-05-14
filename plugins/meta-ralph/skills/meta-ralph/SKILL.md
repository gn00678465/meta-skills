---
name: meta-ralph
description: Scaffold (bootstrap) OR amend a ralph autonomous coding loop in a target git repo — writes prd.json + .ralph/prompt.md + .ralph/ralph.<sh|ts|js|py> + RUNBOOK + .gitignore. Pure scaffolder; does NOT execute the loop. Use for first-time setup OR to append more user stories to an existing scaffolded prd.json. Bootstrap trigger phrases: "init ralph", "set up ralph", "scaffold ralph", "bootstrap ralph", "建立 ralph", "初始化 ralph", "ralph 起手". Amend trigger phrases (every phrase MUST carry ralph/prd/meta-ralph context): "append stories to ralph", "add user stories to ralph prd", "extend the ralph prd", "extend ralph backlog", "grow the ralph prd", "在現有 ralph prd 補 stories", "追加 ralph stories", "在 ralph 加 user story", "ralph prd 新增 story". NOT for running an existing ralph loop (use ralph-loop:ralph-loop instead), NOT for explaining what ralph is (informational queries don't need this skill), and NOT for generic PRD editing, backlog grooming, or writing user stories outside an existing meta-ralph scaffold.
argument-hint: "[--amend] [<free-form stories prompt>]"
---

# meta-ralph

Pure scaffolder for the **ralph autonomous coding loop**. Two modes:

- **Mode A — Bootstrap (default).** First-run scaffolding. The user describes what to build, picks agent + runtime, the SKILL writes `prd.json` + `.ralph/*`. Phases 1–4 below.
- **Mode B — Amend (`--amend` flag).** Second invocation; user already has `prd.json` and wants to **append** new user stories. The SKILL only mutates `prd.json` and never touches `.ralph/*`. Phases B1–B4, defined under "Mode B — Amend" near the end of this file.

Self-contained: scaffold steps, verification, and amend flow are all below. User-facing usage notes live in `plugins/meta-ralph/docs/meta-ralph.md`.

## Constraints (non-negotiable)

- **Pure scaffolder.** Do NOT execute the produced `ralph.<ext>`. Do NOT invoke `claude` / `copilot` / `gemini` CLIs. Do NOT run any code under the user's control.
- **Allowed mutations only:** create `prd.json` at repo root; create / write into `.ralph/`; append lines to `.gitignore`. Nothing else.
- **All file writes use LF line endings** (Windows portability — bash scripts with CRLF break).
- **Verification stays passive.** Phase 4 only inspects file content / existence; no test-runs.

## Output (what gets written)

```
target-project/
├── prd.json                ← git tracked
├── .gitignore              ← appended
└── .ralph/
    ├── prompt.md           ← agent instructions, {{MEMORY_FILE}} replaced
    ├── ralph.<sh|ts|js|py> ← loop driver, placeholder replaced, executable
    ├── RUNBOOK.md          ← user-facing intervention guide, {{RUN_COMMAND}} replaced
    ├── progress.txt        ← seeded with `## Codebase Patterns\n`
    └── package.json        ← conditional: runtime=js only; pins CommonJS so .ralph/ralph.js's require() works under parent `"type":"module"` packages
```

Runtime-only files — created by the driver at run time, never written by the SKILL: `.ralph/.lock`, `.ralph/.complete`, `.ralph/.commit-failure`, `.ralph/.stop`.

## Invocation & argument parsing

`$ARGUMENTS` is a Claude Code substitution holding the raw text after the slash-command / trigger phrase. Parse once, before pre-flight, into:

| Field | Rule |
|---|---|
| `mode` | `amend` iff the token `--amend` (case-sensitive, whole-word) appears in `$ARGUMENTS`; else `bootstrap`. |
| `userPrompt` | `$ARGUMENTS` with the `--amend` token (+ adjacent space) stripped. Used as a **prefill hint only**, never as authoritative content. |

Examples:

| `$ARGUMENTS` | mode | userPrompt |
|---|---|---|
| *(empty)* | `bootstrap` | *(empty)* |
| `--amend` | `amend` | *(empty)* |
| `--amend add login flow with OAuth + 2FA` | `amend` | `add login flow with OAuth + 2FA` |
| `init ralph for my CLI tool` | `bootstrap` | `init ralph for my CLI tool` |
| `--AMEND should not match` | `bootstrap` | `--AMEND should not match` |

**Preferred:** invoke the bundled parser, read the JSON line from stdout: `{"mode":"bootstrap"|"amend","userPrompt":"<trimmed remainder>"}`.

| Host | Tool | Command |
|---|---|---|
| POSIX (Linux / macOS / git-bash / WSL) | Bash | `sh "${CLAUDE_SKILL_DIR}/scripts/parse-args.sh" "$ARGUMENTS"` |
| Windows PowerShell | PowerShell | `pwsh -NoProfile -File "${CLAUDE_SKILL_DIR}/scripts/parse-args.ps1" "$ARGUMENTS"` |

`$ARGUMENTS` MUST be double-quoted at the host-shell level so it arrives as a single argument (otherwise multi-word prompts get re-tokenized; stray `--` or metachars leak in). Both scripts apply identical whole-token `--amend` matching and identical JSON escaping for `userPrompt` (`\`, `"`). Full spec in `scripts/parse-args.sh` header.

`${CLAUDE_SKILL_DIR}` resolves to this skill's bundled directory (Claude Code, Codex, Copilot-via-plugin all provide it). Outside CC-style hosts, substitute the absolute path.

**Fallback — POSIX only (when the script is unreachable):**

```sh
mode="bootstrap"
case " $ARGUMENTS " in *" --amend "*) mode="amend" ;; esac
userPrompt=$(printf '%s' "$ARGUMENTS" | sed -E 's/(^| )--amend( |$)/ /g; s/^ +//; s/ +$//; s/  +/ /g')
```

This fallback **MUST NOT** run on Windows PowerShell — `case` / `sed` semantics differ and a hand-port silently mis-parses. If `parse-args.ps1` is unreachable on PowerShell, abort: *"meta-ralph requires either `scripts/parse-args.ps1` or POSIX shell access. Neither reachable; cannot parse $ARGUMENTS safely."*

If `mode=amend` but no `prd.json` exists at repo root → abort: *"--amend requires an existing prd.json. Run meta-ralph without --amend to bootstrap first."*

## Pre-flight (before Phase 1)

Define an `amendFeasible()` predicate (used to decide whether the bootstrap conflict prompt offers an `[A]mend` option):

```
amendFeasible() ⇔
    .ralph/ directory exists
  ∧ .ralph/.lock does NOT exist
  ∧ existing prd.json validates against templates/prd.schema.json
  ∧ existing prd.json has ≤ 1 story with status: in_progress
  ∧ exactly one of .ralph/ralph.{sh,ts,js,py} exists (runtime detectable)
  ∧ .ralph/prompt.md references exactly one of CLAUDE.md / AGENTS.md / GEMINI.md (agent detectable)
  ∧ .ralph/prompt.md exists (required for agent detection above)
  ∧ .ralph/RUNBOOK.md exists (B1 step 4 will hash it; missing = drift baseline broken)
  ∧ .ralph/progress.txt exists (same reason as RUNBOOK.md)
  ∧ if .ralph/ralph.js is the detected runtime, .ralph/package.json exists (B1 step 4 also hashes it under js runtime; missing = drift baseline broken)
```

If any of the last three are missing, `amendFeasible()` returns false → conflict prompt shows 2-way only (`[O]/[X]`) with the specific missing file named, so user knows what's wrong before they pick.

| Check | Bootstrap | Amend |
|---|---|---|
| cwd is a git repo (`git rev-parse --git-dir` succeeds) | abort | abort |
| `prd.json` exists at repo root | (see "conflict prompt" row) | required (else abort per §Invocation) |
| `.ralph/` directory exists | (see "conflict prompt" row) | required (else abort: scaffold first) |
| **Conflict prompt** — `mode=bootstrap` AND (`prd.json` exists OR `.ralph/` exists) | `.ralph/.lock` exists: refuse to prompt; abort with the lock message (see row below) — neither `[A]` nor `[O]` is safe under a live driver. <br>Else if `amendFeasible()`: 3-way `[A]mend / [O]verwrite (destroys progress) / [X]Cancel`. `A` → flip to amend; `O` → continue bootstrap; `X` → abort. <br>Else: 2-way `[O]/[X]`, **and name the specific reason `[A]` is unavailable** (e.g. "prd.json schema-invalid", "agent token unresolved", "prd.json missing required `runner` field — add it manually then amend"). Don't silently swallow the option. | n/a |
| `.ralph/.lock` exists | Fresh bootstrap (no prior `.ralph/`): n/a. <br>Overwrite bootstrap: abort: *"ralph driver appears to be running. Stop it (or `rm .ralph/.lock` if stale) before re-running meta-ralph."* The conflict-prompt row above refuses entirely when `.lock` exists; this row is the reason for that gate. | abort: *"ralph driver appears to be running. Stop it (or `rm .ralph/.lock` if stale) before amending."* |
| `prd.json` validates against `templates/prd.schema.json` | n/a | abort if invalid — refuse to amend a corrupt PRD. **Migration note:** PRDs scaffolded before `runner` was made mandatory will fail here with "missing required property: runner". Report it as a migration error and tell the user to add the runner block (see Agent Config Table for the correct shape per agent), then re-run amend. |
| `prd.json` has ≤ 1 story with `status: in_progress` | n/a | abort — driver-agent invariant violation; user must reconcile |
| Exactly one runtime file under `.ralph/` (`ralph.sh xor .ts xor .js xor .py`) | n/a | abort — print which files were found; ask user to remove the spurious one(s) |
| `.ralph/prompt.md` references exactly one memory file (`CLAUDE.md / AGENTS.md / GEMINI.md`) | n/a | abort — token unresolved (none/multiple); ask user to confirm intended agent |

## Phase 1 — Tool selection

Two questions, validate after each (missing-PATH is a warning, not an abort — user may install later).

**Q-Agent** — `claude` / `copilot` / `gemini`. Check PATH via POSIX `command -v <agent>` or PowerShell `Get-Command <agent> -ErrorAction SilentlyContinue`.

**Q-Runtime** — `sh` / `ts` / `js` / `py`. If Windows + `sh` chosen → warn (needs git-bash or WSL; suggest ts/js/py). PATH checks per runtime: `sh → jq, bash`; `ts → bun`; `js → node`; `py → uv` (or `python3`).

## Phase 2 — Grill (PRD content)

### Pre-Q-1: Auto-detect from existing files

Read whichever of these exist; use as **prefills** for the grill (don't skip questions, just preload defaults):

| File | Extracts |
|---|---|
| `README.md` | top-level description hint |
| `package.json` | `project` ← `name`; quality checks ← `scripts.typecheck/lint/test` |
| `pyproject.toml` | `project` ← `[project] name`; quality checks from `[tool.*]` if obvious |
| `Cargo.toml` | `project` ← `[package] name` |

### Pre-Q-2: Existing requirements doc?

Ask "Do you have a requirements / spec doc to import? (y/n)". On `y`, take path, read, extract user stories, then run Q1–Q6 to fill gaps. On `n`, run Q1–Q6 from scratch.

### Q1–Q6 (ask one at a time, accept prefills)

| # | Question | Maps to PRD field |
|---|---|---|
| Q1 | What are you building? One sentence. | `description` |
| Q2 | Who is the user? What problem does this solve? | extends `description` |
| Q3 | Minimum success criteria? List 3–5 user stories ("user can do X"). | `userStories` draft (one per line) |
| Q4 | Quality check commands? Provide your typecheck / lint / test commands (one each). | injected into `prompt.md` `## Quality Requirements` section |
| Q5 | Branch name? Suggested default: `ralph/<slug-of-Q1>`. | `branchName` |
| Q6 | Project name? Suggested default: from auto-detect or cwd basename. | `project` |

### Draft + approve

Synthesize into a `prd.json` draft (shape per `templates/prd.json.example`). Print, ask "Looks good? (y / edit)". Only proceed to Phase 3 on `y`; on edit, accept changes and re-print.

## Phase 3 — Scaffold (file writes)

Inputs locked at this point: `agent`, `runtime`, approved `prd.json` content, `qualityChecks`.

### Step 0 — Overwrite cleanup (only when conflict prompt picked `[O]`)

When `[O]verwrite` was chosen, prior state may include managed files the upcoming writes won't replace; leftovers break `amendFeasible()`'s "exactly one runtime file" invariant.

Before any write, run cleanup. Treat ENOENT (file not found) as a no-op — fresh-runtime overwrite legitimately drops drivers that were never there. Abort only on real failures (permissions / locked / I/O), with the failing path, **before** any new write:

1. Under `.ralph/`, delete every `ralph.{sh,ts,js,py}` **except** the one matching the chosen `runtime`.
2. `.ralph/package.json`: keep for `runtime == js` (step 9 will rewrite); delete otherwise (stale CommonJS pin).
3. Leave `prd.json`, `.ralph/prompt.md`, `.ralph/RUNBOOK.md`, `.ralph/progress.txt` in place — upcoming writes overwrite deterministically.
4. Never touch `.ralph/.lock|.complete|.commit-failure|.stop` (runtime-only, not the SKILL's).

Skip Step 0 entirely on a fresh scaffold (no prior `prd.json` AND no prior `.ralph/`).

### Step 1 onwards — render and write

Render in this order:

1. **Render `prompt.md`** from `reference/prompt.md` template:
   - Replace `{{MEMORY_FILE}}` (multiple occurrences) with the agent's memory file (see Agent Config Table).
   - Replace `{{QUALITY_CHECKS}}` (single occurrence) with a bullet list. **Always prepend the runtime-specific `prd.json` validity check below as the FIRST bullet** (regardless of Q4 input), then append the user's Q4 commands. Each line prefixed with `- ` and wrapped in backticks.

     | runtime | JSON-validity check |
     |---|---|
     | sh | `jq empty prd.json` |
     | ts | `bun -e "JSON.parse(require('fs').readFileSync('prd.json','utf8'))"` |
     | js | `node -e "JSON.parse(require('fs').readFileSync('prd.json','utf8'))"` |
     | py | `python -c "import json; json.load(open('prd.json'))"` |

     Rationale: text-level edits to `prd.json` (sed / regex) are a known agent-failure mode that halts the loop next iteration. Prepending this check makes `prd.json` validity a quality gate the agent can't skip; step 7b in the rendered prompt.md re-runs the same command after commit.

2. **Write `ralph.<ext>`** verbatim from `templates/ralph/ralph.<ext>.tpl`. The templates contain no agent placeholders — every driver reads `prd.json.runner` (mandatory) for the agent invocation, so no per-agent substitution happens here.
3. **Write `prd.json`** to repo root. Build the document from the approved Phase 2 content plus the **runner** block derived from the chosen agent (see Agent Config Table below). Runner is required by the schema and by every driver.
4. **Create `.ralph/`** if missing.
5. **Write `.ralph/prompt.md`** (rendered step 1).
6. **Write `.ralph/ralph.<ext>`** (rendered step 2). Force LF. `chmod +x` on Unix (no-op on Windows; ts/js/py run via interpreter regardless).
7. **Write `.ralph/progress.txt`** with single line `## Codebase Patterns\n`.
8. **Render `.ralph/RUNBOOK.md`** from `templates/RUNBOOK.md.tpl`. Replace `{{RUN_COMMAND}}` with the runtime's `runtimeCmd` from the **Runtime Command Table**, *without* the `[N]` suffix (runbook adds `N` in context). LF endings.
9. **(runtime=js only)** Write `.ralph/package.json` with `{"type": "commonjs"}\n`. Reason: `.ralph/ralph.js` uses CommonJS `require()`; a parent `"type":"module"` would misinterpret it, but the closer `.ralph/package.json` wins.
10. **Append to `.gitignore`** (create if absent; skip if these lines already present):
    ```
    # ralph runtime files
    .ralph/progress.txt
    .ralph/.lock
    .ralph/.complete
    .ralph/.commit-failure
    .ralph/.stop
    ```
    `.commit-failure` is the commit-repair sentinel (driver writes, agent removes after repair). `.stop` is the graceful-stop sentinel (user touches to drain after current iteration). Both runtime-only.

### Rollback on failure

Rollback removes only files this run **newly created** — never files that already existed and were overwritten (Phase A doesn't snapshot; only Phase B does, so overwrites are unrecoverable here).

**Preparation before any Phase 3 write**: capture an `existedBefore` set — which of `{prd.json, .ralph/, .ralph/prompt.md, .ralph/ralph.{sh,ts,js,py}, .ralph/RUNBOOK.md, .ralph/progress.txt, .ralph/package.json, .gitignore}` exist on disk now. After each successful write, record the path so the rollback list is bounded to this run.

If any Phase 3 write fails, run rollback in reverse Phase 3 order, then re-raise the original error.

Candidate paths (reverse order; each gated on "this run wrote it AND it was NOT in `existedBefore`"):

1. `.gitignore` block — if step 10 appended in this run, strip exactly those lines; never delete pre-existing `.gitignore` content.
2. `.ralph/package.json` — step 9 wrote it AND not in `existedBefore`.
3. `.ralph/RUNBOOK.md` — step 8 wrote it AND not in `existedBefore`.
4. `.ralph/progress.txt` — step 7 wrote it AND not in `existedBefore`.
5. `.ralph/ralph.<ext>` — step 6 wrote it AND not in `existedBefore`.
6. `.ralph/prompt.md` — step 5 wrote it AND not in `existedBefore`.
7. `.ralph/` dir — step 4 created it AND not in `existedBefore` AND now empty.
8. `prd.json` — step 3 wrote it AND not in `existedBefore`.

For any in-`existedBefore` path overwritten before failing: do NOT delete; list under "unrecoverable overwrites" in the abort message. Never remove runtime-only sentinels (`.lock|.complete|.commit-failure|.stop`). On a rollback-deletion failure: log the path, continue. Abort message bundles: original error + unrecoverable-overwrite list + rollback-failure list.

## Phase 4 — Verification (passive checks)

This table is the executable form of the §Output contract at the top of this file — each check confirms one row of that promised output. Keep them in sync: if you add a written artifact, add the matching check; if you drop a check, drop the artifact from §Output.

| # | Check | On failure |
|---|---|---|
| 1 | `prd.json` exists at repo root | abort |
| 2 | `prd.json` validates against `templates/prd.schema.json` (full JSON Schema validation) | abort |
| 3 | `.ralph/prompt.md` exists; no `{{MEMORY_FILE}}` or `{{QUALITY_CHECKS}}` substring remains | abort |
| 4 | `.ralph/ralph.<ext>` exists, executable on Unix | abort |
| 4b | `prd.json.runner` exists with `{command: <non-empty string>, args: <non-empty array of non-empty strings>}` | abort |
| 5 | `.ralph/progress.txt` exists and starts with `## Codebase Patterns` | abort |
| 6 | `.gitignore` contains all 5 ralph runtime lines (`.ralph/progress.txt`, `.ralph/.lock`, `.ralph/.complete`, `.ralph/.commit-failure`, `.ralph/.stop`) | abort |
| 7 | (Runtime=js only) `.ralph/package.json` exists with `"type": "commonjs"` | abort |
| 8 | `.ralph/RUNBOOK.md` exists; no `{{RUN_COMMAND}}` substring remains | abort |
| 9 | Selected agent CLI in PATH | warn only |
| 10 | Selected runtime dependency in PATH (per Phase 1 mapping) | warn only |

## Closing message

Print (substitute `<runtimeCmd>` from the **Runtime Command Table** below according to the chosen runtime):

```
✅ Scaffolded ralph loop for <project>.
   Branch:   <branchName> (will be created/checked out by ralph script)
   Agent:    <agent>
   Runtime:  <runtime>

To start the loop (default: 10 iterations, agent's default model):
   <runtimeCmd>

Override max iterations with `[N]` and/or pin a specific model with `--model X`
(both optional, any order; see RUNBOOK.md §1 for examples).

The script handles branch checkout itself. Make sure your working tree is clean before starting.

If you get stuck: read .ralph/RUNBOOK.md — it covers status inspection, graceful stop,
intervention when the agent loops, and recovery from driver abort messages.

For long runs (>30 min): suppress OS sleep before launching the driver, otherwise
suspend will freeze the agent process and corrupt the iteration on resume.
  - macOS:   `caffeinate -i <run command>` (or run in a separate iTerm tab)
  - Linux:   `systemd-inhibit --what=sleep <run command>` (or disable sleep in settings)
  - Windows: `powercfg /change standby-timeout-ac 0` before launch (restore after).
```

### Runtime Command Table

| runtime | runtimeCmd | notes |
|---|---|---|
| `sh`  | `bash .ralph/ralph.sh [N] [--model X]`     | On Unix you can also `chmod +x .ralph/ralph.sh && ./.ralph/ralph.sh [N] [--model X]`. On Windows requires git-bash or WSL |
| `ts`  | `bun run .ralph/ralph.ts [N] [--model X]`  | Bun ≥ 1.1; the `#!/usr/bin/env bun` shebang only fires on Unix, on Windows you must use `bun run` |
| `js`  | `node .ralph/ralph.js [N] [--model X]`     | Node ≥ 18; `.ralph/package.json` (auto-written for js runtime) pins CommonJS so this works regardless of the parent project's `"type": "module"` |
| `py`  | `uv run .ralph/ralph.py [N] [--model X]`   | Or `python .ralph/ralph.py [N] [--model X]` if `uv` is not installed (Python ≥ 3.11) |

Arguments (any order):
- `[N]` — optional max-iterations; default 10
- `[--model X]` — optional model selector. Driver passes `--model X` to the agent CLI (claude / copilot / gemini all accept `--model`). When `runner.args` already contains `--model` / `--model=*` / `-m` / `-m=*`, the driver strips those (and their values) before appending the CLI's `--model X` — so this flag is a **true override**, not a duplicate-and-hope. When omitted, `runner.args` passes through verbatim. Supports both `--model X` and `--model=X` syntax.

## Agent Config Table (data the SKILL needs)

The scaffolder writes the `runner` block into `prd.json` using the columns below. Drivers consume `runner.command` + `runner.args` verbatim every iteration (no baked default in the driver template; `runner` is mandatory).

| Agent | memoryFile | runner.command | runner.args (JSON array literal, `"{PROMPT}"` sentinel) |
|---|---|---|---|
| `claude` | `CLAUDE.md` | `"claude"` | `["-p", "{PROMPT}", "--dangerously-skip-permissions"]` |
| `copilot` | `AGENTS.md` | `"copilot"` | `["--yolo", "--allow-tools", "--prompt", "{PROMPT}"]` |
| `gemini` | `GEMINI.md` | `"gemini"` | `["-p", "{PROMPT}", "--yolo"]` |

Notes:
- `"{PROMPT}"` is a literal sentinel string inside `args`. The driver replaces it at runtime with the contents of `.ralph/prompt.md`; if it's missing the driver appends the prompt at the end with a stderr warning.
- v1 only supports these 3 agents out-of-the-box. The schema's `runner.command` is open-ended (`aider`, `cursor-agent`, custom wrappers all work) — adding a new "preferred" agent means extending this table.
- Drivers have NO `{{AGENT_CLI}}` / `{{AGENT_ARGV}}` placeholders. There is no fallback if `prd.json.runner` is missing — the driver aborts with a migration message.

## Runtime configuration (`prd.json.runner`)

The `runner` block in `prd.json` is **required**. It's the single source of truth for how the agent CLI is spawned each iteration:

```json
{
  "runner": {
    "command": "claude",
    "args": ["-p", "{PROMPT}", "--model", "opus", "--dangerously-skip-permissions"]
  }
}
```

Rules (enforced by `prd.schema.json` + every driver):

- **All-or-nothing shape.** `command` is a non-empty string; `args` is a non-empty array of non-empty strings.
- **`{PROMPT}` sentinel** in `args` is replaced at runtime with `.ralph/prompt.md` content; if absent, prompt is appended at the end with a stderr warning.
- **Precedence — driver CLI `--model X` is a true override (B3 strip-then-append):** before exec, the driver strips any `--model` / `--model=*` / `-m` / `-m=*` tokens (and their separate values) from `runner.args`, then appends `--model X` once at the end. A dangling `--model` / `-m` with no value following aborts. No reliance on agent CLI "last-flag-wins"; the spawn args contain exactly one `--model` selector.
  - When CLI `--model` is **not** given, `runner.args` passes through verbatim (no strip).
  - The driver prints one stderr `ℹ️ Stripped N --model/-m flag(s)…` line at startup when strip is non-trivial.
- **Per-iteration validation** re-checks runner shape each iteration; corruption mid-loop aborts.
- **Security:** `runner.command` controls process execution. Treat `prd.json` edits in PRs as code review — a malicious `command` change is a process-injection vector. The schema deliberately does NOT allowlist commands (we support `aider`, `cursor-agent`, custom wrappers); that puts the security burden on review.
- sh driver parses `runner` via the `jq` dep it already has; ts / js / py validate via in-language type checks.

`templates/prd.json.example` ships the canonical shape as a reference; the scaffolder always emits a working `runner` block tailored to the chosen agent.

## Mode B — Amend (append user stories)

Triggered by `mode=amend` from arg parsing OR conflict prompt picking `[A]`. Pre-flight already verified: git repo, valid `prd.json`, `.ralph/` exists, no `.ralph/.lock`, ≤ 1 existing `in_progress`.

**Scope (non-negotiable):** append-only on `userStories`. Do NOT modify top-level `description` / `branchName` / `project` or any existing story field. Do NOT touch `.ralph/prompt.md`, `.ralph/ralph.<ext>`, `.ralph/RUNBOOK.md`, `.ralph/progress.txt`, `.ralph/package.json`, or `.gitignore`. (Quality checks live in `prompt.md`, not `prd.json`.) To change any of the above, re-bootstrap via Mode A `[O]verwrite` and accept the progress loss.

### Phase B1 — Read-back & confirm config

1. **Read + snapshot.** Read existing `prd.json` and parse it. Hold the **parsed JSON object** in memory as `preAmendSnapshot` (NOT a string snapshot — comparisons in B4 are deep-equal on the parsed structure, not byte-equal on the file). Also record `preAmendSerialized` = the file's exact bytes, used **only** for restore-on-failure in B3/B4.
2. **Detect runtime** from `.ralph/`: exactly one of `ralph.sh` / `ralph.ts` / `ralph.js` / `ralph.py` must exist. If multiple or none, Pre-flight already aborted; if you reach B1 and still see ambiguity, abort with diagnostic and do not write anything.
3. **Detect agent** from the memory-file token referenced inside `.ralph/prompt.md`:

   | Token in prompt.md | agent |
   |---|---|
   | `CLAUDE.md` | `claude` |
   | `AGENTS.md` | `copilot` |
   | `GEMINI.md` | `gemini` |

   Pre-flight already aborted on none/multiple; B1 just trusts the resolution.
4. **Hash `.ralph/*` for B4-7 drift detection.** Compute `sha256` of these (stable order): `.ralph/prompt.md`, `.ralph/ralph.<ext>`, `.ralph/RUNBOOK.md`, `.ralph/progress.txt`, plus `.ralph/package.json` only when `runtime == js` (covers the js-runtime append-only contract). Store as `preAmendRalphHashes` keyed by filename.

   **Normalize to lowercase hex digest** (no filename, no whitespace, no algorithm prefix):

   | Primitive | Raw shape | Normalize |
   |---|---|---|
   | POSIX `sha256sum` / `shasum -a 256` | `<hex>  <filename>` | field 1, lowercase |
   | PowerShell `Get-FileHash -Algorithm SHA256` | `[PSCustomObject]{ Hash="<UPPER_HEX>" }` | `.Hash.ToLower()` |
   | Node `crypto.createHash('sha256').update(buf).digest('hex')` | lowercase hex | use as-is |

   B4-7 deep-compares normalized strings. If any required file is missing at B1 → abort (defensive against TOCTOU; `amendFeasible()` should have caught it).
5. **Confirm with user.** Print a single line and require `y`:
   ```
   Detected: agent=<X>, runtime=<Y>. Will append new stories to prd.json (existing .ralph/* untouched). Continue? (y/n)
   ```
   On `n` → abort cleanly, no files written. (Optional UX: offer `--rebuild-meta` future flag pointer if user explains they wanted to change agent/runtime — that path is v1.2.)

### Phase B2 — Mini grill (append-only)

1. **Pre-Q (auto):** read `userPrompt` from argument parsing. If non-empty, treat it as a **draft hint** — quote it back to the user and ask "use this as the seed for new stories? (y / edit / discard)". Do not silently inject.
2. **B2-Q1:** "How many new stories to append? (integer ≥ 1)"
3. **B2-Q2 (loop, once per new story):**
   - Title (single line, required)
   - Description (defaults to title if user hits enter — same shape as bootstrap Q3 stories)
   - Acceptance criteria (one per line; submit empty line to finish; require ≥ 1)
4. **DO NOT ASK FOR:** `id` (auto), `priority` (auto), `status` (always `todo`), `branchName`, `project`, `description` (top-level). Also do not ask about quality-check commands — those live in `.ralph/prompt.md` (rendered from Phase 2 grill into `{{QUALITY_CHECKS}}`), not in `prd.json`, and amend never touches `.ralph/prompt.md`. If the user volunteers any of these, politely decline: *"That field can't be changed in amend mode. Run Mode A `[O]verwrite` if you need to."*

### Phase B3 — Atomic prd.json write

1. **Auto-assign per new story:**
   - `id` = `US-<NNN>` where the numeric suffix = `max(parseInt(existingIds.suffix)) + 1`, then increment per new story. **Zero-pad to width `W = max(3, len(longest existing suffix))`** — i.e. if existing PRD has `US-001..US-099` use width 3; if it has `US-1234` somewhere use width 4 for both old and new (compare on integer value not string). Never shrink the width relative to existing IDs.
   - `priority` = `max(existingPriorities) + 1`, then increment per new story. **Append-to-tail, not insert-and-shift.** Rationale: ralph driver picks lowest-priority `todo`, so existing backlog runs first; user's "amend" semantic is "add more work", not "preempt the queue". Users who want insert-and-shift can edit `prd.json` by hand.
   - `status` = `"todo"` (always, no exceptions).
   - `notes` = omitted (defaults to empty per schema).
2. **Build draft:** clone `preAmendSnapshot` (deep clone, not reference), push new stories onto `userStories` in question-order. Print the draft (full file) and ask: *"Append these N stories? (y / edit / abort)"*. Only proceed on `y`.
3. **Atomic write:**
   - Stringify with 2-space indent + trailing LF.
   - Write to `prd.json.tmp` in the same directory (same filesystem for atomic rename).
   - Best-effort `fsync` if the host provides it.
   - Rename `prd.json.tmp` → `prd.json` (POSIX `mv -f` / Windows `Move-Item -Force`).
   - On Windows, rename may EPERM/EACCES if a handle is held. **Retry once after explicit sleep** — POSIX: `sh -c 'sleep 0.25'` via Bash tool; PowerShell: `Start-Sleep -Milliseconds 250` via PowerShell tool. (The agent has no implicit sleep primitive — always go through a tool.)
   - Second failure → delete `.tmp` unconditionally, abort with the original error (`prd.json` is intact because the rename never landed).

### Phase B4 — Verification

Compare against B1's `preAmendSnapshot` using **deep-equal on parsed object structure**, not byte-equal. `preAmendSerialized` (raw bytes) is for the restore path only.

| # | Check | On failure |
|---|---|---|
| B4-1 | `prd.json` exists and validates against `templates/prd.schema.json` | hard fail — restore + abort |
| B4-2a | **Total length invariant.** `userStories.length === N_old + N_new` (defends against agent hallucination padding the array tail with extra entries) | hard fail — restore + abort |
| B4-2b | For every `i ∈ [0, N_old)`: deep-equal between `userStories[i]` in the new file and `preAmendSnapshot.userStories[i]`. All other top-level fields (`project`, `branchName`, `description`) deep-equal `preAmendSnapshot`. | hard fail — restore + abort |
| B4-3 | New stories occupy indices `[N_old, N_old + N_new)`; each has `status === "todo"`; `id` matches `^US-\d{3,}$`; `acceptanceCriteria.length ≥ 1` | hard fail — restore + abort |
| B4-4 | **Priority append-to-tail invariant.** For every new story `s`: `s.priority > max(preAmendSnapshot.userStories.map(s ⇒ s.priority))`. New story priorities are pairwise unique. | hard fail — restore + abort |
| B4-5 | All story `id` values across the whole array are unique | hard fail — restore + abort |
| B4-6 | Total count of stories with `status === "in_progress"` is ≤ 1 (driver–agent invariant enforced by every driver template) | hard fail — restore + abort |
| B4-7 | Sanity drift check on `.ralph/*`. For each path that was hashed at B1 step 4 (the four core files always, plus `.ralph/package.json` when `runtime == js`): file still exists and `sha256` (normalized lowercase hex digest) matches `preAmendRalphHashes` captured at B1 step 4. | warn — record drifted file list, surface in closing message (do NOT restore — those files weren't supposed to change, but if they did, user must reconcile manually) |

**Restore procedure** on hard-fail B4-1..B4-6 or B3 write failure:
1. Write `preAmendSerialized` (B1's raw bytes) to `prd.json.restore.tmp`.
2. Rename → `prd.json` (same retry-once-with-sleep policy as B3).
3. Delete any leftover `prd.json.tmp` from B3.
4. Print which check failed; abort non-zero.

Restores `prd.json` byte-for-byte (whitespace / key-order preserved) — avoids noise diff if the user had already committed it.

### Amend closing message

The default success line:

```
✅ Appended <N> stories to prd.json (<US-XXX>..<US-YYY>).
   Existing .ralph/* untouched. Driver state preserved.

To resume the loop:
   <runtimeCmd>
```

**Conditional variant** when B4-7 reported drift (one or more `.ralph/*` files were modified during this SKILL run despite the append-only contract):

```
✅ Appended <N> stories to prd.json (<US-XXX>..<US-YYY>).
⚠️  .ralph/* drift detected — these files changed during this SKILL run:
       <list of drifted file paths>
    The append-only contract was violated. This is a SKILL bug; please review
    the diff against git before resuming the loop.

To resume the loop (only after reviewing drift):
   <runtimeCmd>
```

`<runtimeCmd>` comes from the same Runtime Command Table used by Mode A. No big banner; user already saw it the first time.

## See also

Bundled with this plugin (every path resolves under `plugins/meta-ralph/`):

- `docs/meta-ralph.md` — user-facing quickstart for operators.
- `skills/meta-ralph/templates/prd.schema.json` — JSON Schema used by Phase 4 check #2.
- `skills/meta-ralph/templates/prd.json.example` — canonical runner-block + PRD reference (see "Runtime configuration" above).
- `skills/meta-ralph/templates/RUNBOOK.md.tpl` — user-intervention guide rendered in Phase 3 step 8.
- `skills/meta-ralph/templates/ralph/ralph.{sh,ts,js,py}.tpl` — driver templates rendered in Phase 3 step 6.
- `skills/meta-ralph/reference/prompt.md` — agent prompt template loaded in Phase 3 step 1.
- `skills/meta-ralph/scripts/parse-args.sh` / `parse-args.ps1` — `$ARGUMENTS` parsers for mode dispatch (see "Invocation & argument parsing"). Output `{"mode":"bootstrap"|"amend","userPrompt":"..."}`.
