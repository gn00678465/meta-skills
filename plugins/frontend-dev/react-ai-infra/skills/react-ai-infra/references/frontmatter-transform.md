# Frontmatter Transform: paths → applyTo

Bundled rules in `rules/<name>.md` use a `paths:` array that Claude Code keeps verbatim. Copilot's `.github/instructions/<name>.instructions.md` uses `applyTo:` (single comma-separated string). This file specifies how to convert one to the other.

## Source format (Claude / react-ai-infra)

```yaml
---
paths:
  - "src/**/*.{tsx,jsx}"
  - "app/**/*.tsx"
---
```

- YAML list of glob patterns.
- Brace expansion (`{a,b}`) is allowed.
- Comma is a literal character within strings (do **not** treat as separator).

## Target format (Copilot)

```yaml
---
applyTo: "src/**/*.tsx,src/**/*.jsx,app/**/*.tsx"
---
```

- Single string.
- Multiple globs separated by `,`.
- No brace expansion — each branch must appear as its own glob.

## Algorithm

```
function transform(source_frontmatter):
    paths = source_frontmatter.get("paths", [])
    expanded = []
    for p in paths:
        expanded.extend(brace_expand(p))
    return {"applyTo": ",".join(expanded)}
```

### brace_expand(pattern)

Recursively expand the leftmost top-level `{...}`:

| Input | Output |
|-------|--------|
| `src/**/*.tsx` | `["src/**/*.tsx"]` |
| `src/**/*.{tsx,jsx}` | `["src/**/*.tsx", "src/**/*.jsx"]` |
| `src/{a,b}/{c,d}.ts` | `["src/a/c.ts", "src/a/d.ts", "src/b/c.ts", "src/b/d.ts"]` |
| `src/no-braces/file.ts` | `["src/no-braces/file.ts"]` |

Pseudocode:

```
function brace_expand(s):
    i = find_top_level_brace(s)
    if i == -1: return [s]
    prefix, branches, suffix = split_brace(s, i)
    out = []
    for branch in branches:
        for tail in brace_expand(prefix + branch + suffix):
            out.append(tail)
    return out
```

`find_top_level_brace` ignores braces escaped with `\{` or inside other braces. If braces are unbalanced, return `[s]` (treat as literal).

## Worked example

Source `rules/react-components.md`:

```yaml
---
paths:
  - "src/**/*.{tsx,jsx}"
---

# React Components Rules
...
```

Output `.github/instructions/react-components.instructions.md`:

```yaml
---
applyTo: "src/**/*.tsx,src/**/*.jsx"
---

# React Components Rules
...
```

Body content is copied unchanged.

## Edge cases

| Case | Handling |
|------|----------|
| `paths:` missing or empty | Emit `applyTo: "**"` and log a warning. The Copilot output MUST always contain an `applyTo:` field. |
| `paths:` contains a non-string entry | Skip that entry, log a warning. If the resulting list is empty, fall back to `applyTo: "**"`. |
| `paths:` has unbalanced braces or otherwise unparseable globs | Pass the literal pattern through `applyTo:` (do not crash). If every entry fails, fall back to `applyTo: "**"` with a warning. |
| Pattern contains literal commas | Quote the entire `applyTo:` value; comma is the only separator |
| Pattern contains nested braces | Recurse on each branch |
| Pattern is `**` | Pass through verbatim |
| Source frontmatter has other keys (e.g. `description:`) | Preserve them in the Copilot output unchanged; `applyTo:` replaces only `paths:` |

## What NOT to transform

- Do **not** modify the markdown body. Headers, code blocks, links — all copied byte-for-byte.
- Do **not** rewrite skill cross-references (e.g. `/no-use-effect`). Both ecosystems resolve them locally.
- Do **not** convert `paths:` to anything other than `applyTo:`. Other Copilot frontmatter fields (`description:`, `mode:`) are left to user authorship.
