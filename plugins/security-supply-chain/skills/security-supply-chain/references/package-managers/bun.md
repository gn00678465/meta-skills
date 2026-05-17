# Bun Supply Chain Hardening

**Open when:** configuring Bun against malicious-version attacks — `minimumReleaseAge`, `trustedDependencies`, `ignoreScripts`, `linker`.

**Source of truth (config):**
- [`examples/bun/bunfig.toml`](../../examples/bun/bunfig.toml) — age gate + explicit-no-hoisted check + ignoreScripts guidance

Merge those keys into your existing `bunfig.toml`. This document explains the reasoning and the two non-obvious footguns.

## Minimum Release Age (Bun ≥1.2)

Key line:
```toml
[install]
minimumReleaseAge = 604800   # SECONDS
```

Unit is **seconds** — different from pnpm (minutes) and npm (days). 604800 = 7 days. Easy to mix up; check the comment in [`bunfig.toml`](../../examples/bun/bunfig.toml).

## ⚠️ Verify the Linker, Don't Just Assume `isolated`

Bun's `isolated` linker is the phantom-dependency defense. Stay on `isolated`, but **don't assume you're already on it**:

| Project shape | Default linker |
|---|---|
| New workspace (Bun ≥1.3.2) | `isolated` ✓ |
| New single-package project | `hoisted` ⚠️ |
| Project created before Bun 1.3.2 | `hoisted` ⚠️ |

`bun pm` does not currently expose a `config get` subcommand, so settings cannot be introspected from the CLI. Verify the active linker by inspecting `node_modules/` structure:

```bash
# isolated linker: deps live under node_modules/.bun/ and are symlinked
ls node_modules/.bun 2>/dev/null && echo "linker = isolated"

# hoisted linker: deps appear directly under node_modules/
ls node_modules/.bun 2>/dev/null || echo "linker = hoisted (or unknown)"
```

If you're on `hoisted`, explicitly set `linker = "isolated"` in `bunfig.toml`. The phantom-dep risk is independent of the age gate — hoisted mode lets code `require()` packages **not declared** in `package.json`, the exact attack surface a hijacked transitive uses to escape an audit of your direct deps.

## `trustedDependencies` (allowlist) — lives in `package.json`

Bun does not run `postinstall` for any third-party package by default — they must opt in via `trustedDependencies` at the top level of `package.json`:

```json
// package.json — top-level, NOT under "bun"
"trustedDependencies": ["esbuild", "sharp", "@prisma/client"]
```

### Caveat — `trustedDependencies` does NOT cover non-registry specifiers

The allowlist applies only to **registry-resolved** dependencies. It does **not** cover:

- `file:` specifiers (local paths)
- `link:` specifiers (linked workspace)
- `git:` / `github:` specifiers (git URLs and shorthand)

If you depend on a `git:` package and need its postinstall, vendor it through a registry or accept that its scripts will not run. Read [Bun's lifecycle docs](https://bun.com/docs/install/lifecycle) for current behavior.

## ⚠️ `ignoreScripts` Overrides `trustedDependencies`

This is the second non-obvious footgun. Setting `ignoreScripts = true` in `bunfig.toml` disables **all** lifecycle scripts — **including** the packages you allowlisted in `trustedDependencies`. This is **different** from pnpm/Yarn, where the kill-switch and the allowlist co-exist.

Recommended workflow:

- Leave `ignoreScripts` **unset** in normal projects. Bun already defaults to not running scripts for most third-party packages; `trustedDependencies` lets the necessary ones through.
- Enable `ignoreScripts = true` **only** in high-risk environments (CI runners that don't need native builds, or environments using a vendoring proxy that builds packages out-of-band). Accept that allowlisted scripts also stop running.

The example file ships `ignoreScripts` **commented out** for this reason.

## Package Manager Pinning

```json
// package.json
"packageManager": "bun@1.2.0"
```

Bun does not yet support the corepack integrity-hash format — track upstream for when it lands.

## Verification

`bun pm` does not expose `config get` (verified against Bun 1.3.11). Settings can't be read back via CLI — verify by **functional test only**, which is the more reliable check anyway.

### Step 1 — pick a genuinely fresh version

Query the registry for the precise publish time of the target version. Do **not** rely on `time.modified` — that field reflects registry metadata changes (deprecate/unpublish), not the version's publish date.

```bash
curl -s https://registry.npmjs.org/<pkg> | \
  python -c "import json,sys; d=json.load(sys.stdin); v=d['dist-tags']['latest']; print(v, d['time'][v])"
```

Pick a version with a publish time within the last 24h.

### Step 2 — try to add it

```bash
bun add <pkg>@<fresh-version>
```

The error **must** contain `minimum-release-age` (Bun emits the kebab-case form, e.g. `blocked by minimum-release-age: 604800 seconds`). Generic 404 / network / `failed to resolve` without that phrase means the test is invalid — pick a different fresh package.

### Step 3 — confirm older versions still install

```bash
bun add <pkg>@<old-version>     # > 7 days old; should succeed
```

This is the negative control — proves the gate isn't simply blocking the entire package.

## Upstream Docs

- [`minimumReleaseAge` in bunfig](https://bun.com/docs/runtime/bunfig#installminimumreleaseage)
- [`linker` defaults and behavior](https://bun.com/docs/runtime/bunfig#installlinker)
- [Install lifecycle (`trustedDependencies`, `ignoreScripts`)](https://bun.com/docs/install/lifecycle)
- [`bun install` CLI flags](https://bun.com/docs/pm/cli/install)
- [`bun pm audit`](https://bun.com/docs/pm/cli/audit)
