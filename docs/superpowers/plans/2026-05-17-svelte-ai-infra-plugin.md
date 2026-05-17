# svelte-ai-infra plugin conversion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把現有 untracked 的 `plugins/frontend-dev/svelte-ai-infra/` 補成可載入的 plugin（加 manifest + marketplace 註冊 + commit 既有 skill 檔），結構對齊兄弟 plugin `react-ai-infra`。

**Architecture:** 兩個檔案異動（新增 `plugin.json` + 在 `marketplace.json` 陣列尾端追加一個物件），加上把現有 untracked 的 skill 內容納入版控。所有變更皆為 declarative 設定，不影響 skill 執行邏輯。

**Tech Stack:** JSON config files (`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`); Git for version control; `node` 用來做 JSON 驗證。

**Spec reference:** `docs/superpowers/specs/2026-05-17-svelte-ai-infra-plugin-design.md`

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `plugins/frontend-dev/svelte-ai-infra/.claude-plugin/plugin.json` | Plugin metadata（name / version / description / author / keywords） | **Create** |
| `.claude-plugin/marketplace.json` | Marketplace 主索引；追加 svelte-ai-infra 條目到 `plugins` 陣列 | **Modify**（追加陣列元素，保留既有縮排） |
| `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/**` | 既有 untracked skill 內容（SKILL.md + assets/ + scripts/） | **Track**（git add，不修改內容） |

---

## Task 1: Commit 既有 untracked skill 內容

把 svelte-ai-infra skill 樹納入版控，做為後續 manifest 工作的乾淨起點。Skill 檔本身不修改（spec 驗收條件 #4：byte-for-byte 不變）。

**Files:**
- Track (no modification): `plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/**`

- [ ] **Step 1: 確認當前未追蹤檔範圍**

Run:
```bash
git status --short plugins/frontend-dev/svelte-ai-infra/
```

Expected output（順序可能不同，但應只看到 `??` 開頭、且僅限 `skills/svelte-ai-infra/` 下的檔）：
```
?? plugins/frontend-dev/svelte-ai-infra/
```

若出現 `.claude-plugin/` 或其他非 skill 子目錄請停下，這代表環境已被別處改過，先回報。

- [ ] **Step 2: 列出將被加入的具體檔案**

Run:
```bash
git ls-files --others --exclude-standard plugins/frontend-dev/svelte-ai-infra/
```

Expected output（7 個檔，順序可能不同）：
```
plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/SKILL.md
plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/assets/.lsp.json
plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/assets/.apm/agents/svelte-file-editor.agent.md
plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/assets/.apm/instructions/svelte-mcp-tools.instructions.md
plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/assets/apm.yml
plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/scripts/ensure-frontmatter.sh
plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/scripts/fetch-agent.sh
```

數量 ≠ 7 或路徑含非預期項時停下回報。

- [ ] **Step 3: 暫存並驗證**

Run:
```bash
git add plugins/frontend-dev/svelte-ai-infra/skills/
git diff --cached --stat plugins/frontend-dev/svelte-ai-infra/
```

Expected: 7 個檔顯示為新增（`|` 後均為 `+` 數字），最後一行類似 `7 files changed, NNN insertions(+)`。

- [ ] **Step 4: Commit**

Run:
```bash
git commit -m "feat(svelte-ai-infra): add skill contents (SKILL.md, assets, scripts)

Tracks existing untracked svelte-ai-infra skill tree. Plugin manifest
and marketplace registration follow in subsequent commits."
```

Expected: commit 成功，`git status` 顯示 `nothing to commit, working tree clean`。

---

## Task 2: 新增 `.claude-plugin/plugin.json`

建立 plugin manifest，欄位 1:1 鏡像 `react-ai-infra` 的 `plugin.json`，內容對應 svelte。

**Files:**
- Create: `plugins/frontend-dev/svelte-ai-infra/.claude-plugin/plugin.json`

- [ ] **Step 1: 驗證目標路徑尚未存在**

Run:
```bash
ls plugins/frontend-dev/svelte-ai-infra/.claude-plugin/ 2>/dev/null || echo "DIR_MISSING"
```

Expected: `DIR_MISSING`。若目錄已存在請停下回報（spec 預期是新建）。

- [ ] **Step 2: 建立 plugin.json**

Create `plugins/frontend-dev/svelte-ai-infra/.claude-plugin/plugin.json` 內容：

```json
{
  "name": "svelte-ai-infra",
  "version": "0.1.0",
  "description": "Bootstrap Svelte AI infrastructure into an existing Svelte/SvelteKit project: APM config, Svelte MCP server, agents, instructions, skills, and LSP settings — all wired in one shot for Claude Code, GitHub Copilot, and VS Code. Does not scaffold the Svelte app itself.",
  "author": {
    "name": "Madao",
    "email": "gn00678465@gmail.com"
  },
  "homepage": "https://github.com/gn00678465/meta-skills",
  "repository": "https://github.com/gn00678465/meta-skills",
  "license": "MIT",
  "keywords": [
    "skills",
    "svelte",
    "sveltekit",
    "agent-assets",
    "apm",
    "mcp"
  ]
}
```

- [ ] **Step 3: 驗證為合法 JSON 且關鍵欄位正確**

Run:
```bash
node -e "const j=JSON.parse(require('fs').readFileSync('plugins/frontend-dev/svelte-ai-infra/.claude-plugin/plugin.json','utf8')); console.log('name:',j.name); console.log('version:',j.version); console.log('keywords:',j.keywords.join(','));"
```

Expected output:
```
name: svelte-ai-infra
version: 0.1.0
keywords: skills,svelte,sveltekit,agent-assets,apm,mcp
```

任一行不符就回去修 `plugin.json` 再驗一次。

- [ ] **Step 4: 與 react-ai-infra plugin.json 做欄位順序對比**

Run:
```bash
node -e "console.log(Object.keys(JSON.parse(require('fs').readFileSync('plugins/frontend-dev/react-ai-infra/.claude-plugin/plugin.json','utf8'))).join(','))"
node -e "console.log(Object.keys(JSON.parse(require('fs').readFileSync('plugins/frontend-dev/svelte-ai-infra/.claude-plugin/plugin.json','utf8'))).join(','))"
```

Expected: 兩行輸出完全相同（都是 `name,version,description,author,homepage,repository,license,keywords`）。

- [ ] **Step 5: Commit**

Run:
```bash
git add plugins/frontend-dev/svelte-ai-infra/.claude-plugin/plugin.json
git commit -m "feat(svelte-ai-infra): add plugin manifest

Mirrors react-ai-infra plugin.json field layout; keywords include
'mcp' because svelte flow wires up Svelte MCP server."
```

Expected: commit 成功。

---

## Task 3: 在 `marketplace.json` 註冊 svelte-ai-infra 條目

在現有 `plugins` 陣列尾端追加 svelte-ai-infra 物件。**用 Edit 而非 Write**，避免破壞既有 2-space 縮排與其他條目格式。

**Files:**
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: 抓取追加前的條目數量做為基準**

Run:
```bash
node -e "console.log(JSON.parse(require('fs').readFileSync('.claude-plugin/marketplace.json','utf8')).plugins.length)"
```

Expected: `3`（目前有 meta-ralph / react-ai-infra / security-supply-chain 三條）。

若 ≠ 3 請停下確認 marketplace.json 是否已被別處改過。

- [ ] **Step 2: 用 Edit 在 security-supply-chain 條目後追加新條目**

定位 `marketplace.json` 結尾的這段（含 security-supply-chain 物件的閉合 `]` 之前的最後一行）：

```json
        "renovate",
        "dependabot",
        "skills"
      ]
    }
  ]
}
```

替換為：

```json
        "renovate",
        "dependabot",
        "skills"
      ]
    },
    {
      "name": "svelte-ai-infra",
      "source": "./plugins/frontend-dev/svelte-ai-infra",
      "description": "Bootstrap Svelte AI infrastructure into an existing Svelte/SvelteKit project: APM config, Svelte MCP server, agents, instructions, skills, and LSP settings — all wired in one shot for Claude Code, GitHub Copilot, and VS Code. Does not scaffold the Svelte app itself.",
      "category": "frontend",
      "tags": [
        "svelte",
        "sveltekit",
        "apm",
        "mcp",
        "agent-assets",
        "skills"
      ]
    }
  ]
}
```

**重點**：把 security-supply-chain 物件閉合的 `}` 後面從原本沒逗號改成 `},`，然後新物件接著走。

- [ ] **Step 3: 驗證仍為合法 JSON 且條目正確**

Run:
```bash
node -e "const m=JSON.parse(require('fs').readFileSync('.claude-plugin/marketplace.json','utf8')); console.log('count:',m.plugins.length); const s=m.plugins.find(p=>p.name==='svelte-ai-infra'); console.log('source:',s.source); console.log('category:',s.category); console.log('tags:',s.tags.join(','));"
```

Expected output:
```
count: 4
source: ./plugins/frontend-dev/svelte-ai-infra
category: frontend
tags: svelte,sveltekit,apm,mcp,agent-assets,skills
```

任一行不符就回 Step 2 修正。

- [ ] **Step 4: 驗證 description 與 plugin.json 字串一致**

Run:
```bash
node -e "const p=JSON.parse(require('fs').readFileSync('plugins/frontend-dev/svelte-ai-infra/.claude-plugin/plugin.json','utf8')); const m=JSON.parse(require('fs').readFileSync('.claude-plugin/marketplace.json','utf8')); const s=m.plugins.find(x=>x.name==='svelte-ai-infra'); console.log(p.description===s.description ? 'MATCH' : 'MISMATCH');"
```

Expected: `MATCH`（spec 驗收條件 #5）。

若 `MISMATCH` 請從 `plugin.json` 複製 description 字串覆寫 marketplace.json 該欄位。

- [ ] **Step 5: 驗證 diff 範圍只動了預期區域**

Run:
```bash
git diff --stat .claude-plugin/marketplace.json
git diff .claude-plugin/marketplace.json
```

Expected:
- stat 顯示 `1 file changed`，新增約 14-15 行、刪除 1 行（把 `}` 改成 `},` 算 1 刪 1 增，加上 13 行新物件）
- diff 內容應只在 `security-supply-chain` 條目尾端追加新物件，**沒有**任何 unrelated 行被改（reformat / 引號改變 / 縮排漂移）

若 diff 顯示其他位置也被動到，回去檢查 Edit 是否誤觸。

- [ ] **Step 6: Commit**

Run:
```bash
git add .claude-plugin/marketplace.json
git commit -m "feat(svelte-ai-infra): register plugin in marketplace

Appends svelte-ai-infra entry to plugins array with description
matching plugin.json byte-for-byte."
```

Expected: commit 成功。

---

## Task 4: 整體驗收

按 spec 驗收條件逐條檢查。

- [ ] **Step 1: 列出本 branch 三個 commit**

Run:
```bash
git log --oneline main..HEAD -- plugins/frontend-dev/svelte-ai-infra/ .claude-plugin/marketplace.json
```

Expected: 看到本 plan 產出的 3 個 feat commit + 先前的 design spec commit（共 4 條）。

- [ ] **Step 2: 驗收條件 #1 — plugin.json 為合法 JSON**

Run:
```bash
node -e "JSON.parse(require('fs').readFileSync('plugins/frontend-dev/svelte-ai-infra/.claude-plugin/plugin.json','utf8'))" && echo OK
```

Expected: `OK`

- [ ] **Step 3: 驗收條件 #2、#3 — marketplace.json 含條目且為合法 JSON**

Run:
```bash
node -e "const m=JSON.parse(require('fs').readFileSync('.claude-plugin/marketplace.json','utf8')); const s=m.plugins.find(p=>p.name==='svelte-ai-infra'); if(!s) process.exit(1); if(s.source!=='./plugins/frontend-dev/svelte-ai-infra') process.exit(2); console.log('OK');"
```

Expected: `OK`

- [ ] **Step 4: 驗收條件 #4 — skill 檔 byte-for-byte 未被本 plan 修改**

Run:
```bash
git log --name-only --pretty=format: HEAD~3..HEAD -- plugins/frontend-dev/svelte-ai-infra/skills/svelte-ai-infra/ | grep -v '^$' | sort -u
```

Expected: 只列出 Task 1 加入的 7 個檔（全為新增），**沒有**任何後續 commit 又修改了 skill 樹內檔案。

- [ ] **Step 5: 驗收條件 #5 — 兩個 description 字串完全一致**

Run:
```bash
node -e "const p=JSON.parse(require('fs').readFileSync('plugins/frontend-dev/svelte-ai-infra/.claude-plugin/plugin.json','utf8')); const m=JSON.parse(require('fs').readFileSync('.claude-plugin/marketplace.json','utf8')); const s=m.plugins.find(x=>x.name==='svelte-ai-infra'); console.log(p.description===s.description ? 'MATCH' : 'MISMATCH');"
```

Expected: `MATCH`

- [ ] **Step 6: 確認 working tree 乾淨**

Run:
```bash
git status --short
```

Expected: 空輸出（所有變更已 commit）。

- [ ] **Step 7: 回報完工狀態**

向使用者回報：
- 共 3 個 feat commit + 先前 1 個 docs commit
- 全部 5 條 spec 驗收條件 PASS
- 下一步建議：開 PR（branch `feature/svelte-ai-infra` → `main`）
