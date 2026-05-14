# meta-ralph

Pure scaffolder for the [ralph](https://ghuntley.com/ralph/) autonomous coding loop. Writes `prd.json` + `.ralph/*` into a target git repo so an agent CLI (`claude` / `copilot` / `gemini`) can iterate on the backlog until done. The skill itself never executes the loop — once scaffolded you start the driver manually.

The authoritative spec is `SKILL.md`; this README is the user-facing quickstart.

## Two modes

**Bootstrap** (default) — first-run scaffolding:

```
init ralph for my CLI tool
```

The skill asks for agent + runtime, then grills 6 questions (description, users, success criteria / user stories, quality-check commands, branch name, project name) and writes `prd.json` + `.ralph/*`.

**Amend** (`--amend`) — append more user stories to an existing PRD:

```
--amend add OAuth login flow and 2FA
```

Append-only on `userStories`. Top-level fields and `.ralph/*` are left untouched, so a running driver keeps its state. Trying to change agent / runtime / quality checks requires re-bootstrap.

### Trigger phrases

Either typing the phrase or invoking `/meta-skills:meta-ralph` works. Bootstrap and amend share the same skill; `--amend` switches mode.

- **Bootstrap:** "init ralph", "set up ralph", "scaffold ralph", "bootstrap ralph", "建立 ralph", "初始化 ralph", "ralph 起手"
- **Amend:** "append stories", "add more user stories", "extend the ralph PRD", "想多加幾項", "加幾個 story", "在現有 PRD 補 stories", "追加 stories", "新增 user story"

## What gets scaffolded

```
target-project/
├── prd.json                 (git tracked — PRD with userStories)
├── .gitignore               (appended: .ralph/.lock, .ralph/.complete, …)
└── .ralph/
    ├── prompt.md            (agent instructions, memory file resolved)
    ├── ralph.<sh|ts|js|py>  (loop driver, runtime-specific)
    ├── RUNBOOK.md           (operator intervention guide)
    └── progress.txt         (seeded with `## Codebase Patterns`)
```

`.ralph/.lock`, `.ralph/.complete`, `.ralph/.commit-failure`, `.ralph/.stop` are runtime-only — the skill never writes them; the driver and `.stop` sentinel manage them at run time.

## Agent / runtime matrix

| Agent | Memory file | Notes |
|---|---|---|
| `claude` | `CLAUDE.md` | Uses `-p` + `--dangerously-skip-permissions` |
| `copilot` | `AGENTS.md` | Uses `--yolo --allow-tools --prompt` |
| `gemini` | `GEMINI.md` | Uses `-p` + `--yolo` |

| Runtime | Run command | Requires |
|---|---|---|
| `sh` | `bash .ralph/ralph.sh [N] [--model X]` | `bash`, `jq`; on Windows needs git-bash or WSL |
| `ts` | `bun run .ralph/ralph.ts [N] [--model X]` | Bun ≥ 1.1 |
| `js` | `node .ralph/ralph.js [N] [--model X]` | Node ≥ 18 |
| `py` | `uv run .ralph/ralph.py [N] [--model X]` | Python ≥ 3.11 (`uv` preferred) |

`[N]` overrides max iterations (default 10); `--model X` is passed through to the agent CLI.

## Operating the loop

After scaffolding the skill prints the exact start command for your chosen runtime. From there, `.ralph/RUNBOOK.md` is the operator's intervention guide — it covers status inspection, graceful stop (`touch .ralph/.stop`), recovery from `.ralph/.commit-failure`, and what to do when the agent loops.

For long runs (>30 min): suppress OS sleep before launching the driver — suspend will freeze the agent process and corrupt the iteration on resume. See `docs/meta-ralph-spec.md` §7.3 for OS-specific commands.

## Runtime configuration via `prd.json.runner`

`runner` is **required** in `prd.json` — it's the single source of truth for how the agent CLI is spawned each iteration. The scaffolder writes it for you tailored to the chosen agent; edit it later to switch CLI, change model, or tweak flags without re-running the skill:

```json
{
  "runner": {
    "command": "claude",
    "args": ["-p", "{PROMPT}", "--model", "opus", "--dangerously-skip-permissions"]
  }
}
```

- Both `command` (non-empty string) and `args` (non-empty array of non-empty strings) are required (schema-enforced).
- Use `"{PROMPT}"` as the placeholder for the prompt content (`.ralph/prompt.md`); the driver replaces it at runtime. If missing, prompt is appended at the end with a warning.
- **`--model X` is a true override (B3 strip-then-append):** when you run the driver with `--model X`, it strips any existing `--model` / `--model=*` / `-m` / `-m=*` tokens from `runner.args` (and their values), then appends `--model X` once. Without the CLI flag, `runner.args` passes through verbatim. The spawn args always contain at most one `--model` selector — no reliance on agent "last-flag-wins" behavior.
- All 4 driver runtimes (`sh` / `ts` / `js` / `py`) implement identical strip + substitute + append logic. `sh` parses via `jq`; `ts` / `js` / `py` validate via in-language type checks.

Security note: `runner.command` controls process execution. Treat `prd.json` edits in PRs the same way you'd treat code changes — a malicious `command` change is a process-injection vector. The schema deliberately keeps `command` open-ended (so `aider`, `cursor-agent`, custom wrappers still work); the security burden lives in code review.

Migration (existing PRDs scaffolded before runner was mandatory): driver and amend mode both abort with a message that includes the exact JSON block to paste in. Add the `runner` block (see Agent / runtime matrix above for the default per agent), commit, and re-run.

## Further reading

- `SKILL.md` — full skill spec (bootstrap phases, amend phases, pre-flight checks, verification table).
- `docs/meta-ralph-spec.md` — authoritative Driver–Agent Contract, bash skeleton, known v1 limits, v2 plans index.
- `docs/meta-ralph-v2-plans.md` — detailed designs for v2 plans, indexed 1:1 against spec §12.
- `docs/meta-ralph.md` — original design notes (historical context).
- `templates/prd.schema.json` — schema used by Phase 4 verification.
- `templates/RUNBOOK.md.tpl` — operator guide template rendered at scaffold time.
- `reference/prompt.md` — agent prompt template loaded at scaffold time.
- `scripts/parse-args.sh` / `scripts/parse-args.ps1` — `$ARGUMENTS` parsers for mode dispatch.
