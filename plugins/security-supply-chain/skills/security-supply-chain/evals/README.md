# Evals for `security-supply-chain`

Static-validation suite. Three checks, all deterministic, all run in seconds.

## What this suite is — and what it isn't

This skill ships **docs + native config examples**, not an LLM task chain. So the eval is not "run a prompt, grade an output" — it's "scan the files we ship and verify they're internally coherent and externally parseable."

The classes of bug this suite is designed to catch were all bugs that previously took multiple rounds of LLM review to surface (and some only surfaced *because* an earlier review introduced a regression). All of them are deterministically detectable:

| Past bug class | Reviewer round caught | This eval would have caught it |
|---|---|---|
| `\.lock\.` regex doesn't match `package-lock.json` / `pnpm-lock.yaml` | round 1 | `check_consistency` (regex coverage) |
| `pnpm config get` false-pass (`.npmrc` doesn't read workspace yaml) | round 1 | `check_consistency` (cross-doc claim) |
| `renovate.json` → `renovate.json5` filename drift | round 1 | `check_links` |
| `../../examples/` path wrong from 1-level-deep references | round 3 | `check_links` |
| `ignore-scripts=true` in `.npmrc` for pnpm (silent no-op) | round 4 (Copilot gpt-5.4) | `check_consistency` |
| `actions/checkout@v6.0.0` SHA actually pointing at v5.x | round 4 (Copilot gpt-5.4) | `validate_examples` (GH Actions SHA-pin format) |
| Dependabot patch floor `1` contradicts SKILL.md global `3` floor | round 4 (Copilot gpt-5.4) | `check_consistency` |
| `enableScripts` default wrongly stated to affect workspace packages | round 4 (Copilot gpt-5.4) | `check_consistency` |

## Running

```bash
# from the skill root (skills/security-supply-chain/)
./evals/run.sh

# or directly
python evals/scripts/validate_examples.py
python evals/scripts/check_links.py
python evals/scripts/check_consistency.py
```

Each script exits non-zero on failure. `run.sh` chains them with explicit per-check status.

## Dependencies

Python ≥3.11 (for `tomllib`). Pure-stdlib for the rest — no PyPI install required.

For YAML parsing the scripts use `ruamel.yaml` if available, falling back to `pyyaml`. At least one must be installed:

```bash
pip install ruamel.yaml      # preferred
# or
pip install pyyaml
```

`json5` is parsed via a tolerant manual reader since `json5` isn't in stdlib and the only `.json5` file we ship is `renovate.json5`.

## CI

Hook into any CI runner with one line:

```yaml
- run: python plugins/security-supply-chain/skills/security-supply-chain/evals/scripts/validate_examples.py && \
       python plugins/security-supply-chain/skills/security-supply-chain/evals/scripts/check_links.py && \
       python plugins/security-supply-chain/skills/security-supply-chain/evals/scripts/check_consistency.py
```

Or call `run.sh`.

## When to update

- Adding a new package manager → add its example dir to `validate_examples.py`'s parser dispatch table; add its version claims to `check_consistency.py`'s rules.
- Adding a new reference file → no change needed (`check_links.py` walks the tree automatically).
- A reviewer catches a bug class not covered here → add a rule.
