# Install Workflow

Step-by-step procedure that the agent runs when the meta-react skill is invoked. Each step is concrete and tool-mappable.

## Step 0 — Verify apm is installed

This MUST be the first action — every later step depends on the `apm` CLI.

Detection:

```bash
apm --version
```

If the exit code is non-zero or the shell reports `command not found` / `not recognized`, stop immediately. Do NOT continue to Step 1.

Print this message verbatim to the user:

```
APM (Agent Package Manager) is not installed or not on PATH.
Install it first:

  Windows (PowerShell):  irm https://aka.ms/apm-windows | iex
  macOS / Linux:         curl -sSL https://aka.ms/apm-unix | sh
  Homebrew:              brew install microsoft/apm/apm
  pip:                   pip install apm-cli

After installing, re-run this skill.
Docs: https://github.com/microsoft/apm
```

Detection table (platform-specific cues for the agent):

| Symptom | Platform hint |
|---------|---------------|
| `bash: apm: command not found` | macOS / Linux / WSL |
| `'apm' is not recognized as ... cmdlet` | Windows PowerShell |
| `apm: The term 'apm' is not recognized` | Windows PowerShell (alt phrasing) |
| Bash exit code 127 | POSIX shell — command not found |
| `apm --version` succeeds but prints `0.0.x` < `0.1` | Outdated; recommend `apm update` then continue with caution |

Never offer to install `apm` automatically — installation requires elevated privileges or shell-profile modification, which the user must own.

## Step 1 — Detect target environments

Run from `<project-root>`:

| Check | Result | Adds target |
|-------|--------|-------------|
| `Glob` `.claude/**` matches OR `CLAUDE.md` exists | Claude Code present | `claude` |
| `Glob` `.github/**` matches OR `.github/copilot-instructions.md` exists | Copilot present | `copilot` |
| Always | Cross-client skill bus | `agent-skills` |

If neither `.claude/` nor `.github/` is present, ask the user:

> No `.claude/` or `.github/` directory found. Scaffold for which agent(s)? [claude / copilot / both — default: both]

## Step 2 — Generate or merge apm.yml

### 2a. Resolve project name

Order of fallbacks:

1. Read `<project-root>/package.json` and use the `name` field.
2. If no `package.json`, use the basename of `<project-root>`.
3. Replace any whitespace with `-`; strip scope prefixes (`@org/foo` → `foo`).

### 2b. Generate or merge

```text
exists = file_exists(<project-root>/apm.yml)
template = read(<this-skill>/templates/apm.yml)
template = substitute(template, "<project-name>", resolved_name)
template = set_targets(template, detected_targets)   # writes `targets:` block list

if not exists:
    write(<project-root>/apm.yml, template)
else:
    existing = parse_yaml(<project-root>/apm.yml)
    incoming = parse_yaml(template)
    merged = deep_merge(existing, incoming, dedupe_keys=["dependencies.apm", "dependencies.mcp"])
    # User-set keys win; we only ADD missing ones.
    write(<project-root>/apm.yml, dump_yaml(merged))
```

Merge rules:

- `dependencies.apm` and `dependencies.mcp`: union by **canonical key**. If two entries share the same canonical key, keep the existing (user) entry — never replace.
- `targets`: if the existing manifest already has a `targets` field (or the legacy singular `target`), keep it untouched. Otherwise add the detected list as block-style YAML under `targets:`. Never write the singular `target:` or inline-array `[a, b]` — current APM CLI versions reject both with `Unknown target '['claude'`.
- `name`, `version`, `description`, scripts: never overwrite existing values.

### Canonical key for dedup

The canonical key is the part of the entry that identifies *which package* is referenced, ignoring version pins and per-install options. Compute it like this:

For an `apm` dependency:

| Form | Canonical key |
|------|---------------|
| String `owner/repo` | `owner/repo` (lowercased) |
| String `owner/repo#ref` | `owner/repo` (strip everything from `#` onward) |
| String `owner/repo/sub/path` | `owner/repo/sub/path` (subpath is part of identity) |
| String URL `https://host/owner/repo.git` | `host/owner/repo` (strip scheme, `.git`, ref) |
| Object `{ source: X, ref: Y, skills: [...] }` | canonical key of `X` (apply the rules above to `source`) |
| Local path `./pkg` or `../pkg` | the absolute, normalized filesystem path |

For an `mcp` dependency: canonical key is the `name:` field (or the URL if no name). Two MCP entries with the same name are the same server even if transport/url differ.

Examples:

| Existing | Incoming | Same? |
|----------|----------|-------|
| `vercel-labs/agent-skills/skills/react-best-practices` | `vercel-labs/agent-skills/skills/react-best-practices#main` | yes — keep existing |
| `vercel-labs/agent-skills/skills/react-best-practices` | `vercel-labs/agent-skills/skills/react-best-practices/sub` | no — distinct subpaths |
| `Vercel-Labs/agent-skills` | `vercel-labs/agent-skills` | yes — case-insensitive |
| Object `{source: vercel-labs/agent-skills, skills: [a]}` | String `vercel-labs/agent-skills#main` | yes — keep object form (user authored) |

## Step 3 — Construct and run apm install

```bash
apm install --target <comma-separated-targets>
```

Examples:

| Detected | Command |
|----------|---------|
| Claude only | `apm install --target claude,agent-skills` |
| Copilot only | `apm install --target copilot,agent-skills` |
| Both | `apm install --target claude,copilot,agent-skills` |

Always confirm with the user before executing. On failure (non-zero exit), surface stderr and stop — local deployment in Steps 4-5 expects `apm install` succeeded.

If `apm` is not on PATH, instruct the user to install it (see `SKILL.md` "Required inputs") and stop.

## Step 4 — Deploy bundled skills

Source: `<this-skill>/skills/<name>/`

Destinations:

- `<project-root>/.agents/skills/<name>/` (always)
- `<project-root>/.claude/skills/<name>/` (only if `claude` target is active)

Copy the entire directory tree. Skill `SKILL.md` frontmatter is identical across both ecosystems — no transformation.

If a destination already exists, prompt the user before overwriting. Show a diff summary if possible.

## Step 5 — Deploy bundled rules

Source: `<this-skill>/rules/<name>.md`

Destinations and transforms:

| Target | Destination | Transform |
|--------|-------------|-----------|
| `claude` | `<project-root>/.claude/rules/<name>.md` | None — copy verbatim |
| `copilot` | `<project-root>/.github/instructions/<name>.instructions.md` | Frontmatter `paths:` → `applyTo:` (see `frontmatter-transform.md`) |

Create parent directories on demand.

## Step 6 — Verify and report

Run a quick sanity check:

```bash
ls <project-root>/.claude/skills/      # if claude
ls <project-root>/.agents/skills/
ls <project-root>/.claude/rules/       # if claude
ls <project-root>/.github/instructions/  # if copilot
```

Report deployed paths and any merge advisories.

## Failure modes

| Symptom | Action |
|---------|--------|
| `apm: command not found` | Should be caught by Step 0. If somehow reached here, fall back to the Step 0 install message and stop. |
| `apm install` returns non-zero | Print stderr, stop. Do not deploy local files. |
| `package.json` is malformed | Fall back to directory basename for `<project-name>`. |
| Destination file is user-edited (different content + has writes) | Prompt user before overwriting; default to skip. |
| `paths:` frontmatter has unsupported syntax | Fall back to `applyTo: "**"` and log a warning naming the file. The Copilot output MUST always contain an `applyTo:` field — see SPEC.md acceptance criterion 4. |
