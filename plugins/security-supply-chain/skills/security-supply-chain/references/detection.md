# Detecting Package Managers in Scope

Open when starting hardening on an unknown repo and you need to know which package managers and dependency bots apply.

Run the variant for the local shell. Apply hardening for **every** lockfile found. A repo with both `package-lock.json` and `pnpm-lock.yaml` has a real problem — flag it before configuring anything.

## Bash / zsh (macOS, Linux, Git Bash)

```bash
ls package-lock.json pnpm-lock.yaml yarn.lock bun.lock bun.lockb 2>/dev/null
grep -E '"packageManager"|"engines"' package.json 2>/dev/null
ls uv.lock Pipfile.lock poetry.lock requirements*.txt pyproject.toml 2>/dev/null
ls .github/dependabot.yml renovate.json .github/renovate.json 2>/dev/null
```

## PowerShell (Windows)

```powershell
Get-ChildItem package-lock.json, pnpm-lock.yaml, yarn.lock, bun.lock, bun.lockb -ErrorAction Ignore
Select-String -Path package.json -Pattern '"packageManager"|"engines"' -ErrorAction Ignore
Get-ChildItem uv.lock, Pipfile.lock, poetry.lock, requirements*.txt, pyproject.toml -ErrorAction Ignore
Get-ChildItem .github/dependabot.yml, renovate.json, .github/renovate.json -ErrorAction Ignore
```

## Interpreting the results

| Finding | Action |
|---|---|
| One PM lockfile + matching `packageManager` field | Standard case — open the matching `references/package-managers/<pm>.md` |
| Multiple PM lockfiles in same repo | **Stop.** Decide on one PM before hardening; mixed lockfiles defeat frozen-install guarantees |
| Lockfile present but no `packageManager` field | Pin the PM version in `package.json` `packageManager` field before hardening |
| Python: both `uv.lock` and `poetry.lock` / `Pipfile.lock` | Same rule — pick one resolver |
| `dependabot.yml` and `renovate.json` both present | Pick one bot; running both creates conflicting PRs |
