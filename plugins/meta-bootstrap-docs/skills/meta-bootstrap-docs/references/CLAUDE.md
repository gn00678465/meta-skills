# CLAUDE.md 設計原則摘要

源自 Claude Code 實戰經驗（Boris Cherny 等）。
本檔為操作時對照用的精煉版（原始文章為「CLAUDE.md 八條反直覺實踐」一文）。

## 1. 越短越好，200 行上限
CLAUDE.md 每次會話都會加載，吃上下文窗口。多餘行數擠佔 Claude 理解代碼的空間。

**驗證標準**：沒看過你專案的人，讀完能在 30 秒內回答三個問題 —
- 這是什麼產品？
- 技術棧是什麼？
- 新代碼放哪裡？

## 2. 「不要引入」和「要引入」同等重要
Claude 知識有截止日，不知道你的歷史包袱。沒有禁止清單會讓 Claude 善意引入不兼容方案。

> 這條規則值千金。它防止的不是一次糾正，而是後續 10 次會話都在修兼容性問題。

格式範例：
```
Do NOT introduce unless explicitly requested:
- Redux（已遷移到 React Context + Zustand）
- styled-components（全站 Tailwind，不接受 CSS-in-JS）
- Material UI（與 shadcn/ui 樣式衝突）
- MongoDB（數據層已鎖定 PostgreSQL）
```

## 3. 規則必須可操作，不是可感受
Claude 不懂「乾淨」，懂「用 named export 而不是 default export」。

- ❌「寫乾淨的代碼」「保持簡潔」「注重性能」
- ✅「使用 named export」「組件不超過 200 行」「async/await 不用 then 鏈」「禁止 any，用泛型或 interface」

**驗證**：讀完規則後，能不能在 5 秒內判斷一段代碼是否符合？能 → 合格；不能 → 改寫。

## 4. CLAUDE.md 是 router，不是 library
職責不是儲存信息，是告訴 Claude 去哪找信息。

漸進式上下文（Progressive Disclosure）：
- Tier 1（每次加載）：CLAUDE.md — 項目是什麼 + 怎麼工作
- Tier 2（按需加載）：`docs/architecture.md`, `docs/api.md` — Claude 工作時自動讀取
- Tier 3（忽略）：`docs/archive/` — 除非明確要求，不碰

## 5. 敏感模組開本地 CLAUDE.md
`src/auth/`、`src/payments/`、`infra/` 等高風險目錄各放一個本地 CLAUDE.md，Claude 操作該目錄時會自動加載。像給危險區裝護欄。

本地 CLAUDE.md 內容範例：
- 安全紅線（不可修改的邏輯）
- 已知陷阱（依賴特定隨機方法、儲存位置等）
- 強制測試指令

## 6. 規則靠 Hook 強制執行，不靠記憶
Claude 的記憶不可靠，Hook 可靠。把 CLAUDE.md 規則變成 Hook 觸發條件。

- CLAUDE.md 的規則 = 「請記住」
- 配了 Hook 的規則 = 「你必須」

## 7. 用 MEMORY.md 建立跨會話記憶
在 CLAUDE.md 加指令讓 Claude 自己維護 `MEMORY.md`：
- 新任務開始前讀 MEMORY.md
- 任務結束有跨會話價值的洞察則 append

> 比任何向量數據庫都簡單、可控、可 Git 追蹤。成本：一個文件。

## 8. 用 CLAUDE.md 代替每次會話開場白
寫入「你是誰」和「你討厭什麼」，省掉每次新會話前 5 條消息。

範例（My Working Style）：
- 先給方案，不要直接寫代碼
- 不確定時列出選項，不要猜測
- 重大變更前先問，小優化可直接執行
- 不要用「Great question!」「I'd be happy to help!」這類套話
- 回覆用中文，代碼註解用英文
- 文件路徑用 repo-root-relative（例如 `src/auth/login.ts`），避免 host-specific 絕對路徑

## 立刻可做的 4 件事（用於驗收）
1. 刪到 200 行以內
2. 加 Do NOT introduce 區塊，列至少 3 個禁用 lib
3. 把每條模糊規則改成具體可驗證指令
4. 為敏感模組（auth / billing / infra）加本地 CLAUDE.md

## 與 README 的分工
- README → 給人類看（架構、願景、來龍去脈）
- CLAUDE.md → 給機器看（規則、工作流、防坑指南）
- 兩份都要維護 — 接受這個成本，是 AI 時代工程實踐的第一步
