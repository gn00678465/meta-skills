# Pre-Merge Screening

**Open when:** setting up automated checks on PRs that change lockfiles or `package.json` dependencies.

The bot's cooldown (`dependency-bots.md`) buys you time. Pre-merge screening uses that time to actually catch tampered packages, typosquats, and unsigned releases before they land in `main`.

## Lockfile Diff Review (human side)

When a PR changes `pnpm-lock.yaml` / `package-lock.json` / `yarn.lock` / `bun.lockb` / `uv.lock`, the reviewer must inspect:

- **New `resolved` URLs** — does the registry match? `https://registry.npmjs.org/...` ≠ `https://attacker-mirror.com/...`.
- **Integrity hashes** — `sha512-...`. **A flipped integrity hash on an unchanged version is a tamper signal.** Legitimate version bumps change the hash; unchanged versions should keep the same hash forever.
- **Version jumps that skip major versions** — usually intentional but worth confirming.
- **New transitive packages** — has anyone reviewed what they are?

Require a CODEOWNER on lockfile changes:

```
# .github/CODEOWNERS
*-lock.json    @security-team
*.lock         @security-team
*-lock.yaml    @security-team
bun.lockb      @security-team
```

## Lockfile Integrity Diff (CI side)

Catch hash-flip tampering automatically:

```bash
# Install with the committed lockfile (no resolution)
pnpm install --frozen-lockfile

# Compare node_modules integrity against lockfile integrity
# Tooling varies; the principle is: any mismatch = block the merge
```

For npm: `npm ci` already enforces this. For pnpm: `--frozen-lockfile` is equivalent. The CI step that **must** be added on top is a separate check that the resolved tree's hashes match the lockfile after install — some PMs warn but don't fail on integrity drift.

## Signature Verification

```bash
npm audit signatures
```

Runs against the resolved tree. Rejects packages whose published signature doesn't match the registry attestation. Wire into CI on every lockfile-changing PR.

Bun, pnpm, and yarn vary in support — check the relevant `package-managers/<pm>.md`.

## Malicious-Package Scanning

Pick at least one:

| Service | Strength |
|---|---|
| [Socket.dev](https://socket.dev) | Behavior-based detection (network calls, fs access, install scripts); typosquat alerts; free for open source |
| [Snyk](https://snyk.io) | CVE + supply-chain risk scoring; license + advisory data |
| [OSV-scanner](https://google.github.io/osv-scanner/) | Open-source, integrates well with CI; uses the OSV vulnerability database |
| GitHub Dependabot alerts | Free, baseline; surface advisories only |

Run on every PR that touches a lockfile. Configure the bot to **block merge** on critical findings.

## Typosquat Detection

Typosquatting: an attacker publishes `lodahs`, `reqests`, `colors2` hoping for a developer typo. Socket and Snyk flag these automatically.

For a self-hosted check: write a CI script that computes [Levenshtein distance](https://en.wikipedia.org/wiki/Levenshtein_distance) between each new dependency name and your existing dependency tree. Flag distance ≤ 2 for human review. There is no canonical npm-registry tool for this — write the script yourself or use the SCA service's built-in detection.

## Provenance-Based Filter (optional, strict)

Reject any new dependency that does **not** publish provenance attestations:

```bash
# Roughly — replace with proper tooling in CI
npm view <pkg> dist.attestations
# If empty, block the dependency from being added
```

This is high-friction (many packages still don't sign) but is the strongest filter when you can apply it.

## Verification Checklist

- [ ] CODEOWNERS requires security-team review on lockfile changes
- [ ] CI runs `--frozen-lockfile` (or PM equivalent) on every PR
- [ ] CI runs `npm audit signatures` (or PM equivalent) on every lockfile-changing PR
- [ ] At least one SCA tool (Socket / Snyk / OSV-scanner) runs on every lockfile-changing PR with merge-blocking severity gates
- [ ] PRs adding new dependencies require human approval, not bot-merge

## Upstream Docs

- [npm audit signatures](https://docs.npmjs.com/cli/v11/commands/npm-audit)
- [Socket.dev docs](https://docs.socket.dev/)
- [OSV-scanner](https://google.github.io/osv-scanner/)
- [GitHub Dependabot alerts](https://docs.github.com/en/code-security/dependabot/dependabot-alerts/about-dependabot-alerts)
