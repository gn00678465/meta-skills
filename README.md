# meta-skills

A Claude Code plugin marketplace that ships **meta-skills** — skills that scaffold *other* agentic workflows, rather than running them.

## Skills

| Skill | Summary | Docs |
|---|---|---|
| `meta-ralph` | Scaffolds a [ralph](https://ghuntley.com/ralph/) autonomous coding loop (`prd.json` + `.ralph/*`) into a target git repo. Pure scaffolder; never executes the loop. | [docs/meta-ralph.md](docs/meta-ralph.md) · [SKILL.md](skills/meta-ralph/SKILL.md) |

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
│   ├── marketplace.json     (single-plugin marketplace; source: "./")
│   └── plugin.json          (plugin manifest)
└── skills/
    └── meta-ralph/          (see skills/meta-ralph/README.md)
```

## Further reading

- [Claude Code plugin marketplaces](https://code.claude.com/docs/zh-TW/plugin-marketplaces) — official docs.

## License

MIT — see the `license` field in `.claude-plugin/plugin.json`.
