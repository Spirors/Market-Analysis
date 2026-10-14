---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-10-13
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-10-13 - Phase 3 step 2 verified: the first production capture (run
38490902295 -> `main` commit `5f38214`) holds the real 10-12 history
(identical to local), valid; 10-13's close was not yet source-available at
run time (recorded by the next refresh - never fabricated). Fold + re-fold
clean no-ops; nothing overwritten. **Steps 3-5 await the owner's go.** No
schedules; no monitoring.

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
- **Hosting (2026-10-13)**: private transport validated (synthetic `dry-run`);
  local `state/` + first production capture on private `main`
  (`60ab0d1` -> `5f38214`, disjoint from `dry-run`); fold/idempotency verified;
  workflow still manual / `ci/**` only - no `schedule:`; steps 3-5 await owner go.
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

- **Hosting phase 3 (steps 1-2 done; 3-5 await go)**: next = backup drill +
  monitoring + schedule activation. Watch: same-day close bars can lag past
  the intended capture window (recorded on a later run instead); data-repo
  default branch is `dry-run`; `suppressed_sources.json` not mirrored.
- Open, unowned: the serial `pytest -q` abort (leaked lifecycle-watchdog
  thread) - pre-existing, no owner yet.
