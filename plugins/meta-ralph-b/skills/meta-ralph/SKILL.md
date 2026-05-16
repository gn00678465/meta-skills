---
name: meta-ralph
description: >-
  Scaffold (bootstrap) OR amend a ralph autonomous coding loop in a target git repo — writes prd.json + .ralph/prompt.md + .ralph/ralph.<sh|ts|js|py> + RUNBOOK + .gitignore. Pure scaffolder; does NOT execute the loop. Use for first-time setup OR to append more user stories to an existing scaffolded prd.json. Bootstrap trigger phrases: "init ralph", "set up ralph", "scaffold ralph", "bootstrap ralph", "建立 ralph", "初始化 ralph", "ralph 起手". Amend trigger phrases (every phrase MUST carry ralph/prd/meta-ralph context): "append stories to ralph", "add user stories to ralph prd", "extend the ralph prd", "extend ralph backlog", "grow the ralph prd", "在現有 ralph prd 補 stories", "追加 ralph stories", "在 ralph 加 user story", "ralph prd 新增 story". NOT for running an existing ralph loop (use ralph-loop:ralph-loop instead), NOT for explaining what ralph is (informational queries don't need this skill), and NOT for generic PRD editing, backlog grooming, or writing user stories outside an existing meta-ralph scaffold.
argument-hint: "[--amend] [<free-form stories prompt>]"
---

# meta-ralph

Pure scaffolder for the ralph autonomous coding loop. **`docs/meta-ralph-spec.md` is authoritative**; when this file disagrees with the spec, the spec wins.

Two modes, routed by whether `$ARGUMENTS` contains the whole-token `--amend`:

- **Bootstrap** (default) — write `prd.json` + `.ralph/*`. Phases 1–4.
- **Amend** (`--amend`) — append-only on `prd.json.userStories`. Phases B1–B4.

## Constraints (non-negotiable)

- Pure scaffolder — never invoke `claude` / `copilot` / `gemini`, never run a produced driver.
- Allowed mutations: `prd.json` (write/amend), `.ralph/*` (write), `.gitignore` (append). Nothing else.
- All writes use LF line endings.
- Verification is passive (no test runs).

## Output (bootstrap)

```
prd.json                ← git tracked
.gitignore              ← appended (5 ralph runtime lines)
.ralph/
  prompt.md             ← {{MEMORY_FILE}} + {{QUALITY_CHECKS}} replaced
  ralph.<sh|ts|js|py>   ← from templates/ralph/, executable on Unix
  RUNBOOK.md            ← {{RUN_COMMAND}} replaced
  progress.txt          ← `## Codebase Patterns\n`
  package.json          ← only when runtime=js (`{"type":"commonjs"}`)
```

Runtime sentinels (never written by SKILL): `.ralph/{.lock, .complete, .commit-failure, .stop}`.

## Argument parsing

Run the bundled parser; read its JSON line — `{"mode":"bootstrap"|"amend","userPrompt":"<remainder>"}`:

- POSIX: `sh "${CLAUDE_SKILL_DIR}/scripts/parse-args.sh" "$ARGUMENTS"`
- Windows: `pwsh -NoProfile -File "${CLAUDE_SKILL_DIR}/scripts/parse-args.ps1" "$ARGUMENTS"`

`userPrompt` is a prefill hint, never authoritative. Amend with no `prd.json` → abort.

## Pre-flight (both modes)

- cwd must be a git repo; `.ralph/.lock` present → abort (driver running).
- **Bootstrap + existing `prd.json` or `.ralph/`** → conflict prompt. Show `[A]mend / [O]verwrite / [X]Cancel` if `amendFeasible()` (schema valid, exactly one runtime detectable in `.ralph/`, agent token resolvable from `.ralph/prompt.md`, ≤1 in_progress story); else `[O]/[X]` and name why `[A]` is unavailable.
- **Amend** → validate `prd.json` against `templates/prd.schema.json`; exactly one runtime in `.ralph/`; agent token resolvable; ≤1 in_progress. Any failure → abort.

## Mode A — Bootstrap

**Phase 1 — Tools.** Two questions, PATH probe (missing = warn, not abort): Q-Agent (`claude`/`copilot`/`gemini`); Q-Runtime (`sh`/`ts`/`js`/`py`, warn on Windows + `sh`).

**Phase 2 — Grill.** Prefill from `README.md`, `package.json`, `pyproject.toml`, `Cargo.toml`. Ask if user has a requirements doc to import. Then Q1–Q6 one at a time:

| # | Question | PRD field |
|---|---|---|
| Q1 | What are you building? One sentence. | `description` |
| Q2 | Who is the user? Problem solved? | extends `description` |
| Q3 | 3–5 user stories ("user can do X"). | `userStories` |
| Q4 | typecheck / lint / test commands. | `prompt.md` `{{QUALITY_CHECKS}}` |
| Q5 | Branch name? Default `ralph/<slug-of-Q1>`. | `branchName` |
| Q6 | Project name? Default auto-detect / cwd basename. | `project` |

Synthesize `prd.json` draft (shape: `templates/prd.json.example`). Print; require `y` before Phase 3.

**Phase 3 — Scaffold.** Capture an `existedBefore` set before any write. If `[O]verwrite`: delete every `.ralph/ralph.{sh,ts,js,py}` except the chosen runtime; delete stale `.ralph/package.json` unless `runtime=js`. Then write in order:

1. **Render `prompt.md`** from `reference/prompt.md`: replace `{{MEMORY_FILE}}` (Agent Config Table) and `{{QUALITY_CHECKS}}` — bullet list with the runtime's JSON-validity check **as the first bullet** (`jq empty prd.json` / `JSON.parse(require('fs').readFileSync('prd.json','utf8'))` for ts+js / `python -c "import json; json.load(open('prd.json'))"`), then Q4 commands.
2. Write `prd.json` at repo root with `runner` block per Agent Config Table.
3. `mkdir .ralph/` if missing.
4. Write `.ralph/prompt.md` (step 1 output).
5. Write `.ralph/ralph.<ext>` verbatim from `templates/ralph/ralph.<ext>.tpl`; LF; `chmod +x` on Unix.
6. Write `.ralph/progress.txt` = `## Codebase Patterns\n`.
7. Render + write `.ralph/RUNBOOK.md` from `templates/RUNBOOK.md.tpl`; replace `{{RUN_COMMAND}}` with the Runtime Command Table entry (without trailing `[N]`).
8. If `runtime=js`: write `.ralph/package.json` = `{"type":"commonjs"}\n`.
9. Append to `.gitignore` (create if absent; skip lines already present): `.ralph/progress.txt`, `.ralph/.lock`, `.ralph/.complete`, `.ralph/.commit-failure`, `.ralph/.stop`.

On write failure: reverse the order; delete only files **this run created** (use `existedBefore`); never delete runtime sentinels. Atomic-write protocol — SPEC §11.2.

**Phase 4 — Verify (passive).**

| Check | On fail |
|---|---|
| `prd.json` exists + validates `prd.schema.json` (incl. `runner` shape) | abort |
| `.ralph/prompt.md` exists; no `{{MEMORY_FILE}}` / `{{QUALITY_CHECKS}}` remain | abort |
| `.ralph/ralph.<ext>` exists, executable on Unix | abort |
| `.ralph/progress.txt` starts with `## Codebase Patterns` | abort |
| `.ralph/RUNBOOK.md` exists; no `{{RUN_COMMAND}}` remains | abort |
| `.gitignore` has all 5 ralph runtime lines | abort |
| (`runtime=js`) `.ralph/package.json` has `"type":"commonjs"` | abort |
| Selected agent + runtime dependencies in PATH | warn |

## Mode B — Amend (append-only)

**Scope:** only append to `prd.json.userStories`. NEVER modify other top-level fields. NEVER touch `.ralph/*`.

**B1 — Read-back.** Parse `prd.json` → `preAmendSnapshot` (parsed) + `preAmendSerialized` (raw bytes for restore). Detect runtime (single `.ralph/ralph.<ext>`) and agent (memory-file token in `.ralph/prompt.md`: `CLAUDE.md`→claude / `AGENTS.md`→copilot / `GEMINI.md`→gemini). Hash `.ralph/prompt.md`, `.ralph/ralph.<ext>`, `.ralph/RUNBOOK.md`, `.ralph/progress.txt` (+ `package.json` when js) → `preAmendRalphHashes` (lowercase hex SHA-256; normalize per SPEC §11.3). Print `Detected: agent=<X>, runtime=<Y>. Append? (y/n)`; require `y`.

**B2 — Mini grill.** If parser's `userPrompt` non-empty, quote it back: `seed? (y/edit/discard)`. Then: `How many new stories? (≥1)`; per story: title (req), description (defaults to title), acceptance criteria (one per line, blank to finish, ≥1). NEVER ask for `id` / `priority` / `status` / `branchName` / `project` / top-level `description` / quality-checks. Politely refuse if user volunteers.

**B3 — Atomic write.** Auto-assign per new story: `id = US-<NNN>` with width `max(3, longest existing suffix)`; `priority = max(existing) + 1`, increment per new story (append-to-tail); `status = "todo"`; `notes` omitted. Deep-clone `preAmendSnapshot`, push new stories; print full file; ask `Append? (y/edit/abort)`. Stringify (2-space indent + trailing LF); atomic write per SPEC §11.2 (tmp + rename + 250 ms Windows retry).

**B4 — Verify.** Run SPEC §11.1 invariants (length, deep-equal old stories, new-story shape, append-to-tail priorities), plus: schema validates; all story ids unique; ≤1 in_progress. Hash-compare `.ralph/*` vs `preAmendRalphHashes` — **warn-only** drift (record drifted file list; do not restore). Any hard fail → restore from `preAmendSerialized` per SPEC §11.2.

## Agent Config Table

| Agent | memoryFile | runner.command | runner.args |
|---|---|---|---|
| `claude` | `CLAUDE.md` | `"claude"` | `["-p", "{PROMPT}", "--dangerously-skip-permissions"]` |
| `copilot` | `AGENTS.md` | `"copilot"` | `["--yolo", "--allow-tools", "--prompt", "{PROMPT}"]` |
| `gemini` | `GEMINI.md` | `"gemini"` | `["-p", "{PROMPT}", "--yolo"]` |

`"{PROMPT}"` is the literal sentinel — driver substitutes `.ralph/prompt.md` content at runtime. See SPEC §8 for the full runner contract and §8.2 for the CLI `--model X` strip-and-append override.

## Runtime Command Table

| runtime | runtimeCmd |
|---|---|
| `sh` | `bash .ralph/ralph.sh [N] [--model X]` |
| `ts` | `bun run .ralph/ralph.ts [N] [--model X]` |
| `js` | `node .ralph/ralph.js [N] [--model X]` |
| `py` | `uv run .ralph/ralph.py [N] [--model X]` (or `python` ≥3.11 without uv) |

`[N]` = max iterations (default 10); `[--model X]` = override per SPEC §8.2.

## Closing messages

**Bootstrap:**

```
✅ Scaffolded ralph loop for <project>.
   Branch: <branchName> | Agent: <agent> | Runtime: <runtime>
To start: <runtimeCmd>
For runs >30 min: suppress OS sleep (SPEC §7.3). Read .ralph/RUNBOOK.md if stuck.
```

**Amend:**

```
✅ Appended <N> stories to prd.json (<US-XXX>..<US-YYY>). Existing .ralph/* untouched.
To resume: <runtimeCmd>
```

If B4 hash-compare reports drift, prepend `⚠️  .ralph/* drift: <files>` and tell the user to review before resuming.

## See also

- `docs/meta-ralph-spec.md` — authoritative invariants (§1–§12: scope, driver-agent contract A1–A7, runner block, amend §11, driver §9).
- `templates/{prd.schema.json, prd.json.example, RUNBOOK.md.tpl, ralph/ralph.{sh,ts,js,py}.tpl}` — Phase 3 templates.
- `reference/prompt.md` — Phase 3 step 1 input.
- `scripts/parse-args.{sh,ps1}` — argument parsers.
