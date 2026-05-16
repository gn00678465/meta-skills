# Verification Checklist

Open when controls have been applied and you need to confirm each one took effect (not just that the file parsed).

**Each "must fail" check requires that you read the error message and confirm the failure reason is the age gate**, not a typo, cache miss, registry auth issue, or network error.

## Age gate is live

- [ ] `pnpm config get minimum-release-age` returns the expected value (see [`package-managers/pnpm.md`](package-managers/pnpm.md))
- [ ] `npm config get min-release-age` returns 7
- [ ] pnpm ≥10.26.0 (so `blockExoticSubdeps` default-on applies); not overridden to `false`
- [ ] **Age-gate functional test** — install a package version published in the last 24h. The error **must** contain one of: `minimumReleaseAge` (pnpm/bun/uv), `min-release-age` (npm), `npmMinimalAgeGate` (yarn), `uploaded-prior-to` (pip), or `PACKAGE_TOO_FRESH`. Any other failure (404, 403, network) means the test is invalid — pick a different fresh package.

## Lockfile discipline

- [ ] Lockfile is committed and tracked (`git ls-files | grep -E 'lock(file)?$|\.lock\.|\.lockb$'`)
- [ ] CI uses a frozen/immutable install command (`npm ci`, `pnpm install --frozen-lockfile`, `bun install --frozen-lockfile`, `yarn install --immutable`, `uv sync --locked`)
- [ ] `package.json` has no `^` or `~` in `dependencies` / `devDependencies` (or there is a deliberate, documented exception)
- [ ] Renovate/Dependabot config matches or exceeds the package manager's cooldown

## Scripts and publish path

- [ ] Lifecycle scripts: allowlist exists **before** any kill-switch is enabled (see [`lifecycle-script-allowlists.md`](lifecycle-script-allowlists.md))
- [ ] Publish workflow uses OIDC + `--provenance`; trust policy pins exact repo, workflow, and protected environment (see [`publish-path-hardening.md`](publish-path-hardening.md))
- [ ] `npm audit signatures` runs in CI (or equivalent for the ecosystem)
- [ ] A malicious-package scanner (Socket.dev / Snyk / OSV-scanner) runs on every lockfile-changing PR

## Secrets and supply hygiene

- [ ] Pre-commit secret scanner (gitleaks/trufflehog) installed (see [`secret-hygiene-and-sbom.md`](secret-hygiene-and-sbom.md))
- [ ] `.npmrc` in the repo contains **no** `_authToken`, `_auth`, `_password`, or `email` lines
- [ ] SBOM emitted per build and stored with the artifact
