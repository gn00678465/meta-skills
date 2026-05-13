---
name: meta-ralph
description: Scaffold (bootstrap) OR amend a ralph autonomous coding loop in a target git repo — writes prd.json + .ralph/prompt.md + .ralph/ralph.<sh|ts|js|py> + RUNBOOK + .gitignore. Pure scaffolder; does NOT execute the loop. Use for first-time setup OR to append more user stories to an existing scaffolded prd.json. Bootstrap trigger phrases: "init ralph", "set up ralph", "scaffold ralph", "bootstrap ralph", "建立 ralph", "初始化 ralph", "ralph 起手". Amend trigger phrases (every phrase MUST carry ralph/prd/meta-ralph context): "append stories to ralph", "add user stories to ralph prd", "extend the ralph prd", "extend ralph backlog", "grow the ralph prd", "在現有 ralph prd 補 stories", "追加 ralph stories", "在 ralph 加 user story", "ralph prd 新增 story". NOT for running an existing ralph loop (use ralph-loop:ralph-loop instead), NOT for explaining what ralph is (informational queries don't need this skill), and NOT for generic PRD editing, backlog grooming, or writing user stories outside an existing meta-ralph scaffold.
argument-hint: "[--amend] [<free-form stories prompt>]"
---

# meta-ralph

Pure scaffolder for the **ralph autonomous coding loop**. Two modes:

- **Mode A — Bootstrap (default).** First-run scaffolding. The user describes what to build, picks agent + runtime, the SKILL writes `prd.json` + `.ralph/*`. Phases 1–4 below.
- **Mode B — Amend (`--amend` flag).** Second invocation; user already has `prd.json` and wants to **append** new user stories. The SKILL only mutates `prd.json` and never touches `.ralph/*`. Phases B1–B4, defined under "Mode B — Amend" near the end of this file.

This file is self-contained: the Driver–Agent Contract, scaffold steps, verification table, and amend flow live entirely below. User-facing usage notes are in `plugins/meta-ralph/docs/meta-ralph.md`.

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

The SKILL receives `$ARGUMENTS` — a Claude Code substitution variable holding the raw text the user typed after the slash-command (or trigger phrase). Parse it once, before pre-flight, into:

| Field | Rule |
|---|---|
| `mode` | `amend` if the token `--amend` (case-sensitive, whole-word) appears anywhere in `$ARGUMENTS`; otherwise `bootstrap`. |
| `userPrompt` | `$ARGUMENTS` with the literal `--amend` token (and one adjacent space) stripped. May be empty. Used as a **prefill hint** only — never as authoritative content. |

Examples:

| `$ARGUMENTS` | mode | userPrompt |
|---|---|---|
| *(empty)* | `bootstrap` | *(empty)* |
| `--amend` | `amend` | *(empty)* |
| `--amend add login flow with OAuth + 2FA` | `amend` | `add login flow with OAuth + 2FA` |
| `--amend story with "quoted" title and \backslash` | `amend` | `story with "quoted" title and \backslash` |
| `init ralph for my CLI tool` | `bootstrap` | `init ralph for my CLI tool` |
| `--AMEND should not match` | `bootstrap` | `--AMEND should not match` |

**Preferred:** invoke the bundled parser script and read the single-line JSON it emits to stdout:

```
{"mode":"bootstrap"|"amend","userPrompt":"<trimmed remainder>"}
```

| Host | Tool to invoke from | Command |
|---|---|---|
| POSIX (Linux / macOS / git-bash / WSL — POSIX-native paths) | Bash tool | `sh "${CLAUDE_SKILL_DIR}/scripts/parse-args.sh" "$ARGUMENTS"` |
| Windows PowerShell (Windows-native paths) | PowerShell tool | `pwsh -NoProfile -File "${CLAUDE_SKILL_DIR}/scripts/parse-args.ps1" "$ARGUMENTS"` |

`$ARGUMENTS` MUST be wrapped in **double quotes** at the host-shell level so it arrives as a single argument; without quoting, multi-word prompts get re-tokenized and the parser sees several arguments instead of one (the script does join them again, but a stray `--` or shell metachar can leak in). Both scripts implement the same case-sensitive whole-token rule for `--amend` and the same JSON-escape contract for `userPrompt` (backslash, double-quote). See `scripts/parse-args.sh` header for the full specification.

`${CLAUDE_SKILL_DIR}` is a Claude Code substitution variable that resolves to this skill's bundled directory. Other CC-compatible hosts (Codex, Copilot CLI when running this SKILL via plugin import) provide it too. If you must run the parser outside any CC-style host, substitute the absolute path to this skill's directory.

**Fallback (inline, when the script is unreachable):**

```sh
mode="bootstrap"
case " $ARGUMENTS " in *" --amend "*) mode="amend" ;; esac
userPrompt=$(printf '%s' "$ARGUMENTS" | sed -E 's/(^| )--amend( |$)/ /g; s/^ +//; s/ +$//; s/  +/ /g')
```

If `mode=amend` but no `prd.json` exists at repo root → abort early with: *"--amend requires an existing prd.json. Run meta-ralph without --amend to bootstrap first."*

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
```

If any of the last three are missing, `amendFeasible()` returns false → conflict prompt shows 2-way only (`[O]/[X]`) with the specific missing file named, so user knows what's wrong before they pick.

| Check | Bootstrap | Amend |
|---|---|---|
| cwd is a git repo (`git rev-parse --git-dir` succeeds) | abort | abort |
| `prd.json` exists at repo root | (see "conflict prompt" row) | required (else abort per §Invocation) |
| `.ralph/` directory exists | (see "conflict prompt" row) | required (else abort: scaffold first) |
| **Conflict prompt** — `mode=bootstrap` AND (`prd.json` exists OR `.ralph/` exists) | If `.ralph/.lock` exists: refuse to prompt; abort with the lock message (see `.ralph/.lock` row below) — neither `[A]mend` nor `[O]verwrite` is safe while a driver may be running. <br>Else if `amendFeasible()`: offer 3-way prompt `[A]mend / [O]verwrite (rerun bootstrap — destroys progress) / [X]Cancel`. Pick `A` → flip mode to `amend`. Pick `O` → continue bootstrap. Pick `X` → abort. <br>Else: offer 2-way prompt `[O]verwrite / [X]Cancel`, **and tell the user the specific reason `[A]` is unavailable** (e.g. "prd.json schema-invalid", "agent token unresolved in prompt.md"). Do not silently swallow the option. | n/a |
| `.ralph/.lock` exists | **Fresh bootstrap** (no prior `.ralph/`): n/a — no driver could be running. <br>**Overwrite bootstrap** (conflict prompt picked `[O]`): abort: *"ralph driver appears to be running. Stop it (or `rm .ralph/.lock` if stale) before [O]verwrite."* The lock means a live driver may still be iterating against the very files Phase 3 is about to rewrite — that corrupts running state. Conflict prompt itself should not offer `[O]` while `.lock` is present; surface this as the same "specific reason" message the prompt already prints for other blockers. | abort: *"ralph driver appears to be running. Stop it (or `rm .ralph/.lock` if stale) before amending."* |
| Existing `prd.json` validates against `templates/prd.schema.json` | n/a | abort if invalid — refuse to amend a corrupt PRD |
| Existing `prd.json` has at most one story with `status: in_progress` | n/a | abort — driver-agent invariant violation; user must reconcile manually |
| Exactly one runtime file present under `.ralph/` (`ralph.sh` xor `.ts` xor `.js` xor `.py`) | n/a | abort — print which files were found and ask user to remove the spurious one(s) |
| `.ralph/prompt.md` references exactly one memory file token (`CLAUDE.md` / `AGENTS.md` / `GEMINI.md`) | n/a | abort — token unresolved (none / multiple); ask user to confirm intended agent before retrying |

## Phase 1 — Tool selection

Ask 2 questions, validate after each.

**Q-Agent:** which agent? `claude` / `copilot` / `gemini`
- After answer: check `which <agent>` (or equivalent on Windows). Not in PATH → emit warning, do NOT abort (user may install later).

**Q-Runtime:** which loop driver runtime? `sh` / `ts` / `js` / `py`
- If user is on Windows AND chose `sh` → emit warning: needs git-bash or WSL; suggest switching to ts/js/py.
- After answer: check runtime dependency in PATH:
  - sh → `jq`, `bash`
  - ts → `bun`
  - js → `node`
  - py → `uv` (or `python3`)
- Not in PATH → emit warning, do NOT abort.

## Phase 2 — Grill (PRD content)

### Pre-Q-1: Auto-detect from existing files

Read whichever exist in cwd; use as **prefills** for grill answers (don't skip questions, just preload defaults):

| File | Extracts |
|---|---|
| `README.md` | top-level description hint |
| `package.json` | `project` ← `name` field; quality check commands ← `scripts.typecheck/lint/test` |
| `pyproject.toml` | `project` ← `[project] name`; quality checks from `[tool.*]` if obvious |
| `Cargo.toml` | `project` ← `[package] name` |

### Pre-Q-2: Existing requirements doc?

Ask: "Do you have an existing requirements / spec doc you'd like me to import? (y/n)"
- If yes → ask for path → read it → extract user stories → run Q1–Q6 to fill gaps.
- If no → run Q1–Q6 from scratch.

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

Synthesize the answers into a `prd.json` draft (per `templates/prd.json.example` shape). Print it. Ask: "Looks good? (y / edit)". Only proceed to Phase 3 on `y`. If edit, accept changes and re-print.

## Phase 3 — Scaffold (file writes)

Inputs locked at this point: `agent`, `runtime`, approved `prd.json` content, `qualityChecks`.

### Step 0 — Overwrite cleanup (only when conflict prompt picked `[O]`)

When pre-flight's conflict prompt resolved to `[O]verwrite`, prior bootstrap state may include managed files that the upcoming writes won't replace. Without cleanup, leftovers violate `amendFeasible()`'s "exactly one runtime file present" invariant and prevent future amend mode from working.

Before any Phase 3 write, run this cleanup. If any deletion fails (e.g. permissions), abort with the failing path **before** writing new files — no partial state:

1. Delete every managed runtime driver under `.ralph/` **except** the one matching the chosen `runtime`. Targets:
   - `.ralph/ralph.sh`
   - `.ralph/ralph.ts`
   - `.ralph/ralph.js`
   - `.ralph/ralph.py`
2. Reconcile `.ralph/package.json` with the chosen `runtime`:
   - `runtime == js` → leave for step 9 below to (re)write.
   - `runtime != js` → delete `.ralph/package.json` if present (stale CommonJS pin from a prior js scaffold).
3. Leave `prd.json`, `.ralph/prompt.md`, `.ralph/RUNBOOK.md`, `.ralph/progress.txt` in place — the upcoming writes overwrite them deterministically.
4. Never touch runtime-only files (`.ralph/.lock`, `.ralph/.complete`, `.ralph/.commit-failure`, `.ralph/.stop`) — those are not the SKILL's to manage.

Skip Step 0 entirely on a fresh scaffold (no prior `prd.json` AND no prior `.ralph/`).

### Step 1 onwards — render and write

Render in this order:

1. **Render `prompt.md`** from `reference/prompt.md` template:
   - Replace `{{MEMORY_FILE}}` (multiple occurrences) with the agent's memory file (see Agent Config Table).
   - Replace `{{QUALITY_CHECKS}}` (single occurrence) with a bullet list of the user's Q4 commands, one per line, each prefixed with `- ` and wrapped in backticks. Example:
     ```
     - `bun run typecheck`
     - `bun test`
     - `bun run lint`
     ```
2. **Render `ralph.<ext>`** from `templates/ralph/ralph.<ext>.tpl`:
   - For `sh`: replace `{{AGENT_CLI}}` with the agent's `shellForm`.
   - For `ts` / `js` / `py`: replace `{{AGENT_ARGV}}` with the agent's `argv` array (with `PROMPT` as a bare identifier — the runtime reads `.ralph/prompt.md` and binds it).
3. **Write `prd.json`** to repo root.
4. **Create `.ralph/`** if missing (plain `mkdir`, not recursive — though here recursive is fine since `.ralph/` is a single level).
5. **Write `.ralph/prompt.md`** (rendered step 1).
6. **Write `.ralph/ralph.<ext>`** (rendered step 2). Force LF. `chmod +x` on Unix; on Windows the executable bit isn't meaningful but ts/js/py are run via interpreter anyway.
7. **Write `.ralph/progress.txt`** with single line: `## Codebase Patterns\n`.
8. **Render `.ralph/RUNBOOK.md`** from `templates/RUNBOOK.md.tpl`:
   - Replace `{{RUN_COMMAND}}` (multiple occurrences) with the runtime's `runtimeCmd` from the **Runtime Command Table** in this SKILL's closing-message section, *without* the `[N]` argument suffix (so `bun run .ralph/ralph.ts`, not `bun run .ralph/ralph.ts [N]`). The runbook adds `N` itself in context.
   - Use LF line endings.
9. **(Conditional, runtime=js only)** Write `.ralph/package.json` with `{"type": "commonjs"}\n`. Reason: `.ralph/ralph.js` uses CommonJS `require()`; if the parent project's `package.json` declares `"type": "module"`, Node will misinterpret the file. The `.ralph/package.json` is the closest one to the script, so it wins. Skip this step for sh/ts/py runtimes.
10. **Append to `.gitignore`** (create if absent):
   ```
   # ralph runtime files
   .ralph/progress.txt
   .ralph/.lock
   .ralph/.complete
   .ralph/.commit-failure
   .ralph/.stop
   ```
   If `.gitignore` already contains these lines, skip — don't duplicate. Notes: `.commit-failure` is the commit-repair sentinel — the driver writes it on commit failure, the agent deletes it after successful repair, so it's runtime-only and never tracked. `.stop` is the graceful-stop sentinel — the user touches it from another terminal to make the driver exit cleanly after the current iteration.

### Rollback on failure

If any Phase 3 write fails, perform this rollback before aborting (mirrors Phase 3's write order, deleting only what *this* Phase actually created in *this* run). Track each successful write in memory; on failure, delete those tracked files in reverse order, then re-raise the original error.

Candidate paths to remove, in reverse Phase 3 order:

1. `.gitignore` block — if step 10 appended the ralph block, strip those exact lines (do not delete pre-existing `.gitignore` content).
2. `.ralph/package.json` — only if Phase 3 step 9 wrote it (runtime=js).
3. `.ralph/RUNBOOK.md` — if step 8 wrote it.
4. `.ralph/progress.txt` — if step 7 wrote it.
5. `.ralph/ralph.<ext>` — if step 6 wrote it.
6. `.ralph/prompt.md` — if step 5 wrote it.
7. `.ralph/` directory — only if step 4 created it AND it is now empty (do not remove a pre-existing `.ralph/` left untouched by overwrite).
8. `prd.json` — only if step 3 created it on a fresh scaffold (do not delete an existing user-authored `prd.json` that step 3 overwrote — refuse to delete what the user already owned).

Never remove runtime-only sentinels (`.lock`, `.complete`, `.commit-failure`, `.stop`) during rollback. If any deletion itself fails, log the path and continue with the rest — surface both the original write error and the rollback failures in the abort message.

## Phase 4 — Verification (passive checks)

This table is the executable form of the §Output contract at the top of this file — each check confirms one row of that promised output. Keep them in sync: if you add a written artifact, add the matching check; if you drop a check, drop the artifact from §Output.

| # | Check | On failure |
|---|---|---|
| 1 | `prd.json` exists at repo root | abort |
| 2 | `prd.json` validates against `templates/prd.schema.json` (full JSON Schema validation) | abort |
| 3 | `.ralph/prompt.md` exists; no `{{MEMORY_FILE}}` or `{{QUALITY_CHECKS}}` substring remains | abort |
| 4 | `.ralph/ralph.<ext>` exists, executable on Unix, no `{{AGENT_CLI}}` or `{{AGENT_ARGV}}` substring remains | abort |
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
- `[--model X]` — optional `--model X` flag passed through to the agent CLI (claude / copilot / gemini all accept `--model`); when omitted, the agent uses its own default model. Supports both `--model X` and `--model=X` syntax.

## Agent Config Table (data the SKILL needs)

| Agent | memoryFile | shellForm (sh template) | argv (ts/js/py templates) |
|---|---|---|---|
| `claude` | `CLAUDE.md` | `claude -p "$(cat .ralph/prompt.md)" --dangerously-skip-permissions` | `["claude", "-p", PROMPT, "--dangerously-skip-permissions"]` |
| `copilot` | `AGENTS.md` | `copilot --yolo --allow-tools --prompt "$(cat .ralph/prompt.md)"` | `["copilot", "--yolo", "--allow-tools", "--prompt", PROMPT]` |
| `gemini` | `GEMINI.md` | `gemini -p "$(cat .ralph/prompt.md)" --yolo` | `["gemini", "-p", PROMPT, "--yolo"]` |

Notes:
- `PROMPT` in the argv form is a **bare identifier**, not a string literal. The ts/js/py templates resolve it at runtime by reading `.ralph/prompt.md`.
- v1 only supports these 3 agents. Adding a new agent requires extending this table with all 3 fields (`memoryFile`, `shellForm`, `argv`), not just one.
- The scaffolder **does not** write a `runner` field into `prd.json` by default — users add it themselves when they want to override the baked invocation. See "Runtime override" below.

## Runtime override (`prd.json.runner`)

Users can override the scaffold-time baked agent invocation by adding an optional `runner` object to `prd.json`. This lets them swap CLI binary, change model, or add flags without re-scaffolding.

Schema (enforced by both `prd.schema.json` and runtime validation in all 4 drivers):

```json
{
  "runner": {
    "command": "claude",
    "args": ["-p", "{PROMPT}", "--model", "opus", "--dangerously-skip-permissions"]
  }
}
```

Rules:

- **All-or-nothing**: when `runner` is present, both `command` (non-empty string) and `args` (non-empty array of non-empty strings) are required. Partial override is rejected at schema and runtime.
- **`{PROMPT}` sentinel**: the literal string `"{PROMPT}"` inside `args` is replaced at runtime with the contents of `.ralph/prompt.md`. If absent, the prompt is appended at the end as a positional argument with a stderr warning.
- **Precedence**: driver CLI flags (e.g. `--model X`) still append to the resolved args, so last-flag-wins agents honor CLI overrides. Effective order: CLI flags > `runner.args` > scaffold-time baked default.
- **Per-iteration validation**: the runner shape is re-checked each iteration (same as other prd.json fields). Agents that corrupt `runner` mid-loop trigger an abort.
- **Security**: `runner.command` controls process execution. In a shared repo, treat edits to `runner` like code changes — review them in PRs.
- **sh driver dependency**: parsing `runner` from `prd.json` uses `jq`, which the sh driver already requires.

The scaffolder does not auto-emit `runner` because the baked invocation is the documented default. `templates/prd.json.example` includes a `runner` block purely as documentation.

## Mode B — Amend (append user stories)

Triggered when (`mode=amend` from `$ARGUMENTS` parsing) **OR** (existing-files prompt picked `[A]`). Pre-flight already verified: git repo, `prd.json` exists + schema-valid, `.ralph/` exists, `.ralph/.lock` absent, ≤ 1 existing `in_progress`.

**Scope (non-negotiable):** append-only on `userStories`. Do NOT modify `prd.json` top-level fields (`description`, `branchName`, `project`) or any existing story's fields. Do NOT touch `.ralph/prompt.md`, `.ralph/ralph.<ext>`, `.ralph/RUNBOOK.md`, `.ralph/progress.txt`, `.ralph/package.json`, or `.gitignore`. (Quality checks live in `.ralph/prompt.md` via the `{{QUALITY_CHECKS}}` placeholder, not in `prd.json` — they're covered by the prompt.md prohibition above.) Want to change any of these? Re-bootstrap (Mode A with `[O]verwrite`) — accept that you lose progress.

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
4. **Hash `.ralph/*` pre-amend state** for B4-7 drift detection. Compute `sha256` of these four files (in this exact order, for stable comparison): `.ralph/prompt.md`, `.ralph/ralph.<ext>`, `.ralph/RUNBOOK.md`, `.ralph/progress.txt`. Store as `preAmendRalphHashes` keyed by filename.

   **Output format must be normalized to lowercase hex digest (no filename, no whitespace, no algorithm prefix)** — different host primitives return different shapes:

   | Host primitive | Raw output shape | How to normalize |
   |---|---|---|
   | POSIX `sha256sum` | `<hex>  <filename>` | take field 1, lowercase |
   | macOS / BSD `shasum -a 256` | `<hex>  <filename>` | take field 1, lowercase |
   | PowerShell `Get-FileHash -Algorithm SHA256` | `[PSCustomObject]{ Hash = "<UPPER_HEX>"; Path = ... }` | `.Hash.ToLower()` |
   | Node `crypto.createHash('sha256').update(buf).digest('hex')` | already lowercase hex | use as-is |

   B4-7 compares `preAmendRalphHashes[<file>] === currentHash(<file>)`, both normalized the same way. If any of the four files don't exist at B1 time → abort (Pre-flight `amendFeasible()` should have caught this; defensive check here in case of TOCTOU).
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
   - Stringify the draft with 2-space indent and a trailing LF newline.
   - Write to `prd.json.tmp` in the same directory as `prd.json` (must be same filesystem for atomic rename).
   - Best-effort `fsync` on the tmp file (skip if host shell lacks the primitive).
   - Rename `prd.json.tmp` → `prd.json` (POSIX `mv -f` / Windows `Move-Item -Force`).
   - On Windows, rename can fail with EPERM/EACCES if another process holds a handle. **Retry once** after a deliberate sleep:
     - POSIX hosts: invoke `sh -c 'sleep 0.25'` via the Bash tool.
     - Windows PowerShell hosts: invoke `Start-Sleep -Milliseconds 250` via the PowerShell tool.
     - Do NOT just "wait" without a tool call — the agent has no implicit sleep primitive.
   - Second failure → **delete the `.tmp` file** unconditionally and abort with the original error. The file `prd.json` is unchanged because the rename never landed.

### Phase B4 — Verification

Compare against `preAmendSnapshot` (the parsed-JSON snapshot from B1) using **deep-equal on the parsed object structure**, not byte-equal on the file. `preAmendSerialized` (raw bytes) is reserved for the restore path described below.

| # | Check | On failure |
|---|---|---|
| B4-1 | `prd.json` exists and validates against `templates/prd.schema.json` | hard fail — restore + abort |
| B4-2a | **Total length invariant.** `userStories.length === N_old + N_new` (defends against agent hallucination padding the array tail with extra entries) | hard fail — restore + abort |
| B4-2b | For every `i ∈ [0, N_old)`: deep-equal between `userStories[i]` in the new file and `preAmendSnapshot.userStories[i]`. All other top-level fields (`project`, `branchName`, `description`) deep-equal `preAmendSnapshot`. | hard fail — restore + abort |
| B4-3 | New stories occupy indices `[N_old, N_old + N_new)`; each has `status === "todo"`; `id` matches `^US-\d{3,}$`; `acceptanceCriteria.length ≥ 1` | hard fail — restore + abort |
| B4-4 | **Priority append-to-tail invariant.** For every new story `s`: `s.priority > max(preAmendSnapshot.userStories.map(s ⇒ s.priority))`. New story priorities are pairwise unique. | hard fail — restore + abort |
| B4-5 | All story `id` values across the whole array are unique | hard fail — restore + abort |
| B4-6 | Total count of stories with `status === "in_progress"` is ≤ 1 (driver–agent invariant enforced by every driver template) | hard fail — restore + abort |
| B4-7 | Sanity drift check on `.ralph/*`. For each of `.ralph/prompt.md`, `.ralph/ralph.<ext>`, `.ralph/RUNBOOK.md`, `.ralph/progress.txt`: file still exists and `sha256` (normalized lowercase hex digest) matches `preAmendRalphHashes` captured at B1 step 4. | warn — record drifted file list, surface in closing message (do NOT restore — those files weren't supposed to change, but if they did, user must reconcile manually) |

**Restore procedure.** On any hard fail (B4-1..B4-6) or B3 atomic-write failure:
1. Write `preAmendSerialized` (raw bytes from B1) to `prd.json.restore.tmp`.
2. Rename `prd.json.restore.tmp` → `prd.json` (atomic rename, same retry-once-with-explicit-sleep policy as B3).
3. If a `prd.json.tmp` left over from B3, delete it.
4. Print which check failed + abort with non-zero exit signal to caller.

This restores `prd.json` to **exact byte-for-byte pre-amend state**, including any whitespace / key-order quirks the file had before — important because the user may already have committed `prd.json` to git and we don't want to introduce a noise diff.

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
- `skills/meta-ralph/templates/prd.json.example` — runner-block reference (see "Runtime override" above).
- `skills/meta-ralph/templates/RUNBOOK.md.tpl` — user-intervention guide rendered in Phase 3 step 8.
- `skills/meta-ralph/templates/ralph/ralph.{sh,ts,js,py}.tpl` — driver templates rendered in Phase 3 step 6.
- `skills/meta-ralph/reference/prompt.md` — agent prompt template loaded in Phase 3 step 1.
- `skills/meta-ralph/scripts/parse-args.sh` / `parse-args.ps1` — `$ARGUMENTS` parsers for mode dispatch (see "Invocation & argument parsing"). Output `{"mode":"bootstrap"|"amend","userPrompt":"..."}`.
