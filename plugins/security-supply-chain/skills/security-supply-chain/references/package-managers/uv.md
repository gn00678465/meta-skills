# uv Supply Chain Hardening

**Open when:** configuring [uv](https://docs.astral.sh/uv/) against malicious-version attacks — `exclude-newer` in `pyproject.toml`.

uv replaces pip + pip-tools + virtualenv + poetry for most projects. If you can move Python projects to uv, do it — `exclude-newer` is more ergonomic and stable than pip's `--uploaded-prior-to` and is fully supported in CI today.

**Source of truth (config):**
- [`examples/uv/pyproject.toml`](../../examples/uv/pyproject.toml) — the `[tool.uv]` section to merge

Merge the `[tool.uv]` block into your existing `pyproject.toml`. This document explains the reasoning and the value-format options.

## Minimum Release Age (uv ≥0.9.17)

Key line:
```toml
[tool.uv]
exclude-newer = "7 days"
```

uv accepts:
- Human duration: `"7 days"`, `"24 hours"`, `"1 week"`
- ISO 8601 duration: `"P7D"`
- Absolute timestamp: `"2026-01-15T00:00:00Z"`

> The `"7d"` shorthand is **not documented**. Use `"7 days"` or `"P7D"`.

Relative durations require **uv ≥0.9.17**. Earlier versions accept only absolute timestamps.

## Per-Index Variant (advanced)

If you mirror PyPI through an internal index, enforce cooldowns at the **proxy**, not in `[[tool.uv.index]]`. As of writing, `exclude-newer` is documented as a top-level `[tool.uv]` setting, not a per-index setting. See [`../registry-controls.md`](../registry-controls.md).

## Lockfile Workflow

```bash
uv lock                       # generate uv.lock
uv sync --locked              # install exactly what's locked (CI)
```

Commit `uv.lock`. In CI, always use `--locked` to fail on drift.

## Audit

```bash
uv pip audit                  # scan installed packages for known CVEs
```

## Verification

```bash
uv add <pkg>==<fresh-version>      # version published in the last 24h
```

The error **must** contain `exclude-newer` wording. Generic 404 / network errors mean the test is invalid.

## Upstream Docs

- [`exclude-newer`](https://docs.astral.sh/uv/reference/settings/#exclude-newer)
- [Reproducible resolutions](https://docs.astral.sh/uv/concepts/resolution/#reproducible-resolutions)
- [uv 0.9.17 release notes](https://github.com/astral-sh/uv/releases/tag/0.9.17)
