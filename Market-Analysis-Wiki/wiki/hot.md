---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-10-14
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-10-14 - First scheduled capture attempts failed red: scheduled runs carry
no dispatch inputs, so `--mode ""` killed `Export captures`. Fixed `d95aaed` -
scheduled runs now default to production (private repo, repo data -> `main`);
proof = next scheduled attempt. Last good capture `479e4c0` (`2026-10-13`).
Backups await a destination. Suite 858 green; all safety invariants hold.

## Where things live now

- **Live state = `wiki/hot.md` (here) + the code.** There is no separate canonical
  audit document in the repo.
- **The archived audit** = `sources/docs__audit__*`, grouped under `### history`
  in `wiki/index.md`. Historical; not live.
- The retrieval index is rebuilt at session end (`contextual-prefix.py --all
  --no-llm`, then `bm25-index.py build`).

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory; durable decisions live in
  `wiki/sources/` (`### decision (58)`).
- **Portfolio history**: write-if-absent per settled US close date (~16:15 ET
  guard); a missing close nulls the holding AND the portfolio total - never a
  partial sum; the writer rides `service.refresh_all`.
- **Portfolio Performance chart**: one aggregate total line for the selected
  set - dashed = retrospective-only stretch, solid from the first recorded
  snapshot; ranges persist at `localStorage.pfHistoryRange`.
- **Quotes are the latest live intraday print** (one bulk 5m/5d pull) with the
  prior close anchored to the last settled daily bar before the print's date;
  per-symbol cache `LIVE_QUOTE_TTL = 120s`; Refresh forces freshness.
- **Hosting (scheduled-path fix 2026-10-14)**: three UTC attempts + local
  `MarketAnalysis-Sync`; the scheduler originally published nothing
  (`--mode ""` exit 2) - fixed `d95aaed`, now production (private repo, repo
  data -> `main`); mirror six state files; healthchecks live; backup tool ready
  (destination gated).
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`), through a `claude-obsidian.transaction.v1` bundle - never a host
  Edit. Methodology is Generic. Product root: `../claude-obsidian`.
- **A green suite is the norm:** frontend **261 passed / 0 failed**, backend
  **846** tests green (serial `pytest -q` aborts on a pre-existing leaked
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

- **Hosting phase 3 (production on; scheduled path fixed 2026-10-14)**:
  remaining = backup destination; watch: next scheduled attempts proving
  `d95aaed` (first two failed pre-fix), Yahoo EOD tail (attempts cover),
  data-repo default branch still `dry-run`.
- Open, unowned: the serial `pytest -q` abort (leaked lifecycle-watchdog
  thread) - pre-existing, no owner yet.
