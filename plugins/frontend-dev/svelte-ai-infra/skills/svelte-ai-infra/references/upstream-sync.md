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
   # (流程詳見 workflow.md)
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
