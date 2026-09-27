---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-09-27
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-09-27 - The long-run handoff queue (`docs/audit/next-session.md`) is worked:
cross-section tooltip convergence, the `06-X` interruptible cancel, and the P3
polish batches are landed. The frontend suite is **241 passed / 0 failed** and the
backend suite is green (754 tests). Two items are parked for user decisions
(`02-N` naming, `06-O` role wording); three are deferred (`02-O`, `01-BADGE`,
`01-RISE`). Full state is `docs/audit/README.md`.

## Active audit - canonical state

The multi-session app + wiki audit lives in **`docs/audit/`**. Read
`docs/audit/README.md` first - canonical for scope, priorities, status board,
backlog, open decisions and the verified test baseline. `docs/audit/wiki.md` is
the wiki retrieval audit (COMPLETE); `docs/audit/next-session.md` is the long-run
handoff prompt. Do not copy its tables here.

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory: 104 live source pages and 55 durable
  decisions under `### decision (55)`.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`), through a `claude-obsidian.transaction.v1` bundle - never a host
  Edit. Methodology is Generic. Product root: `../claude-obsidian`.
- **The retrieval index is rebuilt at session end:** `contextual-prefix.py --all
  --no-llm`, then `bm25-index.py build`; query read-only with `retrieve.py --top
  5 --no-rerank`.
- **A green suite is the norm:** frontend **241 passed / 0 failed**, backend 754
  tests green. A new failure is a real regression, not baseline drift.
- **Native `title=` tooltips are converged onto `attachTooltip`** across
  bottleneck (06-A), shell, events and portfolio/`tickerTable` (`fe40eed`). Only
  documented natives remain: the `tickerTable` arrow buttons (their tooltip
  surface sits behind the Columns menu, `z-index 90` vs `100`), the disabled
  reorder branch, and the `watchColors` star (its `title` must equal its
  `aria-label`).
- **All 13 `CARD_TOOLTIPS` entries state as-of/freshness** (`2894c5e`).
- **A cancelled generation job is now interruptible** (`8f40461`, `06-X`): the
  job path is `app/topic_agent.py`; the HTTP completion runs on an abandonable
  daemon thread and child processes are cancelled/killed/reaped - the serial lock,
  terminal status and atomic writes are preserved.
- **The `ai_sentiment` card renders an explicit unavailable state** for an empty
  payload (no fabricated `0`, no empty cohort table / flip block).
- **Event timestamps are explicit UTC** (`Z`); readers treat a missing designator
  as UTC.
- **Never fetch a URL taken from untrusted content without a public-host guard.**
- **Tickers are US-listed only, ADR-mapped** (`_strip_non_us_tickers`,
  `_resolve_tickers`, `_filter_dead_sources`).

## Active Threads

- The audit backlog is effectively closed. Parked for user decisions
  (`docs/audit/README.md` Sec 13): `02-N` (user-facing naming drift) and `06-O`
  (the bottleneck topic card's schema-echo "Role" row). Deferred: `02-O` (tooltip
  constant de-dup), `01-BADGE` (fragility coverage badge), `01-RISE` (the
  asymmetric-rising test).
