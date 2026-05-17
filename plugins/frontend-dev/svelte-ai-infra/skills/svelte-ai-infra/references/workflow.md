# svelte-ai-infra workflow detail (Step 0 → 4)

完整 bootstrap 流程。每步驟末「驗證」是離開該步驟前必須通過的檢查。

設環境變數 `SKILL_ROOT` 為這個 skill 在當前環境的實際安裝路徑（見主 SKILL.md「SKILL_ROOT 解析」段）。

## Step 0 — Preflight：檢測既有檔案、決定覆寫策略

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

## Step 1 — 複製 assets 到專案根目錄 + 替換 4 個 placeholder

把 skill 內 `assets/` 全部複製到專案根目錄（包含隱藏檔 `.apm/`、`.lsp.json`）。`scripts/` 與 `.upstream-ref` **不要複製**，由 skill 直接以 `$SKILL_ROOT/...` 引用。

```bash
# 複製 assets（含隱藏檔）
cp -r "$SKILL_ROOT/assets/." .
```

接著用 **Read + Edit**（不要用 Write，見 [troubleshooting.md](troubleshooting.md)）編輯 `apm.yml`，把 **4 個** placeholder 換成實際值：

```yaml
name: <project-name>          # ← 改為實際名稱
description: <project-description>  # ← 改為實際描述
author: <author>              # ← 改為作者名稱

# 並把 dependencies 內的 __UPSTREAM_SHA__ 換成 .upstream-ref 內容：
dependencies:
  apm:
  - sveltejs/ai-tools#__UPSTREAM_SHA__/plugins/claude/svelte
                          ↑ 這個 placeholder 也要替換
```

讀取 SHA：
```bash
UPSTREAM_SHA=$(cat "$SKILL_ROOT/.upstream-ref")
```

然後 Read + Edit 把 `apm.yml` 內 `__UPSTREAM_SHA__` 字面 取代為 `$UPSTREAM_SHA` 的值。

**驗證**：
- `grep -q '<project-name>\|<project-description>\|<author>\|__UPSTREAM_SHA__' apm.yml` 必須失敗（exit 1）— 代表 4 個佔位都被替換
- `[ -f .apm/agents/svelte-file-editor.agent.md ]`
- `[ -f .apm/instructions/svelte-mcp-tools.instructions.md ]`
- `[ -f .lsp.json ]`

## Step 2 — Refresh `.apm/` 源檔（pinned SHA）+ 規範化 frontmatter

`assets/.apm/` 內附「pin 上游 SHA 當時」的版本作為 fallback。此步驟從 `.upstream-ref` 指定的 commit 拉取對應版本覆蓋；下載失敗時 `fetch-agent.sh` 自動使用第 3 個參數的 fallback。最後用 `ensure-frontmatter.sh` 確保 instructions 檔有正確 frontmatter（idempotent，處理 BOM、覆寫錯誤欄位、避免重複堆疊）。

```bash
REF=$(cat "$SKILL_ROOT/.upstream-ref")

# 1) svelte-file-editor agent
"$SKILL_ROOT/scripts/fetch-agent.sh" \
  "https://raw.githubusercontent.com/sveltejs/ai-tools/${REF}/plugins/claude/svelte/agents/svelte-file-editor.md" \
  .apm/agents/svelte-file-editor.agent.md \
  "$SKILL_ROOT/assets/.apm/agents/svelte-file-editor.agent.md"

# 2) svelte MCP tools instructions
"$SKILL_ROOT/scripts/fetch-agent.sh" \
  "https://raw.githubusercontent.com/sveltejs/ai-tools/${REF}/tools/instructions/AGENTS.md" \
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

## Step 3 — 執行 `apm install`

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
- `apm install` 輸出 **不應**含 `unpinned` warning（因為已 pin SHA）

若 exit code ≠ 0，看錯誤訊息修正（最常見：`apm.yml` 殘留 placeholder、網路問題、apm CLI 版本過舊。詳見 [version-compat.md](version-compat.md)）。

## Step 4 — 驗收最終結構

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

任何 `MISS` 路徑：先比對 `apm.lock.yaml` 的 `deployed_files` 段落，若 lockfile 也沒有就重跑 Step 3。詳細 fallback 見 [troubleshooting.md](troubleshooting.md)。
