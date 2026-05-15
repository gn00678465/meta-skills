# AGENTS.md Deployment

Owns Step 7 of the workflow: how `<this-skill>/templates/agents/<framework>.md` becomes `<project-root>/AGENTS.md`. Selected by the framework slug chosen in Step 2.

## Framework → template mapping

| Framework slug (from Step 2) | Template file | Behaviour |
|------------------------------|---------------|-----------|
| `nextjs` | `templates/agents/nextjs.md` | Deploy (see contract below) |
| `tanstack-start` | _(none shipped yet)_ | **Skip Step 7 entirely**, log `No AGENTS.md template for tanstack-start yet — skipped` |
| `vite-react` | _(none shipped yet)_ | **Skip Step 7 entirely**, log `No AGENTS.md template for vite-react yet — skipped` |

Skipping is **not an error**. Step 7 returns success and the run continues to Step 8.

Adding a new framework: drop `templates/agents/<slug>.md` with `<!-- BEGIN:<slug>-agent-rules -->` / `<!-- END:<slug>-agent-rules -->` markers, then this table is the only file that needs updating.

## Contract

Source: `<this-skill>/templates/agents/<framework>.md`
Destination: `<project-root>/AGENTS.md`
Run order: **after** Step 4 (`apm install`) — APM may itself have written `AGENTS.md` by the time this step runs (see §APM coexistence below).

```text
template_path = <this-skill>/templates/agents/<framework>.md

# Branch 0 — framework has no template shipped
if not file_exists(template_path):
    report("No AGENTS.md template for <framework> yet — skipped")
    return SUCCESS

template = read(template_path)
dest = <project-root>/AGENTS.md

# Branch 1 — destination does not exist
if not file_exists(dest):
    write(dest, template)
    report("AGENTS.md: created (template <framework>.md)")
    return SUCCESS

existing = read(dest)
markers = ("<!-- BEGIN:<framework>-agent-rules -->",
           "<!-- END:<framework>-agent-rules -->")

# Branch 2 — destination has the managed markers
if both_markers_present(existing, markers):
    merged = replace_between_markers(existing, markers,
                                     block_between_markers(template, markers))
    write(dest, merged)
    report("AGENTS.md: managed section refreshed (markers <framework>-agent-rules)")
    return SUCCESS

# Branch 3 — destination exists but has no markers
if just_emitted_by_apm_copilot(dest):
    # APM's `copilot` target wrote AGENTS.md in Step 4 (this run).
    # Default to append so APM's instructions stay intact.
    write(dest, existing + "\n\n" + template)
    report("AGENTS.md: appended managed block below APM-generated content")
    return SUCCESS

# Branch 4 — destination is pre-existing user content, no markers
choice = prompt_user(
    "AGENTS.md exists without managed markers. [append (default) / overwrite / skip]")
if choice == "overwrite":
    write(dest, template)
    report("AGENTS.md: overwritten (user choice)")
elif choice == "skip":
    report("AGENTS.md: skipped (user kept existing file)")
else:  # append (default)
    write(dest, existing + "\n\n" + template)
    report("AGENTS.md: appended managed block to existing file")
return SUCCESS
```

### Detecting `just_emitted_by_apm_copilot`

The reliable signal is: the `copilot` target is in the chosen target list **and** `AGENTS.md` did not exist before Step 4 ran. Capture that state at the start of Step 4 (e.g. as `agents_md_existed_pre_apm = file_exists(dest)`) and reuse it here. Do not try to fingerprint APM's emitted content — APM may change its template across versions.

If the implementation cannot capture the pre-Step-4 state (e.g. resuming after a crash), fall through to Branch 4 — prompting with `append` as the default still keeps APM's content safe.

## Marker convention

`<!-- BEGIN:<framework-slug>-agent-rules -->` / `<!-- END:<framework-slug>-agent-rules -->`. Adopted from the [official Next.js AI agents guide](https://nextjs.org/docs/app/guides/ai-agents#understanding-agentsmd). Properties this gives us:

- The managed block can live anywhere in the file; merge replaces only the bytes between the markers.
- Anything outside the markers is preserved verbatim — user-authored instructions, APM-emitted content, other tools' managed sections (as long as they use a different `<slug>` marker pair).
- The slug in the marker name MUST equal the framework slug; otherwise Branch 2 falls through to Branch 3/4.

## APM coexistence

`apm install --target copilot` (Step 4) may itself emit an `AGENTS.md` at the project root — see `apm-yml-template.md` → Target selection.

On the **first** run, Step 7 therefore finds an APM-generated `AGENTS.md` without our markers. Branch 3 above handles that case: append the managed block below APM's content. On every subsequent run, the markers exist and Branch 2 runs — only the bytes between markers are rewritten, so APM's content stays intact.

The contract is: **APM owns content outside our managed markers; this skill owns content inside the markers.** Users may freely add instructions outside the markers without worrying about re-runs.

## Failure modes

| Symptom | Action |
|---------|--------|
| Template file missing for chosen framework | Branch 0 — report `skipped`, do not fail. |
| Destination contains only one of the two markers (truncated / hand-edited) | Treat as no-markers (Branch 3/4). Log `AGENTS.md: marker pair incomplete, falling back to append/prompt`. |
| Destination contains markers in reversed order (`END` before `BEGIN`) | Same as above — Branch 3/4 with the same log. |
| Destination contains duplicate `BEGIN:<slug>-agent-rules` blocks | Replace only the **first** block; log `AGENTS.md: duplicate managed blocks detected, refreshed the first occurrence`. The user should clean the rest manually. |
| Future template ships without a marker pair | Refuse to deploy: log `templates/agents/<slug>.md is missing its <slug>-agent-rules markers; skipping`. This protects users from non-idempotent deployments. |
| User picks `skip` in Branch 4 | Leave the file untouched; surface in Step 8 output so the user knows nothing was written. |

## Reporting terms

Step 7 emits exactly one of the following strings to the Step 8 verification report. Keep these in sync with `SKILL.md` Output format and the install-workflow Step 7 entry.

| Branch | Report string |
|--------|---------------|
| 0 | `No AGENTS.md template for <framework> yet — skipped` |
| 1 | `AGENTS.md: created (template <framework>.md)` |
| 2 | `AGENTS.md: managed section refreshed (markers <framework>-agent-rules)` |
| 3 | `AGENTS.md: appended managed block below APM-generated content` |
| 4-append | `AGENTS.md: appended managed block to existing file` |
| 4-overwrite | `AGENTS.md: overwritten (user choice)` |
| 4-skip | `AGENTS.md: skipped (user kept existing file)` |
