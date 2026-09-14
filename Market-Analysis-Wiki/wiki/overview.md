---
type: overview
title: Vault Overview
status: evergreen
created: 2026-09-13
updated: 2026-09-13
tags:
  - overview
---

# Vault Overview

A local-first knowledge base for the **Market Analysis Tool** (Spirors/Market-Analysis).
The vault is managed by the [claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian)
tool chain and consumed by the project's agent orchestrator.

## What lives here

| Path | Purpose |
|---|---|
| `wiki/hot.md` | Bounded context cache (≤ 500 words). Read at every session start; rewritten at session end. The single source of truth for "what is the project doing right now." |
| `wiki/log.md` | Append-only operation log, newest entry first. One entry per completed knowledge operation (ingest, save, fold, lint). |
| `wiki/index.md` | Catalog of every page in the vault, grouped by category. The navigation map — start here when you don't know a page's slug. |
| `wiki/overview.md` | This file. Describes vault structure and read/write roles. |
| `wiki/meta/` | Engine metadata: ledgers (claim-ledger, source-ledger) and session-memory protocol docs. Not edited by hand. |
| `wiki/sources/` | One Markdown page per ingested source. Each page cites back to its canonical path + SHA-256 + the immutable capture in `.raw/captured/<sha>.md`. Durable decisions and session logs live here. |

## Who writes, who reads

- **Orchestrator** is the only writer. It triggers `save` / `wiki-ingest` transactions that
  update `hot.md`, `log.md`, `index.md`, and the meta ledgers as a single atomic operation.
- **Sub-agents** (Explorer, Oracle, Librarian, Fixer, Designer, Observer) are read-only on
  the wiki. The Orchestrator passes relevant wiki context inline in dispatch prompts.
- **The user** reads `wiki/index.md` for navigation and `wiki/hot.md` for "what's current."

## Migration history

- **2026-09-13 — initial ingest.** 99 sources ingested from `inbox/project_rules/`,
  `inbox/project_rules/archive/`, and `inbox/docs/`.
- **2026-09-13 — wiki-native session memory adopted.** `AGENTS.md` and `README.md`
  pointed at the vault; the inbox-based session-start protocol was deprecated. The
  `inbox/project_rules/` directory is preserved as a frozen archive (its content is
  already canonicalised in `wiki/sources/`) and must not be re-read as live context.

See [[wiki/index.md]] for the full catalog.