# svelte-ai-infra SKILL.md refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 svelte-ai-infra 的 SKILL.md（207 行 monolith）重構為 router (≤ 100 行) + 4 個 references 檔，並把上游 `sveltejs/ai-tools` 從 `refs/heads/main` 改為 pin 到 commit SHA（透過 `.upstream-ref` SOT），兌現 reproducibility 承諾並提升 progressive disclosure。

**Architecture:** 三層分工：(1) SOT 層 = `.upstream-ref`（單行 full SHA）+ `assets/apm.yml` 內 `__UPSTREAM_SHA__` placeholder；(2) router 層 = 新 SKILL.md（觸發決策、總覽流程、連結 references）；(3) detail 層 = `references/` 下 4 個檔（workflow / version-compat / troubleshooting / upstream-sync）。所有變更皆為 declarative 設定 + 內容重新分配，不改 `scripts/` 介面。

**Tech Stack:** Markdown, YAML (apm.yml), Bash (smoke test runner), `gh` CLI (查上游 SHA), Node.js (JSON 驗證), `apm` CLI ≥ 0.13.0.

**Spec reference:** `docs/superpowers/specs/2026-05-17-svelte-ai-infra-skill-refactor-design.md`

**Branch:** `feature/svelte-ai-infra-skill-refactor`（已含 PR #7 全部 commits）

**Skill root path（所有 task 內以 `$SR` 簡寫）：**
```
plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra
```

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `$SR/.upstream-ref` | 單行 full SHA（pin 上游） | **Create** |
| `$SR/assets/apm.yml` | 加 `__UPSTREAM_SHA__` placeholder 取代 `sveltejs/ai-tools` 字串 | **Modify** |
| `$SR/references/workflow.md` | 完整 Step 0–4 細節（從 SKILL.md 搬，套用 SHA 變更） | **Create** |
| `$SR/references/version-compat.md` | apm 版本、host/tool 限制、`copilot=vscode` 等 compatibility 資訊 | **Create** |
| `$SR/references/troubleshooting.md` | 已知陷阱 + 各 Step 失敗 fallback | **Create** |
| `$SR/references/upstream-sync.md` | bump `.upstream-ref` 流程 | **Create** |
| `$SR/SKILL.md` | 重寫為 router（≤ 100 行） | **Rewrite** |

---

## Task 1: Bootstrap SHA pin infrastructure

建立 `.upstream-ref` SOT，並在 `assets/apm.yml` 加入 `__UPSTREAM_SHA__` placeholder。這是後續所有 task 的依賴 — references/workflow.md 會引用這兩個檔。

**Files:**
- Create: `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/.upstream-ref`
- Modify: `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/assets/apm.yml`

- [ ] **Step 1: 查上游 main HEAD 完整 SHA**

Run:
```bash
gh api repos/sveltejs/ai-tools/commits/main --jq '.sha'
```

Expected: 一行 40-char hex（如 `5b4d3aa68a7df8285de4d08fb3d0c4a0505fc449`）。記下這個值，下面稱為 `<SHA>`。

若 `gh api` 失敗：嘗試 `curl -sSL https://api.github.com/repos/sveltejs/ai-tools/commits/main | grep -m1 '"sha"' | head -1` 取出 sha 欄位。

- [ ] **Step 2: 建立 `.upstream-ref`**

寫入單行內容（無前後空白、無 trailing newline 也可）：
```
<SHA>
```

例：
```
5b4d3aa68a7df8285de4d08fb3d0c4a0505fc449
```

- [ ] **Step 3: 驗證 `.upstream-ref` 格式**

Run:
```bash
node -e "const s=require('fs').readFileSync('plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/.upstream-ref','utf8').trim(); console.log(/^[0-9a-f]{40}\$/.test(s) ? 'PASS_SHA_FORMAT' : 'FAIL: not 40-char hex, got: '+s.slice(0,20));"
```

Expected: `PASS_SHA_FORMAT`

- [ ] **Step 4: 讀目前 assets/apm.yml**

Use the Read tool on `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/assets/apm.yml`. Current content includes line `  - sveltejs/ai-tools/plugins/claude/svelte` under `dependencies.apm`.

- [ ] **Step 5: Edit `assets/apm.yml` — 把 dep 字串改成含 placeholder**

Use Edit tool. Change:
```yaml
  apm:
  - sveltejs/ai-tools/plugins/claude/svelte
```
to:
```yaml
  apm:
  - sveltejs/ai-tools/plugins/claude/svelte#__UPSTREAM_SHA__
```

- [ ] **Step 6: 驗證 apm.yml 仍為合法 YAML 且含 placeholder**

Run:
```bash
node -e "
const yaml=require('fs').readFileSync('plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/assets/apm.yml','utf8');
if(!yaml.includes('__UPSTREAM_SHA__')) {console.log('FAIL: placeholder missing'); process.exit(1);}
if(!yaml.includes('sveltejs/ai-tools/plugins/claude/svelte#__UPSTREAM_SHA__')) {console.log('FAIL: dep string wrong'); process.exit(2);}
console.log('PASS');
"
```

Expected: `PASS`

YAML 合法性（apm 不一定可在 CI 上裝，所以用 yaml lint 替代）：
```bash
node -e "
try {
  const yaml = require('yaml');
  yaml.parse(require('fs').readFileSync('plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/assets/apm.yml','utf8'));
  console.log('YAML_OK');
} catch(e) {
  console.log('YAML_FAIL:', e.message);
  process.exit(1);
}
" 2>&1 || echo "(yaml module may not be installed — fallback: visual inspect)"
```

若 `yaml` 模組不存在，跳過 YAML lint，改用 visual inspect：`cat assets/apm.yml` 確認沒漏掉 colon、indent 維持原樣。

- [ ] **Step 7: Commit**

Run:
```bash
git add plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/.upstream-ref \
        plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/assets/apm.yml
git commit -m "feat(svelte-ai-infra): pin upstream sveltejs/ai-tools via .upstream-ref SOT

Adds .upstream-ref (single line full SHA) as single source of truth for
upstream pinning. apm.yml template now uses __UPSTREAM_SHA__ placeholder
that Step 1 will substitute from .upstream-ref content at deploy time.
Replaces previous 'follow main HEAD' behavior that contradicted the
reproducibility claim."
```

Expected: commit 成功。

---

## Task 2: Create `references/workflow.md`

提取 Step 0–4 細節到 references/workflow.md，**並同步套用兩個 SHA 變更**：
- Step 1 多一條 placeholder 替換 (`__UPSTREAM_SHA__`)
- Step 2 fetch URL 從 `refs/heads/main` 改用 `REF=$(cat .upstream-ref)`

**Files:**
- Create: `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/workflow.md`

- [ ] **Step 1: 建立 references/ 目錄與 workflow.md**

Write the following exact content to `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/workflow.md`:

````markdown
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
  - sveltejs/ai-tools/plugins/claude/svelte#__UPSTREAM_SHA__
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
````

- [ ] **Step 2: 驗證內容**

Run:
```bash
WF=plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/workflow.md
[ -f "$WF" ] && echo "EXISTS" || { echo "FAIL: file not created"; exit 1; }
grep -q '__UPSTREAM_SHA__' "$WF" && echo "PASS: placeholder mentioned" || echo "FAIL: placeholder reference missing"
grep -q 'REF=\$(cat "\$SKILL_ROOT/.upstream-ref")' "$WF" && echo "PASS: REF assignment present" || echo "FAIL: REF assignment missing"
grep -q 'refs/heads/main' "$WF" && echo "FAIL: drift URL still present" || echo "PASS: no drift URL"
wc -l "$WF"
```

Expected:
```
EXISTS
PASS: placeholder mentioned
PASS: REF assignment present
PASS: no drift URL
<line count, expect 90-110>
```

- [ ] **Step 3: Commit**

Run:
```bash
git add plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/workflow.md
git commit -m "docs(svelte-ai-infra): extract Step 0-4 detail into references/workflow.md

Moves verbose step procedure out of SKILL.md and inlines the SHA pin
changes: Step 1 now substitutes __UPSTREAM_SHA__ in addition to the 3
project placeholders, Step 2 fetch URLs read REF from .upstream-ref
instead of refs/heads/main."
```

Expected: commit 成功。

---

## Task 3: Create `references/version-compat.md`

提取與版本/host/tool 限制相關的 compatibility 資訊。

**Files:**
- Create: `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/version-compat.md`

- [ ] **Step 1: Write file**

Write the following exact content to `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/version-compat.md`:

````markdown
# Version & host compatibility

執行 svelte-ai-infra 流程前需要符合下列環境要求。版本門檻是這份 skill 經 E2E smoke test 驗證過的最低值；過舊版本可能在不同 step 失敗。

## apm CLI ≥ 0.13.0（必要）

**為什麼：** apm 0.12.x 對 `apm.yml` 內 `targets: [claude, copilot]` 的路由有 bug — 上游 plugin 的 agent / skills / instructions **不會**部署到 `.claude/`，Step 4 驗收會缺 4 條 `.claude/*` 路徑（`.claude/agents/svelte-file-editor.md`、`.claude/skills/svelte-code-writer/SKILL.md`、`.claude/skills/svelte-core-bestpractices/SKILL.md`、`.claude/rules/svelte-mcp-tools.md`）。0.13.0 已修。

**升級：** `apm update`（從現有 apm 自動拉新版）。Windows 預設安裝路徑通常在 `C:\Users\<User>\AppData\Local\Programs\apm\bin\apm.cmd`。

## Bash 環境（必要）

Step 1–2 的腳本（`fetch-agent.sh`、`ensure-frontmatter.sh`）是 Bash-only。支援：
- Linux / macOS 原生 shell
- Windows Git Bash / WSL

PowerShell 直接跑 `.sh` 腳本不會 work — Windows 上請開 Git Bash 跑這兩 step，或在 PowerShell 用 `bash scripts/...` 顯式呼叫。

## Git Bash 找不到 `apm`（Windows 限定）

Windows 上 `apm` 安裝後是 `.cmd` 檔，bash 預設的 PATH 解析不會自動補副檔名，會回 `command not found`。

**處置：**
- 在 Git Bash 用 `apm.cmd install`（顯式帶副檔名）
- 或切到 PowerShell / cmd 跑 `apm install`

## `--target copilot,claude` 解讀為 `claude, vscode`

舊版 apm 把 `copilot` 等同 `vscode`（CLI flag 用 `--target` 時觸發）。本 skill 透過 `apm.yml` 內 `targets:` 欄位設定，不走 `--target` flag，所以這個陷阱**不影響**本流程；但若使用者手動補 `apm install --target copilot,claude`，需要分兩次跑：

```bash
apm install --target copilot
apm install --target claude
```

## `apm compile` 不產生輸出 的條件

當專案內 `.claude/`、`.github/`、`.agents/` 目錄都不存在時，`apm compile` 不會主動建立。先跑過一次 `apm install`（會建立目錄）後再 compile 才會有輸出。

## host/tool 限制：修改既有檔請用 Read + Edit

Step 1 的 4 個 placeholder 替換，因為 `apm.yml` 是剛從 assets 複製過來「已存在」的檔，必須先 `Read` 再 `Edit`；直接 `Write` 會回 `File has not been read yet`。

| 情境 | 工具 |
|---|---|
| 建立新檔 | Write |
| 修改既有檔少量內容 | Read + Edit |
| 完全重寫既有檔 | Read + Write |

## lockfile 與檔案不同步處置

手動移除 `.claude/`、`.github/` 等輸出目錄後，`apm.lock.yaml` 仍會聲明這些檔存在，但 `apm compile` 不會自動補回，必須重跑 `apm install` 觸發部署。
````

- [ ] **Step 2: 驗證**

Run:
```bash
VC=plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/version-compat.md
[ -f "$VC" ] && echo "EXISTS" || { echo "FAIL"; exit 1; }
grep -q '0.13.0' "$VC" && echo "PASS: apm version" || echo "FAIL: missing apm version note"
grep -q 'Read + Edit' "$VC" && echo "PASS: tool guide present" || echo "FAIL: missing tool guide"
grep -q 'Git Bash' "$VC" && echo "PASS: Git Bash note present" || echo "FAIL: missing Git Bash note"
wc -l "$VC"
```

Expected: 3 行 PASS + line count (expect 40-60)。

- [ ] **Step 3: Commit**

Run:
```bash
git add plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/version-compat.md
git commit -m "docs(svelte-ai-infra): extract version/host/tool compatibility to references"
```

---

## Task 4: Create `references/troubleshooting.md`

已知陷阱 + 各 Step 失敗時的具體 fallback。

**Files:**
- Create: `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/troubleshooting.md`

- [ ] **Step 1: Write file**

Write the following exact content to `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/troubleshooting.md`:

````markdown
# svelte-ai-infra troubleshooting

針對本 skill 流程的常見 failure mode 與處置。版本/host/tool 性質的限制請見 [version-compat.md](version-compat.md)。

## Step 0 略過導致靜默覆寫

**症狀：** 在既有專案直接跑 `cp -r assets/. .` 蓋掉了既有 `apm.yml` / `.mcp.json` / `.lsp.json` 的設定。

**處置：** 永遠先跑 Step 0 的存在性檢查腳本。若 Step 0 表中標「**停止並確認**」的檔案存在，**必須**先與使用者確認策略再進 Step 1。CI / 排程環境一律 abort。

## frontmatter 不要手動 prepend

**症狀：** 直接 `echo "---\n..." > file.md` 或在文字編輯器手動加 frontmatter，造成 BOM、欄位重複堆疊、frontmatter 內 `---` 數量錯亂。

**處置：** 固定用 `$SKILL_ROOT/scripts/ensure-frontmatter.sh`，它處理 BOM、idempotent 寫入、欄位覆寫，不會堆疊重複。

## Step 1 失敗：placeholder 沒被替換

**症狀：** Step 1 驗證 `grep -q '<project-name>\|<project-description>\|<author>\|__UPSTREAM_SHA__' apm.yml` 反而 exit 0（找到 placeholder）。

**處置：**
- 確認 4 個 placeholder 都被 Read + Edit 替換過（**不是**只改 3 個 project placeholder 而漏掉 `__UPSTREAM_SHA__`）
- 確認 `.upstream-ref` 內容是合法 40-char hex（`grep -E '^[0-9a-f]{40}$' "$SKILL_ROOT/.upstream-ref"`）
- 若用 Write 整檔覆寫而非 Read + Edit，可能順序錯亂或漏值 — 改用 Read + Edit

## Step 2 失敗：fetch 失敗、fallback 也壞

**症狀：** `fetch-agent.sh` exit non-zero，或下載成功但內容不正確（HTML 錯誤頁、空檔等）。

**處置：**
- 確認 `.upstream-ref` 指向的 SHA 在上游確實存在：`gh api repos/sveltejs/ai-tools/commits/$(cat "$SKILL_ROOT/.upstream-ref") --jq '.sha'`
- 若 SHA 不存在（如被 force-push 移除），按 [upstream-sync.md](upstream-sync.md) bump 到新 SHA
- 若 fetch 失敗但 fallback 也壞：檢查 `$SKILL_ROOT/assets/.apm/` 內檔案是否完整、frontmatter 合法

## Step 3 失敗：`apm install` exit ≠ 0

**症狀：** `apm install` 非 0 退出。

**常見原因與處置：**
- **apm.yml 殘留 placeholder** → 回 Step 1 重新替換
- **網路問題** → 重試；確認 git/curl 可連 github.com
- **apm CLI 版本過舊** → `apm --version` 確認 ≥ 0.13.0，否則 `apm update`（詳見 [version-compat.md](version-compat.md)）
- **依賴 SHA 解析失敗** → `.upstream-ref` 內容必須是 commit SHA，不是 tag 或分支名

## Step 4 失敗：路徑 MISS

**症狀：** 10 條路徑檢查有 `MISS`。

**處置：**
1. 看 `apm.lock.yaml` 的 `deployed_files` 段落，比對該檔是否被 lockfile 宣告
2. 若 lockfile **未**宣告該檔 → `apm install` 沒處理到，重跑 Step 3；若仍未宣告，可能是 apm 版本太舊（檢查 [version-compat.md](version-compat.md) `apm ≥ 0.13.0` 段）
3. 若 lockfile **有**宣告但檔案不存在 → `apm install` 中途失敗未部署完，重跑 Step 3
4. 若 MCP `.mcp.json` 缺少 svelte server → 確認 `apm.yml` 內 `dependencies.mcp` 有 `name: svelte` 條目，再重跑 Step 3
````

- [ ] **Step 2: 驗證**

Run:
```bash
TS=plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/troubleshooting.md
[ -f "$TS" ] && echo "EXISTS" || { echo "FAIL"; exit 1; }
grep -q 'Step 0' "$TS" && grep -q 'Step 4' "$TS" && echo "PASS: covers Step 0-4" || echo "FAIL: missing step coverage"
wc -l "$TS"
```

Expected: 2 行 PASS + line count (expect 50-80)。

- [ ] **Step 3: Commit**

Run:
```bash
git add plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/troubleshooting.md
git commit -m "docs(svelte-ai-infra): extract known traps and step-failure handling to references"
```

---

## Task 5: Create `references/upstream-sync.md`

bump `.upstream-ref` SHA 的完整 5 步流程。

**Files:**
- Create: `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/upstream-sync.md`

- [ ] **Step 1: Write file**

Write the following exact content to `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/upstream-sync.md`:

````markdown
# Upstream sveltejs/ai-tools sync

本 skill pin 上游 `sveltejs/ai-tools` 到固定 commit SHA，避免每次 invocation 拉到不同版本造成行為漂移。

## SOT

`.upstream-ref` — 單行 full SHA（40-char hex），無前後空白。

## 為什麼是 SHA 而不是 tag

`sveltejs/ai-tools` repo 只對 `@sveltejs/opencode` 子套件出 git tag，claude/svelte plugin 本身**沒有**對應的 release tag（可用 `gh api repos/sveltejs/ai-tools/tags --jq '.[].name'` 確認）。只能 pin commit SHA。

## Bump 流程

1. **查上游 main 當前 HEAD**：
   ```bash
   gh api repos/sveltejs/ai-tools/commits/main --jq '.sha'
   ```
   記下 40-char hex SHA。

2. **更新 `.upstream-ref`**：
   覆寫整檔內容為新 SHA（單行、無前後空白）。

3. **同步更新 fallback assets**（若上游檔內容有變）：
   ```bash
   REF=$(cat .upstream-ref)
   curl -sSL "https://raw.githubusercontent.com/sveltejs/ai-tools/${REF}/plugins/claude/svelte/agents/svelte-file-editor.md" \
     -o assets/.apm/agents/svelte-file-editor.agent.md
   curl -sSL "https://raw.githubusercontent.com/sveltejs/ai-tools/${REF}/tools/instructions/AGENTS.md" \
     -o assets/.apm/instructions/svelte-mcp-tools.instructions.md
   # 規範化 frontmatter
   scripts/ensure-frontmatter.sh assets/.apm/instructions/svelte-mcp-tools.instructions.md \
     "Instructions for using the Svelte MCP server tools for documentation lookup, code analysis, and validation" \
     "**/*.svelte"
   ```
   若 fallback 內容無變化（diff 為空），跳過第 3 步。

4. **跑 E2E smoke test**：
   ```bash
   # 在 repo 外新建 SvelteKit 專案
   cd /tmp
   rm -rf svelte-ai-infra-bump-test
   npx --yes sv@latest create svelte-ai-infra-bump-test --template minimal --types ts --no-add-ons --no-install

   # 跑完 Step 0-4，10/10 路徑須 OK + MCP 配 svelte server
   # (流程詳見 references/workflow.md)
   ```
   若 smoke test 失敗：上游可能 breaking change 了 — 不要 bump，先查上游 commit 看影響範圍。

5. **Commit**：
   ```bash
   SHORT=$(cat .upstream-ref | cut -c1-10)
   git add .upstream-ref assets/.apm/
   git commit -m "chore(svelte-ai-infra): bump upstream sveltejs/ai-tools to ${SHORT}"
   ```

## Bump 頻率建議

- 沒有定期計畫；按需 bump（上游有重要修復、user 回報問題、季度 review 等）
- 任何 bump 都**必須**跑 Step 4 smoke test 才能進 main
- 若上游 force-push 移除了 pinned SHA：smoke test 會在 Step 2 fail，按本檔案流程 bump 到當前 main HEAD
````

- [ ] **Step 2: 驗證**

Run:
```bash
US=plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/upstream-sync.md
[ -f "$US" ] && echo "EXISTS" || { echo "FAIL"; exit 1; }
grep -q 'Bump 流程' "$US" && echo "PASS: bump procedure" || echo "FAIL"
grep -c '^[0-9]\. \*\*' "$US" | xargs -I{} sh -c '[ {} -eq 5 ] && echo "PASS: 5 numbered steps" || echo "FAIL: expected 5 steps, got {}"'
wc -l "$US"
```

Expected: 2 行 PASS + step count check PASS + line count (expect 50-80)。

- [ ] **Step 3: Commit**

Run:
```bash
git add plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references/upstream-sync.md
git commit -m "docs(svelte-ai-infra): add upstream-sync.md with SHA bump procedure"
```

---

## Task 6: Rewrite `SKILL.md` as router (≤ 100 lines)

把當前 207 行的 SKILL.md 重寫為短 router，描述加入明確 `Use when ... Do NOT use when ...`，移除硬編 `.claude/skills/` 假設，所有 step 細節指向 references/。

**Files:**
- Modify (rewrite): `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/SKILL.md`

- [ ] **Step 1: Read current SKILL.md（必要 — 因為要 Write overwrite）**

Use Read tool on `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/SKILL.md` to satisfy the "must read before write" requirement.

- [ ] **Step 2: Overwrite with new router content**

Write the following exact content to `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/SKILL.md`:

````markdown
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
````

- [ ] **Step 3: 驗證行數 ≤ 100**

Run:
```bash
SK=plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/SKILL.md
LC=$(wc -l < "$SK")
echo "Line count: $LC"
if [ "$LC" -le 100 ]; then echo "PASS: ≤ 100 lines"; else echo "FAIL: $LC > 100"; exit 1; fi
```

Expected:
```
Line count: <some number ≤ 100>
PASS: ≤ 100 lines
```

- [ ] **Step 4: 驗證關鍵內容**

Run:
```bash
SK=plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/SKILL.md
grep -q 'Use when' "$SK" && echo "PASS: Use when present" || echo "FAIL: missing 'Use when'"
grep -q 'Do NOT use when' "$SK" && echo "PASS: Do NOT use when present" || echo "FAIL"
grep -q 'references/workflow.md' "$SK" && echo "PASS: links to workflow" || echo "FAIL"
grep -q 'references/version-compat.md' "$SK" && echo "PASS: links to version-compat" || echo "FAIL"
grep -q 'references/troubleshooting.md' "$SK" && echo "PASS: links to troubleshooting" || echo "FAIL"
grep -q 'references/upstream-sync.md' "$SK" && echo "PASS: links to upstream-sync" || echo "FAIL"
grep -q '\.upstream-ref' "$SK" && echo "PASS: mentions .upstream-ref" || echo "FAIL"
grep -q 'refs/heads/main' "$SK" && echo "FAIL: drift URL still in SKILL.md" || echo "PASS: no drift URL"
grep -q 'SKILL_ROOT' "$SK" && echo "PASS: SKILL_ROOT guidance" || echo "FAIL: missing SKILL_ROOT section"
```

Expected: 9 行 PASS。任一 FAIL 就回 Step 2 修正。

- [ ] **Step 5: Commit**

Run:
```bash
git add plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/SKILL.md
git commit -m "refactor(svelte-ai-infra): rewrite SKILL.md as router with explicit Use when triggers

SKILL.md (207 lines) is now a router (≤ 100 lines) that defers step
detail to references/workflow.md, version constraints to
references/version-compat.md, known traps to
references/troubleshooting.md, and SHA bump procedure to
references/upstream-sync.md.

Description gains explicit 'Use when ... Do NOT use when ...' triggers
(per skill-writer spec) and the hardcoded .claude/skills/ SKILL_ROOT
assumption is replaced with portable resolution guidance."
```

---

## Task 7: E2E smoke test (full repro from clean SvelteKit)

實際跑一遍 SKILL Step 0–4，驗證 refactor 後流程仍 work。**這是最重要的回歸驗證 — 任何 Step 失敗都代表 refactor 有 bug。**

**Files:**
- 不修改 repo 內任何檔
- 建立並驗證：`D:\tmp\svelte-ai-infra-refactor-smoke\`（測完保留供 Task 8 用）

- [ ] **Step 1: 建 fresh SvelteKit 專案**

Run:
```bash
rm -rf /d/tmp/svelte-ai-infra-refactor-smoke
cd /d/tmp
npx --yes sv@latest create svelte-ai-infra-refactor-smoke --template minimal --types ts --no-add-ons --no-install
ls /d/tmp/svelte-ai-infra-refactor-smoke
```

Expected: 看到 `package.json`、`src/`、`svelte.config.js`、`vite.config.ts` 等 SvelteKit minimal 結構。

- [ ] **Step 2: 跑 Step 0 — Preflight**

Run:
```bash
cd /d/tmp/svelte-ai-infra-refactor-smoke
for p in apm.yml apm.lock.yaml .apm .lsp.json .mcp.json .claude .github .agents; do
  if [ -e "$p" ]; then echo "EXISTS: $p"; fi
done
```

Expected: 無輸出（fresh project 沒有任何衝突檔）。

- [ ] **Step 3: 跑 Step 1 — Copy assets + 替換 4 個 placeholder**

Run:
```bash
SKILL_ROOT="/d/Skills/meta-skills/plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra"
cd /d/tmp/svelte-ai-infra-refactor-smoke
cp -r "$SKILL_ROOT/assets/." .
```

Then Edit `apm.yml` to replace 4 placeholders (use Read + Edit, not Write):

讀 SHA：
```bash
cat "$SKILL_ROOT/.upstream-ref"
```

把以下 4 個 placeholder 換成實際值：
- `<project-name>` → `svelte-ai-infra-refactor-smoke`
- `<project-description>` → `Refactor smoke test project`
- `<author>` → `Madao`
- `__UPSTREAM_SHA__` → (上面 cat 出來的 40-char SHA)

驗證：
```bash
cd /d/tmp/svelte-ai-infra-refactor-smoke
if grep -q '<project-name>\|<project-description>\|<author>\|__UPSTREAM_SHA__' apm.yml; then
  echo "FAIL: placeholders not all replaced"; exit 1
else
  echo "PASS: all 4 placeholders replaced"
fi
[ -f .apm/agents/svelte-file-editor.agent.md ] && echo "PASS: agent fallback present" || echo "FAIL"
[ -f .apm/instructions/svelte-mcp-tools.instructions.md ] && echo "PASS: instructions fallback present" || echo "FAIL"
[ -f .lsp.json ] && echo "PASS: .lsp.json present" || echo "FAIL"
```

Expected: 4 行 PASS。

- [ ] **Step 4: 跑 Step 2 — Refresh `.apm/` 源檔（pinned SHA）+ frontmatter**

Run:
```bash
SKILL_ROOT="/d/Skills/meta-skills/plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra"
cd /d/tmp/svelte-ai-infra-refactor-smoke
REF=$(cat "$SKILL_ROOT/.upstream-ref")
echo "Using REF=$REF"

"$SKILL_ROOT/scripts/fetch-agent.sh" \
  "https://raw.githubusercontent.com/sveltejs/ai-tools/${REF}/plugins/claude/svelte/agents/svelte-file-editor.md" \
  .apm/agents/svelte-file-editor.agent.md \
  "$SKILL_ROOT/assets/.apm/agents/svelte-file-editor.agent.md"

"$SKILL_ROOT/scripts/fetch-agent.sh" \
  "https://raw.githubusercontent.com/sveltejs/ai-tools/${REF}/tools/instructions/AGENTS.md" \
  .apm/instructions/svelte-mcp-tools.instructions.md \
  "$SKILL_ROOT/assets/.apm/instructions/svelte-mcp-tools.instructions.md"

"$SKILL_ROOT/scripts/ensure-frontmatter.sh" \
  .apm/instructions/svelte-mcp-tools.instructions.md \
  "Instructions for using the Svelte MCP server tools for documentation lookup, code analysis, and validation" \
  "**/*.svelte"

echo "---"
grep -q 'Svelte MCP server' .apm/agents/svelte-file-editor.agent.md && echo "PASS: agent content" || echo "FAIL"
[ "$(head -1 .apm/instructions/svelte-mcp-tools.instructions.md)" = "---" ] && echo "PASS: instructions frontmatter delimiter" || echo "FAIL"
grep -q '^applyTo: "\*\*/\*\.svelte"$' .apm/instructions/svelte-mcp-tools.instructions.md && echo "PASS: applyTo" || echo "FAIL"
grep -q '^description: Instructions for using the Svelte MCP server' .apm/instructions/svelte-mcp-tools.instructions.md && echo "PASS: description" || echo "FAIL"
```

Expected: 看到「Using REF=<40-char hex>」+ 4 行 PASS。fetch 輸出應顯示 `[fetched]` 而非 `[fallback]`。

- [ ] **Step 5: 跑 Step 3 — `apm install`**

Run:
```bash
cd /d/tmp/svelte-ai-infra-refactor-smoke
apm.cmd install 2>&1 | tee /tmp/apm-install-output.txt
EXIT=${PIPESTATUS[0]}
echo "EXIT_CODE: $EXIT"

if [ "$EXIT" -ne 0 ]; then echo "FAIL: apm install exit $EXIT"; exit 1; fi
[ -f apm.lock.yaml ] && echo "PASS: lockfile exists" || echo "FAIL"
grep -q 'sveltejs/ai-tools' apm.lock.yaml && echo "PASS: lockfile has dep" || echo "FAIL"
grep -q '^mcp_servers:' apm.lock.yaml && echo "PASS: mcp_servers block" || echo "FAIL"

# 額外：驗證 pin 生效（不應有 unpinned warning）
if grep -q 'unpinned' /tmp/apm-install-output.txt; then
  echo "FAIL: 'unpinned' warning still present — SHA pin not effective"
  exit 1
else
  echo "PASS: no unpinned warning"
fi
```

Expected: `EXIT_CODE: 0` + 4 行 PASS。

- [ ] **Step 6: 跑 Step 4 — 10-path acceptance + MCP**

Run:
```bash
cd /d/tmp/svelte-ai-infra-refactor-smoke
echo "=== 10-path check ==="
OK=0; MISS=0
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
  if [ -f "$p" ]; then echo "OK   $p"; OK=$((OK+1)); else echo "MISS $p"; MISS=$((MISS+1)); fi
done

echo "Summary: $OK OK / $MISS MISS"
[ "$OK" -eq 10 ] && [ "$MISS" -eq 0 ] && echo "PASS: 10/10 paths" || { echo "FAIL"; exit 1; }

echo ""
echo "=== .mcp.json check ==="
[ -f .mcp.json ] && cat .mcp.json | grep -q '"svelte"' && echo "PASS: .mcp.json has svelte server" || echo "FAIL"
```

Expected: `Summary: 10 OK / 0 MISS` + `PASS: 10/10 paths` + `PASS: .mcp.json has svelte server`.

- [ ] **Step 7: 記錄 smoke test 結果**

Capture exact output of Step 5 (`apm install` output) and Step 6 (path summary). 不需 commit，但下一 task 會用這些結果做最終驗收 report。

---

## Task 8: 最終 acceptance verification

跑 spec 的 8 條 acceptance criteria，逐條 PASS/FAIL 報。

**Files:**
- 不修改任何檔，純驗收

- [ ] **Step 1: Acceptance #1 — SKILL.md ≤ 100 行（不含 frontmatter 開閉 ---）**

Run:
```bash
SK=plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/SKILL.md
TOTAL=$(wc -l < "$SK")
FM_LINES=$(awk '/^---/{c++; if(c==2){print NR; exit}}' "$SK")
# Body lines = TOTAL - FM_LINES (frontmatter starts at line 1, ends at FM_LINES; body is FM_LINES+1 to end)
BODY=$((TOTAL - FM_LINES))
echo "Total: $TOTAL, frontmatter ends line: $FM_LINES, body lines: $BODY"
if [ "$BODY" -le 100 ]; then echo "PASS_1: body $BODY ≤ 100"; else echo "FAIL_1: body $BODY > 100"; fi
```

Expected: `PASS_1`. If FAIL, may need to trim SKILL.md further — revisit Task 6.

- [ ] **Step 2: Acceptance #2 — `.upstream-ref` valid**

Run:
```bash
node -e "const s=require('fs').readFileSync('plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/.upstream-ref','utf8').trim(); console.log(/^[0-9a-f]{40}\$/.test(s) ? 'PASS_2' : 'FAIL_2: '+s);"
```

Expected: `PASS_2`

- [ ] **Step 3: Acceptance #3 — `assets/apm.yml` contains `__UPSTREAM_SHA__`**

Run:
```bash
grep -q '__UPSTREAM_SHA__' plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/assets/apm.yml && echo "PASS_3" || echo "FAIL_3"
```

Expected: `PASS_3`

- [ ] **Step 4: Acceptance #4 — 4 references files exist and non-empty**

Run:
```bash
REFS_DIR=plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/references
for f in workflow.md version-compat.md troubleshooting.md upstream-sync.md; do
  P="$REFS_DIR/$f"
  if [ -f "$P" ] && [ -s "$P" ]; then echo "OK   $f ($(wc -l < $P) lines)"; else echo "MISS $f"; fi
done
```

Expected: 4 行 `OK` + line counts。

- [ ] **Step 5: Acceptance #5 — No `refs/heads/main` in SKILL.md or references/**

Run:
```bash
cd plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra
if grep -rn 'refs/heads/main' SKILL.md references/ 2>/dev/null; then
  echo "FAIL_5: drift URL found above"; exit 1
else
  echo "PASS_5: no refs/heads/main in SKILL.md or references/"
fi
cd - > /dev/null
```

Expected: `PASS_5`

- [ ] **Step 6: Acceptance #6 — E2E smoke test passed (from Task 7)**

Confirm from Task 7 results that:
- 10/10 paths OK
- `.mcp.json` contains svelte server
- `apm install` exit 0

Report:
```
Acceptance #6: PASS / FAIL (based on Task 7 Step 6 output)
```

- [ ] **Step 7: Acceptance #7 — `apm install` output shows pinned SHA**

From Task 7 Step 5 saved output (`/tmp/apm-install-output.txt`):

Run:
```bash
SHORT=$(cat plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/.upstream-ref | cut -c1-8)
if grep -q "ai-tools @${SHORT}" /tmp/apm-install-output.txt; then
  echo "PASS_7: apm install confirms pinned SHA ${SHORT}"
else
  echo "FAIL_7: apm install output does not show @${SHORT}"
  echo "(actual output below for inspection)"
  grep -A1 'sveltejs/ai-tools' /tmp/apm-install-output.txt | head -3
fi
```

Expected: `PASS_7`. The apm install output format from 0.13.0 is `[+] github.com/sveltejs/ai-tools/plugins/claude/svelte @<short-sha>`.

- [ ] **Step 8: Acceptance #8 — Deployed apm.yml does NOT contain `__UPSTREAM_SHA__`**

Run:
```bash
if grep -q '__UPSTREAM_SHA__' /d/tmp/svelte-ai-infra-refactor-smoke/apm.yml; then
  echo "FAIL_8: placeholder still in deployed apm.yml"
else
  echo "PASS_8: placeholder correctly substituted in deployed apm.yml"
fi
```

Expected: `PASS_8`

- [ ] **Step 9: 清掃並回報**

Cleanup test project:
```bash
rm -rf /d/tmp/svelte-ai-infra-refactor-smoke
echo "test project removed"
```

Generate summary report covering:
- Branch state: `git log --oneline main..HEAD` (列出 spec + 6 個 task commits)
- SKILL.md line count delta: 207 → <new count>
- references/ files: 4 個 created, total lines
- Acceptance criteria 1-8: 全部 PASS
- Suggested next step: ready for whole-branch code review + PR
