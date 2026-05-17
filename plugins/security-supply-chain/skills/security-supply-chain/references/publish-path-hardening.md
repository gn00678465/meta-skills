# Publish-Path Hardening (OIDC, 2FA, Provenance)

**Open when:** you maintain a published package, are migrating away from long-lived publish tokens, or are reviewing an existing publish workflow.

The package install side and the package publish side are separate threat models. The age gate (rest of this skill) protects **consumers**. This file protects **maintainers** and the publish pipeline.

**Source of truth (workflow):**
- [`examples/github-actions/release-with-oidc.yml`](../examples/github-actions/release-with-oidc.yml) — Trusted Publishing skeleton for npm via GitHub Actions OIDC

## 1. Hardware-Key 2FA on Every Maintainer Account

```bash
# npm — require hardware-key 2FA for publish ops on a package
npm access set mfa=publish <package>
```

- **Avoid SMS-based 2FA.** SIM swaps account for a non-trivial share of takeovers.
- Use a **FIDO2 hardware key** (YubiKey, Titan) or a platform authenticator. Backup keys stored offline.
- **Same policy on PyPI**: enforce 2FA on every account that can publish to the project.

### Separate publish vs. browsing accounts

The account that logs into npmjs.com / pypi.org for searching, watching, or commenting should **not** be the account that publishes. If the web account is phished, the publish account stays intact. No email forwarding rules on either account — those are the highest-leverage social-engineering target.

## 2. Fine-Grained / Scope-Limited Tokens

Replace classic ("legacy") npm tokens with granular tokens:

- **Scope**: single package or org, never account-wide.
- **Permissions**: publish-only, never read-write API.
- **Expiry**: 90 days max; rotate quarterly.
- **Storage**: GitHub Actions secrets or your org's secrets manager — never `.env` files, never `~/.npmrc`.

On PyPI: use **project-scoped API tokens**, not the account token.

## 3. Trusted Publishing via OIDC (the recommended target state)

OIDC-based "Trusted Publishing" replaces stored tokens with short-lived credentials minted per workflow run. npm requires npm 11.5.1+ and Node 22.14.0+; PyPI has supported this since 2023.

The canonical workflow is in [`examples/github-actions/release-with-oidc.yml`](../examples/github-actions/release-with-oidc.yml). The critical lines are:

```yaml
permissions:
  contents: read
  id-token: write    # required for OIDC

jobs:
  publish:
    runs-on: ubuntu-24.04        # pin the runner OS
    environment: production      # GitHub environment (optional but recommended)
    steps:
      - uses: actions/checkout@<sha>          # ⚠️ SHA-pinned, not @v6
      - uses: actions/setup-node@<sha>
        with:
          node-version: '24'
          package-manager-cache: false
      - run: npm ci
      - run: npm publish --access public      # no --provenance needed — Trusted Publishing auto-generates it
```

### ⚠️ Three independent footguns

#### 1. Trust-policy scope

A trust policy that's too broad lets **any contributor** land a workflow file that mints a publish token. Configure narrowly on the npm/PyPI side (the *registry* side, not just the workflow file):

- Pin **exact repository** (`owner/repo`).
- Pin **exact workflow filename** (`release.yml`, not `*.yml`, not glob).
- Pin a **GitHub environment** if you set one (npm marks this **optional**, but it's the primary mitigation against "any contributor can publish"). The environment must exist in repo settings with **required reviewers** and **branch protection** enabled before the workflow can publish successfully.
- Pin **branch** to `main`, or a tag pattern; **never `*`**, never accept fork PRs.

#### 2. SHA-pinning every `uses:` line

The publish workflow holds `id-token: write` — a tag-pinned action (`@v6`) whose maintainer moves the tag (or whose account is compromised) can inject token-exfil code at the moment your workflow mints an OIDC credential. SHA-pinning closes this. Renovate / Dependabot can update SHA pins, so you don't lose update automation.

#### 3. `--provenance` is auto-generated under Trusted Publishing

Per current npm docs: "When publishing via Trusted Publishing, npm automatically generates provenance." **Do not** pass `--provenance` explicitly in a Trusted Publishing workflow — it's redundant and may emit a warning. Plain `npm publish --access public` gets you the attestation.

If you're publishing with a long-lived token (the old way), `--provenance` is required and works as before — but you're not on Trusted Publishing yet.

### Review checks for any PR touching the publish workflow

- Reject PRs that **add** `id-token: write` to a workflow that didn't have it.
- Reject PRs that **modify** the trusted-publisher config on npm/PyPI.
- Require a second approver from the security team for either.
- Quarterly: audit every workflow file with `permissions: id-token: write`. Confirm it actually needs OIDC.

## 4. Provenance & Attestations

> **Read section 3 first.** If you're on Trusted Publishing (the recommended path), `npm publish` **without** `--provenance` is correct — Trusted Publishing auto-generates the attestation. The `--provenance` flag below applies **only** to the legacy long-lived-token publish path.

### Legacy long-lived-token path (not Trusted Publishing)

```bash
# Publisher side — emit a provenance statement (only when using a stored token,
# NOT under Trusted Publishing)
npm publish --provenance
```

Whether emitted explicitly (legacy) or auto-generated (Trusted Publishing), the attestation signs:
- the source commit SHA,
- the GitHub Actions workflow run that built it,
- the runner image,

via Sigstore.

### Consumer side (applies to both paths)

```bash
# Verify signatures across installed deps
npm audit signatures
```

Wire `npm audit signatures` into CI and fail the build on any mismatch.

PyPI has its own attestation flow — see [PyPI attestations](https://docs.pypi.org/attestations/) — same concept, separate command set.

## 5. Revoke Legacy Tokens After Migrating

After Trusted Publishing is live and a release has shipped via OIDC, **revoke every legacy publish token**. A leaked legacy token that "no one uses any more" is still a working publish credential. Audit with:

```bash
npm token list                # see active tokens
npm token revoke <id>         # revoke one
```

PyPI: revoke at `https://pypi.org/manage/account/token/`.

## Verification Checklist

- [ ] 2FA enforced on every publishing account (hardware key, not SMS)
- [ ] Publish and web accounts are separate
- [ ] Tokens are scope-limited, ≤90 day expiry
- [ ] Publish workflow runs in a protected GitHub environment
- [ ] OIDC trust policy pins repo + workflow filename + environment + branch
- [ ] `id-token: write` permission appears on exactly one workflow
- [ ] Every `uses:` line in the publish workflow is SHA-pinned (40-char commit hash, not tag or branch)
- [ ] No long-lived publish tokens remain in repo secrets after migration
- [ ] Plain `npm publish` (Trusted Publishing auto-generates provenance); legacy token-auth flow uses `npm publish --provenance` explicitly
- [ ] `npm audit signatures` runs in CI

## Upstream Docs

- [npm Trusted Publishers](https://docs.npmjs.com/trusted-publishers)
- [`npm access`](https://docs.npmjs.com/cli/v11/commands/npm-access)
- [npm provenance](https://docs.npmjs.com/generating-provenance-statements)
- [npm audit signatures](https://docs.npmjs.com/cli/v11/commands/npm-audit)
- [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/)
- [PyPI Attestations](https://docs.pypi.org/attestations/)
- [GitHub OIDC for cloud deployments](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
