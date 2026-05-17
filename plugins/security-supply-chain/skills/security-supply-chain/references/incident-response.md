# Responding to a Published Compromise

**Open when:** a public advisory drops for a package you use, or a developer suspects they just ran a malicious `postinstall`.

The order of operations here matters more than any individual step. **Reinstalling a clean lockfile does not undo exfiltration that already happened.** Token rotation must precede everything else, including reading the advisory body in detail.

## The Runbook

### Step 1 — Rotate first, investigate second

Within 5 minutes of being notified, revoke or rotate every credential the compromised package's process could have reached:

- **Publish tokens**: `npm token revoke <id>`, PyPI tokens at `https://pypi.org/manage/account/token/`
- **CI secrets**: GitHub Actions secrets, CircleCI contexts, GitLab CI variables, Azure DevOps service connections
- **Cloud credentials** the build process used: AWS (`aws iam delete-access-key`), GCP service account keys, Azure service principals
- **GitHub PATs and GitHub App installation tokens**
- **Browser session cookies** for developer accounts → force reauth at GitHub, npm, PyPI, cloud consoles
- **Any token a `postinstall` could `cat ~/.aws/credentials || cat ~/.npmrc || env` to find**

Do this from a **different machine** than the one that ran the install. If the workstation is breached, anything you type there can be observed.

### Step 2 — Identify the exposure window

Get from the advisory (GitHub Security Advisory, Socket, Snyk):
- The malicious version range (e.g. `1.4.0–1.4.3`).
- The publish and detection timestamps.
- The known payload behavior (data exfil? backdoor? cryptominer?).

### Step 3 — Check lockfiles

Bash / zsh:
```bash
grep -E "<package>" pnpm-lock.yaml bun.lock package-lock.json yarn.lock uv.lock Pipfile.lock 2>/dev/null
```

PowerShell:
```powershell
Select-String -Path pnpm-lock.yaml,bun.lock,package-lock.json,yarn.lock,uv.lock,Pipfile.lock -Pattern "<package>" -ErrorAction Ignore
```

Check **every repo in the org**, not just the one that triggered the alert. A typical organization has the same dep in dozens of projects.

### Step 4 — If clean

Confirm the age gate would have blocked the install (verify per the relevant [`package-managers/<pm>.md`](./package-managers/) reference), then move on.

### Step 5 — If hit

1. Revert the affected lockfile to the last known-good commit.
2. Delete `node_modules` **and** the per-PM cache:
   - npm: `~/.npm`
   - pnpm: `~/.pnpm-store`
   - bun: `~/.bun/install/cache`
   - yarn: `~/.yarn/berry/cache`
   - pip / uv: `~/.cache/pip`, `~/.cache/uv`
3. Reinstall from the reverted lockfile.
4. Re-run all CI pipelines that may have run with the malicious version cached.
5. Open an issue to track the audit; close only after every affected repo is verified clean.

### Step 6 — Tighten

Apply the configs in this skill's [`package-managers/`](./package-managers/) references if not already in place. The compromise is the reminder that the protections were always needed.

## Workstation Forensics: If You Ran the Malicious Install

If a developer's machine actually executed the compromised `postinstall`, **treat the workstation as breached.** Sophisticated malware persists in places no shell-command audit can fully enumerate.

### Cred sweep — assume everything below is exfiltrated

| Location | Action |
|---|---|
| `~/.npmrc` | Revoke `_authToken`; rotate publish creds |
| `~/.yarnrc.yml` | Revoke any `npmAuthToken` entries |
| `~/.config/pip/pip.conf`, `~/.pypirc` | Revoke PyPI tokens |
| `~/.gem/credentials` | Revoke RubyGems API keys |
| `~/.cargo/credentials` | Revoke crates.io tokens |
| `~/.docker/config.json` | Revoke registry creds; rotate |
| `~/.kube/config` | Rotate kubeconfig tokens / certs |
| `~/.aws/credentials`, `~/.aws/config` | Rotate access keys; check `aws iam list-access-keys` for unknown keys |
| `~/.config/gh/hosts.yml` | Revoke GitHub CLI token; check `gh auth status` |
| `~/.config/gcloud/` | Revoke gcloud creds; rotate service account keys |
| Project `.env`, `.env.local`, `.env.*` | Audit and rotate every secret listed |

### SSH

```bash
ls -la ~/.ssh/                          # confirm what's there
cat ~/.ssh/authorized_keys              # check for unexpected entries
cat ~/.ssh/config                       # check for unexpected host aliases
```

Rotate every SSH key. Revoke from every server that trusts the old key. Audit `authorized_keys` on every server the user can reach.

### Persistence locations

```bash
crontab -l                                                   # cron jobs
ls -la ~/Library/LaunchAgents/ /Library/LaunchDaemons/       # macOS launchd
ls -la ~/.config/systemd/user/                               # Linux user systemd
cat ~/.bashrc ~/.zshrc ~/.profile ~/.config/fish/config.fish # shell rc
```

Windows:
```powershell
Get-ScheduledTask | Where-Object { $_.Author -notlike "Microsoft*" }
Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Run
Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Run
```

### Browser

Assume saved passwords and session cookies are exfiltrated:

- Force-revoke sessions on **every** developer account: GitHub, npm, PyPI, GitLab, cloud consoles, Vercel/Netlify, Slack, password manager.
- Rotate the password manager's master password from a different device.
- 1Password / Bitwarden CLI: invalidate active sessions, rotate the unlock secret.

### Hardware key state

The key itself is still trusted (the attacker doesn't physically have it), but the **password-half** of each multi-factor login is leaked. Rotate every password that the hardware key gated.

### After rotation: reimage, don't clean

Sophisticated malware persists in places this list doesn't enumerate (firmware, EFI partitions, kernel-level rootkits). **Reimage the workstation** rather than try to clean it. If regulated, preserve a forensic image first.

## Communication

- **Internal**: notify the security team and engineering leadership within 1 hour of confirming exposure.
- **External (regulated industries)**: follow your incident-disclosure policy. GDPR / PCI / HIPAA timelines start when *exposure is confirmed*, not when the advisory was published.
- **Customers**: only after the internal investigation has scoped the blast radius.

## Verification Checklist

- [ ] Every credential reachable from the affected process is rotated, not just the obviously-related ones
- [ ] Rotation happens from a clean machine
- [ ] Lockfile reverted, cache deleted, fresh install verified
- [ ] All repos in the org checked for the affected version range
- [ ] Affected workstation is reimaged (not just cleaned)
- [ ] Incident timeline is documented (advisory time, rotation time, scope-confirmation time)

## Upstream Docs

- [GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories)
- [Socket.dev advisory feed](https://socket.dev/blog)
- [Snyk security advisories](https://security.snyk.io/)
- [npm token management](https://docs.npmjs.com/cli/v11/commands/npm-token)
- [PyPI token management](https://pypi.org/help/#apitoken)
