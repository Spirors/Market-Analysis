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

2026-09-13T23:45:00Z — Wiki-native session-memory protocol adopted **and**
Layer 1 prune complete. 4 umbrella pages retired to `wiki/sources/_retired/`.

## Key Recent Facts

- The project is a local-first FastAPI + vanilla-JS webapp for macro-trend
  market analysis (regime classification, breadth/vol/yield indicators,
  chokepoint bottlenecks, filtered news timeline, trend-shift risk engine).
  Free, no-key data sources (yfinance + English-edition RSS); runs locally on
  Windows.
- The knowledge base is an Obsidian vault at `Market-Analysis-Wiki/wiki/`,
  managed by the `claude-obsidian` tool chain. 95 live source pages
  (4 retired to `wiki/sources/_retired/`); 47 durable decisions live as
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

- `wiki/sources/_retired/` — new subdirectory; 4 umbrella pages
  (`HANDOFF`, `DECISIONS`, `SESSION_LOG`, `ROADMAP`) moved here with
  `status: retired` frontmatter and Obsidian `> [!deprecated]` callouts
  pointing at their wiki-native successors.
- `wiki/index.md` — removed 4 single-entry groups; added `### retired (4)`
  with supersession mapping.
- `wiki/log.md` — new `wiki-fold` entry at the top recording the prune;
  the wiki-native-migration entry remains below.
- `wiki/overview.md` — expanded from a one-line stub to a full vault map.
- `wiki/meta/session-memory-protocol.md` — created.
- `AGENTS.md` — rewritten to wiki-native session protocol.
- `README.md` — Architecture section points at the vault.

## Active Threads

None. Phase 0–2 closed in prior sessions; Phase 3 backlog is open-ended and
the user will pull from it on request. The Layer 1 prune is complete; the
8 historical `docs/logs/*` pages and `ARCHITECTURE_DETAILS.md` are
deliberately left in place (Layer 2 is a separate decision).