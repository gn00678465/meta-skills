---
name: meta-react
description: |
  Scaffold or extend a React project with cross-platform agent assets.
  ACTIVATE when bootstrapping a new React app, onboarding the team's React
  skill set into an existing repo, or porting a project to multi-agent
  (Claude Code + Copilot) workflows. Generates apm.yml at the project root,
  runs `apm install`, and deploys bundled skills/rules to .claude/skills/,
  .agents/skills/, .claude/rules/, and .github/instructions/.
---

# Meta-React

A meta-skill that bootstraps React projects with [APM](https://github.com/microsoft/apm) (Agent Package Manager) and deploys the team's curated React skill set across Claude Code and GitHub Copilot.

## What this skill does

| Step | Action | Tool |
|------|--------|------|
| 0 | Verify `apm` CLI is installed; abort with install instructions if not | Bash |
| 1 | Detect target environments at the project root | Glob / Bash |
| 2 | Generate (or merge) `apm.yml` at project root from `templates/apm.yml` | Read / Write |
| 3 | Run `apm install --target <list>` (with user confirmation) | Bash |
| 4 | Copy bundled skills to `.claude/skills/` and `.agents/skills/` | Read / Write |
| 5 | Copy bundled rules to `.claude/rules/` and (with frontmatter transform) `.github/instructions/<name>.instructions.md` | Read / Write |
| 6 | Verify deployment and report | Glob / Bash |

## When to use

- User starts a new React/Next.js/Vite project and wants the team's agent assets ready.
- An existing React repo needs Claude Code + Copilot parity (skills + rules in both ecosystems).
- Onboarding APM-managed dependencies (e.g. `react-best-practices`) into a project.

## When NOT to use

- Non-React projects.
- The user only wants to install one APM package — call `apm install <pkg>` directly.
- The project must NOT install APM (some monorepos pin tooling versions).

## Required inputs

- A working directory that is the **project root** (where `package.json` lives, or will live).
- `apm` CLI installed and on `PATH` (verified in Step 0).

## Workflow

### 0. Verify `apm` is installed

Before any other step, run `apm --version` (or `apm targets`) via Bash. If the command is not found OR returns a non-zero exit code, **stop immediately** and print this message to the user verbatim:

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

### 2. Generate or merge `apm.yml`

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

### 3. Run `apm install`

Build the command:

```
apm install --target <comma-separated-targets>
```

Example: `apm install --target claude,copilot,agent-skills`

- Print the exact command and pause for user confirmation before executing.
- On user approval, run via Bash from the project root.
- Stream output. If exit code ≠ 0, surface the error and stop — do **not** proceed to local deployment.

### 4. Deploy bundled skills

For each subdirectory `<name>` under `<this-skill>/skills/`:

- Always copy the entire directory tree to `<project-root>/.agents/skills/<name>/` (cross-client target).
- If the `claude` target is active, also copy to `<project-root>/.claude/skills/<name>/`.

Skills are copied verbatim — no frontmatter transformation needed (Claude Code and Copilot both consume `SKILL.md` with the same frontmatter shape).

### 5. Deploy bundled rules (with frontmatter transform)

For each `<name>.md` under `<this-skill>/rules/`:

- **Claude target** (`claude` selected): copy verbatim to `<project-root>/.claude/rules/<name>.md`. Source `paths:` frontmatter is kept as-is.
- **Copilot target** (`copilot` selected): transform frontmatter and write to `<project-root>/.github/instructions/<name>.instructions.md`.
  - `paths: ["src/**/*.{tsx,jsx}"]` becomes `applyTo: "src/**/*.tsx,src/**/*.jsx"`
  - See `references/frontmatter-transform.md` for the full algorithm and edge cases.

Create destination directories if they do not exist.

### 6. Verify and report

- List every file created / overwritten with its absolute path.
- Confirm the `apm install` exit status.
- Highlight any merge conflicts in `apm.yml` that required user-side review.
- Suggest the user reload their agent (Claude Code: `/reload-plugins`; Copilot: restart VS Code) so new skills are picked up.

## Output format

```
Targets detected: claude, copilot, agent-skills

apm.yml: created (or: merged — added 1 dependency)
apm install: success

Deployed skills:
  - .claude/skills/no-use-effect/SKILL.md
  - .agents/skills/no-use-effect/SKILL.md

Deployed rules:
  - .claude/rules/react-components.md
  - .github/instructions/react-components.instructions.md (frontmatter: paths -> applyTo)

Next steps:
  - Reload your agent so it picks up the new skills/rules.
```

## References

| Open when... | Read |
|--------------|------|
| Need step-by-step install commands or target detection details | `references/install-workflow.md` |
| Transforming `paths:` frontmatter to Copilot `applyTo:` | `references/frontmatter-transform.md` |
| Mapping source files to destination paths across targets | `references/path-mapping.md` |
| Customizing the generated `apm.yml` (extra deps, MCP servers, scripts) | `references/apm-yml-template.md` |

## Bundled assets

| Path | Purpose |
|------|---------|
| `templates/apm.yml` | Source manifest copied to project root and customized |
| `skills/no-use-effect/SKILL.md` | Bundled skill: ban `useEffect`, prescribe replacement patterns |
| `rules/react-components.md` | Bundled rule: scoped to `src/**/*.{tsx,jsx}` files |

To add a new bundled skill: drop it under `skills/<name>/`. To add a new rule: drop it under `rules/<name>.md` with `paths:` frontmatter. Both are picked up automatically by Step 4 / Step 5.
