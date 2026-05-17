# svelte-ai-infra SKILL.md refactor — design

- **Date**: 2026-05-17
- **Branch**: `feature/svelte-ai-infra-skill-refactor`
- **Builds on**: PR #7 (`feature/svelte-ai-infra` — plugin packaging)
- **Driven by**: Copilot CLI review (gpt-5.4 + skill-writer skill) on the current SKILL.md

## Context

PR #7 packaged `svelte-ai-infra` as an installable plugin (manifest + marketplace registration). It deliberately left `SKILL.md` content untouched. A subsequent Copilot review of `SKILL.md` (207 lines) surfaced 8 findings ranging CRITICAL → LOW; the CRITICAL one is a real behavioral inconsistency, not a doc issue:

- Line 25 claims this is a "reproducible (reproducible) Svelte AI infra deployment flow"
- Lines 100/106 fetch upstream assets from `refs/heads/main` (always latest)
- Line 180 itself admits "依賴未 pin … 會漂移"

The other HIGH findings call out missing `Use when ...` description trigger, lack of progressive disclosure (file is 207 lines / 7,904 chars — past the suggested split threshold), and hardcoded `.claude/skills/...` `SKILL_ROOT` assumption.

## Scope

### In scope

| # | 變更 | 動機 | Copilot finding |
|---|---|---|---|
| 1 | Pin upstream `sveltejs/ai-tools` to commit SHA via `.upstream-ref` SOT | 兌現 reproducibility 承諾 | CRITICAL |
| 2 | Rewrite SKILL.md `description` with explicit `Use when ...` + `Do NOT use when ...` | Trigger 精準度 / anti-trigger 前移 | HIGH + MEDIUM |
| 3 | Split SKILL.md into router (`≤ 100` lines) + 4 references files | Progressive disclosure | HIGH |
| 4 | Remove hardcoded `.claude/skills/...` `SKILL_ROOT` assumption from SKILL.md, give portable resolution guidance | Plugin lifestyle 中立性 | HIGH |
| 5 | Move time-sensitive info (apm version gates, `copilot=vscode` mapping, etc.) to `references/version-compat.md` | 維運可控 | MEDIUM |
| 6 | Move 已知陷阱 + bundled assets 清單 to references | 主檔不必每次必讀 | LOW |
| 7 | Add `references/upstream-sync.md` with bump procedure | 配合 #1，SHA 維運可重現 | (derived from #1) |

### Out of scope

- 自動 bump GitHub Action（已在 brainstorming 範圍決策時排除）
- `scripts/fetch-agent.sh` / `scripts/ensure-frontmatter.sh` 介面變更（純參數值改動，腳本本身不動）
- 上游 `sveltejs/ai-tools` repo 本身任何變更

## 目錄結構（變更後）

```
plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/
├── SKILL.md                ← 重寫為 router（≤ 100 行）
├── .upstream-ref           ← NEW: 單行 full SHA（SOT）
├── assets/                 ← 結構不變
│   ├── .lsp.json
│   ├── apm.yml             ← 多 1 個 placeholder：__UPSTREAM_SHA__
│   └── .apm/
│       ├── agents/svelte-file-editor.agent.md
│       └── instructions/svelte-mcp-tools.instructions.md
├── scripts/                ← 不動
│   ├── ensure-frontmatter.sh
│   └── fetch-agent.sh
└── references/             ← NEW 目錄
    ├── workflow.md         ← 完整 Step 0–4 步驟細節
    ├── version-compat.md   ← apm CLI 版本、host/tool 限制
    ├── troubleshooting.md  ← 已知陷阱、failure 處置
    └── upstream-sync.md    ← bump .upstream-ref 流程
```

**Note**：`.upstream-ref` 放在 skill root（不在 `assets/`），所以 `cp -r assets/.` 不會把它帶到 user 專案 — 它純粹是 skill 內部 metadata。

## CRITICAL：reproducibility 解法

採 **single source of truth + 三處讀** 模式：

### `.upstream-ref`

```
5b4d3aa68a7df8285de4d08fb3d0c4a0505fc449
```

（單行、無前後空白；初始值 = 2026-05-15 main HEAD，剛通過 E2E smoke test 的版本）

### `assets/apm.yml`（modified）

```yaml
dependencies:
  apm:
  - sveltejs/ai-tools/plugins/claude/svelte#__UPSTREAM_SHA__
```

Step 1 placeholder 替換從 3 個變 4 個，多一條：
```bash
# Read .upstream-ref + Edit apm.yml: __UPSTREAM_SHA__ → <SHA>
```

### SKILL.md / references/workflow.md Step 2

URL 從 `refs/heads/main` 改為讀 `.upstream-ref`：

```bash
REF=$(cat "$SKILL_ROOT/.upstream-ref")
"$SKILL_ROOT/scripts/fetch-agent.sh" \
  "https://raw.githubusercontent.com/sveltejs/ai-tools/${REF}/plugins/claude/svelte/agents/svelte-file-editor.md" \
  .apm/agents/svelte-file-editor.agent.md \
  "$SKILL_ROOT/assets/.apm/agents/svelte-file-editor.agent.md"
```

### 為什麼 SHA 而非 tag

上游 `sveltejs/ai-tools` repo 只對 `@sveltejs/opencode` 子套件出 git tag（已用 `gh api repos/sveltejs/ai-tools/tags` 確認），claude/svelte plugin 沒有對應 release tag — 只能 pin commit SHA。

## SKILL.md 新骨架（≤ 100 行）

```markdown
---
name: svelte-ai-infra
description: Bootstrap a Svelte/SvelteKit repo's full AI infrastructure end-to-end
  — APM config, Svelte MCP server, agents, instructions, skills, LSP. Use when
  asked to enable / initialize / set up Svelte AI tooling for a project,
  bootstrap svelte ai infra, or wire up sveltejs/ai-tools plugin in one shot.
  Do NOT use when only modifying one of: a single skill file, .mcp.json, a
  single target's config, or apm.yml content (use Read+Edit directly).
---

# svelte-ai-infra

[簡介一段]

## 適用 / 不適用 情境
[3-5 bullet]

## 前置條件
- `apm` CLI ≥ 0.13.0（理由詳見 references/version-compat.md）
- Bash 環境
- 可上網（offline 時 fallback）

## 流程速覽

| Step | 動作 | 詳細 |
|---|---|---|
| 0 | Preflight 衝突檢測 | references/workflow.md#step-0 |
| 1 | 複製 assets + 替換 4 個 placeholder | references/workflow.md#step-1 |
| 2 | Refresh `.apm/` 源檔（pinned SHA）+ frontmatter | references/workflow.md#step-2 |
| 3 | `apm install` | references/workflow.md#step-3 |
| 4 | 驗收 10 條路徑 + MCP | references/workflow.md#step-4 |

## SKILL_ROOT 解析
[一段：不要硬編 .claude/skills/...，給可攜路徑指引]

## Output Format
[Step 4 結束後回報 5 項]

## 升級上游 plugin 版本
詳見 references/upstream-sync.md。

## 疑難排解
詳見 references/troubleshooting.md。
```

## references/ 內容分配

### workflow.md（最大宗）
完整 Step 0–4 步驟，**從現 SKILL.md line 35–163 搬過來**，套用 CRITICAL 變更：
- Step 1 placeholder 替換多 1 條（`__UPSTREAM_SHA__`）
- Step 2 fetch URL 改用 `REF=$(cat $SKILL_ROOT/.upstream-ref)`

### version-compat.md
| 主題 | 來源 |
|---|---|
| `apm` CLI ≥ 0.13.0 理由 | 現 line 30 |
| Bash-only / Git Bash `apm.cmd` | 現 line 31-32 |
| `copilot=vscode` 映射 | 現 line 179 |
| `apm compile` 不產輸出 條件 | 現 line 178 |
| host/tool 限制（Read+Edit vs Write） | 現 line 182-188 |
| lockfile 與檔案不同步 處置 | 現 line 181 |

### troubleshooting.md
| 主題 | 來源 |
|---|---|
| Step 0 略過導致靜默覆寫 | 現 line 190 |
| frontmatter 不要手動 prepend | 現 line 191 |
| 各 Step 驗證失敗時的 fallback | 從現 Step 1-4 抽出 |

### upstream-sync.md（NEW）
- SOT 說明：`.upstream-ref`
- Bump 流程（5 步）：查 main HEAD → 改 `.upstream-ref` → 同步 fallback assets → 重跑 E2E smoke test → commit `chore(svelte-ai-infra): bump upstream sveltejs/ai-tools to <short-sha>`
- 為什麼不 pin tag（上游無 tag）

## 驗收條件

實作完成後須滿足：

1. SKILL.md 行數 ≤ 100（不含 frontmatter `---` 開閉行）
2. `.upstream-ref` 存在、單行、為 40-char hex（full SHA）
3. `assets/apm.yml` 包含 `__UPSTREAM_SHA__` 字串（部署前的 skill 樹內）
4. `references/` 下 4 個 .md 檔皆存在且非空
5. `grep -rn 'refs/heads/main' SKILL.md references/ 2>/dev/null` 無結果（沒有殘留漂移路徑）
6. **E2E smoke test**：建 fresh SvelteKit 跑 SKILL Step 0–4，10/10 路徑 OK + MCP 配 svelte server
7. `apm install` 輸出含 `+ sveltejs/ai-tools @5b4d3aa6`（pinned SHA 生效，不再有「unpinned」warning）
8. 部署到 user 專案的 `apm.yml` 內**不含** `__UPSTREAM_SHA__` 字面（Step 1 替換生效）

## Out-of-scope 處置記錄

- **自動 bump CI**：先用 manual bump（references/upstream-sync.md），需要時再加。
- **scripts/ 改動**：fetch-agent.sh 與 ensure-frontmatter.sh 介面（命令列參數）不動，呼叫端 URL 改變即可達到 pin 效果。
- **PR #7 互動**：本 branch 從 `feature/svelte-ai-infra` 分出，已含 PR #7 全部 commits（包含 apm 版本要求那一行）。PR #7 merge 後本 branch 需要 rebase main；若先 merge 本 branch，PR #7 內容已被涵蓋。
