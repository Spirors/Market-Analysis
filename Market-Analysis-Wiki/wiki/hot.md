---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-10-15
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-10-15 - Scheduled capture pipeline PROVEN end-to-end: both new scheduled
attempts green (runs `38687648085` / `38703529900`) with the full production
path, after `d95aaed` was pushed to GitHub `main`. They published the
`2026-10-14` settled close - capture commits `0e9c53b` + `b03e7cd` on the data
repo `main` (the second attempt's history was a designed write-if-absent
no-op). Backup destination still gated.

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
- **Hosting (proven green 2026-10-15)**: scheduled runs publish captures to the
  private repo `main` (fix `d95aaed`); last capture `b03e7cd` (`2026-10-14`
  close); healthchecks live; backup destination still gated.
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

- **Hosting phase 3 (scheduled path proven green 2026-10-15)**: remaining =
  backup destination; watch: today's 12:00 UTC attempt (still pending), Yahoo
  EOD tail, data-repo default branch still `dry-run`.
- Open, unowned: the serial `pytest -q` abort (leaked lifecycle-watchdog
  thread) - pre-existing.
