# Secret Hygiene & SBOM

**Open when:** adding commit-time secret scanning, CI log-redaction policies, or per-build SBOM emission.

The age gate doesn't help if a maintainer's token is already in the repo. A leaked `_authToken` is a working publish credential for anyone who clones the repo. This file covers the **before-it-leaks** and **after-it's-leaked** layers.

## Pre-Commit Secret Scanning

Catch tokens before they hit `git commit`.

### Gitleaks (recommended for solo / small teams)

**Source of truth (config):** [`examples/pre-commit/.pre-commit-config.yaml`](../examples/pre-commit/.pre-commit-config.yaml) — drop in your repo root.

```bash
# Install once per machine
brew install gitleaks    # macOS / Homebrew
# or download from https://github.com/gitleaks/gitleaks/releases

# Wire into git hooks once per clone (after .pre-commit-config.yaml is in repo)
pip install pre-commit
pre-commit install

# Run ad-hoc against all files
pre-commit run --all-files
```

Gitleaks ships with built-in rules for npm `_authToken`, PyPI tokens, AWS keys, GitHub PATs, Slack webhooks, and ~100 other token formats.

### TruffleHog (recommended for high-volume repos / CI)

```bash
trufflehog git file://. --since-commit HEAD~10
```

TruffleHog **verifies** each finding by attempting to use the credential — fewer false positives than pattern-only tools.

### GitHub Push Protection (server-side, recommended for all GitHub repos)

Free for public repos. Part of GitHub Advanced Security for private repos. **Rejects pushes** containing recognized token formats — even if a developer skipped their pre-commit hook.

Enable at: `Settings → Code security → Push protection`.

## CI Runner Secret Hygiene

When the runner has access to a secret, the runner's log can leak it. Defensive habits:

- **Never `set -x`** in a script that touches env-bound secrets. Same for `bash -x`, `pwsh -Verbose`. The shell prints every variable expansion.
- **Mask secrets explicitly** when constructing them at runtime:
  ```yaml
  # GitHub Actions
  - run: |
      DERIVED_SECRET=$(some-command)
      echo "::add-mask::$DERIVED_SECRET"
  ```
  ```yaml
  # Azure DevOps
  - script: |
      DERIVED=$(some-command)
      echo "##vso[task.setvariable variable=DERIVED;issecret=true]$DERIVED"
  ```
- **Audit CI logs quarterly** for accidental leaks. Search for `npm_`, `pypi-`, `ghp_`, `AKIA`, `xoxb-` prefixes across the last 90 days of runs.
- **Minimize artifact retention.** Build artifacts often include `.env` snapshots, debug logs, full process environments. 7-day retention is plenty for most jobs.
- **Scope CI tokens.** Each runner job should have the minimum permissions it needs. Use OIDC for cloud deployments (see `publish-path-hardening.md`) so no static credential lives on the runner at all.

## SBOM Generation

Emit a Software Bill of Materials (SBOM) per build. When an advisory drops, you grep SBOMs across all your releases instead of re-resolving every project's dependency tree.

### Tools

| Tool | Formats | Best fit |
|---|---|---|
| `npm sbom` | CycloneDX, SPDX | npm-native, simplest |
| [`syft`](https://github.com/anchore/syft) | CycloneDX, SPDX, GitHub | Multi-ecosystem, recommended general-purpose |
| [`cdxgen`](https://github.com/CycloneDX/cdxgen) | CycloneDX | Most ecosystem coverage |
| `pip-audit --format=cyclonedx-json` | CycloneDX | Python projects |

### Example: GitHub Actions step

```yaml
- name: Generate SBOM
  run: |
    npm sbom --sbom-format=cyclonedx > sbom.cdx.json
- uses: actions/upload-artifact@v4
  with:
    name: sbom
    path: sbom.cdx.json
    retention-days: 365     # SBOMs deserve long retention
```

Store SBOMs alongside the release artifact — both publicly (release assets) and internally (security data lake). When the next supply chain incident hits, you can answer "which releases shipped the malicious version" in minutes instead of days.

## Sandboxed Ad-Hoc Installs

For one-off `npm install` of unfamiliar packages, **never use the workstation that holds your AWS keys, SSH keys, and password manager.** Run inside a fresh container:

```bash
# Quick, disposable sandbox
docker run --rm -it -v "$(pwd):/app" -w /app node:lts bash

# Inside: install, inspect, and let the container die
npm install <suspicious-pkg>
ls node_modules/<suspicious-pkg>
exit
```

For deeper inspection, use a VM with no network egress except to npmjs.com.

## Verification Checklist

- [ ] Gitleaks or TruffleHog runs as a pre-commit hook
- [ ] GitHub Push Protection enabled on every repo (or equivalent for non-GitHub hosts)
- [ ] CI workflows don't use `set -x` against secret-bearing env vars
- [ ] CI artifact retention ≤ 14 days (longer requires a written reason)
- [ ] SBOM emitted on every release build, retained ≥ 1 year
- [ ] Ad-hoc install of unfamiliar packages happens in a sandbox, not on the dev workstation

## Upstream Docs

- [Gitleaks](https://github.com/gitleaks/gitleaks)
- [TruffleHog](https://github.com/trufflesecurity/trufflehog)
- [GitHub Push Protection](https://docs.github.com/en/code-security/secret-scanning/protecting-pushes-with-secret-scanning)
- [CycloneDX spec](https://cyclonedx.org/specification/overview/)
- [SPDX spec](https://spdx.dev/specifications/)
- [Anchore Syft](https://github.com/anchore/syft)
