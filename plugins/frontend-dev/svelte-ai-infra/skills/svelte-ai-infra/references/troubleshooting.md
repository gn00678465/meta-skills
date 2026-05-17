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
