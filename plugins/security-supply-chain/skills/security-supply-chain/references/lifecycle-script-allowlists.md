# Lifecycle-Script Allowlists (allowlist first, kill-switch second)

**Open when:** you want to block `postinstall` / `preinstall` / `install` script execution from arbitrary packages while keeping legitimate native-build packages working.

`postinstall` is the most common malware execution path. A single line in `package.json` runs arbitrary code on developer machines and CI runners during `npm install`. **Disabling all scripts** is the safe default — but **doing it before building the allowlist** breaks `esbuild`, `sharp`, `prisma`, `puppeteer`, `playwright`, `cypress`, `swc`, `node-sass`, `bcrypt`, `canvas`, `better-sqlite3` and forces frustrated teams to disable the protection entirely.

## Rollout Workflow (every ecosystem)

1. **Inventory.** Run `pnpm install --ignore-scripts` (or your PM's equivalent dry-run) and note what fails.
2. **Allowlist only what you actually need** from the starter set below.
3. **Then** enable the global kill-switch.

### Starter allowlist (trim to your actual deps)

```
esbuild
sharp
prisma
@prisma/client
puppeteer
playwright
cypress
@swc/core
node-sass
bcrypt
canvas
better-sqlite3
node-gyp
```

Most projects need 3–5 of these, not all of them. **Audit your own deps with `pnpm install --ignore-scripts` first.** The list above is a starting point, not a recommendation.

## Per-Ecosystem Configuration

### pnpm ≥10.26 — `allowBuilds` in `pnpm-workspace.yaml`

```yaml
# pnpm-workspace.yaml
allowBuilds:
  esbuild: true
  sharp: true
  "@prisma/*": true
```

Unreviewed builds auto-populate this file as placeholders during install. Approve interactively with `pnpm approve-builds`. See `package-managers/pnpm.md` for the legacy `pnpm.onlyBuiltDependencies` form (pnpm <10.26) and the pnpm 11 cutover (legacy form removed entirely).

**Kill-switch (must go in `pnpm-workspace.yaml`, NOT `.npmrc`):**

```yaml
# pnpm-workspace.yaml
ignoreScripts: true
```

> ⚠️ **`ignore-scripts=true` in `.npmrc` is a silent no-op for pnpm.** pnpm reads only auth and registry settings from `.npmrc`; behavior settings must live in `pnpm-workspace.yaml` as `ignoreScripts` (camelCase). See [`package-managers/pnpm.md`](package-managers/pnpm.md) for the full `.npmrc` trap table.

### Bun — `trustedDependencies` in `package.json`

```json
// package.json (top-level)
{
  "trustedDependencies": ["esbuild", "sharp", "@prisma/client"]
}
```

Bun already defaults to **not** running scripts for third-party packages — `trustedDependencies` is the explicit allowlist.

**Caveat:** `trustedDependencies` does **not** cover `file:` / `link:` / `git:` / `github:` specifiers. Those need vendoring through the registry to receive any allowlist treatment. See `package-managers/bun.md`.

**Kill-switch:**

```toml
# bunfig.toml
[install]
ignoreScripts = true
```

> ⚠️ **Not `[install] auto = false`** — `install.auto` controls auto-import resolution, not scripts. Wrong key.

### Yarn 4 — `dependenciesMeta` in `package.json`

```json
// package.json
{
  "dependenciesMeta": {
    "esbuild": { "built": true },
    "sharp": { "built": true }
  }
}
```

Yarn 4 disables third-party `postinstall` by default. The `built: true` opt-in is the allowlist.

**Explicit default (third-party only — workspaces still run their own scripts):**

```yaml
# .yarnrc.yml
enableScripts: false   # already the Yarn 4 default; listed for visibility
```

Per [Yarn docs](https://yarnpkg.com/configuration/yarnrc#enableScripts): `enableScripts: false` is the documented default and disables `postinstall` scripts only for **third-party** packages. Workspace packages always run their own postinstall scripts regardless — Yarn assumes workspace code is trusted.

There is **no built-in kill-switch for workspace postinstall** in Yarn 4. If you need that, audit your workspaces directly or wrap CI with a script-skipping linker.

### npm — wrap with `@lavamoat/allow-scripts`

npm has **no native allowlist** mechanism. Use [`@lavamoat/allow-scripts`](https://lavamoat.github.io/guides/allow-scripts/):

```bash
# one-time setup — writes config skeleton into package.json
npx allow-scripts setup

# interactively populate the allowlist from current deps
npx allow-scripts auto
```

Then in CI:

```bash
npm ci --ignore-scripts        # install without scripts
npx allow-scripts run          # run only the allowlisted scripts
```

## Verification

- [ ] `pnpm install --ignore-scripts` completes successfully and produces a working build (i.e. all native deps got their builds via the allowlist mechanism, not via free-floating `postinstall`)
- [ ] CI install uses `--ignore-scripts` (or PM equivalent) followed by an explicit allowlist-runner step
- [ ] The allowlist file (`pnpm-workspace.yaml` / `package.json`) is tracked and reviewed in code review

## Upstream Docs

- [pnpm `allowBuilds`](https://pnpm.io/settings#allowbuilds)
- [pnpm `approve-builds` CLI](https://pnpm.io/cli/approve-builds)
- [Bun `trustedDependencies`](https://bun.com/docs/install/lifecycle)
- [Yarn `dependenciesMeta`](https://yarnpkg.com/configuration/manifest#dependenciesMeta)
- [Yarn `enableScripts`](https://yarnpkg.com/configuration/yarnrc#enableScripts)
- [`@lavamoat/allow-scripts`](https://lavamoat.github.io/guides/allow-scripts/)
