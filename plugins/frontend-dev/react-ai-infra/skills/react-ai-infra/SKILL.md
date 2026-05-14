---
name: react-ai-infra
description: |
  Deploys cross-platform agent assets into an already-created React project.
  ACTIVATE when a React/Next.js/TanStack Start/Vite repo (existing or
  freshly bootstrapped by its own CLI) needs APM-managed dependencies,
  bundled skills/rules, and a framework-specific AGENTS.md wired in for
  Claude Code, GitHub Copilot, and the cross-client `.agents/skills/` bus.
  Asks which React framework is in use, generates apm.yml at the project
  root, runs `apm install`, and writes assets to .claude/skills/,
  .agents/skills/, .claude/rules/, .github/instructions/, and the project
  root. Does NOT create the React app itself.
---

# react-ai-infra

A meta-skill that wires [APM](https://github.com/microsoft/apm) (Agent Package Manager) and the team's curated React skill set into an existing React project across Claude Code and GitHub Copilot.

This skill does **not** scaffold the React project itself — the user is expected to have already run `create-next-app`, `create-tsrouter-app`, `npm create vite`, or equivalent. What this skill owns is the agent-asset layer: `apm.yml`, bundled skills and rules, and the framework-specific `AGENTS.md`.

## What this skill does

| Step | Action | Tool |
|------|--------|------|
| 0 | Verify `apm` CLI is installed; abort with install instructions if not | Shell |
| 1 | Detect target environments at the project root | Glob / Shell |
| 2 | Ask which React framework is in use (Next.js / TanStack Start / Vite + React) | Prompt |
| 3 | Generate (or merge) `apm.yml` at project root from `templates/apm.yml` | Read / Write |
| 4 | Run `apm install --target <list>` (with user confirmation) | Shell |
| 5 | Copy bundled skills to `.claude/skills/` and `.agents/skills/` | Read / Write |
| 6 | Copy bundled rules to `.claude/rules/` and (with frontmatter transform) `.github/instructions/<name>.instructions.md` | Read / Write |
| 7 | Deploy framework-specific `AGENTS.md` to project root (Next.js only currently — others skip cleanly) | Read / Write |
| 8 | Verify deployment and report | Glob / Shell |

## When to use

- A React/Next.js/TanStack Start/Vite repo already exists (or has just been created via its own CLI) and needs the team's agent assets wired in.
- An existing React repo needs Claude Code + Copilot parity (skills + rules in both ecosystems).
- Onboarding APM-managed dependencies (e.g. `react-best-practices`) into a project.

## When NOT to use

- Non-React projects.
- The repo has not been created yet — run `create-next-app` / `create-tsrouter-app` / `npm create vite` first, then come back.
- The user only wants to install one APM package — call `apm install <pkg>` directly.
- The project must NOT install APM (some monorepos pin tooling versions).

## Required inputs

- A working directory that is the **project root** (where `package.json` lives — this skill does not create it).
- `apm` CLI installed and on `PATH` (verified in Step 0).
- An interactive session for Step 2's framework prompt. In a non-interactive run, the skill MUST fail fast with a clear message rather than guess (see Step 2 below).

## Workflow

### 0. Verify `apm` is installed

Before any other step, run `apm --version` (or `apm targets`) via whichever shell has `apm` on `PATH`. On Windows the installer typically registers `apm` only for PowerShell, so Git Bash / WSL-style shells may report `command not found` even when `apm` is installed — fall back to PowerShell before declaring it missing. If the command is not found in any available shell OR returns a non-zero exit code, **stop immediately** and print this message to the user verbatim:

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

Do not generate `apm.yml`, do not copy bundled assets — exit cleanly so the user can install APM and retry.

### 1. Detect target environments

Inspect the project root for these markers:

| Marker | Target |
|--------|--------|
| `.claude/` directory or `CLAUDE.md` | `claude` |
| `.github/` directory or `.github/copilot-instructions.md` | `copilot` |
| `.agents/skills/` | cross-client skill bus (always included alongside other targets) |

If neither `.claude/` nor `.github/` exists, ask the user which targets to scaffold (default: both). Record the chosen target list — it drives `apm install --target` and the local-copy steps.

> **Extending targets later.** The detected list is committed to `apm.yml` in Step 3, and Step 3's merge rule keeps an existing `targets:` block untouched (see `references/install-workflow.md` § 3b). If the user later adds `.github/` to a Claude-only setup and re-runs the skill, the new target will NOT be added automatically — they must manually edit `targets:` in `apm.yml` and re-run `apm install`. This is intentional conservative behavior; the union-on-extend variant is tracked separately.

### 2. Ask which React framework

Prompt the user to pick exactly one framework:

```
Which React framework is this project using?
  1) Next.js          (slug: nextjs)
  2) TanStack Start   (slug: tanstack-start)
  3) Vite + React     (slug: vite-react)
```

Record the chosen slug as `<framework>`. **Step 7 is the only consumer** — `apm.yml` and the bundled skills/rules in Steps 3–6 are framework-agnostic for now. The slug also decides whether Step 7 deploys anything at all: only `nextjs` ships an AGENTS.md template; the other two skip Step 7 with a logged notice (see `references/agents-md-deployment.md`).

Do NOT auto-detect. The user is the source of truth — a repo may have leftover config from a previous framework, or be mid-migration.

**Non-interactive runs** (e.g. CI without a TTY): fail fast with `react-ai-infra requires a framework choice (nextjs / tanstack-start / vite-react). Re-run in an interactive session or pass the framework explicitly.` Do not guess and do not proceed past this step.

### 3. Generate or merge `apm.yml`

- If `<project-root>/apm.yml` does **not** exist:
  - Read `templates/apm.yml` (relative to this skill).
  - Resolve the project name: take `package.json` `name`, or fall back to the directory basename. Strip any `@scope/` prefix (`@org/foo` → `foo`) and replace whitespace with `-`.
  - Substitute `<project-name>` with the resolved value.
  - Set the `targets:` field (plural, block-style list) to the detected target list. The list MUST always include `agent-skills` alongside any per-client targets. Do NOT use the singular `target:` or inline-array form `[a, b]` — current APM CLI versions reject both.
  - Write the file.
- If `<project-root>/apm.yml` exists:
  - Parse both YAMLs.
  - Union `dependencies.apm` and `dependencies.mcp` (deduplicate by canonical string).
  - Preserve all user-set keys; only add what is missing.
  - Re-write the merged result.

See `references/apm-yml-template.md` for schema details.

### 4. Run `apm install`

Build the command:

```
apm install --target <comma-separated-targets>
```

Example: `apm install --target claude,copilot,agent-skills`

- Print the exact command and pause for user confirmation before executing.
- On user approval, run via whichever shell has `apm` on `PATH` (see Step 0 — usually PowerShell on Windows, Bash on macOS/Linux/WSL).
- Stream output. If exit code ≠ 0, surface the error and stop — do **not** proceed to local deployment.

> **Side effects to expect:** `apm install` writes installed packages to `apm_modules/` at the project root, and recent APM versions auto-append `apm_modules/` to `.gitignore` (creating one if missing). Surface this in the Step 8 report so the user is not surprised by the new ignore entry.

> **Heads-up for Step 7:** when the `copilot` target is active, `apm install` may itself emit an `AGENTS.md` at the project root. Before running this command, record `agents_md_existed_pre_apm = file_exists(<project-root>/AGENTS.md)` so Step 7 can distinguish "APM just wrote this" from "the user had it before we got here." See `references/agents-md-deployment.md` for why this matters.

### 5. Deploy bundled skills

For each subdirectory `<name>` under `<this-skill>/skills/`:

- Always copy the entire directory tree to `<project-root>/.agents/skills/<name>/` (cross-client target).
- If the `claude` target is active, also copy to `<project-root>/.claude/skills/<name>/`.

Skills are copied verbatim — no frontmatter transformation needed (Claude Code and Copilot both consume `SKILL.md` with the same frontmatter shape).

### 6. Deploy bundled rules (with frontmatter transform)

For each `<name>.md` under `<this-skill>/rules/`:

- **Claude target** (`claude` selected): copy verbatim to `<project-root>/.claude/rules/<name>.md`. Source `paths:` frontmatter is kept as-is.
- **Copilot target** (`copilot` selected): transform frontmatter and write to `<project-root>/.github/instructions/<name>.instructions.md`.
  - `paths: ["src/**/*.{tsx,jsx}"]` becomes `applyTo: "src/**/*.tsx,src/**/*.jsx"`
  - See `references/frontmatter-transform.md` for the full algorithm and edge cases.

Create destination directories if they do not exist.

### 7. Deploy framework-specific `AGENTS.md`

Source: `<this-skill>/templates/agents/<framework>.md`. Destination: `<project-root>/AGENTS.md`.

Step 7 is specified in `references/agents-md-deployment.md`.

- If no template ships for the chosen framework (currently anything other than `nextjs`), **skip cleanly** with a logged notice. Not an error.
- Otherwise follow that reference verbatim for branch selection, marker handling, APM coexistence (uses `agents_md_existed_pre_apm` captured in Step 4), and report strings.

### 8. Verify and report

- List every file created / overwritten with its absolute path.
- Confirm the `apm install` exit status.
- Report whether `<project-root>/apm_modules/` was created or updated by `apm install` (Step 4 side effect).
- Report whether `<project-root>/.gitignore` was created or updated by `apm install` (specifically whether `apm_modules/` was appended).
- Highlight any merge advisories from `apm.yml` (Step 3) or `AGENTS.md` (Step 7).
- Suggest the user reload their agent (Claude Code: `/reload-plugins`; Copilot: restart VS Code) so new skills are picked up.

## Output format

```
Targets detected: claude, copilot, agent-skills
Framework:        nextjs

apm.yml: created (or: merged — added 1 dependency)
apm install: success

Side effects:
  - apm_modules/: created
  - .gitignore: updated (appended `apm_modules/`)
  # both come from `apm install` itself; omit a line if the corresponding
  # path was unchanged on this run.

Deployed skills:
  - .claude/skills/no-use-effect/SKILL.md
  - .agents/skills/no-use-effect/SKILL.md

Deployed rules:
  - .claude/rules/react-components.md
  - .github/instructions/react-components.instructions.md (frontmatter: paths -> applyTo)

AGENTS.md:
  - <one of the report strings from references/agents-md-deployment.md>
  # e.g. "AGENTS.md: created (template nextjs.md)"
  # or   "AGENTS.md: appended managed block below APM-generated content"
  # or   "No AGENTS.md template for vite-react yet — skipped"

Next steps:
  - Reload your agent so it picks up the new skills/rules.
```

## References

| Open when... | Read |
|--------------|------|
| Need step-by-step install commands or target detection details | `references/install-workflow.md` |
| Implementing Step 7 — full branch table, APM coexistence, marker logic, AGENTS.md failure modes | `references/agents-md-deployment.md` |
| Transforming `paths:` frontmatter to Copilot `applyTo:` | `references/frontmatter-transform.md` |
| Mapping source files to destination paths across targets | `references/path-mapping.md` |
| Customizing the generated `apm.yml` (extra deps, MCP servers, scripts) | `references/apm-yml-template.md` |

## Bundled assets

| Path | Purpose |
|------|---------|
| `templates/apm.yml` | Source manifest copied to project root and customized |
| `templates/agents/nextjs.md` | Next.js AGENTS.md template (verbatim from the [official guide](https://nextjs.org/docs/app/guides/ai-agents)) |
| `skills/no-use-effect/SKILL.md` | Bundled skill: ban `useEffect`, prescribe replacement patterns |
| `rules/react-components.md` | Bundled rule: scoped to `src/**/*.{tsx,jsx}` files |

To add a new bundled skill: drop it under `skills/<name>/`. To add a new rule: drop it under `rules/<name>.md` with `paths:` frontmatter. To add an AGENTS.md template for another framework: drop it under `templates/agents/<framework-slug>.md` wrapped in `<!-- BEGIN:<framework-slug>-agent-rules -->` / `<!-- END:<framework-slug>-agent-rules -->` markers, then update the framework → template table in `references/agents-md-deployment.md`. All three are picked up automatically by Steps 5 / 6 / 7.
