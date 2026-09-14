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

2026-09-13T23:55:00Z — Layer 2 prune complete (with correction: Architecture
and Architecture_Details consolidated into a single `### architecture (2)`
group, history drops to (10)).

## Key Recent Facts

- The project is a local-first FastAPI + vanilla-JS webapp for macro-trend
  market analysis (regime classification, breadth/vol/yield indicators,
  chokepoint bottlenecks, filtered news timeline, trend-shift risk engine).
  Free, no-key data sources (yfinance + English-edition RSS); runs locally on
  Windows.
- The knowledge base is an Obsidian vault at `Market-Analysis-Wiki/wiki/`,
  managed by the `claude-obsidian` tool chain. 95 live source pages
  (4 retired to `wiki/sources/_retired/`; 11 historical artifacts regrouped
  into `### history (11)` in [[wiki/index.md]]); 47 durable decisions live as
  individual source pages under
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

- `wiki/index.md` — Layer 2 prune: removed 9 single-entry groups
  (audit, fix-log, improvements-log, migration-guide, park-log,
  refactor-example, refactor-metrics, summary, test-plan); added a
  single `### history (10)` group consolidating all historical
  artifacts. **Correction:** `ARCHITECTURE_DETAILS` was a misclassification
  — it's a live companion to `ARCHITECTURE`, not a historical artifact —
  so it now sits with `ARCHITECTURE` in `### architecture (2)`.
- `wiki/log.md` — new `wiki-fold` entry at the top recording the Layer 2
  regroup; the Layer 1 retire entry remains below.
- `wiki/sources/_retired/` — 4 umbrella pages (HANDOFF, DECISIONS,
  SESSION_LOG, ROADMAP) with `status: retired` frontmatter and
  `> [!deprecated]` callouts.
- `wiki/overview.md` — expanded to a full vault map.
- `wiki/meta/session-memory-protocol.md` — created.
- `AGENTS.md` — rewritten to wiki-native session protocol.
- `README.md` — Architecture section points at the vault.

## Active Threads

None. Phase 0–2 closed in prior sessions; Phase 3 backlog is open-ended and
the user will pull from it on request. Wiki is now lean: 95 live pages
across 13 active index groups, 11 history entries, 4 retired entries.