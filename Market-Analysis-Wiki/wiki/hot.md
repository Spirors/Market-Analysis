---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-10-18
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-10-18 - Capture pipeline verified in steady state: **12/12 scheduled runs
green** since the `d95aaed` fix (2026-10-15 -> 2026-10-18), publishing settled
closes to the private repo `main` (captures through the `2026-10-16` close;
latest run `39138591368-1` ok, 1 new event). Detail:
`wiki/log.md` -> `session-end-20261018-capture-verify-cleanup`. Cleanup: the
phase-1 `pipeline-dry-run.yml` retired (`ed7e8d7`); fully-merged phase-1 test
branches deleted. Suites green (backend 873 / frontend 261). Backup
destination still gated.

## Where things live now

- **Live state = `wiki/hot.md` (here) + the code.** No separate canonical
  audit document in the repo.
- The archived audit = `sources/docs__audit__*`, grouped under `### history` in
  `wiki/index.md`. Historical; not live.
- Retrieval index rebuilt at session end (`contextual-prefix.py --all
  --no-llm`, then `bm25-index.py build`).

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), runs locally on Windows.
- **Gauge news leg**: recency-weighted (half-life 7 d); after any news
  lexicon change run `python run.py --retag-events` (stored live-feed rows
  only, honours `user_edited`, never seeds); the gauge picks changes up on
  the next dashboard load (serve-time recompute).
- **Portfolio history**: write-if-absent per settled US close date (~16:15 ET
  guard); a missing close nulls the holding AND the portfolio total - never a
  partial sum; the writer rides `service.refresh_all`.
- **Portfolio Performance chart**: one aggregate total line; dashed =
  retrospective stretch, solid from the first snapshot; range persists at
  `localStorage.pfHistoryRange`.
- **Quotes are the latest live intraday print** (one bulk 5m/5d pull; prior
  close anchored to the last settled daily bar); `LIVE_QUOTE_TTL = 120s`;
  Refresh forces freshness.
- **Hosting (steady state since 2026-10-15; verified 2026-10-18)**: scheduled
  `capture.yml` attempts (01/03/12 UTC) publish to the private repo `main`;
  the local `Sync` task pushes `state/*` to `main` too; `capture.yml` local
  mode is the manual synthetic path (phase-1 workflow retired); healthchecks
  live; runs land ~+4-5 h after their slots (tolerated); backup destination
  still gated.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`) via a `claude-obsidian.transaction.v1` bundle - never a host
  Edit. Methodology: Generic. Product root: `../claude-obsidian`.
- **A green suite is the norm:** frontend **261 passed / 0 failed**, backend
  **873** tests green (serial `pytest -q` aborts on a pre-existing leaked
  lifecycle-watchdog thread; use a distributed run). A new failure is a real
  regression.
- **Card header extras render beside the `h2`, never inside it** (`00-V`, `00-W`).
  Keep it that way.
- **`/api/meta` is the sanctioned config-to-frontend channel**; consumers keep
  defaults that render identically if it fails.
- **Event timestamps are explicit UTC** (`Z`).
- **Never fetch a URL taken from untrusted content without a public-host guard.**
- **Tickers are US-listed only, ADR-mapped.**

## Active Threads

- **Hosting phase 3**: scheduled path proven + verified steady; remaining =
  backup destination (gated); watch: Yahoo EOD tail (attempts cover).
- Open, unowned: the serial `pytest -q` abort (leaked lifecycle-watchdog
  thread) - pre-existing.
