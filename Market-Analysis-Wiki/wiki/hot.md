---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-10-12
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-10-12 - Portfolio history shipped: the Portfolio card gained a "Portfolio
Performance" gain chart (solid = stored daily settled-close snapshots, dashed =
live retrospective) with a per-portfolio selector; `data/portfolio_history.json`
takes one write-if-absent entry per settled US close date and
`GET /api/portfolios/history` serves snapshots + retrospective. First real
snapshot recorded (close 2026-10-12). Frontend **254 passed / 0 failed**; backend
786 green via a distributed run (`756f8e7`).

## Where things live now

- **Live state = `wiki/hot.md` (here) + the code.** There is no separate canonical
  audit document in the repo.
- **The archived audit** = `sources/docs__audit__*` (summary + 9 sections + the
  wiki audit), grouped under `### history` in `wiki/index.md`. Historical; not live.
- The retrieval index is rebuilt at session end (`contextual-prefix.py --all
  --no-llm`, then `bm25-index.py build`).

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory; durable decisions live in
  `wiki/sources/` (`### decision (57)`).
- **Portfolio history**: the snapshot store is write-if-absent per settled US
  close date (~16:15 ET guard); a missing close nulls the holding AND the
  portfolio total (coverage-stamped) - never a partial sum; the writer rides
  `service.refresh_all`; the chart selector persists at
  `localStorage.pfHistorySelected`.
- **Quotes are the latest live intraday print** (one bulk 5m/5d pull) with the
  prior close anchored to the last settled daily bar strictly before the print's
  session date; per-symbol cache `LIVE_QUOTE_TTL = 120s`; Refresh forces freshness
  (`68f1538`).
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`), through a `claude-obsidian.transaction.v1` bundle - never a host
  Edit. Methodology is Generic. Product root: `../claude-obsidian`.
- **A green suite is the norm:** frontend **254 passed / 0 failed**, backend 786
  tests green (serial `pytest -q` aborts on a pre-existing leaked
  lifecycle-watchdog thread; use a distributed run). A new failure is a real
  regression.
- **Card header extras render beside the `h2`, never inside it** (`00-V` `c589a95`,
  `00-W` `739cc4c`). Keep it that way.
- **`/api/meta` is the sanctioned config-to-frontend channel**; consumers keep
  defaults that render identically if it fails.
- **Native `title=` tooltips are converged onto `attachTooltip`** (`fe40eed`).
- **All 13 `CARD_TOOLTIPS` entries state as-of/freshness** (`2894c5e`).
- **A cancelled generation job is interruptible** (`8f40461`, `06-X`).
- **Event timestamps are explicit UTC** (`Z`).
- **Never fetch a URL taken from untrusted content without a public-host guard.**
- **Tickers are US-listed only, ADR-mapped.**

## Active Threads

- None. The audit is fully closed. Open, unowned: the serial `pytest -q` abort
  (leaked lifecycle-watchdog thread) - pre-existing, no owner yet.
