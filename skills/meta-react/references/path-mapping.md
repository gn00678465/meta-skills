# Path Mapping

Authoritative source-to-destination table. The agent uses this to know exactly where each bundled asset lands and which transform (if any) applies.

## Project root

All destinations are resolved relative to `<project-root>` — the directory where `apm.yml` is being generated. The project root is the agent's current working directory unless the user specified otherwise.

## Source layout (this skill)

```
meta-react/
├── SKILL.md
├── templates/
│   └── apm.yml
├── skills/
│   └── <name>/
│       └── SKILL.md          # plus any nested files
└── rules/
    └── <name>.md             # frontmatter: paths: [...]
```

## Destination layout (per target)

### Claude Code (`claude` target)

| Source | Destination | Transform |
|--------|-------------|-----------|
| `templates/apm.yml` | `<project-root>/apm.yml` | Substitute `<project-name>`; set `targets:` (plural, block-style list) |
| `skills/<name>/**` | `<project-root>/.claude/skills/<name>/**` | None |
| `rules/<name>.md` | `<project-root>/.claude/rules/<name>.md` | None — `paths:` frontmatter preserved |

### GitHub Copilot (`copilot` target)

| Source | Destination | Transform |
|--------|-------------|-----------|
| `templates/apm.yml` | `<project-root>/apm.yml` | Same as above (one apm.yml per project) |
| `skills/<name>/**` | `<project-root>/.agents/skills/<name>/**` | None — Copilot reads from cross-client `.agents/skills/` |
| `rules/<name>.md` | `<project-root>/.github/instructions/<name>.instructions.md` | Frontmatter `paths:` → `applyTo:` (see `frontmatter-transform.md`) |

### Cross-client (`agent-skills`)

Always emit alongside other targets. Skills go to `.agents/skills/` so any APM-aware client (Codex, Cursor, Windsurf, …) can pick them up without re-running install.

| Source | Destination | Transform |
|--------|-------------|-----------|
| `skills/<name>/**` | `<project-root>/.agents/skills/<name>/**` | None |

> Note: `agent-skills` is the same physical directory Copilot reads from. When both `copilot` and `agent-skills` are active, do not double-copy — write each file once.

## What APM handles vs what this skill handles

| Asset class | Handled by |
|-------------|------------|
| External APM packages (`react-best-practices`, etc.) | `apm install` (Step 3) |
| MCP servers declared in `apm.yml` | `apm install` |
| Bundled skills shipped with this meta-skill (`skills/<name>/`) | This skill (Step 5) |
| Bundled rules shipped with this meta-skill (`rules/<name>.md`) | This skill (Step 6) |

The split is intentional: APM owns version-pinned remote dependencies; this skill owns the team's locally-curated, source-of-truth assets that are always fresh from the repo.

## Idempotence

Every step is re-runnable. If the user runs the skill twice:

- `apm install` is naturally idempotent (lockfile-driven).
- Bundled skill copies overwrite identical content with identical content (no-op).
- Bundled rule copies overwrite identical content with identical content.

If the user has hand-edited a deployed rule or skill, prompt before overwriting — the user's edits are not in this skill's source tree.
