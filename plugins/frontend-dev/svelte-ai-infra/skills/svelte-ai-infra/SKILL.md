---
name: svelte-ai-infra
description: Bootstrap 或 refresh 一個 repo 的完整 Svelte AI 基礎設施 — 一次性佈署 APM 設定、Svelte MCP server、agents、instructions、skills 與 LSP 設定。當使用者要求「為這個專案啟用 / 初始化 / 設定 Svelte AI 工具」「bootstrap svelte ai infra」「wire up svelte mcp + apm」「補上 sveltejs/ai-tools plugin」「一次裝好 svelte 的 Claude / Copilot 設定」或類似一次性 bootstrap 指令時使用。
---

# svelte-ai-infra

把這個 skill 內附的 assets 安裝到「目前專案根目錄」，建立完整的 Svelte AI 基礎設施。最終會同時為 Claude Code、GitHub Copilot、VS Code 三個 target 準備好 agents、skills、instructions 與 MCP server。

## 不要在這些情境使用

此 skill 是一次性完整 bootstrap，**不要**用於：

- 排查既有 `apm install` 錯誤（請直接看錯誤訊息與 `apm.lock.yaml`）
- 只想單獨設定 `.mcp.json` 或 MCP server
- 只想更新 `svelte-code-writer` / `svelte-core-bestpractices` 其中一個 skill
- 只想針對 Claude 或 Copilot 其中一個 target 配置
- 修改既有 `apm.yml`（直接 `Read + Edit`）
- 想客製非 sveltejs/ai-tools 來源的 Svelte 工具鏈

## 適用情境

- 新開的 Svelte / SvelteKit 專案要一次性接好 AI 工具鏈
- 既有非 Svelte 專案要新增 Svelte AI infra（**先看 Step 0 衝突處理**）
- 想要可重現 (reproducible) 的 Svelte AI infra 部署流程
- 想 refresh 既有專案的 `.apm/` 源檔到最新上游版本

## 前置條件

- 已安裝 `apm` CLI **≥ 0.13.0**（Windows 通常在 `C:\Users\<User>\AppData\Local\Programs\apm\bin\apm.cmd`）。0.12.x 對 `targets: [claude, copilot]` 路由有 bug：上游 plugin 的 agent / skills / instructions 不會部署到 `.claude/`，Step 4 驗收會缺 4 條 `.claude/*` 路徑。版本過舊請先 `apm update`。
- **Bash 環境**（Linux / macOS / Windows Git Bash）— Step 1–2 的腳本是 Bash-only
- Git Bash 環境下 `apm` 需呼叫為 `apm.cmd`；PowerShell 可直接用 `apm`
- 可上網（拉取 sveltejs/ai-tools plugin 與最新源檔；無網路時會 fallback 到內附版本）

## 流程

按順序執行 Step 0 → 4。每步驟末「驗證」是離開該步驟前必須通過的檢查。

### Step 0 — Preflight：檢測既有檔案、決定覆寫策略

`cp -r` 會靜默覆蓋既有檔案，跑 Step 1 之前必須先確認下列檔案 / 目錄是否已存在，並與使用者確認策略：

```bash
for p in apm.yml apm.lock.yaml .apm .lsp.json .mcp.json .claude .github .agents; do
  if [ -e "$p" ]; then echo "EXISTS: $p"; fi
done
```

**判斷規則**：

| 既有檔 | 預設動作 | 例外處理 |
|---|---|---|
| `apm.yml` | **停止並確認** — 用者要 merge 既有 deps 或重置？ | 若使用者明確說「重置」，繼續 |
| `.apm/` | 安全覆寫（內容會在 Step 2 重抓） | — |
| `.lsp.json` | 若內容已含 `svelte`：保留；否則合併 | — |
| `.mcp.json` | **停止並確認** — 不要覆蓋既有 MCP 設定；改由 `apm install` 增量寫入 | — |
| `.claude/` / `.github/` / `.agents/` | 安全保留 — `apm install` 會增量寫入 | — |
| `apm.lock.yaml` | 刪除 — Step 3 會重新產生 | 除非要做 diff 對比 |

**驗證**：所有「停止並確認」項目都得到使用者明確答覆後才進 Step 1。

**非互動環境**：若是 CI / 排程 / 無人值守流程，當任一「停止並確認」條件觸發時，預設動作為 **abort（非 0 exit）並輸出 `[BLOCKED] <檔名> already exists — aborting in non-interactive mode`**，不要靜默繼續。如需強制覆寫，由呼叫端傳入明確的 override flag。

### Step 1 — 複製 assets 到專案根目錄

把 skill 內 `assets/` 全部複製到專案根目錄（包含隱藏檔 `.apm/`、`.lsp.json`）。`scripts/` **不要複製**，由 skill 直接以 `$SKILL_ROOT/scripts/...` 呼叫（見 Step 2）。

```bash
# $SKILL_ROOT 是這個 skill 在當前環境的實際安裝路徑
# Claude Code 預設為 .claude/skills/svelte-ai-infra；若 layout 不同，請改用實際路徑
SKILL_ROOT=".claude/skills/svelte-ai-infra"

# 複製 assets（含隱藏檔）
cp -r "$SKILL_ROOT/assets/." .
```

接著用 **Read + Edit**（不要用 Write，見「已知陷阱」）編輯 `apm.yml`，把三個佔位換成實際值：

```yaml
name: <project-name>          # ← 改為實際名稱
description: <project-description>  # ← 改為實際描述
author: <author>              # ← 改為作者名稱
```

**驗證**：
- `grep -q '<project-name>\|<project-description>\|<author>' apm.yml` 必須失敗（exit 1）— 代表三個佔位都被替換
- `[ -f .apm/agents/svelte-file-editor.agent.md ]`
- `[ -f .apm/instructions/svelte-mcp-tools.instructions.md ]`
- `[ -f .lsp.json ]`

### Step 2 — Refresh `.apm/` 源檔（並規範化 frontmatter）

`assets/.apm/` 內附「建立 skill 當下」的版本作為 fallback。此步驟嘗試從上游拉取最新版本覆蓋；下載失敗時 `fetch-agent.sh` 自動使用第 3 個參數的 fallback。最後用 `ensure-frontmatter.sh` 確保 instructions 檔有正確 frontmatter（idempotent，處理 BOM、覆寫錯誤欄位、避免重複堆疊）。

```bash
SKILL_ROOT=".claude/skills/svelte-ai-infra"

# 1) svelte-file-editor agent
"$SKILL_ROOT/scripts/fetch-agent.sh" \
  https://raw.githubusercontent.com/sveltejs/ai-tools/refs/heads/main/plugins/claude/svelte/agents/svelte-file-editor.md \
  .apm/agents/svelte-file-editor.agent.md \
  "$SKILL_ROOT/assets/.apm/agents/svelte-file-editor.agent.md"

# 2) svelte MCP tools instructions
"$SKILL_ROOT/scripts/fetch-agent.sh" \
  https://raw.githubusercontent.com/sveltejs/ai-tools/refs/heads/main/tools/instructions/AGENTS.md \
  .apm/instructions/svelte-mcp-tools.instructions.md \
  "$SKILL_ROOT/assets/.apm/instructions/svelte-mcp-tools.instructions.md"

# 3) 規範化 instructions frontmatter（無論 fetch 或 fallback 都會通過）
"$SKILL_ROOT/scripts/ensure-frontmatter.sh" \
  .apm/instructions/svelte-mcp-tools.instructions.md \
  "Instructions for using the Svelte MCP server tools for documentation lookup, code analysis, and validation" \
  "**/*.svelte"
```

**驗證**：
- `grep -q 'Svelte MCP server' .apm/agents/svelte-file-editor.agent.md`（agent 內容正確）
- `head -1 .apm/instructions/svelte-mcp-tools.instructions.md` 結果為 `---`
- `grep -q '^applyTo: "\*\*/\*\.svelte"$' .apm/instructions/svelte-mcp-tools.instructions.md`
- `grep -q '^description: Instructions for using the Svelte MCP server' .apm/instructions/svelte-mcp-tools.instructions.md`

### Step 3 — 執行 `apm install`

```bash
# Windows (Git Bash):
apm.cmd install
# PowerShell / macOS / Linux:
apm install
```

**驗證**（不依賴 CLI 輸出字串，因會隨 apm 版本變動）：
- `apm install` exit code = 0
- `[ -f apm.lock.yaml ]` 為 true（已重新產生）
- `grep -q 'sveltejs/ai-tools' apm.lock.yaml`
- `grep -q '^mcp_servers:' apm.lock.yaml` 且其下含 `svelte`

若 exit code ≠ 0，看錯誤訊息修正（最常見：`apm.yml` 殘留無效路徑、網路問題、apm CLI 版本過舊）。

### Step 4 — 驗收最終結構

檢查以下 10 條路徑（lockfile 也應宣告這些）：

```bash
for p in \
  .apm/agents/svelte-file-editor.agent.md \
  .apm/instructions/svelte-mcp-tools.instructions.md \
  .claude/agents/svelte-file-editor.md \
  .claude/skills/svelte-code-writer/SKILL.md \
  .claude/skills/svelte-core-bestpractices/SKILL.md \
  .claude/rules/svelte-mcp-tools.md \
  .github/agents/svelte-file-editor.agent.md \
  .github/instructions/svelte-mcp-tools.instructions.md \
  .agents/skills/svelte-code-writer/SKILL.md \
  .agents/skills/svelte-core-bestpractices/SKILL.md
do
  [ -f "$p" ] && echo "OK   $p" || echo "MISS $p"
done
```

以及 MCP 設定：對應 client 設定（`.mcp.json` 或 client 內部）含 `svelte` server（`stdio` / `npx -y @sveltejs/mcp`）。

任何 `MISS` 路徑：先比對 `apm.lock.yaml` 的 `deployed_files` 段落，若 lockfile 也沒有就重跑 Step 3。

## Output Format

完成後請在最後回報 5 項：

1. **Fetch 結果**：兩個源檔分別是 `fetched`（取得最新）或 `fallback`（使用內附版本）
2. **`apm.yml` 佔位替換**：三個 `<...>` 是否都已替換
3. **`apm install` 結果**：exit code 與是否產生 `apm.lock.yaml`
4. **驗收清單**：Step 4 的 10 條路徑分別 `OK` 或 `MISS`
5. **MCP 狀態**：`svelte` server 是否已配置到 Claude Code / Copilot / VS Code

## 已知陷阱

- **Git Bash 找不到 `apm`**：Windows 上 `apm` 是 `.cmd`，bash 預設 PATH 不解析，請改用 `apm.cmd` 或切到 PowerShell。
- **`apm compile` 不產生輸出**：當 `.claude/`、`.github/`、`.agents/` 目錄都不存在時，apm 不會主動建立；先跑過一次 `apm install` 後再 compile。
- **`--target copilot,claude` 會被解讀為 `claude, vscode`**：apm 把 `copilot` 等同 `vscode`。要分別產出 GitHub Copilot 與 Claude 兩組，分兩次跑 `--target copilot` 與 `--target claude`。
- **依賴未 pin**：`sveltejs/ai-tools` 預設拉 `main`，會漂移。穩定環境請改成 `sveltejs/ai-tools#<sha>` 或 `#<tag>`。
- **lockfile 與檔案不同步**：手動移除 `.claude/`、`.github/` 等輸出目錄後，`apm.lock.yaml` 仍會聲明這些檔存在，但 `apm compile` 不會自動補回，須重跑 `apm install`。
- **修改既有 `apm.yml` 請用 Edit、不要用 Write**：Step 1 替換三個佔位時，因為 `apm.yml` 是剛從 assets 複製過來「已存在」的檔，必須先 `Read` 再 `Edit`；直接 `Write` 會回 `File has not been read yet`。判準：

  | 情境 | 工具 |
  |---|---|
  | 建立新檔 | Write |
  | 修改既有檔少量內容 | Read + Edit |
  | 完全重寫既有檔 | Read + Write |

- **Step 0 略過導致靜默覆寫**：在既有專案直接跑 `cp -r assets/. .` 會覆蓋同名檔。永遠先跑 Step 0 的存在性檢查。
- **frontmatter 不要手動 prepend**：請固定用 `ensure-frontmatter.sh`，避免 BOM、重複堆疊、欄位漂移。

## 內附 assets 清單

```
.claude/skills/svelte-ai-infra/
├── SKILL.md
├── assets/
│   ├── .lsp.json                                       # svelteserver LSP 設定
│   ├── apm.yml                                         # 模板（含佔位）
│   └── .apm/
│       ├── agents/svelte-file-editor.agent.md          # 初始版本 fallback
│       └── instructions/svelte-mcp-tools.instructions.md  # 初始版本 fallback（含 frontmatter）
└── scripts/
    ├── fetch-agent.sh                                  # 通用 fetch（支援 fallback）
    └── ensure-frontmatter.sh                           # 規範化 frontmatter（idempotent）
```
