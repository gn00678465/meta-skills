# npm Supply Chain Hardening

**Open when:** configuring npm against malicious-version attacks — `min-release-age`, `save-exact`, avoiding `_authToken` leaks.

**Source of truth (config):**
- [`examples/npm/.npmrc`](../../examples/npm/.npmrc) — age gate + save-exact + script kill-switch (with auth warning)

Merge those keys into your existing `.npmrc`. This document explains the reasoning, the auth-leak footgun, and the workflow for pinning the existing tree.

## Minimum Release Age (npm ≥11.10)

Key line:
```ini
min-release-age=7   # DAYS
```

Unit is **days** — different from pnpm (minutes) and Bun (seconds). 7 days is the default. Lower bound 3 days without a written reason.

## ⚠️ Auth-leak footgun

The example `.npmrc` is commit-safe **only** because it contains no auth fields. A committed `.npmrc` is fine as long as it contains only non-secret config. Auth lines must live in `~/.npmrc` (per-user) or come from a CI env var via interpolation in the committed file.

**Forbidden in a repo's `.npmrc`:**

```ini
# DO NOT COMMIT THESE
_authToken=npm_xxxxxxxxxxxx
_auth=base64...
_password=...
email=...
//registry.npmjs.org/:_authToken=npm_xxxxxxxxxxxx
```

**Safe interpolation pattern** (committable):

```ini
//registry.npmjs.org/:_authToken=${NPM_TOKEN}
```

### Audit existing `.npmrc` files

```bash
grep -E '_authToken=npm_|_auth=|_password|email=' .npmrc           # bash
Select-String -Path .npmrc -Pattern '_authToken=npm_|_auth=|_password|email='  # pwsh
```

If a token is in git history, **rotate the token first**, then rewrite history with `git filter-repo --replace-text` and force-push. Assume the token is leaked even after rewrite — anyone who cloned the repo before the rewrite still has it.

## `save-exact=true` — affects new installs only

`save-exact=true` strips `^`/`~` from **new** `npm install` writes. Existing `^4.x` ranges in `package.json` keep floating until you regenerate the lockfile.

To pin the **existing** tree after switching the policy:

```bash
npm install --package-lock-only
```

This re-resolves all ranges and locks them in `package-lock.json` without touching `node_modules`.

## Lifecycle Scripts — no native allowlist

npm has no native allowlist mechanism — it's all-or-nothing via `ignore-scripts=true`. Wrap with `@lavamoat/allow-scripts` for fine-grained control:

```bash
npx allow-scripts setup        # one-time: writes config skeleton to package.json
npx allow-scripts auto         # interactively populate allowlist from current deps
```

In CI:
```bash
npm ci --ignore-scripts        # install without scripts
npx allow-scripts run          # run only the allowlisted scripts
```

Cross-PM picture: [`../lifecycle-script-allowlists.md`](../lifecycle-script-allowlists.md).

## 2FA / Account Hardening

Use `npm access set mfa=publish <package>` (npm v11+) on every published package so even a stolen token cannot publish without a hardware key tap. **Avoid SMS-based 2FA** — SIM swaps account for a non-trivial share of takeovers.

See [`../publish-path-hardening.md`](../publish-path-hardening.md) for the full publish-side hardening (OIDC, provenance, Trusted Publishing).

## Package Manager Pinning

```json
"packageManager": "npm@10.5.0+sha512.<integrity-hash>"
```

Generate the hash with `corepack use npm@10.5.0`.

## Verification

```bash
npm config get min-release-age        # expect: 7
npm config get save-exact             # expect: true
npm config get ignore-scripts         # expect: true (if you enabled the kill-switch)
```

Functional test:
```bash
npm install <pkg>@<fresh-version>     # version published in the last 24h
```

The error **must** contain `min-release-age` wording. Generic 404 / network errors mean the test is invalid.

## Upstream Docs

- [`min-release-age`](https://docs.npmjs.com/cli/v11/using-npm/config#min-release-age) — npm CLI v11+
- [`save-exact`](https://docs.npmjs.com/cli/v11/using-npm/config#save-exact)
- [`npm access`](https://docs.npmjs.com/cli/v11/commands/npm-access)
- [Generating provenance statements](https://docs.npmjs.com/generating-provenance-statements)
- [`npm audit signatures`](https://docs.npmjs.com/cli/v11/commands/npm-audit)
- [`@lavamoat/allow-scripts` guide](https://lavamoat.github.io/guides/allow-scripts/)
