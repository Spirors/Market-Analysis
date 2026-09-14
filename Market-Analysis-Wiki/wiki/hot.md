---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-09-13
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-09-13T23:30:00Z — Wiki-native session-memory protocol adopted. `AGENTS.md`
and `README.md` point at the vault; `inbox/project_rules/` is frozen.

## Key Recent Facts

- The project is a local-first FastAPI + vanilla-JS webapp for macro-trend
  market analysis (regime classification, breadth/vol/yield indicators,
  chokepoint bottlenecks, filtered news timeline, trend-shift risk engine).
  Free, no-key data sources (yfinance + English-edition RSS); runs locally on
  Windows.
- The knowledge base is an Obsidian vault at `Market-Analysis-Wiki/wiki/`,
  managed by the `claude-obsidian` tool chain. 99 source pages ingested; 47
  durable decisions live as individual source pages under
  `wiki/sources/project_rules__archive__decisions__*.md` and are listed under
  `### decision (47)` in `wiki/index.md`.
- `AGENTS.md` is now a thin entry point: the session protocol (read
  `wiki/hot.md` at start, rewrite at end), sub-agent rules (Orchestrator
  writes the wiki; sub-agents are read-only and receive context inline), and
  the load-bearing hard rules (data integrity, frozen files, commit hygiene,
  shared components, file ownership, process hygiene, test isolation,
  wiki sync, documentation hygiene).
- The `Market-Analysis-Wiki/inbox/project_rules/` directory is a frozen
  archive. Its content is canonicalised in `wiki/sources/`. Do not read
  it as live context.
- WSL Ubuntu-22.04 + Python 3.12.13 are installed; vault writes require WSL
  (`os.name == "nt"` fails closed in `claude-obsidian`), but read-only
  queries work natively.

## Recent Changes

- `wiki/overview.md` — expanded from a one-line stub to a full vault map
  (path table, read/write roles, migration history).
- `wiki/meta/session-memory-protocol.md` — new file. Documents the
  hot/log/index/sources roles, write triggers, read protocol for
  Orchestrator vs sub-agents, and the session-end trigger set.
- `AGENTS.md` — rewritten to wiki-native session protocol; old
  `inbox/project_rules/`-based session start deprecated.
- `README.md` — Architecture section updated to point at `wiki/index.md`
  and note the frozen `inbox/project_rules/` archive.
- `wiki/log.md` — new migration entry at the top; the 2026-09-13 initial
  ingest entry remains below.

## Active Threads

None. Phase 0–2 closed in prior sessions; Phase 3 backlog is open-ended and
the user will pull from it on request.