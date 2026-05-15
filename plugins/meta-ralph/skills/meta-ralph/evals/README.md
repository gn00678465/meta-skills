# meta-ralph runner evals

Runner-focused validation suite for the driver templates (`sh` / `ts` / `js` / `py`).

## What gets tested

Each scenario in `evals.json` exercises one runner-related code path:

- **runner-mandatory gating** — driver aborts when `prd.json.runner` is absent.
- **B3 strip-then-append** — `--model` / `--model=*` / `-m` / `-m=*` are stripped from `runner.args` when CLI `--model X` is given, then `--model X` is appended once.
- **dangling-flag abort** — trailing `--model` with no value triggers a clean abort.
- **`{PROMPT}` substitution** — sentinel inside `runner.args` is replaced with `.ralph/prompt.md` content byte-for-byte.
- **`{PROMPT}` missing-sentinel fallback** — prompt is appended at the end of args with a stderr warning.
- **trailing newline preservation** — prompt content's trailing `\n` survives substitution (cross-runtime parity check).
- **embedded newline preservation** — a single `runner.args` element containing `\n` stays as one argv entry (cross-runtime parity check).

12 scenarios × 4 runtimes = 48 runs per iteration.

## How it works

For each (scenario × runtime), `run_evals.py`:

1. Creates a temp directory, `git init`s it, makes an empty initial commit, sets `core.autocrlf=false`.
2. Writes a controlled `prd.json` for the scenario. `runner.command` is set to the current Python interpreter (`sys.executable`); `runner.args` starts with the absolute path to `mock-agent.py`, followed by the scenario's args.
3. Writes `.ralph/prompt.md` with the scenario's prompt content (preserving exact bytes).
4. Copies the driver template to `.ralph/ralph.<ext>`, normalizing line endings to LF.
5. Commits everything so the driver's working-tree-clean check passes.
6. Invokes the driver with max-iter=1 (and optional `--model X`).
7. The driver's iter-1 spawns the mock; the mock dumps its `sys.argv[1:]` to `argv_dump.json`.
8. After the driver exits, the harness reads `argv_dump.json` + stderr + exit code, then runs scenario-specific assertions.

## Running

From the repo root, with Python 3.11+ on PATH and `bash` + `jq` + `bun` + `node` installed (so all 4 runtimes work):

```bash
# Run everything
python plugins/meta-ralph/skills/meta-ralph/evals/run_evals.py

# Subset a runtime (useful while debugging)
python plugins/meta-ralph/skills/meta-ralph/evals/run_evals.py --runtime sh

# Subset a scenario
python plugins/meta-ralph/skills/meta-ralph/evals/run_evals.py --scenario strip-long-form,dangling-aborts

# Keep sandbox tmpdirs around for post-mortem inspection
python plugins/meta-ralph/skills/meta-ralph/evals/run_evals.py --keep-sandbox

# Tag this run as iteration-2 (separate output dir)
python plugins/meta-ralph/skills/meta-ralph/evals/run_evals.py --iteration 2
```

Exits non-zero if any assertion failed.

## Output

```
evals/results/iteration-1/
├── benchmark.md                                       # human-readable summary
├── results.json                                       # machine-readable
└── <NN>-<scenario-name>/
    └── <runtime>/
        ├── grading.json                                # per-assertion pass/fail
        ├── stderr.txt
        ├── stdout.txt
        └── argv_dump.json   (if mock was spawned)
```

`grading.json` uses the skill-creator schema (`expectations: [{text, passed, evidence}]`) so it can be fed to the eval-viewer later if needed.

## Dependencies

| Runtime | Needs |
|---|---|
| sh | `bash` ≥ 4, `jq` (`bash` on Windows requires git-bash or WSL) |
| ts | `bun` ≥ 1.1 |
| js | `node` ≥ 18 |
| py | `python` ≥ 3.11 |

The harness itself (`run_evals.py`) only needs `python` ≥ 3.10 and `git`.

## sh byte-faithfulness regression tests

Two scenarios specifically guard against historical `sh`-only drift bugs (caught by iteration-1 of this eval, fixed in commit `78dd687`). All four runtimes now pass them; they remain as regression tests so the fixes don't quietly regress.

- `prompt-trailing-newline-preserved` — `sh` driver previously used `PROMPT_CONTENT=$(cat .ralph/prompt.md)`, which stripped trailing newlines. Now uses `$(cat .ralph/prompt.md; printf x)` + `${VAR%x}` sentinel-trim to preserve trailing bytes byte-for-byte (cross-runtime parity).
- `embedded-newline-in-args-preserved` — `sh` driver previously read `runner.args` via `jq -r '.runner.args[]' | while IFS= read -r …`, which split any embedded `\n` into multiple argv entries. Now uses NUL-delimited reads (`jq -j '.runner.args[] + "\u0000"' | tr -d '\r'` + `while IFS= read -r -d ''`) so a single `args` element containing `\n` stays one argv entry.

A third companion fix lives in the same commit: `tr -d '\r'` is piped after every `jq` output because Windows `jq.exe` text-mode emits CRLF, which non-byte-faithful `read -r` would not strip.
