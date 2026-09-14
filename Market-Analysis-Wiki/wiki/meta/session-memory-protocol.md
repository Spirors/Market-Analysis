---
type: meta
title: Session Memory Protocol
status: evergreen
created: 2026-09-13
updated: 2026-09-13
tags:
  - meta
  - protocol
  - session-memory
---

# Session Memory Protocol

How the project keeps its knowledge base consistent across sessions and across the
orchestrator/sub-agent boundary. Companion to `AGENTS.md` — that file is the
**what**, this file is the **how**.

## The four moving parts

| File | Role | Lifecycle |
|---|---|---|
| `wiki/hot.md` | Bounded context cache (≤ 500 words). The single source of truth for "what is the project doing right now." | Read at every session start; rewritten at session end (LAST). |
| `wiki/log.md` | Append-only operation log, newest entry first. | One entry per completed knowledge operation. Updated by the transaction, never direct-edited. |
| `wiki/index.md` | Catalog of every page in the vault, grouped by category. | Updated by completed `wiki-ingest` / `save` / `wiki-fold` operations. |
| `wiki/sources/` | One Markdown page per ingested source, with citations back to canonical path + SHA-256 + `.raw/captured/<sha>.md`. | New pages are created by `wiki-ingest`. Durable decisions are written here. |

## When writes happen

The **Orchestrator** is the only writer to the vault. It triggers `save` /
`wiki-ingest` / `wiki-fold` transactions; the transaction updates
`hot.md` + `log.md` + `index.md` + the meta ledgers atomically.

| Trigger | What runs | Who runs it |
|---|---|---|
| New source staged at `inbox/**` | `wiki-ingest` — captures to `.raw/captured/<sha>.md`, creates a `wiki/sources/<slug>.md` page, updates index + log + hot | Orchestrator |
| Durable decision confirmed | `save` (or `wiki-ingest` if it originated in a source) — creates a `wiki/sources/<slug>.md` decision page, appends log entry, refreshes hot | Orchestrator |
| Session ends (see below) | Rewrite `wiki/hot.md`, append one `log.md` entry | Orchestrator |
| Manual `wiki-lint` on request | Read-only health check — reports orphans, broken links, frontmatter drift | Orchestrator or user |
| `wiki-fold` on request | Idempotent rollup of recent log entries into a longer-form page | Orchestrator or user |

## The read protocol — Orchestrator vs sub-agents

**Orchestrator** reads the wiki natively at session start (`hot.md`, then
`index.md` if the task domain is unclear) and during work as needed.

**Sub-agents** (Explorer, Oracle, Librarian, Fixer, Designer, Observer) do NOT
read the wiki on their own. The Orchestrator passes relevant wiki context **inline
in the dispatch prompt** (paths, line ranges, page slugs, or short quotes).
The Orchestrator reconciles sub-agent output against the wiki before
applying any change.

Rationale: sub-agent sessions are short and token-bounded; passing the wiki
slice inline keeps their context window focused and prevents stale wiki
reads. The Explorer agent in particular is scoped to `grep / ast_grep / glob`
over the working tree — never over the vault.

## What counts as "session end"

A session ends at the **first** of:

1. The Orchestrator is about to send a final response that closes a non-trivial
   turn (no follow-up questions, no in-progress todos, no running background
   tasks) → rewrite `hot.md` + append `log.md`.
2. The user explicitly ends the session ("done for today", "that's all", etc.)
   → rewrite `hot.md` + append `log.md`.
3. A multi-session handoff is about to start (long-running task delegated to
   the Background Job Board) → the **spawning** session writes a brief hot.md
   note describing the delegated lane; the **spawned** lane updates hot.md +
   log.md when its own work completes.

`hot.md` is always written **last** in a session, so it reflects the post-state
after all other wiki changes are durable.

## Anti-patterns

- **Direct append to `wiki/log.md`** — the file is updated by the transaction,
  not by the Orchestrator hand-editing. A hand-edited entry will be silently
  overwritten on the next save.
- **Reading `inbox/project_rules/` as live context** — its content is
  canonicalised in `wiki/sources/`. The inbox directory is a frozen archive;
  do not re-read originals unless a wiki source is ambiguous.
- **Sub-agents reading the wiki directly** — the wiki slice must be passed
  inline in the dispatch prompt. Sub-agent sessions are short; a stale
  wiki read will diverge from the canonical state.
- **`hot.md` drifting past 500 words** — the cache is bounded by design.
  When the cache grows, the durable answer lives in `wiki/sources/`; hot.md
  should point at it, not duplicate it.