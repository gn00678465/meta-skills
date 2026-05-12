# meta-skills

A Claude Code plugin marketplace that ships **meta-skills** — skills that scaffold *other* agentic workflows, rather than running them.

## Skills

| Skill | Summary | Docs |
|---|---|---|
| `meta-bootstrap-docs` | Scaffolds `CLAUDE.md` / `AGENTS.md` (and Karpathy-style guidelines) into a target repo so new projects start with a coherent agent-instruction baseline. | [SKILL.md](skills/meta-bootstrap-docs/SKILL.md) |
| `meta-ralph` | Scaffolds a [ralph](https://ghuntley.com/ralph/) autonomous coding loop (`prd.json` + `.ralph/*`) into a target git repo. Pure scaffolder; never executes the loop. | [docs/meta-ralph.md](docs/meta-ralph.md) · [SKILL.md](skills/meta-ralph/SKILL.md) |
| `meta-react` | Scaffolds React-project conventions: APM `apm.yml` template, path-mapping / frontmatter-transform / install-workflow references, `react-components` rules, plus nested skills (e.g. `no-use-effect`). | [SKILL.md](skills/meta-react/SKILL.md) |

## Install

```sh
/plugin marketplace add gn00678465/meta-skills
/plugin install meta-skills@meta-skills
```

Local testing:

```sh
/plugin marketplace add ./path/to/meta-skills
/plugin install meta-skills@meta-skills
```

## Repo layout

```
meta-skills/
├── .claude-plugin/
│   ├── marketplace.json       (single-plugin marketplace; source: "./")
│   └── plugin.json            (plugin manifest)
├── docs/
│   └── meta-ralph.md          (design + usage notes for meta-ralph)
└── skills/
    ├── meta-bootstrap-docs/   (CLAUDE.md / AGENTS.md scaffolder)
    ├── meta-ralph/            (ralph autonomous-loop scaffolder)
    └── meta-react/            (React conventions scaffolder)
```

## Further reading

- [Claude Code plugin marketplaces](https://code.claude.com/docs/zh-TW/plugin-marketplaces) — official docs.

## License

MIT — see the `license` field in `.claude-plugin/plugin.json`.
