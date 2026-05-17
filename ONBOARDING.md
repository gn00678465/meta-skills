# meta-skills — ONBOARDING

A Claude Code plugin marketplace. Each plugin under `plugins/` is a self-contained scaffolder skill. This doc walks through how a non-trivial change actually gets shipped end-to-end, using the **svelte-ai-infra** plugin's plugin-conversion + SKILL.md refactor (PR #7) as the worked example.

For repo layout + install instructions, see [README.md](README.md).

---

## 1. The default workflow

Every multi-step change goes through the same pipeline. Each phase has a dedicated skill from the `superpowers` plugin.

```
brainstorm → write spec → write plan → execute → review → finish branch
   ↓             ↓            ↓          ↓         ↓           ↓
 superpowers:  superpowers:  superpowers: subagent-  final     superpowers:
 brainstorming writing-plans            driven-dev  code-rev finishing-a-
                                                              development-
                                                              branch
```

**Trigger phrases** — what to say to invoke each phase:
- `/brainstorm <topic>` or just describe an ambitious feature → `superpowers:brainstorming`
- After brainstorm approval: skill auto-transitions to `superpowers:writing-plans`
- After plan approval: pick **Subagent-Driven** (recommended) → `superpowers:subagent-driven-development`
- When all tasks done: skill auto-transitions to `superpowers:finishing-a-development-branch`

**Artifacts produced (committed under `docs/superpowers/`):**
- `specs/YYYY-MM-DD-<topic>-design.md` — the validated design with scope (in/out), architecture, acceptance criteria
- `plans/YYYY-MM-DD-<topic>.md` — bite-sized tasks (2–5 min each), each with TDD-style steps, exact commands, exact commit messages

**Why the discipline matters:**
- Spec catches ambiguity *before* code is written. Cheap to revise.
- Plan catches design failure *before* implementation. Each task is independently reviewable.
- Subagent-driven gives **two-stage review per task** (spec compliance → code quality), preventing both under- and over-building.

---

## 2. Subagent-driven execution: how it actually works

For each task in the plan:

1. **Dispatch implementer subagent** (`Agent` tool, `general-purpose`, with a model matched to task complexity — haiku for mechanical, sonnet for judgment).
   - **Never make the subagent read the plan file** — paste the full task text into the prompt.
   - **Always give scene-setting context** — what branch, what prev commits, what comes next.
2. **Spec compliance reviewer** (separate subagent). Verifies the implementer built *exactly* what was asked — nothing missing, nothing extra.
3. **Code quality reviewer** (separate subagent). Apply `write-a-skill` standards as baseline when reviewing skill docs (SKILL.md ≤ 100 lines, `Use when …` triggers, references one level deep, no time-sensitive info in main file).
4. If either reviewer finds issues: dispatch same implementer to fix, re-review.
5. Only mark task complete when both reviews pass.

**Model selection cheat sheet:**
- 1-2 files, complete spec → `haiku`
- Multi-file integration, content extraction → `sonnet`
- Architecture/judgment-heavy review → `sonnet`

After all tasks: **dispatch a whole-branch final reviewer** (sonnet) for holistic check before declaring done.

---

## 3. External cross-check: Copilot CLI review

Internal subagent review can miss spec-level issues (e.g. "this SKILL.md violates progressive disclosure"). When the change is to a skill or doc that has external standards, **add a Copilot CLI review pass**:

```bash
copilot --model gpt-5.4 --allow-all -p '請使用你可用的 /skill-writer 或 /write-a-skill skill 審查 plugins/.../SKILL.md。輸出（用繁體中文）：1. 整體評估 2. 做得好的地方 3. 違反規範或可優化之處（含 line 範圍與理由） 4. 依優先級排序的改善建議（CRITICAL/HIGH/MEDIUM/LOW）'
```

- Copilot has its own `/skill-writer` skill that knows the Agent Skills spec
- Uses a different model family (gpt-5.4) → catches what Claude's review missed
- Triggered the entire SKILL.md refactor in PR #7 (8 findings, 1 CRITICAL)

Use this when shipping anything spec-bound (skills, agent definitions, etc.).

---

## 4. E2E smoke test before claiming done

For any plugin/skill change that deploys files or runs commands, run an **end-to-end smoke test against a fresh project**:

1. Create disposable target project (`/d/tmp/<test-name>` or similar — outside this repo)
2. Run the entire skill workflow (Step 0 → N) as documented
3. Verify every deployment path + side effect
4. Cleanup test project

**svelte-ai-infra smoke test pattern** (used twice in this PR, caught 2 real bugs):

```bash
# Build fresh SvelteKit
rm -rf /d/tmp/svelte-ai-infra-test
cd /d/tmp
npx --yes sv@latest create svelte-ai-infra-test --template minimal --types ts --no-add-ons --no-install

# Run SKILL Step 0–4 against it (SKILL_ROOT overridden to local plugin path)
SKILL_ROOT="/d/Skills/meta-skills/plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra"
cd /d/tmp/svelte-ai-infra-test
cp -r "$SKILL_ROOT/assets/." .
# … Read + Edit 4 placeholders in apm.yml (including __UPSTREAM_SHA__)
# … run fetch-agent.sh twice, ensure-frontmatter.sh once
apm.cmd install
# Verify 10 paths under .apm/, .claude/, .github/, .agents/ all exist
# Verify .mcp.json has svelte server
# Cleanup
rm -rf /d/tmp/svelte-ai-infra-test
```

**Bugs caught this way in PR #7:**
- apm CLI 0.12.x doesn't deploy to `.claude/*` for `targets: [claude, copilot]` (fixed by requiring ≥ 0.13.0)
- apm dep syntax: `repo#SHA/subpath` is parsed as `repo` + branch `SHA/subpath`; correct form is `repo/subpath#SHA`

Neither would have been caught by static review.

---

## 5. Pinning upstream dependencies: the `.upstream-ref` SOT pattern

Several plugins pull files from external repos. **Never track `refs/heads/main`** — that breaks the reproducibility claim and your skill drifts silently.

The pattern (svelte-ai-infra Part 2):

```
skills/<plugin>/
├── .upstream-ref              # single line: 40-char hex SHA
├── assets/
│   └── manifest.yml           # contains __UPSTREAM_SHA__ placeholder
└── references/
    └── upstream-sync.md       # bump procedure
```

**Three readers, one SOT:**
- Deploy step (Step 1): `UPSTREAM_SHA=$(cat $SKILL_ROOT/.upstream-ref)` → Edit `__UPSTREAM_SHA__` → actual SHA in user's deployed manifest
- Fetch step (Step 2): `REF=$(cat $SKILL_ROOT/.upstream-ref)` → fetch URL uses `${REF}` instead of `refs/heads/main`
- Fallback assets in `assets/`: refreshed via bump procedure

**Bump procedure** (`references/upstream-sync.md`): query upstream main HEAD → overwrite `.upstream-ref` → re-fetch fallback assets if changed → **re-run E2E smoke test** → commit `chore(...): bump upstream X to <short-sha>`.

**Why SHA not tag:** verify upstream actually publishes tags for the path you depend on. Many monorepos only tag specific sub-packages (e.g. sveltejs/ai-tools only tags `@sveltejs/opencode`, not `claude/svelte`).

---

## 6. The skill stack used (and not used) in this session

| Skill | When invoked | Purpose |
|---|---|---|
| `superpowers:brainstorming` | Start of any non-trivial change | Scope decisions, propose 2-3 approaches, present design |
| `superpowers:writing-plans` | After spec approval | Bite-sized tasks with exact commands |
| `superpowers:subagent-driven-development` | After plan approval | Dispatch implementer + 2-stage reviewers per task |
| `superpowers:finishing-a-development-branch` | All tasks done | Standard 4-option menu (merge / PR / keep / discard) |
| `cc-copilot-plugin:pull-request` | Open or update GitHub PR | Conventional Commits title, template-based body, UTF-8-safe via `--input` JSON |
| `cc-copilot-plugin:commit-message` | Stage commits in detail | Optional — most commits in this session came from subagent-driven flow directly |
| `~/.claude/skills/write-a-skill` | Authoring/reviewing skills | Spec baseline (`Use when`, ≤ 100 lines, etc.) |
| `copilot --model gpt-5.4 -p '...skill-writer...'` | External cross-check | Different model family, fresh eyes |

---

## 7. Specific gotchas surfaced in this session

**`gh api -f title=@file.txt` does NOT work.** `-f` is raw string; `@file` syntax is only supported by `-F` (typed field). Use `gh api --input payload.json` with `jq -Rsn --rawfile body body.md --arg title "..." '{title: $title, body: $body}'` for safe UTF-8 PR updates. (The `cc-copilot-plugin:commit-message` skill docs are misleading on this point.)

**`gh pr edit --body` is unreliable** due to GitHub Projects (classic) deprecation. Use `gh api -X PATCH "repos/:owner/:repo/pulls/<n>" --input payload.json` instead.

**Fast-forward push to a different branch name is normal git, not destructive.** When `feature/topic-v2` strictly descends from `feature/topic-v1`, you can `git push origin feature/topic-v2:feature/topic-v1` without `--force` — it's just a regular push to update the remote. This is how PR #7 stayed at the same URL while gaining 10 new commits from a "stacked refactor branch."

**SvelteKit non-interactive scaffold:**
```bash
npx --yes sv@latest create <name> --template minimal --types ts --no-add-ons --no-install
```

**Windows `apm` CLI:** `.cmd` file, not `.exe`. Git Bash can't find it without `.cmd` suffix:
- Git Bash: `apm.cmd install`
- PowerShell: `apm install`

**`.upstream-ref` file:** no trailing newline (use `printf '%s' "$SHA" > .upstream-ref`, not `echo`). `$(cat ...)` in bash strips it either way, but other readers may not.

---

## 8. Where to put what

| Artifact | Location | Lifecycle |
|---|---|---|
| Design spec | `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` | Committed before plan; historical reference |
| Implementation plan | `docs/superpowers/plans/YYYY-MM-DD-<topic>.md` | Committed before execution; lives with the change |
| Plugin manifest | `plugins/<category>/<plugin>/.claude-plugin/plugin.json` | Required for marketplace install |
| Marketplace registration | `.claude-plugin/marketplace.json` (root) | Plugins array; one entry per plugin |
| Skill content | `plugins/<...>/skills/<skill-name>/SKILL.md` | Frontmatter `name` must match dir name |
| Skill detail (when SKILL.md > ~100 lines) | `plugins/<...>/skills/<skill-name>/references/*.md` | One level deep, sibling links |
| Plugin-internal scripts | `plugins/<...>/skills/<skill-name>/scripts/` | Called via `$SKILL_ROOT/scripts/...` from SKILL.md |
| Plugin-bundled assets | `plugins/<...>/skills/<skill-name>/assets/` | Copied wholesale to user project |

---

## 9. PR conventions

- **Title:** Conventional Commits — `feat(<plugin>): <imperative summary>`
- **Body:** sections — Summary / 修改內容 / Why / Testing / 風險評估 / 相關連結 / 變更類型
- **Draft first** (`gh pr create --draft`), promote with `gh pr ready <n>` when CI clean
- **One PR per branch**, even if branch covers multiple scopes — link spec/plan docs in body so reviewers can audit decisions
- **commit message style:** zh-TW body OK, English title preferred for international discoverability

---

## 10. Quick start for new contributors

```bash
# 1. Clone + add as local plugin marketplace (for testing)
git clone https://github.com/gn00678465/meta-skills
# In Claude Code session:
/plugin marketplace add ./meta-skills
/plugin install <plugin-name>@meta-skills

# 2. Working on a non-trivial change:
#    a. Just describe the goal in Claude Code → triggers superpowers:brainstorming
#    b. Approve each section as it's presented
#    c. Approve the spec doc that gets committed
#    d. After plan is committed, pick Subagent-Driven execution
#    e. Sit back; review the final whole-branch report
#    f. ship via superpowers:finishing-a-development-branch

# 3. Bump an upstream dependency (svelte-ai-infra et al):
#    Read plugins/<...>/skills/<...>/references/upstream-sync.md
#    Always re-run E2E smoke test before committing
```

For deeper context on this session's case study, read the four committed docs:
- `docs/superpowers/specs/2026-05-17-svelte-ai-infra-plugin-design.md`
- `docs/superpowers/plans/2026-05-17-svelte-ai-infra-plugin.md`
- `docs/superpowers/specs/2026-05-17-svelte-ai-infra-skill-refactor-design.md`
- `docs/superpowers/plans/2026-05-17-svelte-ai-infra-skill-refactor.md`

And PR #7 itself: https://github.com/gn00678465/meta-skills/pull/7
