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
