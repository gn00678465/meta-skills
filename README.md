# meta-skills

A Claude Code plugin marketplace that ships **meta-skills** — skills that scaffold *other* agentic workflows, rather than running them. Each skill is published as its own plugin, so you can install only what you need.

## Plugins

| Plugin | Summary | Docs |
|---|---|---|
| `meta-ralph` | Scaffolds a [ralph](https://ghuntley.com/ralph/) autonomous coding loop (`prd.json` + `.ralph/*`) into a target git repo. Pure scaffolder; never executes the loop. | [docs/meta-ralph.md](plugins/meta-ralph/docs/meta-ralph.md) · [SKILL.md](plugins/meta-ralph/skills/meta-ralph/SKILL.md) · [SPEC.md](plugins/meta-ralph/docs/meta-ralph-spec.md) |
| `react-ai-infra` | Deploys cross-platform agent assets (APM `apm.yml`, bundled skills/rules, framework-specific `AGENTS.md`) into an existing React/Next.js/TanStack Start/Vite project for Claude Code and Copilot. Does not scaffold the React app itself. | [SKILL.md](plugins/frontend-dev/react-ai-infra/skills/react-ai-infra/SKILL.md) |
| `security-supply-chain` | Hardens JS/TS and Python package manager configs (pnpm, bun, npm, yarn, uv, pip) against supply chain attacks via minimum release age gates, lockfile commitment, exact version pinning, lifecycle-script allowlists, OIDC/provenance publishing, and commit-time secret scanning. | [SKILL.md](plugins/security-supply-chain/skills/security-supply-chain/SKILL.md) |

## Install

Add the marketplace once, then install whichever plugins you want:

```sh
/plugin marketplace add gn00678465/meta-skills

/plugin install meta-ralph@meta-skills
/plugin install react-ai-infra@meta-skills
/plugin install security-supply-chain@meta-skills
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
    │   ├── docs/
    │   │   ├── meta-ralph.md            (user-facing quickstart)
    │   │   └── meta-ralph-spec.md       (Driver–Agent contract, stable anchors)
    │   └── skills/meta-ralph/
    │       ├── SKILL.md                 (ralph autonomous-loop scaffolder)
    │       └── evals/                   (runner-focused validation suite, sh/ts/js/py)
    ├── frontend-dev/                    (category folder, no plugin.json)
    │   └── react-ai-infra/
    │       ├── .claude-plugin/plugin.json
    │       └── skills/react-ai-infra/   (React agent-asset deployer)
    └── security-supply-chain/
        ├── .claude-plugin/plugin.json
        └── skills/security-supply-chain/
            ├── SKILL.md                 (supply chain hardening playbook)
            ├── examples/                (pnpm/bun/npm/yarn/uv/pip/CI configs)
            └── references/              (per-tool commentary + incident response)
```

## Further reading

- [Claude Code plugin marketplaces](https://code.claude.com/docs/zh-TW/plugin-marketplaces) — official docs.

## License

MIT — see the `license` field in each plugin's `.claude-plugin/plugin.json`.
