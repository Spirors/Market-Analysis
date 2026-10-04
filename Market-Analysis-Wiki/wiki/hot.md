---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-10-04
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-10-04 - Market quotes are now live: the shared quote provider returns the
latest intraday print with a date-anchored settled prior close, so portfolios,
indices/rates/commodities and futures no longer show the previous session's close
during market hours (`68f1538`). The app audit is closed and archived
(`sources/docs__audit__*`, reference-only). Frontend **246 passed / 0 failed**;
backend 774 green via a distributed run.

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
  `wiki/sources/` (`### decision (56)`).
- **Quotes are the latest live intraday print** (one bulk 5m/5d pull) with the
  prior close anchored to the last settled daily bar strictly before the print's
  session date; per-symbol cache `LIVE_QUOTE_TTL = 120s`; Refresh forces freshness
  (`68f1538`).
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`), through a `claude-obsidian.transaction.v1` bundle - never a host
  Edit. Methodology is Generic. Product root: `../claude-obsidian`.
- **A green suite is the norm:** frontend **246 passed / 0 failed**, backend 774
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
