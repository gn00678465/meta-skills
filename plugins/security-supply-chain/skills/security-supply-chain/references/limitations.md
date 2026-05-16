# Limitations of This Skill

Open when a stakeholder asks "are we covered against X?" and you need to answer honestly — or when scoping a follow-up skill for the gaps.

The minimum release age defense and the controls in this skill **do not** protect against:

- **Long-running infiltrations** where the attacker waits (XZ Utils: ~2 years).
- **Maintainer sabotage** of their own package (colors.js, node-ipc).
- **Build system / CI compromises** (SolarWinds, 3CX).
- **Infrastructure / CDN takeover** (Polyfill.io).
- **Genuine vulnerabilities** discovered post-release (Log4Shell). The gate *delays* the fix.
- **Ecosystems without native age-gate support**: Go modules, Maven, Gradle, Composer. For those, rely on `GOSUMDB` + `GOPROXY=off` for Go, GPG-signed artifacts + `gradle --write-verification-metadata sha256,pgp` for Gradle, `dependency-check` plugins for Maven, and a vendoring proxy for all of them (see [`registry-controls.md`](registry-controls.md)).

## What to pair this skill with

Treat this skill as one layer. Pair with:

- **SCA scanning** — Socket, Snyk, GitHub Advisory Database
- **SBOM generation** — see [`secret-hygiene-and-sbom.md`](secret-hygiene-and-sbom.md)
- **Least-privilege CI tokens** — see [`publish-path-hardening.md`](publish-path-hardening.md)
- **Human review of every lockfile-changing PR** — see [`pre-merge-screening.md`](pre-merge-screening.md)
