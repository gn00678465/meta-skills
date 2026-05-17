# pip Supply Chain Hardening

**Open when:** configuring pip against malicious-version attacks — `--uploaded-prior-to` flag, choosing a config-file location pip actually reads.

If you're starting a new project or can migrate, **prefer [uv](./uv.md)** — its `exclude-newer` config is more ergonomic and works in any uv ≥0.9.17. The pip flag below is for projects that cannot migrate.

**Source of truth (config):**
- [`examples/pip/pip.conf`](../../examples/pip/pip.conf) — config snippet for `--uploaded-prior-to`

## ⚠️ pip Does NOT Auto-Load `pip.conf` From the Repo Root

This is the most common mistake. **pip ignores a `pip.conf` placed at the repo root** unless you explicitly point at it. Pip reads config from (in order of precedence):

1. `$PIP_CONFIG_FILE` (highest priority — point this at any file you want)
2. Per-venv: `$VIRTUAL_ENV/pip.conf` (Linux/macOS) or `$VIRTUAL_ENV\pip.ini` (Windows)
3. Per-user:
   - Linux/macOS: `$XDG_CONFIG_HOME/pip/pip.conf`, `~/.config/pip/pip.conf`, or `~/.pip/pip.conf`
   - Windows: `%APPDATA%\pip\pip.ini` (**note the filename change**: `pip.ini`, not `pip.conf`)
4. System: `/etc/pip.conf`, `/etc/xdg/pip/pip.conf`

See [pip's configuration docs](https://pip.pypa.io/en/stable/topics/configuration/#location).

### To use [`examples/pip/pip.conf`](../../examples/pip/pip.conf), pick one:

- **CI** (recommended for repos): Set `PIP_CONFIG_FILE` in your runner env:
  ```yaml
  # GitHub Actions
  env:
    PIP_CONFIG_FILE: ${{ github.workspace }}/pip.conf
  ```
- **Per-developer**: Copy into the per-user location (and rename to `pip.ini` on Windows):
  ```bash
  # Linux/macOS
  mkdir -p ~/.config/pip && cp pip.conf ~/.config/pip/pip.conf

  # Windows PowerShell
  $dir = Join-Path $env:APPDATA 'pip'; New-Item -ItemType Directory -Force $dir | Out-Null
  Copy-Item pip.conf "$dir\pip.ini"
  ```
- **Per-venv**: After `python -m venv .venv`, copy `pip.conf` into the venv directory.

## `--uploaded-prior-to` flag

| pip version | Release date | Accepted formats |
|---|---|---|
| 26.0 | 2026-01-30 | ISO 8601 datetime only (`2026-01-15T00:00:00Z`) |
| 26.1+ | 2026-04-26 | ISO 8601 datetime **or** ISO 8601 duration (`P7D`) |

Key line in [`pip.conf`](../../examples/pip/pip.conf):
```ini
[install]
uploaded-prior-to = P7D
```

The duration form requires pip ≥26.1. For pip 26.0, use a generated datetime (commands below).

## Generated Datetime (pip 26.0, or fixed cutoff)

```bash
# Linux (GNU date)
pip install --uploaded-prior-to=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ) <pkg>

# macOS / BSD date
pip install --uploaded-prior-to=$(date -u -v-7d +%Y-%m-%dT%H:%M:%SZ) <pkg>
```

```powershell
# PowerShell (Windows)
pip install --uploaded-prior-to=$((Get-Date).AddDays(-7).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")) <pkg>
```

## CI Wiring

Either set `PIP_CONFIG_FILE` to a committed file (shown above), or pass `--uploaded-prior-to=P7D` on the install command. Do not rely on developers remembering the flag locally:

```yaml
# Example: GitHub Actions
- name: Install dependencies with cooldown
  run: pip install --uploaded-prior-to=P7D -r requirements.txt
```

## Older pip (≤25.x)

If you can't upgrade past pip 25.x:

- Migrate to **uv** for new code (no version barrier to entry).
- Use a **vendoring proxy** that enforces the cooldown at the registry layer: Verdaccio, devpi, or Artifactory. See [`../registry-controls.md`](../registry-controls.md).
- Failing both, rely on strict pinning + lockfile (`requirements.txt` from `pip-compile`) + manual lockfile-diff review on every dependency change.

## Verification

```bash
pip --version                                  # confirm 26.1+
pip config list                                # confirm pip sees your settings
pip install --uploaded-prior-to=P1D <pkg>      # 1-day cutoff for the test
```

If `pip config list` doesn't show your `uploaded-prior-to` value, pip isn't reading the file you placed. Re-check the location list above.

Functional test — pick a package version published in the last 24h. The error **must** mention `uploaded-prior-to`. Generic resolution errors mean the test is invalid.

## Upstream Docs

- [pip configuration locations](https://pip.pypa.io/en/stable/topics/configuration/#location)
- [`--uploaded-prior-to` option](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-uploaded-prior-to)
- [pip 26.0 release notes](https://pip.pypa.io/en/stable/news/#v26-0)
- [pip 26.1 release notes](https://pip.pypa.io/en/stable/news/#v26-1)
