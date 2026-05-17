---
name: svelte-ai-infra
description: Bootstrap a Svelte/SvelteKit repo's full AI infrastructure end-to-end — APM config, Svelte MCP server, agents, instructions, skills, LSP — for Claude Code, GitHub Copilot, and VS Code. Use when asked to enable / initialize / set up Svelte AI tooling for a project, bootstrap svelte ai infra, or wire up sveltejs/ai-tools plugin in one shot. Do NOT use when only modifying a single skill file, a single target's config, .mcp.json alone, or apm.yml content (use Read+Edit directly).
---

# svelte-ai-infra

把這個 skill 內附的 assets 安裝到「目前專案根目錄」，建立完整的 Svelte AI 基礎設施。最終會同時為 Claude Code、GitHub Copilot、VS Code 三個 target 準備好 agents、skills、instructions 與 MCP server。

上游 `sveltejs/ai-tools` plugin pin 在 [`.upstream-ref`](.upstream-ref) 指定的 commit SHA，確保部署可重現。要升級上游版本見 [references/upstream-sync.md](references/upstream-sync.md)。

## 適用 / 不適用

**適用：**
- 新開的 Svelte / SvelteKit 專案要一次性接好 AI 工具鏈
- 既有非 Svelte 專案要新增 Svelte AI infra（先看 Step 0 衝突處理）
- 想 refresh 既有專案的 `.apm/` 源檔到 pinned 上游版本

**不適用：**
- 排查既有 `apm install` 錯誤（直接看錯誤訊息與 `apm.lock.yaml`）
- 只想單獨設定 `.mcp.json` 或 MCP server
- 只想更新單一 skill（`svelte-code-writer` / `svelte-core-bestpractices`）
- 只想針對 Claude 或 Copilot 其中一個 target 配置
- 修改既有 `apm.yml`（直接 `Read + Edit`）
- 想客製非 sveltejs/ai-tools 來源的 Svelte 工具鏈

## 前置條件

- `apm` CLI **≥ 0.13.0**（0.12.x 對 `targets: [claude, copilot]` 路由有 bug — 詳見 [references/version-compat.md](references/version-compat.md)）
- Bash 環境（Linux / macOS / Windows Git Bash）
- 可上網（無網時 fallback 到內附版本）

## 流程速覽

按順序執行 Step 0 → 4。每步驟末「驗證」必須通過才進下一步。完整指令、placeholder 清單與驗收條件見 [references/workflow.md](references/workflow.md)。

| Step | 動作 | 詳細 |
|---|---|---|
| 0 | Preflight 衝突檢測 | [workflow.md § Step 0](references/workflow.md#step-0--preflight檢測既有檔案決定覆寫策略) |
| 1 | 複製 assets + 替換 4 個 placeholder | [workflow.md § Step 1](references/workflow.md#step-1--複製-assets-到專案根目錄--替換-4-個-placeholder) |
| 2 | Refresh `.apm/` 源檔（pinned SHA）+ frontmatter | [workflow.md § Step 2](references/workflow.md#step-2--refresh-apm-源檔pinned-sha-規範化-frontmatter) |
| 3 | `apm install` | [workflow.md § Step 3](references/workflow.md#step-3--執行-apm-install) |
| 4 | 驗收 10 條路徑 + MCP 設定 | [workflow.md § Step 4](references/workflow.md#step-4--驗收最終結構) |

## SKILL_ROOT 解析

各 step 引用 `$SKILL_ROOT` — skill 在當前環境的實際安裝路徑。**不要硬編** `.claude/skills/svelte-ai-infra`，因為這份 skill 同時可能透過 plugin marketplace 安裝、或在開發中從本 repo 直接執行。請依當前環境暴露的實際路徑為準：

- **Claude Code 安裝**：通常在 `$CLAUDE_PLUGIN_ROOT/skills/svelte-ai-infra`，若有此環境變數請優先使用
- **本 repo 開發**：`plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra`
- **fallback**：先試 `.claude/skills/svelte-ai-infra`，若不存在就由 caller 顯式傳入

Step 1–2 開頭：
```bash
SKILL_ROOT="<實際安裝路徑>"
```

## Output Format

完成後請在最後回報 5 項：

1. **Fetch 結果**：兩個源檔分別是 `fetched`（取得 pinned SHA 版本）或 `fallback`（使用內附版本）
2. **`apm.yml` 佔位替換**：4 個（3 個 `<...>` + 1 個 `__UPSTREAM_SHA__`）是否都已替換
3. **`apm install` 結果**：exit code 與是否產生 `apm.lock.yaml`
4. **驗收清單**：Step 4 的 10 條路徑分別 `OK` 或 `MISS`
5. **MCP 狀態**：`svelte` server 是否已配置到 Claude Code / Copilot / VS Code

## 升級上游 plugin 版本

詳見 [references/upstream-sync.md](references/upstream-sync.md)。

## 疑難排解 / 已知陷阱

詳見 [references/troubleshooting.md](references/troubleshooting.md)。
