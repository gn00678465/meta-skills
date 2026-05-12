# AGENTS.md

> Default behavioral principles: this repo follows the four core principles in `@docs/karpathy-guidelines.md` — Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution. The rules below are the concrete expansion of those principles for this repo; the principles themselves are not restated here.

## Project Overview
B2B 分析儀表板，面向中型 SaaS 公司的運營經理。
核心目標：縮短「從原始數據到可行動洞察」的時間。
優化優先級：加載速度 > 交互豐富度 > 視覺花俏。

## Tech Stack
- Next.js 15 App Router + TypeScript 5
- Tailwind CSS + shadcn/ui
- Supabase（認證 + Postgres）
- TanStack Query（資料抓取）
- Vitest（單元）+ Playwright（e2e）

### Do NOT introduce unless explicitly requested
| 禁用 | 為什麼 | 用什麼替代 |
|----|----|----|
| Redux | 已遷移完不接受回退 | React Context（共享狀態）/ Zustand（複雜跨組件狀態） |
| styled-components | 全站 Tailwind | Tailwind utility classes |
| Material UI | 與 shadcn/ui 樣式衝突 | shadcn/ui 既有組件 |
| MongoDB | 數據層鎖定 PostgreSQL | Supabase / Prisma + Postgres |
| 直接 `fetch()` 呼 API | 沒有重試與錯誤統一 | `lib/http` 的 `apiClient` |

## Decision Table
| 場景 | 選擇 | 避免 | 為什麼 |
|----|----|----|----|
| 資料抓取 | TanStack Query | 自寫 `useEffect`+`fetch` | 已內建快取、重試、loading 規則 |
| 表單 | react-hook-form + zod | Formik | 體積較小、與 zod 直連 |
| 圖表 | Recharts | Chart.js | 已封裝 Tailwind 主題 |
| 日期處理 | `date-fns` | moment.js | tree-shake 友善 |

## Coding Rules
- 使用 named export，路由檔（`page.tsx`, `layout.tsx`）除外
- 禁止 `any`，必要時用泛型或 `unknown` 再 narrow
- 單組件不超過 200 行（有理由可超，需註解理由）
- async/await 替代 Promise then 鏈
- 變數名全拼，例外只有 `id`, `url`, `ctx`
- 只在意圖不明顯時寫註解；不留註解掉的代碼或 `console.log`
- Server Component 預設，需互動才標 `"use client"`

## Workflows

### 新增 API endpoint
1. 在 `app/api/<resource>/route.ts` 建檔 → verify: 訪問該路由回 200
2. 在 `lib/api/<resource>.ts` 加對應 client function → verify: `pnpm typecheck` 通過
3. 在 `tests/api/<resource>.test.ts` 加 happy + error path → verify: `pnpm test` 全綠
4. 更新 `docs/api.md` 加 endpoint 條目 → verify: 該檔有對應段落

### 新增受保護頁面
1. 建檔 `app/(auth)/<route>/page.tsx` → verify: 未登入訪問該路由跳轉 `/login`
2. 頁內使用 `requireSession()` helper → verify: server 端取得 user
3. 加 Playwright e2e → verify: `pnpm e2e` 通過

## Sensitive Modules
These directories handle higher-risk concerns. Before significant edits, create a local AGENTS.md inside the directory (not yet present in this example):

- `src/auth/` — token validation logic is not to be modified; Magic link depends on `crypto.randomUUID()` and must not be swapped
- `src/billing/` — Stripe webhook signature verification must not be bypassed
- `prisma/migrations/` — never edit existing migrations; always add new ones

## References (Tier 2, on-demand)
- Architecture: `docs/architecture.md`
- ADRs: `docs/adrs/`
- API: `docs/api.md`
- Deployment: `docs/deploy.md`

## Memory
If `MEMORY.md` exists at repo root, read it before starting a task. When finishing a task, append cross-session insights only if they are durable and non-obvious. If `MEMORY.md` does not exist, this section may be removed.
