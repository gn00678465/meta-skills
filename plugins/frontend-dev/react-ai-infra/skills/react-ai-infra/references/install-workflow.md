# Install Workflow

Step-by-step procedure that the agent runs when the react-ai-infra skill is invoked. Each step is concrete and tool-mappable. Step numbers match `SKILL.md` § What this skill does.

## Step 0 — Verify apm is installed

This MUST be the first action — every later step depends on the `apm` CLI.

Detection (try whichever shell has `apm` on `PATH`):

```bash
apm --version
```

If the exit code is non-zero or the shell reports `command not found` / `not recognized`, retry in PowerShell before declaring it missing — on Windows the installer typically registers `apm` only for PowerShell, so Git Bash and WSL-style shells often miss it even when APM is installed. Only stop and emit the install message below if every available shell fails. Do NOT continue to Step 1 if the CLI truly isn't reachable.

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
| `bash: apm: command not found` | macOS / Linux / WSL — APM truly missing (or Git Bash on Windows where APM is registered only for PowerShell — retry there before giving up) |
| `'apm' is not recognized as ... cmdlet` | Windows PowerShell |
| `apm: The term 'apm' is not recognized` | Windows PowerShell (alt phrasing) |
| Bash exit code 127 on Windows but `apm --version` works in PowerShell | Cross-shell PATH mismatch — proceed using PowerShell for all `apm` calls in this run |
| Bash exit code 127 on POSIX | True command-not-found — emit install message |
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

## Step 2 — Ask which React framework

Prompt the user (single-select, no default — the user MUST pick):

```
Which React framework is this project using?
  1) Next.js          (slug: nextjs)
  2) TanStack Start   (slug: tanstack-start)
  3) Vite + React     (slug: vite-react)
```

Record the chosen slug as `<framework>`. **Step 7 is the only consumer**; all other steps stay framework-agnostic. The slug also decides whether Step 7 deploys anything at all — only `nextjs` currently ships a template (see `agents-md-deployment.md` for the table).

Do NOT auto-detect from `package.json` or lockfiles. Repos can be mid-migration, have leftover config, or include multiple framework hints — only the user knows the intended target.

If the agent runtime does not support interactive prompts (e.g. a non-interactive CI run), fail with:

> react-ai-infra requires a framework choice (nextjs / tanstack-start / vite-react). Re-run in an interactive session or pass the framework explicitly.

## Step 3 — Generate or merge apm.yml

### 3a. Resolve project name

Order of fallbacks:

1. Read `<project-root>/package.json` and use the `name` field.
2. If no `package.json`, use the basename of `<project-root>`.
3. Replace any whitespace with `-`; strip scope prefixes (`@org/foo` → `foo`).

### 3b. Generate or merge

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

## Step 4 — Construct and run apm install

Before running, capture pre-state for Step 7:

```text
agents_md_existed_pre_apm = file_exists(<project-root>/AGENTS.md)
```

Then build the command:

```bash
apm install --target <comma-separated-targets>
```

Examples:

| Detected | Command |
|----------|---------|
| Claude only | `apm install --target claude,agent-skills` |
| Copilot only | `apm install --target copilot,agent-skills` |
| Both | `apm install --target claude,copilot,agent-skills` |

Always confirm with the user before executing. On failure (non-zero exit), surface stderr and stop — local deployment in Steps 5–7 expects `apm install` succeeded.

If `apm` is not on PATH in any available shell, instruct the user to install it (see `SKILL.md` "Required inputs") and stop. On Windows specifically, retry in PowerShell before declaring it missing — see Step 0.

> **Side effects from `apm install`.** It writes resolved packages to `<project-root>/apm_modules/`, and APM ≥ 0.12 also appends `apm_modules/` to `<project-root>/.gitignore` (creating the file if absent). Capture both effects in Step 8's report so the user sees what `.gitignore` and `apm_modules/` changed without having to read APM's own output.

> When the `copilot` target is active, `apm install` may itself emit `AGENTS.md` at the project root. Step 7 uses `agents_md_existed_pre_apm` to detect that and auto-append instead of clobbering. See `agents-md-deployment.md` for why.

## Step 5 — Deploy bundled skills

Source: `<this-skill>/skills/<name>/`

Destinations:

- `<project-root>/.agents/skills/<name>/` (always)
- `<project-root>/.claude/skills/<name>/` (only if `claude` target is active)

Copy the entire directory tree. Skill `SKILL.md` frontmatter is identical across both ecosystems — no transformation.

If a destination already exists, prompt the user before overwriting. Show a diff summary if possible.

## Step 6 — Deploy bundled rules

Source: `<this-skill>/rules/<name>.md`

Destinations and transforms:

| Target | Destination | Transform |
|--------|-------------|-----------|
| `claude` | `<project-root>/.claude/rules/<name>.md` | None — copy verbatim |
| `copilot` | `<project-root>/.github/instructions/<name>.instructions.md` | Frontmatter `paths:` → `applyTo:` (see `frontmatter-transform.md`) |

Create parent directories on demand.

## Step 7 — Deploy framework-specific AGENTS.md

The full contract lives in `agents-md-deployment.md`. Routing notes for this workflow:

- Look up `templates/agents/<framework>.md` using the slug from Step 2.
- If no template ships for that framework, log the canonical skip string and continue. Currently only `nextjs` ships.
- Otherwise follow `agents-md-deployment.md` verbatim for branch selection and report strings.
- **Branch 3 safety condition** — the APM-just-emitted branch fires only when `copilot` is in the selected targets **and** `agents_md_existed_pre_apm == false`. If `copilot` was not selected, an unmarked `AGENTS.md` is Branch 4 even if the file appeared during this run. Do not reduce this to "pre-state was false."

## Step 8 — Verify and report

Run a quick sanity check:

```bash
ls <project-root>/.claude/skills/      # if claude
ls <project-root>/.agents/skills/
ls <project-root>/.claude/rules/       # if claude
ls <project-root>/.github/instructions/  # if copilot
ls <project-root>/AGENTS.md            # if Step 7 wrote anything
ls <project-root>/apm_modules/         # Step 4 side effect
grep -F 'apm_modules/' <project-root>/.gitignore  # Step 4 side effect — confirm apm appended the entry
```

Report deployed paths and any merge advisories. Use the Step 7 report string from `agents-md-deployment.md` § Reporting terms verbatim — that table is the canonical source. Also report whether `apm_modules/` was created or updated and whether `.gitignore` was created or updated by APM (including the `apm_modules/` append) — these are the Step 4 side effects the user expects to see surfaced rather than discover via `git diff`.

## Failure modes

Cross-cutting failures only. AGENTS.md-specific failure modes live in `agents-md-deployment.md` § Failure modes.

| Symptom | Action |
|---------|--------|
| `apm: command not found` | Should be caught by Step 0. If somehow reached here, fall back to the Step 0 install message and stop. |
| `apm install` returns non-zero | Print stderr, stop. Do not deploy local files. |
| `package.json` is malformed | Fall back to directory basename for `<project-name>`. |
| Step 2 reached in a non-interactive runtime (no TTY for the framework prompt) | Fail fast with the framework-required message in §Step 2 — do not guess a slug and do not skip to Step 3. |
| Destination file is user-edited (different content + has writes) | Prompt user before overwriting; default to skip. (AGENTS.md follows a different rule — see `agents-md-deployment.md`.) |
| `paths:` frontmatter has unsupported syntax | Fall back to `applyTo: "**"` and log a warning naming the file. The Copilot output MUST always contain an `applyTo:` field. |
