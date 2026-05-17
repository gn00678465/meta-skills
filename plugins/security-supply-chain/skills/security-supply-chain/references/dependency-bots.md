# Dependency Bots: Renovate & Dependabot

**Open when:** configuring an automated dependency updater. Bots are the most common path for a malicious version to land in `main` because they auto-open PRs the day a release ships.

**Source of truth (configs):**
- [`examples/renovate/renovate.json`](../../examples/renovate/renovate.json) — Renovate config
- [`examples/dependabot/dependabot.yml`](../../examples/dependabot/dependabot.yml) — Dependabot config (place at `.github/dependabot.yml`)

The bot's cooldown must **match or exceed** the package manager's cooldown. If pnpm refuses installs <7d but Renovate opens PRs on day 1, the PR sits in `main`-bound state until the cooldown expires anyway — and humans tend to merge the PR rather than investigate why the install fails.

## Renovate — Key Decisions

Tiered cooldowns in `packageRules`:
- **Major: 14 days** — highest blast radius if malicious, lowest cost from a 14-day delay.
- **Minor: 7 days** — default.
- **Patch: 3 days** — fastest update because patches are usually CVE fixes.

### Why no `vulnerabilityAlerts.minimumReleaseAge: "0 days"` override

Renovate **already bypasses `minimumReleaseAge` for security updates** by default. The explicit `"0 days"` override is unnecessary and obscures the actual policy. The upstream security preset uses `vulnerabilityAlerts: { enabled: true }` without an age-gate override — match that pattern. See [Renovate Minimum Release Age key concepts](https://docs.renovatebot.com/key-concepts/minimum-release-age/).

### Why `dependencyDashboard: true`

Surfaces cooldown-bypassed updates so they don't auto-merge silently. A security update is the highest-leverage point in your dependency lifecycle — humans should see it land, not learn about it from a deploy.

## Dependabot — Key Decisions

### Why `groups`

Without grouping, Dependabot opens one PR per dep. With 30+ deps, reviewers rubber-stamp — defeating the lockfile-diff review (`../pre-merge-screening.md`). One grouped PR per week, reviewed carefully, beats 30 individual PRs.

The example file groups `production-deps` separately from `dev-deps` so a production-dep change still triggers more careful review than a dev-only bump.

### Cooldown scope

Dependabot cooldown applies to **version** updates only. Security updates bypass the cooldown — same as Renovate, intentional and correct. When a CVE is published, the existing version is already known-bad.

## Cross-cutting Recommendations

- **Require human review on lockfile-changing PRs.** Branch protection: require a CODEOWNER on `*.lock` / `*-lock.*` / `bun.lockb`.
- **Run `npm audit signatures` (or equivalent) in the bot's PR check.** Catches anything published without provenance.
- **Pair with `../pre-merge-screening.md`** (Socket.dev / Snyk / OSV-scanner) on every bot PR.

## Upstream Docs

- [Renovate: Minimum Release Age](https://docs.renovatebot.com/key-concepts/minimum-release-age/)
- [Renovate config options](https://docs.renovatebot.com/configuration-options/)
- [Dependabot cooldown](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file#cooldown)
- [Dependabot groups](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file#groups)
