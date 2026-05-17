# Yarn 4 Supply Chain Hardening

**Open when:** configuring Yarn 4 (Berry) against malicious-version attacks — `npmMinimalAgeGate`, `defaultSemverRangePrefix`, `enableScripts`.

This skill covers Yarn 4 (Berry) only. Yarn 1 (Classic) is end-of-life — migrate to Yarn 4 or another PM.

**Source of truth (config):**
- [`examples/yarn/.yarnrc.yml`](../../examples/yarn/.yarnrc.yml) — age gate + save-exact-equivalent + script kill-switch (with auth warning)

Merge those keys into your existing `.yarnrc.yml`. This document explains the reasoning.

## Minimum Release Age (Yarn ≥4.10)

Key line:
```yaml
npmMinimalAgeGate: "7d"
```

Minimum version is **4.10** (introduced via [berry PR #6901](https://github.com/yarnpkg/berry/pull/6901), released 2025-09-18). The Yarn security documentation page sometimes cites "4.12 introduced" — the GitHub release notes are authoritative; 4.10 is the real floor. Accepts duration shorthand: `"7d"`, `"24h"`.

## Lifecycle Scripts — Default-Off for Third-Party

Yarn 4 already disables `postinstall` for non-workspace packages by default. `enableScripts: false` is the implicit default. The example file lists it explicitly so reviewers see the policy and any accidental override is visible in diff.

To opt specific packages back in, use `dependenciesMeta` in `package.json`:

```json
"dependenciesMeta": {
  "esbuild": { "built": true },
  "sharp": { "built": true }
}
```

Cross-PM picture: [`../lifecycle-script-allowlists.md`](../lifecycle-script-allowlists.md).

## ⚠️ Auth Hygiene

`.yarnrc.yml` can hold `npmAuthToken` and `npmAuthIdent` keys. Treat them like npm's `_authToken`:

- Never commit literal tokens.
- Use `${NPM_TOKEN}` interpolation in the committed file.
- Audit with: `grep -E 'npmAuthToken|npmAuthIdent' .yarnrc.yml` (bash) or `Select-String -Path .yarnrc.yml -Pattern 'npmAuthToken|npmAuthIdent'` (PowerShell).
- If a token is in git history, rotate first, then `git filter-repo --replace-text`, then force-push.

## Package Manager Pinning

```json
"packageManager": "yarn@4.10.0+sha512.<integrity-hash>"
```

Generate the hash with `corepack use yarn@4.10.0`.

## Verification

```bash
yarn config get npmMinimalAgeGate           # expect: 7d
yarn config get defaultSemverRangePrefix    # expect: ""
yarn config get enableScripts               # expect: false
```

Functional test:
```bash
yarn add <pkg>@<fresh-version>              # version published in the last 24h
```

The error **must** contain `npmMinimalAgeGate` wording. Generic 404 / network errors mean the test is invalid.

## Upstream Docs

- [`npmMinimalAgeGate`](https://yarnpkg.com/configuration/yarnrc#npmMinimalAgeGate)
- [`defaultSemverRangePrefix`](https://yarnpkg.com/configuration/yarnrc#defaultSemverRangePrefix)
- [`enableScripts`](https://yarnpkg.com/configuration/yarnrc#enableScripts)
- [`dependenciesMeta`](https://yarnpkg.com/configuration/manifest#dependenciesMeta)
- [berry PR #6901 — introduces npmMinimalAgeGate (released in v4.10.0)](https://github.com/yarnpkg/berry/pull/6901)
- [Yarn supply chain security overview](https://yarnpkg.com/features/security)
