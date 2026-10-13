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

2026-10-13 - Hosting phase 2 implemented + tested: `Spirors/Market-Analysis-Data`
(private repo) is the approved cloud transport (cloud `captures/**`, local
`state/**`). Missed dates backfill only when the book is provably unchanged;
else a gap (`backfilled: true`). `run.py --sync`, the capture workflow,
freshness gate + heartbeats shipped; **846 tests green; CI green**
(`ci/capture-phase2`, synthetic/local). **Private-mode validation + production
pending owner.** No schedules; no real data migrated.

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
- **Hosting (2026-10-13)**: GHA + private data repo approved; the capture
  workflow is manual / `ci/**` only - no `schedule:`; synthetic data is pinned
  to the `dry-run` branch; heartbeats no-op until `HEALTHCHECK_URL` is set.
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

- **Hosting**: run the private-repo validation (`Capture (private data repo)` →
  Run workflow → `repo_mode=private`, `data=synthetic`); then production
  activation (schedules + real data) waits for explicit owner approval. Origin
  test branches: `ci/dry-run-phase1`, `ci/capture-phase2`, `spike/gha-probe`.
- Open, unowned: the serial `pytest -q` abort (leaked lifecycle-watchdog
  thread) - pre-existing, no owner yet.
