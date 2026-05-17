# Registry Controls (Internal Mirror, Approved-Registry Policy)

**Open when:** the project handles sensitive data or runs in a regulated environment, and you want to enforce supply-chain controls at the **registry layer** rather than per-developer.

The age gate and screening controls in the rest of this skill run on the consumer side. A registry proxy moves the same controls upstream of every developer machine and every CI runner. Faster, more uniform, and the only viable answer in air-gapped environments.

## Why a Registry Proxy

A single internal mirror gives you:

- **One choke point** for cooldown, signature, and audit policies — set once, applies everywhere.
- **Kill switch** when an upstream compromise is announced: remove or quarantine the malicious version on the mirror; downstream installs immediately fail or fall back to the prior version.
- **Caching** of the entire dependency tree, so a malicious package can be pulled from the registry without affecting in-flight builds.
- **Audit trail** of every install, scoped to the proxy's access logs.

## Options

| Tool | Best fit | License |
|---|---|---|
| [Verdaccio](https://verdaccio.org) | Small teams; npm-only | Open source (MIT) |
| [JFrog Artifactory](https://jfrog.com/artifactory/) | Enterprise; multi-ecosystem (npm, PyPI, Docker, Maven, etc.) | Commercial |
| [Sonatype Nexus Repository](https://www.sonatype.com/products/sonatype-nexus-repository) | Enterprise; long-running standard | Commercial (OSS edition available) |
| [Cloudsmith](https://cloudsmith.com) | SaaS; multi-ecosystem | Commercial |
| [devpi](https://devpi.net) | Python-only | Open source |
| [pulpcore](https://docs.pulpproject.org) | Self-host enterprise; multi-ecosystem | Open source |

For a Node.js + Python team starting from scratch, **Verdaccio + devpi** (or a single Artifactory instance) covers both ecosystems.

## Approved-Registry Policy

Once the proxy is running, point every PM at it:

```ini
# .npmrc (commit this — points to internal mirror)
registry=https://npm.internal.example.com/
```

```toml
# bunfig.toml
[install]
registry = "https://npm.internal.example.com/"
```

```yaml
# .yarnrc.yml
npmRegistryServer: "https://npm.internal.example.com/"
```

```toml
# pyproject.toml (uv)
[[tool.uv.index]]
name = "internal"
url = "https://pypi.internal.example.com/simple"
default = true
```

CI runners should have these same values pinned in their base images so a misconfigured project can't fall back to the public registry silently.

## Air-Gapped / Vendored Builds (high-risk environments)

For projects where any upstream traffic is unacceptable:

- **pnpm + offline store**: `pnpm fetch` builds a local store; subsequent installs work offline.
- **Vendored `node_modules`**: commit the entire tree if it's small enough to review (rare for modern JS, more common for security-critical embedded projects).
- **Python wheel mirror**: `pip download -d ./wheels -r requirements.txt`, vet, then install with `pip install --no-index --find-links=./wheels`.

This is the strongest defense and the highest maintenance cost — only worth it when the threat model demands it.

## Verification Checklist

- [ ] `npm config get registry` (and PM equivalents) returns the internal mirror URL
- [ ] CI base images pin the registry — no fallback to public registry
- [ ] The mirror has cooldown / quarantine policies configured upstream of every PM client
- [ ] Mirror audit logs are exported to a SIEM / log aggregator with retention ≥ 90 days
- [ ] A documented procedure exists for "quarantine package X across the entire org" with a target time-to-quarantine

## Upstream Docs

- [Verdaccio](https://verdaccio.org/docs/what-is-verdaccio)
- [JFrog Artifactory + npm](https://jfrog.com/help/r/jfrog-artifactory-documentation/npm-registry)
- [devpi](https://devpi.net/docs/devpi/devpi/latest/+d/index.html)
- [Sonatype Nexus + npm](https://help.sonatype.com/repomanager3/nexus-repository-administration/formats/npm-registry)
