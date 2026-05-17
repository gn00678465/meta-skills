# pnpm Supply Chain Hardening

**Open when:** configuring pnpm against malicious-version attacks — `minimumReleaseAge`, `blockExoticSubdeps`, `allowBuilds`, `ignoreScripts`, `savePrefix`.

**Source of truth (configs):**
- [`examples/pnpm/pnpm-workspace.yaml`](../../examples/pnpm/pnpm-workspace.yaml) — age gate + exotic-subdeps block + script allowlist + kill-switch + exact-pin
- [`examples/pnpm/.npmrc`](../../examples/pnpm/.npmrc) — **auth and registry only**

Merge those files' keys into your existing config — do **not** replace your files. This document explains the reasoning and the footguns.

## ⚠️ The `.npmrc` Trap

pnpm reads only **auth and registry** settings from `.npmrc`. Behavior settings — `ignore-scripts`, `save-exact`, `min-release-age`, etc. — placed in `.npmrc` are **silently ignored** by pnpm. They live in `pnpm-workspace.yaml` instead, with different (camelCase) names:

| What you might write in `.npmrc` (ignored) | Where it actually goes (in `pnpm-workspace.yaml`) |
|---|---|
| `ignore-scripts=true` | `ignoreScripts: true` |
| `save-exact=true` | `savePrefix: ""` |
| `min-release-age=7` | `minimumReleaseAge: 10080` (minutes) |

The npm `.npmrc` syntax works for npm but **silently no-ops for pnpm**. See [pnpm's .npmrc docs](https://pnpm.io/npmrc) for the exact keys pnpm honors.

## Minimum Release Age (pnpm ≥10.16)

Key line in [`pnpm-workspace.yaml`](../../examples/pnpm/pnpm-workspace.yaml):
```yaml
minimumReleaseAge: 10080   # MINUTES
```

Unit is **minutes** — different from Bun (seconds) and npm (days). 10080 = 7 days. Lower bound 4320 (3 days) without a written reason.

When pnpm refuses an install, the error reads `ERR_PNPM_PACKAGE_TOO_FRESH` (or names the offending package and its age). Read the error before bumping the threshold.

**Glob patterns** in `minimumReleaseAgeExclude` require pnpm **≥10.17.0**; exact-name matching works on 10.16.

## `blockExoticSubdeps` (pnpm ≥10.26.0)

[Default `true`](https://pnpm.io/settings#blockexoticsubdeps) since pnpm 10.26. Listed explicitly in the example so reviewers see the policy and any accidental override is visible in diff.

It prevents *transitive* dependencies from being pulled from git URLs or tarball URLs — a smuggling path where a hijacked sub-dep replaces a registry pointer with `git+ssh://attacker/...`. Direct dependencies in your root `package.json` are still allowed to use those sources.

### Remediation ladder when an install fails because of `blockExoticSubdeps`

**Do not disable it.** Work through:

1. `pnpm why <offending-package>` — see which direct dep pulled in the exotic transitive.
2. If upstream is mature, file an issue asking them to depend on the registry copy instead of git.
3. If you control a fork, publish it to the registry (or your internal mirror) and add `pnpm.overrides` pinning the transitive to the registry version.
4. Last resort: promote the exotic dep to a *direct* dependency in your root `package.json` so it surfaces in code review and provenance audits.

## Lifecycle-Script Allowlist (pnpm ≥10.26.0)

`allowBuilds` in `pnpm-workspace.yaml` was **added in pnpm 10.26.0**. pnpm 11 also removes the legacy `pnpm.onlyBuiltDependencies` array in `package.json` (the `package.json` `pnpm` namespace is no longer read in v11).

**Workflow (allowlist first, kill-switch second):**

1. `pnpm install --ignore-scripts` — see what fails.
2. Add only the packages you actually need to `allowBuilds` (or run `pnpm approve-builds` to populate interactively).
3. Set `ignoreScripts: true` in `pnpm-workspace.yaml`.

Cross-PM picture: [`../lifecycle-script-allowlists.md`](../lifecycle-script-allowlists.md).

### pnpm 10.x (legacy form, before allowBuilds existed)

If you're on pnpm <10.26, you have the legacy form:

```json
// package.json — pnpm <10.26 only
{
  "pnpm": {
    "onlyBuiltDependencies": ["esbuild", "@prisma/client"]
  }
}
```

Plan an upgrade to pnpm 10.26+ or 11.x. The legacy form is not in [`examples/pnpm/`](../../examples/pnpm/) because new projects should not adopt it.

## Exact Pinning

`savePrefix: ""` in `pnpm-workspace.yaml` is the pnpm equivalent of npm's `save-exact=true`. Strips `^`/`~` from new installs.

**Existing ranges in `package.json` keep floating** until you regenerate the lockfile. To pin the existing tree after switching the policy:

```bash
pnpm install --lockfile-only
```

## Package Manager Pinning

In `package.json`:

```json
"packageManager": "pnpm@10.26.0+sha512.<integrity-hash>"
```

Generate the hash with `corepack use pnpm@10.26.0`. Pins pnpm itself — a compromised pnpm release cannot auto-update.

## Verification

```bash
pnpm config get minimumReleaseAge       # expect: 10080 (or your value)
pnpm config get blockExoticSubdeps      # expect: true
pnpm config get ignoreScripts           # expect: true (if kill-switch is on)
pnpm config get savePrefix              # expect: ""
```

Functional test: pick a package version published in the last 24h and try `pnpm add <pkg>@<fresh-version>`. The error **must** contain `minimumReleaseAge` or `PACKAGE_TOO_FRESH`. Any other failure (404, 403, network) means the test is invalid — pick a different fresh package.

## Upstream Docs

- [pnpm `.npmrc` — only auth and registry settings honored here](https://pnpm.io/npmrc)
- [`minimumReleaseAge`](https://pnpm.io/settings#minimumreleaseage)
- [`minimumReleaseAgeExclude`](https://pnpm.io/settings#minimumreleaseageexclude)
- [`blockExoticSubdeps`](https://pnpm.io/settings#blockexoticsubdeps)
- [`allowBuilds`](https://pnpm.io/settings#allowbuilds)
- [`ignoreScripts`](https://pnpm.io/settings#ignorescripts)
- [`savePrefix`](https://pnpm.io/settings#saveprefix)
- [`pnpm approve-builds`](https://pnpm.io/cli/approve-builds)
- [Supply chain security overview](https://pnpm.io/supply-chain-security)
