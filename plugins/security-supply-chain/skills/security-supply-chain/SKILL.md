---
name: security-supply-chain
description: Harden JavaScript/TypeScript and Python package manager configs (pnpm, bun, npm, yarn, uv, pip) against supply chain attacks using minimum release age gates, lockfile commitment, exact version pinning, lifecycle-script allowlists, provenance/attestation, OIDC trusted publishing, and secret-scanning at commit time. Use when initializing projects, configuring dependency bots (Renovate, Dependabot), reviewing package manager config files (.npmrc, pnpm-workspace.yaml, bunfig.toml, .yarnrc.yml, pyproject.toml, dependabot.yml, renovate.json), evaluating whether a specific package@version is safe to install today, rotating publish tokens or migrating to Trusted Publishing, hardening a developer workstation, or responding to a published npm/PyPI compromise (TanStack-style hijacks, chalk/debug, qix, recent malicious-version incidents).
---

# Security Supply Chain Hardening

## Overview

Most npm/PyPI supply chain attacks follow the same playbook: an attacker phishes or hijacks a maintainer account, publishes a malicious version, and gets detected within hours. A **minimum release age gate** — refuse to install any package version younger than N days — blocks the install window entirely. Per the [Simplest Supply Chain Defense](https://daniakash.com/posts/simplest-supply-chain-defense/) analysis, a 7-day delay would have blocked roughly half of documented attacks from 2018–2026 (axios 4h, Solana web3.js 5h, ua-parser-js 4h, Ledger Connect Kit 5h, etc).

This skill applies that defense across pnpm, bun, npm, yarn, uv, pip, and the major dependency bots — plus the controls that handle what the age gate doesn't: lifecycle-script allowlists, publish-path hardening, secret hygiene, and incident response.

> **The age gate is risk reduction, not protection.** It does nothing against long infiltrations (XZ), maintainer sabotage, infra takeovers, or `postinstall` scripts that already executed. Treat every layer in this skill as additive.

## When to Use

- Initializing a new Node.js, Bun, or Python project
- Reviewing or auditing an existing project's package manager config
- After a public npm/PyPI compromise is announced
- Setting up Renovate or Dependabot for a repo
- Onboarding a fresh dev machine (global package manager config)
- Migrating from long-lived publish tokens to Trusted Publishing / OIDC
- Evaluating whether a specific package version is safe to install today

## Quick Wins (Copy-Paste-Ready Configs)

The canonical, ready-to-merge configs live in `examples/`. **Merge their keys into your existing files — do not replace your files.** A blind paste over an existing `.npmrc` or `pnpm-workspace.yaml` can clobber `registry=`, `_authToken`, proxy settings, or workspace declarations — opening dependency-confusion paths.

| Tool | Example config (source of truth) | Commentary / footguns |
|---|---|---|
| pnpm ≥10.16 | [`examples/pnpm/pnpm-workspace.yaml`](examples/pnpm/pnpm-workspace.yaml), [`examples/pnpm/.npmrc`](examples/pnpm/.npmrc) | [`references/package-managers/pnpm.md`](references/package-managers/pnpm.md) |
| bun ≥1.2 | [`examples/bun/bunfig.toml`](examples/bun/bunfig.toml) | [`references/package-managers/bun.md`](references/package-managers/bun.md) |
| npm ≥11.10 | [`examples/npm/.npmrc`](examples/npm/.npmrc) | [`references/package-managers/npm.md`](references/package-managers/npm.md) |
| yarn ≥4.10 | [`examples/yarn/.yarnrc.yml`](examples/yarn/.yarnrc.yml) | [`references/package-managers/yarn.md`](references/package-managers/yarn.md) |
| uv ≥0.9.17 | [`examples/uv/pyproject.toml`](examples/uv/pyproject.toml) | [`references/package-managers/uv.md`](references/package-managers/uv.md) |
| pip ≥26.1 | [`examples/pip/pip.conf`](examples/pip/pip.conf) | [`references/package-managers/pip.md`](references/package-managers/pip.md) |
| Renovate | [`examples/renovate/renovate.json5`](examples/renovate/renovate.json5) | [`references/dependency-bots.md`](references/dependency-bots.md) |
| Dependabot | [`examples/dependabot/dependabot.yml`](examples/dependabot/dependabot.yml) | [`references/dependency-bots.md`](references/dependency-bots.md) |
| GitHub Actions OIDC publish | [`examples/github-actions/release-with-oidc.yml`](examples/github-actions/release-with-oidc.yml) | [`references/publish-path-hardening.md`](references/publish-path-hardening.md) |
| Pre-commit secret scan | [`examples/pre-commit/.pre-commit-config.yaml`](examples/pre-commit/.pre-commit-config.yaml) | [`references/secret-hygiene-and-sbom.md`](references/secret-hygiene-and-sbom.md) |

Every example file has inline comments explaining each setting and warning about common footguns. Before merging, **read the corresponding commentary file** for the rationale.

Bot configs use tiered variants: 3-day patch / 7-day minor / 14-day major. For the package manager itself, a single 7-day default is usually enough. Do not weaken below 3 days without a written reason.

## Detection: Which Package Managers Are in Scope

Run the variant for the local shell. Apply hardening for **every** lockfile found. A repo with both `package-lock.json` and `pnpm-lock.yaml` has a real problem — flag it before configuring anything.

**Bash / zsh (macOS, Linux, Git Bash):**
```bash
ls package-lock.json pnpm-lock.yaml yarn.lock bun.lock bun.lockb 2>/dev/null
grep -E '"packageManager"|"engines"' package.json 2>/dev/null
ls uv.lock Pipfile.lock poetry.lock requirements*.txt pyproject.toml 2>/dev/null
ls .github/dependabot.yml renovate.json .github/renovate.json 2>/dev/null
```

**PowerShell (Windows):**
```powershell
Get-ChildItem package-lock.json, pnpm-lock.yaml, yarn.lock, bun.lock, bun.lockb -ErrorAction Ignore
Select-String -Path package.json -Pattern '"packageManager"|"engines"' -ErrorAction Ignore
Get-ChildItem uv.lock, Pipfile.lock, poetry.lock, requirements*.txt, pyproject.toml -ErrorAction Ignore
Get-ChildItem .github/dependabot.yml, renovate.json, .github/renovate.json -ErrorAction Ignore
```

## Open When…

| Open when you need to… | Read |
|---|---|
| configure pnpm — minimumReleaseAge, blockExoticSubdeps, allowBuilds/onlyBuiltDependencies | [`references/package-managers/pnpm.md`](references/package-managers/pnpm.md) |
| configure Bun — minimumReleaseAge, trustedDependencies, ignoreScripts; avoid the `linker = "hoisted"` footgun | [`references/package-managers/bun.md`](references/package-managers/bun.md) |
| configure npm — min-release-age, save-exact, avoid leaking `_authToken` | [`references/package-managers/npm.md`](references/package-managers/npm.md) |
| configure Yarn 4 — npmMinimalAgeGate, dependenciesMeta | [`references/package-managers/yarn.md`](references/package-managers/yarn.md) |
| configure uv — exclude-newer | [`references/package-managers/uv.md`](references/package-managers/uv.md) |
| configure pip — `--uploaded-prior-to`, cross-platform timestamp generation | [`references/package-managers/pip.md`](references/package-managers/pip.md) |
| configure Renovate or Dependabot | [`references/dependency-bots.md`](references/dependency-bots.md) |
| **evaluate whether a specific package@version is safe to install today** | [`references/pre-merge-screening.md`](references/pre-merge-screening.md) (Socket / Snyk / signature checks) + [`references/incident-response.md`](references/incident-response.md) if a compromise was announced |
| **prevent committing an npm/PyPI token** or scan repo history for leaks | [`examples/pre-commit/.pre-commit-config.yaml`](examples/pre-commit/.pre-commit-config.yaml) + [`references/secret-hygiene-and-sbom.md`](references/secret-hygiene-and-sbom.md) + [`references/package-managers/npm.md`](references/package-managers/npm.md) (interpolation pattern) |
| harden the **publish path** — OIDC, hardware-key 2FA, provenance, Trusted Publishing | [`references/publish-path-hardening.md`](references/publish-path-hardening.md) |
| lock down `postinstall` scripts — allowlist first, kill-switch second | [`references/lifecycle-script-allowlists.md`](references/lifecycle-script-allowlists.md) |
| add pre-merge package screening — lockfile diff, signatures, Socket/Snyk | [`references/pre-merge-screening.md`](references/pre-merge-screening.md) |
| set up an internal registry / proxy or air-gapped install | [`references/registry-controls.md`](references/registry-controls.md) |
| add commit-time secret scanning, CI log redaction, and SBOM | [`references/secret-hygiene-and-sbom.md`](references/secret-hygiene-and-sbom.md) |
| respond to a published compromise or a suspected workstation breach | [`references/incident-response.md`](references/incident-response.md) |
| grab a copy-paste-ready config in its native format | [`examples/`](examples/) (canonical configs — source of truth) |
| understand maintenance: when to re-verify against upstream docs | [`SPEC.md`](SPEC.md) |

## Verification Checklist

After applying, verify each control actually took effect. **Each "must fail" check requires that you read the error message and confirm the failure reason is the age gate**, not a typo, cache miss, registry auth issue, or network error.

- [ ] `pnpm config get minimum-release-age` returns the expected value (see `references/package-managers/pnpm.md`)
- [ ] `npm config get min-release-age` returns 7
- [ ] pnpm ≥10.26.0 (so `blockExoticSubdeps` default-on applies); not overridden to `false`
- [ ] **Age-gate functional test** — install a package version published in the last 24h. The error **must** contain one of: `minimumReleaseAge` (pnpm/bun/uv), `min-release-age` (npm), `npmMinimalAgeGate` (yarn), `uploaded-prior-to` (pip), or `PACKAGE_TOO_FRESH`. Any other failure (404, 403, network) means the test is invalid — pick a different fresh package.
- [ ] Lockfile is committed and tracked (`git ls-files | grep -E 'lock(file)?$|\.lock\.|\.lockb$'`)
- [ ] CI uses a frozen/immutable install command (`npm ci`, `pnpm install --frozen-lockfile`, `bun install --frozen-lockfile`, `yarn install --immutable`, `uv sync --locked`)
- [ ] `package.json` has no `^` or `~` in `dependencies` / `devDependencies` (or there is a deliberate, documented exception)
- [ ] Renovate/Dependabot config matches or exceeds the package manager's cooldown
- [ ] Lifecycle scripts: allowlist exists **before** any kill-switch is enabled (see `references/lifecycle-script-allowlists.md`)
- [ ] Publish workflow uses OIDC + `--provenance`; trust policy pins exact repo, workflow, and protected environment (see `references/publish-path-hardening.md`)
- [ ] `npm audit signatures` runs in CI (or equivalent for the ecosystem)
- [ ] A malicious-package scanner (Socket.dev / Snyk / OSV-scanner) runs on every lockfile-changing PR
- [ ] Pre-commit secret scanner (gitleaks/trufflehog) installed (see `references/secret-hygiene-and-sbom.md`)
- [ ] `.npmrc` in the repo contains **no** `_authToken`, `_auth`, `_password`, or `email` lines
- [ ] SBOM emitted per build and stored with the artifact

## Limitations

The minimum release age defense and the controls in this skill **do not** protect against:

- **Long-running infiltrations** where the attacker waits (XZ Utils: ~2 years).
- **Maintainer sabotage** of their own package (colors.js, node-ipc).
- **Build system / CI compromises** (SolarWinds, 3CX).
- **Infrastructure / CDN takeover** (Polyfill.io).
- **Genuine vulnerabilities** discovered post-release (Log4Shell). The gate *delays* the fix.
- **Ecosystems without native age-gate support**: Go modules, Maven, Gradle, Composer. For those, rely on `GOSUMDB` + `GOPROXY=off` for Go, GPG-signed artifacts + `gradle --write-verification-metadata sha256,pgp` for Gradle, `dependency-check` plugins for Maven, and a vendoring proxy for all of them (see `references/registry-controls.md`).

Treat this skill as one layer. Pair with SCA scanning (Socket, Snyk, GitHub Advisory), SBOM generation, least-privilege CI tokens, and human review of every lockfile-changing PR.

## References

Upstream docs are linked from each `references/<topic>.md` file. The maintenance contract — version cutoffs, source-verification policy, and when to re-audit — is in [`SPEC.md`](SPEC.md).

External source for the cross-ecosystem matrix: Daniel Akash, [The Simplest Supply Chain Defense](https://daniakash.com/posts/simplest-supply-chain-defense/).
