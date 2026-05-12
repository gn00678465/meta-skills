---
name: meta-bootstrap-docs
description: Use when bootstrapping, fully rewriting (after explicit confirmation), or auditing an existing AGENTS.md / CLAUDE.md / docs/karpathy-guidelines.md trio for a repository against this skill's contract. Triggered by phrases like "bootstrap agent docs", "initialise CLAUDE.md", "set up agent context for this project", "audit our AGENTS.md", "幫我建立 AGENTS.md". Do NOT use for surgical incremental edits to an already-good AGENTS.md (use a normal edit instead), for provider-specific rule files (.cursorrules, .github/copilot-instructions.md), or when the user only wants one file out of the trio.
---

# meta-bootstrap-docs

## Produces
Three files at the target repo root:
1. `docs/karpathy-guidelines.md` — copied from this skill's `assets/`
2. `AGENTS.md` — references the karpathy file above + applies the design wisdom in `references/AGENTS.md` (7 effective patterns) and `references/CLAUDE.md` (8 counter-intuitive practices)
3. `CLAUDE.md` — single line `@AGENTS.md` (single rule source; no two files to keep in sync — therefore the wisdom from `references/CLAUDE.md` is folded into AGENTS.md)

## Workflow
```
Stage 1: scan repo  →  Stage 2: grill the user  →  Stage 3: generate  →  Stage 4: verify
```
At any stage where information is missing, stop and ask the user. **Never hallucinate. Never write a `<TBD>` placeholder.**

## Stage 1 — Pre-flight scan (use built-in Glob/Grep/Read)

Check, in order:
- Existing docs: `AGENTS.md`, `CLAUDE.md`, `docs/karpathy-guidelines.md`, `README.md`
- Package manager / build manifest: use Glob against the ecosystem's common filenames (e.g. JS family `package.json` / Python `pyproject.toml` `requirements.txt` / Rust `Cargo.toml` / Go `go.mod` / Java `pom.xml` `build.gradle*` / Ruby `Gemfile` / PHP `composer.json` / Elixir `mix.exs` / Swift `Package.swift`); if none match, state "no manifest detected" — **do not guess**
- Lock files / monorepo signals: `pnpm-lock.yaml`, `yarn.lock`, `uv.lock`, `Pipfile.lock`, `pnpm-workspace.yaml`, `turbo.json`, `nx.json`, etc.
- CI / hooks: `.github/workflows/`, `.gitlab-ci.yml`, `.husky/`, `.pre-commit-config.yaml`
- Structure: list top-level directories; flag candidates for sensitive modules: `src/`, `app/`, `tests/`, `migrations/`, `auth/`, `billing/`, `infra/`

Emit a ≤10-line "known facts" summary (language, package manager, primary framework, test framework, CI, sensitive-directory candidates). Items you cannot detect must be marked honestly and deferred to Stage 2.

**Branch**:
- No existing `AGENTS.md` / `CLAUDE.md` → proceed to Stage 2
- Existing files with substantive content → take the **Existing-file branch** below

### Existing-file branch (read → compare → propose, never edit in place)
1. Read `AGENTS.md` / `CLAUDE.md`. **Load `references/AGENTS.md` and `references/CLAUDE.md` immediately at this point** (the gap analysis cannot proceed without them).
2. Produce a gap report containing both sections:
   - **(A) Trio contract check (hard requirements)**: (i) `docs/karpathy-guidelines.md` exists and matches `assets/karpathy-guidelines.md` byte-for-byte; (ii) AGENTS.md first paragraph is the fixed Stage 3 step 2 paragraph; (iii) CLAUDE.md is exactly the single line `@AGENTS.md`. Any failure must be listed as ❌.
   - **(B) Design-wisdom check**: compare against the 7 effective patterns + 8 counter-intuitive practices, classifying each item as ✅ already met / ⚠️ partial + suggestion / ❌ missing + suggested content.
3. Present the full gap report and offer three options:
   - (a) Apply all suggestions
   - (b) Pick a subset
   - (c) Leave as-is
4. Modify files only after explicit user choice. Before any modification, back the file up as `<file>.bak.<YYYYMMDD-HHMM>`.

`docs/karpathy-guidelines.md` already exists → diff against `assets/karpathy-guidelines.md`; only overwrite after user confirmation.

## Stage 2 — Grill the user

> Interview the user relentlessly until shared understanding. Walk down each branch one at a time. For each question, provide your recommended answer. Ask **one question at a time**. **If a question can be answered by exploring the codebase, explore instead of asking.**

**Ask the questions below in order 1→9. The moment all five exit criteria are met, stop grilling and proceed to Stage 3 (you do not have to ask all nine).** Skip any question already answered by Stage 1's scan.

1. Product positioning (one sentence) + primary users → satisfies exit criterion (i)
2. Core goal + optimisation priority order → reinforces (i)
3. Tech stack details / framework versions → satisfies (ii) (skip if Stage 1 already detected)
4. "Do NOT introduce" list (historical baggage, conflicting alternatives), each paired with a "Do" alternative → satisfies (iii)
5. Decision Table — at least one "two-or-three-equally-valid-but-we-picked-this" row → satisfies (iv)
6. At least one numbered workflow, each step with a verify check → satisfies (v)
7. Coding rules — each must be judgeable in 5 seconds (optional, may skip)
8. Sensitive modules (auth / payments / migrations / infra) — should each get a local AGENTS.md? (optional, may skip)
9. MEMORY.md cross-session flow yes/no + working style (reply language, no filler phrases, propose-before-code, etc.) (optional, may skip)

### Exit criteria (all five must be satisfied before Stage 3)
(i) Project overview (3–5 lines)
(ii) Tech stack with ≥3 concrete entries
(iii) ≥1 banned library + Do alternative
(iv) ≥1 Decision Table row
(v) ≥1 numbered workflow + verify per step

Once all five are met, stop immediately — do not chase 7~9. Insufficient information → return to grilling.

### Provenance rule (strict anti-hallucination)
Every entry written into AGENTS.md must come from either **(A) facts detected during Stage 1 scan or (B) explicit user answers from Stage 2**.
- Do not use generic examples as filler (e.g. do not copy `example/AGENTS.md`'s Redux / styled-components / MongoDB rows as this project's banned-lib list)
- `example/` exists for format reference only, not for content
- When uncertain → return to grilling, not placeholders

## Stage 3 — Generate

In order:
1. Copy `assets/karpathy-guidelines.md` → `<repo>/docs/karpathy-guidelines.md` (create `docs/` if missing)
2. Write `<repo>/AGENTS.md`. Its first paragraph must be **exactly**:
   > Default behavioral principles: this repo follows the four core principles in `@docs/karpathy-guidelines.md` — Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution. The rules below expand those principles for this repo; the principles themselves are not restated.
3. Fill the body from Stage 2 results: Project Overview / Tech Stack / Do NOT introduce / Decision Table / Coding Rules / Workflows / (Sensitive Modules) / (References) / (Memory)
4. Write `<repo>/CLAUDE.md` — exactly one line: `@AGENTS.md`

Use `example/AGENTS.md` for format. Use `references/` for content discipline.

## Stage 4 — Verify (run the checklist; list every failure)

| Check | Rule |
|---|---|
| `docs/karpathy-guidelines.md` exists | File present |
| AGENTS.md first paragraph | Matches Stage 3 step 2 paragraph character-for-character |
| AGENTS.md line count | ≤150 |
| CLAUDE.md | Exactly `@AGENTS.md`, nothing else |
| Do NOT pairing | Every `Do NOT` has a paired `Do` alternative |
| Decision Table | ≥1 row |
| Workflow | ≥1 numbered, each step with verify |
| Coding Rules | Each judgeable in 5 seconds |
| Describes current state | No patterns the codebase doesn't yet have |
| References paths | Every reference resolves to a real file |
| Portability | No absolute paths (`C:\...`, `/Users/...`) |
| No placeholders | grep finds no `<TBD` |
| Sensitive modules consistent | Each listed directory either has a local AGENTS.md or is flagged as follow-up |
| Memory consistent | Section retained only if `MEMORY.md` is referenced; otherwise removed entirely |

Any failure → return to the corresponding stage and fix. All pass → report completion to the user and list follow-ups (e.g. local AGENTS.md still to be created for sensitive directories).

## Phased file loading (save context; don't load everything up front)
| Stage | Load |
|---|---|
| Stage 1 (scan) | This SKILL.md only. **If existing `AGENTS.md` / `CLAUDE.md` is detected, also load `references/AGENTS.md` + `references/CLAUDE.md`** (required for gap analysis) |
| Stage 2 (grill) | `assets/karpathy-guidelines.md` |
| Stage 3 (generate) | `references/AGENTS.md`, `references/CLAUDE.md` (skip if already loaded in Stage 1) |
| Stage 4 (verify) | `example/AGENTS.md`, `example/CLAUDE.md` |

## Failure modes
- `<TBD>` placeholders appearing → grilling was incomplete; do not write yet
- 15+ consecutive Do NOT rules without paired Do → agent over-explores and ships less work
- Describing patterns the codebase doesn't yet have → agent walks toward fabricated code
- README architecture / history bleeding into AGENTS.md → audience confusion; both files degrade
- Asking the user questions that the codebase could answer → violates Karpathy principle 1
- Overwriting an existing file without asking → always read, compare, propose, then act
