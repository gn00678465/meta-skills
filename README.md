# meta-skills

A Claude Code plugin marketplace that ships **meta-skills** — skills that scaffold *other* agentic workflows, rather than running them. Each skill is published as its own plugin, so you can install only what you need.

## Plugins

| Plugin | Summary | Docs |
|---|---|---|
| `meta-ralph` | Scaffolds a [ralph](https://ghuntley.com/ralph/) autonomous coding loop (`prd.json` + `.ralph/*`) into a target git repo. Pure scaffolder; never executes the loop. | [docs/meta-ralph.md](plugins/meta-ralph/docs/meta-ralph.md) · [SKILL.md](plugins/meta-ralph/skills/meta-ralph/SKILL.md) |
| `react-ai-infra` | Deploys cross-platform agent assets (APM `apm.yml`, bundled skills/rules, framework-specific `AGENTS.md`) into an existing React/Next.js/TanStack Start/Vite project for Claude Code and Copilot. Does not scaffold the React app itself. | [SKILL.md](plugins/frontend-dev/react-ai-infra/skills/react-ai-infra/SKILL.md) |

## Install

Add the marketplace once, then install whichever plugins you want:

```sh
/plugin marketplace add gn00678465/meta-skills

/plugin install meta-ralph@meta-skills
/plugin install react-ai-infra@meta-skills
```

Local testing:

```sh
/plugin marketplace add ./path/to/meta-skills
/plugin install meta-ralph@meta-skills
```

## Repo layout

```
meta-skills/
├── .claude-plugin/
│   └── marketplace.json                 (multi-plugin marketplace)
└── plugins/
    ├── meta-ralph/
    │   ├── .claude-plugin/plugin.json
    │   ├── docs/meta-ralph.md           (design + usage notes)
    │   └── skills/meta-ralph/           (ralph autonomous-loop scaffolder)
    └── frontend-dev/                    (category folder, no plugin.json)
        └── react-ai-infra/
            ├── .claude-plugin/plugin.json
            └── skills/react-ai-infra/   (React agent-asset deployer)
```

## Further reading

- [Claude Code plugin marketplaces](https://code.claude.com/docs/zh-TW/plugin-marketplaces) — official docs.

## License

MIT — see the `license` field in each plugin's `.claude-plugin/plugin.json`.
