# svelte-ai-infra → plugin 方案 design

- **Date**: 2026-05-17
- **Branch**: `feature/svelte-ai-infra`
- **Goal**: 把現有 untracked 的 `plugins/frontend-dev/svelte-ai-infra/` 補成可載入的 plugin，結構對齊兄弟 plugin `react-ai-infra`。

## Context

當前 `plugins/frontend-dev/svelte-ai-infra/` 已存在（untracked），但只包含 skill 內容（`skills/svelte-ai-infra/SKILL.md` + `assets/` + `scripts/`），缺少 plugin 必要的 manifest 與 marketplace 註冊：

- 缺 `.claude-plugin/plugin.json`
- 未在 `.claude-plugin/marketplace.json` 的 `plugins` 陣列註冊

兄弟 plugin `react-ai-infra` 已具備完整 plugin 結構，本案以它為對齊基準。

## Scope

### In scope

| # | 變更 | 檔案 | 動作 |
|---|---|---|---|
| 1 | 新增 plugin manifest | `plugins/frontend-dev/svelte-ai-infra/.claude-plugin/plugin.json` | **新增** |
| 2 | 註冊到 marketplace | `.claude-plugin/marketplace.json` | **修改**（陣列尾端追加一個物件） |

### Out of scope（這次不做）

- 拆 `SKILL.md` → `references/`（另案處理，與 `security-supply-chain` commit `c8de4e6` 同思路）
- 改寫 SKILL.md 流程文案 / 精簡內容
- 把 `assets/` 改名為 `templates/`（語義上 svelte 的 `assets/` 是整批複製的完整檔樹含隱藏目錄，與 react 的字串樣板 `templates/` 角色不同 — 詳見「設計取捨」）
- 改動 `skills/svelte-ai-infra/**` 既有內容

## 目錄結構（變更後）

```
plugins/frontend-dev/svelte-ai-infra/
├── .claude-plugin/
│   └── plugin.json              ← 新增（鏡像 react-ai-infra 欄位順序）
└── skills/
    └── svelte-ai-infra/
        ├── SKILL.md             ← 不動
        ├── assets/              ← 不動（保留原名）
        │   ├── .lsp.json
        │   ├── apm.yml
        │   └── .apm/
        │       ├── agents/svelte-file-editor.agent.md
        │       └── instructions/svelte-mcp-tools.instructions.md
        └── scripts/             ← 不動（svelte 流程需要的 bash helpers）
            ├── ensure-frontmatter.sh
            └── fetch-agent.sh
```

## 設計取捨

### 為什麼保留 `assets/` 命名而非對齊 react 的 `templates/`

| react-ai-infra | svelte-ai-infra |
|---|---|
| `templates/apm.yml` 是字串樣板 → Step 3 動態填佔位後 `Write` 到專案根目錄 | `assets/apm.yml` 是完整檔（含佔位）→ Step 1 用 `cp -r assets/.` 整批複製，Step 2 再 `Read+Edit` 替換佔位 |
| 無隱藏目錄需求 | `.apm/` 是隱藏目錄，要原樣複製。「assets」語意更貼切 |

兩者語意不同；改名只會讓 SKILL.md 內所有 `$SKILL_ROOT/assets/...` 路徑都要改，無收益。

### 為什麼 `description` 改寫為英文

`plugin.json` 與 `marketplace.json` 的 `description` 是 marketplace UI 顯示用，與 `SKILL.md` frontmatter 內的中文 description（用於 skill triggering）角色不同。對齊 react-ai-infra 的英文一句話風格。

SKILL.md 內的中文 description 不動。

## 檔案內容

### `plugins/frontend-dev/svelte-ai-infra/.claude-plugin/plugin.json`

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

對齊原則：
- 欄位集合與順序 1:1 鏡像 `react-ai-infra/.claude-plugin/plugin.json`
- `keywords` 反映 svelte 特性，比 react 多 `mcp`（svelte 流程確實裝 Svelte MCP server，react 流程沒有）
- `homepage` / `repository` / `license` / `author` 與 react 完全一致

### `.claude-plugin/marketplace.json` — `plugins` 陣列尾端追加

```json
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
```

對齊原則：
- `category: "frontend"` 與 react-ai-infra 一致（兩者同屬 `plugins/frontend-dev/`）
- `description` 與 `plugin.json` 一字不差，避免兩處漂移
- `tags` 反映 svelte 特性：含 `mcp`，不含 framework variants（react 條目列了 nextjs/tanstack/vite，svelte 沒有對應分支）

## 驗收條件

實作完成後須滿足：

1. `plugins/frontend-dev/svelte-ai-infra/.claude-plugin/plugin.json` 存在且為有效 JSON
2. `.claude-plugin/marketplace.json` 的 `plugins` 陣列含 `name: "svelte-ai-infra"` 條目，`source` 指向 `./plugins/frontend-dev/svelte-ai-infra`
3. `marketplace.json` 整體仍為有效 JSON（可用 `node -e "JSON.parse(require('fs').readFileSync('.claude-plugin/marketplace.json'))"` 驗證）
4. `skills/svelte-ai-infra/**` 內所有檔案 byte-for-byte 不變
5. 兩個 `description` 欄位（plugin.json 與 marketplace.json）字串完全一致

## Implementation 提示

留給 writing-plans 階段細化，但兩個關鍵點先記下：

- **JSON 編輯**：`marketplace.json` 是 existing file，用 `Read + Edit`（追加陣列元素），不要 `Write` 整檔以免破壞既有縮排
- **plugin.json 是新檔**：直接 `Write`
