# meta-ralph spec

Authoritative contract for the **meta-ralph** skill, the **ralph driver**, and the **agent** that runs inside the loop. SKILL.md describes the scaffolding procedure; this file fixes the invariants both sides must honor at runtime. When wording in SKILL.md and this spec disagrees, this spec wins.

Sections are stable anchors — driver template comments, `prd.schema.json`, and `RUNBOOK.md.tpl` point at numbered references here (e.g., `§9.1`, `§7.3`). Do not renumber.

---

## §1 Purpose

`meta-ralph` is a **pure scaffolder** for the ralph autonomous coding loop. It writes:

- `prd.json` at the target repo root
- `.ralph/prompt.md`, `.ralph/ralph.<sh|ts|js|py>`, `.ralph/progress.txt`, `.ralph/RUNBOOK.md`, optionally `.ralph/package.json`
- `.gitignore` (appended)

It does NOT execute the produced driver, invoke any agent CLI, or run any user code. Two modes:

- **Bootstrap** — first-run scaffolding (Phases 1–4 in SKILL.md).
- **Amend** — append-only mutation of `prd.json.userStories` (Phases B1–B4 in SKILL.md).

## §2 Allowed mutations

The skill may only:

1. Create `prd.json` at the target repo root (bootstrap) OR append to its `userStories` array (amend).
2. Create / write into the target repo's `.ralph/` directory (bootstrap only).
3. Append the ralph block to `.gitignore` (bootstrap only).

Any other filesystem mutation is a spec violation.

Runtime-only files — created by the driver, never by the skill — are `.ralph/.lock`, `.ralph/.complete`, `.ralph/.commit-failure`, `.ralph/.stop`. They are gitignored.

## §3 Inputs

Bootstrap requires:

- Agent choice — one of `claude` / `copilot` / `gemini` (see §8 `runner.command`).
- Runtime choice — one of `sh` / `ts` / `js` / `py`.
- PRD content — `project`, `branchName`, `description`, ≥1 `userStories[].{title,description,acceptanceCriteria}`, quality-check commands (typecheck / lint / test).

Amend requires:

- Existing `prd.json` that validates against `prd.schema.json` (in particular: has `runner`).
- An existing `.ralph/` with exactly one driver runtime detectable.
- ≤1 story currently `in_progress`.

## §4 Outputs

All writes use **LF line endings** (CRLF on `bash`/`sh` is a fatal portability bug on Windows).

Driver script is `chmod +x` on POSIX; on Windows it runs via interpreter regardless.

File-by-file contract is in SKILL.md "Output (what gets written)" — verification table (SKILL.md "Phase 4 — Verification") confirms each row passively (no test runs).

## §5 prd.json schema

Defined formally in `plugins/meta-ralph/skills/meta-ralph/templates/prd.schema.json` (Draft-07). Validated:

- Once at scaffold time (SKILL Phase 4).
- Once at driver startup (Step 5 in every driver).
- Once per iteration boundary (Step 10a + 10d post-validate).

Validation failure aborts the loop — agents must edit via parse → mutate → serialize (§7.2), never via text-level tools.

## §6 PRD field semantics

| Field | Type | Semantics |
|---|---|---|
| `project` | string (non-empty) | Display name. Usually inferred from `package.json.name` or cwd basename. |
| `branchName` | string matching `^[a-zA-Z0-9/_-]+$` | Git branch the driver checks out / creates at Step 8. Convention: `ralph/<slug>`. |
| `description` | string (non-empty) | One-paragraph context. Surfaces in run-summary; not read by agent. |
| `userStories[].id` | string matching `^US-\d{3,}$` | Stable identifier. Width ≥ 3 digits, grows monotonically. |
| `userStories[].title` | string (non-empty) | One-liner. Used in commit message subject (`<type>: <id> - <title>`). |
| `userStories[].description` | string (non-empty) | Story narrative for the agent. |
| `userStories[].acceptanceCriteria` | array of non-empty strings (≥1) | Concrete checks the agent must satisfy before flipping to `passed`. |
| `userStories[].priority` | integer ≥ 1 | **Lower = higher priority.** Driver picks lowest `priority` whose `status` is `todo` or `in_progress`. |
| `userStories[].status` | enum `todo` / `in_progress` / `passed` / `blocked` | Lifecycle. See §7. Invariant: ≤1 story `in_progress` at iteration boundaries. |
| `userStories[].notes` | string (optional) | Agent-appended free-form (gotchas, blocker reasons). |
| `runner` | object — see §8 | **Required.** Agent invocation. |

## §7 Driver–Agent contract

Both driver and agent must honor these. Violations abort the loop.

### §7.1 Single in-progress invariant

At every iteration boundary (Step 10e), at most one story may have `status: in_progress`. The driver enforces this via `jq` / in-language count and aborts with exit 1 on violation.

### §7.2 PRD edit procedure (parse → mutate → serialize)

The agent MUST edit `prd.json` via this exact procedure:

1. Read file → `JSON.parse` (or runtime equivalent).
2. Mutate the in-memory object.
3. `JSON.stringify(obj, null, 2) + "\n"`.
4. Write to `prd.json.tmp` in the same directory.
5. Atomic rename `prd.json.tmp` → `prd.json`.
6. Re-read and re-parse to confirm.

The agent MUST NOT edit `prd.json` with `sed`, `awk`, `grep`, regex, or any line-anchored text tool. String values contain `"`, `\`, `\n`, full-width punctuation — text edits silently destroy object boundaries and the driver aborts the loop on next iteration when `loadAndValidatePrd` fails to parse.

Step 7b of the rendered `prompt.md` enforces a runtime-specific JSON-validity check **after** the commit lands (`jq empty` / `JSON.parse` / `python -c "json.load(...)"`).

### §7.3 OS sleep / hibernate during long runs

The driver runs the agent CLI synchronously per iteration. If the host OS suspends mid-iteration, the agent process freezes and the iteration's working tree is corrupt on resume (partial writes, abandoned `.commit-failure` retries).

Before launching the driver for a run expected to exceed ~30 minutes, suppress OS sleep:

| OS | Command |
|---|---|
| macOS | `caffeinate -i bash .ralph/ralph.sh` (or run inside a fresh iTerm tab; `caffeinate` is inherited) |
| Linux (systemd) | `systemd-inhibit --what=sleep --who=ralph --why="ralph loop" bash .ralph/ralph.sh` |
| Linux (other) | Disable sleep in GNOME / KDE / `xset s off` / power-management equivalent |
| Windows | `powercfg /change standby-timeout-ac 0` before launch; restore after (note: this is a global setting, not per-process) |

For SIGCONT-resumed runs: the driver does not detect suspend/resume natively. If a run resumes after suspend, inspect `git status` for partial writes before continuing.

### §7.4 Status-transition / commit-verify invariant

Any `todo`/`in_progress` → `passed` transition for a story between iterations MUST coincide with a new git commit on the branch (`HEAD` advanced). Driver step 10f compares `before_passed_set` vs `after_passed_set` and the pre/post HEAD SHA; mismatch aborts.

Limitation: the driver does NOT detect empty commits or unrelated commits. The agent contract forbids both — they're enforced by code review, not the driver.

### §7.5 Agent obligations A1–A7

The rendered `.ralph/prompt.md` codifies these. RUNBOOK and SKILL.md reference them as "Contract A1–A7":

- **A1.** Check for `.ralph/.commit-failure` before picking a new story. If present, repair only (see §12.2).
- **A2.** Read `prd.json` + `.ralph/progress.txt` (Codebase Patterns first).
- **A3.** Pick a single story — lowest `priority` whose `status` is `todo` or `in_progress`. Set `status: in_progress` if not already.
- **A4.** Implement that one story. Stay in scope — no edits to other stories.
- **A5.** Run all quality-check commands listed under `{{QUALITY_CHECKS}}` in `prompt.md`. All must pass.
- **A6.** Update the agent's memory file (`CLAUDE.md` / `AGENTS.md` / `GEMINI.md`) if a reusable pattern was discovered.
- **A7.** Atomically flip `status: passed` (or `blocked`) via §7.2, then commit code + PRD edit in one git commit, message `<type>: <Story ID> - <Story Title>`. Run JSON-validity check post-commit (step 7b). If validity check fails, forward-fix per `prompt.md` §7b.

### §7.6 Branch-state invariant

The agent MUST NOT run `git checkout`, `git reset`, `git stash`, `git rebase`, `git cherry-pick`, or `git branch` during an iteration. `git commit` on the current branch is required (A7) and explicitly allowed; the prohibition targets operations that switch the active branch or rewrite history.

The driver controls branch state at Step 8 (checkout / create from base). Mid-iteration branch mutation breaks the next iteration's setup.

## §8 Runner block

**Required.** Single source of truth for agent CLI invocation. Schema in `prd.schema.json` `#/definitions/runner`.

```json
"runner": {
  "command": "claude",
  "args": ["-p", "{PROMPT}", "--dangerously-skip-permissions"]
}
```

- `command` — non-empty string, the binary to spawn. Open-ended (supports `claude` / `copilot` / `gemini` / `aider` / `cursor-agent` / custom wrappers). **Security boundary** — see §8.3.
- `args` — non-empty array of non-empty strings. The literal token `"{PROMPT}"` is replaced at runtime by the contents of `.ralph/prompt.md`. If the sentinel is absent, the prompt is appended at the end of args with a stderr warning (degraded mode — still works, but invites user error).

### §8.1 Per-iteration revalidation

Every driver re-runs the runner shape check at the iteration boundary (Step 10d). Mid-loop corruption (agent or user hand-edit) aborts.

### §8.2 `--model` precedence (B3 strip-then-append)

When the driver is started with `--model X`:

1. Driver scans `runner.args` and strips every occurrence of `--model` / `--model=*` / `-m` / `-m=*`. For the long forms `--model` and `-m`, the **following arg** (the value) is also dropped. Dangling `--model` / `-m` at the end of `args` aborts.
2. After substituting `{PROMPT}` (per §8), the driver appends `--model X` once at the end.

Result: the spawned argv contains **exactly one** `--model` selector, sourced from the CLI flag. No reliance on agent CLI "last-flag-wins" behavior. When the driver is launched without `--model`, `runner.args` passes through verbatim (no strip).

A one-line stderr `ℹ️  Stripped N --model/-m flag(s)…` is emitted at startup when the strip is non-trivial, so users see why their `runner.args` `--model` didn't take effect.

### §8.3 Security — `runner.command` is process execution

`prd.json` is git-tracked. `runner.command` controls **which binary the driver spawns** every iteration, with `runner.args` as its argument list. A malicious PR can repoint `command` to anything on PATH (shell wrapper, curl-bash one-liner via `sh -c`, exfiltration script).

The schema deliberately does **not** allowlist `command` — we support legitimate non-default CLIs (`aider`, `cursor-agent`, custom wrappers). The security burden therefore lives in code review, not validation. RUNBOOK §7 ships a per-PR checklist.

## §9 Driver implementation

### §9.1 Authoritative bash skeleton

`templates/ralph/ralph.sh.tpl` is the authoritative implementation. Behavior of all other runtimes (ts/js/py) MUST mirror it modulo language idioms. If the bash script and another runtime disagree, the bash script wins and the other runtime is buggy.

Iteration loop (numbered steps in the script source):

| Step | Action | Failure mode |
|---|---|---|
| 1 | `cd` to repo root | n/a |
| 1.5 | Parse CLI `[N] [--model X]` | abort 1 on unknown |
| 2 | Probe required binaries (`git`, `jq` for sh) | abort 1 |
| 3 | Acquire `.ralph/.lock` via non-recursive `mkdir` | abort 1 if held |
| 4 | Working tree clean check | abort 1 |
| 5 | Validate `prd.json` (JSON, required fields, story status enum, runner shape) | abort 1 with migration message for missing `runner` |
| 6 | Detached-HEAD check | abort 1 |
| 7 | Detect base branch (`origin/HEAD` → `main` → `master` → `init.defaultBranch`) | abort 1 |
| 8 | Checkout / create `branchName` | abort 1 |
| 9 | Clear stale `.complete` sentinel | n/a |
| 9b | Capture initial SHA + timestamp for exit summary | n/a |
| 10 | Main loop — see §9.1.1 | various |
| 11 | If max iterations reached without exit, report and exit 1 | n/a |

#### §9.1.1 Per-iteration steps

| Step | Action |
|---|---|
| 10a | Pre-validate `prd.json` (catches user mid-edit corruption) |
| 10b | Snapshot HEAD SHA + already-passed story id set |
| 10b' | Backlog-exhausted pre-check — see §12.1 |
| 10c | Invoke agent (`runner.command` + resolved `runner.args` + optional `--model X`). Capture exit code; do not propagate yet. |
| 10c' | Commit-failure detection — see §12.2 |
| 10d | Post-validate `prd.json` (agent may have corrupted it) |
| 10e | Single-in-progress invariant (§7.1) |
| 10f | Commit-verify invariant (§7.4) |
| 10g | Sentinel cross-check — `.ralph/.complete` honored only if (all stories passed) AND (working tree clean) |
| 10h (post-stop-check) | Propagate agent's non-zero exit code if consistency checks all passed |

Stop-sentinel polling (Step 10g→10h boundary): if `.ralph/.stop` is present, the driver removes it, sets `SHOULD_STOP=1`, and breaks out of the loop with exit 0 (Step 11 reports max-iters as exit 1 only if `SHOULD_STOP` is unset). Mid-repair stop is honored too — exit 1 with working tree preserved.

### §9.2 Cross-runtime mapping

| Runtime | Source of truth | Mirror constraints |
|---|---|---|
| `sh` | `templates/ralph/ralph.sh.tpl` | Authoritative. Uses `jq` for all PRD reads. |
| `ts` | `templates/ralph/ralph.ts.tpl` | Run with `bun`. Validates in-language; mirrors numbered Step 1–11 exactly. |
| `js` | `templates/ralph/ralph.js.tpl` | CommonJS (parent `package.json` may be ESM; `.ralph/package.json` pins `"type":"commonjs"`). |
| `py` | `templates/ralph/ralph.py.tpl` | Run with `uv` or `python ≥ 3.11`. UTF-8 stdio reconfigure for Windows cp950 / cp1252. |

Signal exit codes: all 4 runtimes use POSIX `128 + signum` (`SIGINT → 130`, `SIGTERM → 143`, `SIGHUP → 129`, `SIGQUIT → 131`). Windows lacks `SIGHUP` / `SIGQUIT`; the py / ts / js drivers guard via `getattr(signal, 'SIGHUP', None)` / `process.on('SIGHUP'…)` (Node silently no-ops on unavailable signals).

`{PROMPT}` substitution + `--model` strip-and-append (§8.2) are identical across runtimes — each runtime has its own `strip_model_flags()` / `stripModelFlags()` helper with the same algorithm.

## §10 Verification (Phase 4)

Passive — no test runs, only file content / existence checks. Table in SKILL.md "Phase 4 — Verification" is the executable form of §4. Each row corresponds 1:1 with an §4 output guarantee.

## §11 Amend mode contract

Append-only on `prd.json.userStories`. Top-level fields (`project`, `branchName`, `description`, `runner`) MUST NOT be modified. `.ralph/*` files MUST NOT be touched.

### §11.1 Append-only invariant

For amend Phase B4:

- `userStories.length === N_old + N_new` (no padding).
- For every `i ∈ [0, N_old)`: `userStories[i]` deep-equals the pre-amend snapshot.
- New stories occupy indices `[N_old, N_old + N_new)` with `status === "todo"`, `id` matching `^US-\d{3,}$`, ≥1 `acceptanceCriteria`.
- Priorities of new stories are strictly greater than every pre-amend priority (append-to-tail, not insert-and-shift). Driver picks lowest priority first, so existing backlog runs before appended stories.

### §11.2 Atomic write & restore policy

Both the amend forward write (Phase B3) and the restore-on-failure path (Phase B4) follow the same tmp-and-rename protocol.

**Forward write (B3):**

1. Stringify the new document with 2-space indent + trailing LF.
2. Write to `prd.json.tmp` in the same directory as `prd.json` (same filesystem — required for an atomic rename).
3. Best-effort `fsync` if the host provides it.
4. Rename `prd.json.tmp` → `prd.json` (POSIX `mv -f` / Windows `Move-Item -Force`).
5. On Windows EPERM/EACCES (file-handle race), sleep 250ms once, retry the rename.
6. Second failure → delete `.tmp` unconditionally, abort with the original error. `prd.json` remains intact because the rename never landed.

**Restore-on-failure (B4):**

If any B4 hard-fail check fires, restore `prd.json` byte-for-byte from `preAmendSerialized` (captured in B1):

1. Write the raw bytes to `prd.json.restore.tmp`.
2. Rename → `prd.json` using the same retry-once-with-sleep policy as the forward write.
3. Delete any leftover `prd.json.tmp` from B3.
4. Print which check failed; abort non-zero.

Byte-for-byte restore preserves whitespace and key order — no noise diff if the user had already committed the pre-amend state.

### §11.3 Drift sanity check (B4-7)

After the B3 write lands, the amend verifier (SKILL step B4-7, not the runtime driver) re-hashes `.ralph/prompt.md`, `.ralph/ralph.<ext>`, `.ralph/RUNBOOK.md`, `.ralph/progress.txt` (and `.ralph/package.json` when `runtime == js`). Mismatch versus B1's `preAmendRalphHashes` is a **warn**, not a hard fail — surface drift in the closing message; user reconciles manually.

## §12 Driver enhancements (formerly v2 plans, now implemented)

This section absorbs what was previously tracked in a separate `meta-ralph-v2-plans.md` (now retired). Each enhancement has an Issue # for traceability against the original plan thread.

### §12.1 Issue #14 — Backlog-exhausted pre-check (Step 10b')

**Problem.** Without this check, the driver would invoke the agent CLI even when there's nothing actionable, burning tokens on empty iterations.

**Behavior.** At Step 10b', after PRD load + snapshot, before agent spawn:

- Count stories with `status` in `todo` / `in_progress`.
- If count == 0 **and** working tree is clean:
  - Clear any stale `.ralph/.commit-failure` (defensive — see §12.2 reset logic).
  - If 0 stories are `blocked` → exit 0 with "ALL STORIES COMPLETE".
  - Else → exit **2** (distinct from generic exit 1, signals "needs human attention"). Print blocked-story id + first 120 chars of `notes`.

**Working-tree-clean guard.** If dirty (e.g., previous iter hit commit-failure and `continue`d), defer the early-exit to Step 10c — otherwise we could silently exit 0 with uncommitted changes.

### §12.2 Issue #15 — Commit-failure detection & repair (gnhf-inspired)

**Problem.** Pre-commit hooks, lint gates, signing failures all cause `git commit` to fail. The agent exits non-zero, but the working tree is dirty (the agent did real work) and HEAD didn't move. Without explicit handling, the driver would abort and lose the WIP.

**Detection (Step 10c').** Three-condition AND:

1. `agent_exit != 0`
2. Working tree dirty (`git status --porcelain` non-empty)
3. HEAD didn't move (`before_sha == after_sha`)

**Sentinel.** Driver writes `.ralph/.commit-failure` as JSON `{retry, timestamp, iteration}` via tmp-and-rename. Increments retry on subsequent failures.

**Retry budget.** Limit 3 (`COMMIT_FAILURE_RETRY_LIMIT`). On 4th failure, abort exit 1 with "COMMIT REPAIR EXHAUSTED"; working tree preserved.

**Agent contract.** On iter start, agent reads `.ralph/.commit-failure` (A1). If present, repair is the only work this iteration — diagnose, fix root cause, re-run quality checks, commit with the same intended message, `rm .ralph/.commit-failure`. On retry == 3 the agent biases toward marking the story `blocked` + dropping WIP (`git restore --staged . && git restore .`) rather than another same-approach attempt. See `prompt.md` "Commit Repair" for the full procedure.

**Reset.** Driver auto-clears `.commit-failure` when the working tree is clean post-iter (Step 10f→10g boundary) — backstop in case the agent forgot. Also cleared on backlog-exhausted exit (§12.1) so a stale sentinel doesn't leak retry count into the next bootstrap.

**Stop-during-repair.** If `.ralph/.stop` is present during commit-failure repair, the driver honors it with exit 1 (tree dirty) — see §9.1.1 Step 10c'. Sustained commit failures otherwise swallow stop requests.

### §12.3 Issue #12 — Graceful stop sentinel (`.ralph/.stop`)

`touch .ralph/.stop` from another terminal. The driver polls it at the iteration boundary (between Step 10g and 10h), removes it, and exits 0 with "STOPPED BY USER". Sets the `SHOULD_STOP` flag before the agent-exit propagation so a graceful stop wins over a non-zero agent exit.

`SIGINT` (Ctrl-C) keeps single-stage v1 behavior: immediate exit 130 via signal trap. RUNBOOK §2 documents both surfaces.

---

## See also

- `plugins/meta-ralph/skills/meta-ralph/SKILL.md` — bootstrap + amend procedure (Phases 1–4 / B1–B4).
- `plugins/meta-ralph/skills/meta-ralph/templates/prd.schema.json` — formal `prd.json` schema.
- `plugins/meta-ralph/skills/meta-ralph/templates/ralph/ralph.sh.tpl` — §9.1 authoritative implementation.
- `plugins/meta-ralph/skills/meta-ralph/reference/prompt.md` — agent obligations A1–A7 (rendered into target repo as `.ralph/prompt.md`).
- `plugins/meta-ralph/skills/meta-ralph/templates/RUNBOOK.md.tpl` — operator intervention guide.
