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

2026-10-14 - AI capex-cycle gauge audit. The gauge moved right ("Healthy
expansion", 30.2) while AI stocks tumbled: the freshest bad AI news (Oct 9-14)
had all scored neutral, and four bearish Sep-14 events aged out of the 30-day
window at once. Fix: lexicon expansion #2 + `python run.py --retag-events`
(`d503f8a`, `9f8c4bd`); retag flipped the news leg +60 -> -30, gauge now 3.2
"Balanced / mixed". Suite 866 green; retag rides `data/events.json` (pipeline
auto-commit).

## Where things live now

- **Live state = `wiki/hot.md` (here) + the code.** No separate canonical
  audit document in the repo.
- **The archived audit** = `sources/docs__audit__*`, grouped under `### history`
  in `wiki/index.md`. Historical; not live.
- Retrieval index rebuilt at session end (`contextual-prefix.py --all
  --no-llm`, then `bm25-index.py build`).

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), runs locally on Windows.
- **After any news-direction lexicon change, run `python run.py
  --retag-events`** - it recomputes stored live-feed rows only, honours
  `user_edited`, never touches seeds; the gauge picks it up on the next
  dashboard load (serve-time recompute).
- **Portfolio history**: write-if-absent per settled US close date (~16:15 ET
  guard); a missing close nulls the holding AND the portfolio total - never a
  partial sum; the writer rides `service.refresh_all`.
- **Portfolio Performance chart**: one aggregate total line; dashed =
  retrospective stretch, solid from the first snapshot; range persists at
  `localStorage.pfHistoryRange`.
- **Quotes are the latest live intraday print** (one bulk 5m/5d pull; prior
  close anchored to the last settled daily bar); `LIVE_QUOTE_TTL = 120s`;
  Refresh forces freshness.
- **Hosting (scheduled-path fix 2026-10-14)**: production (private repo, repo
  data -> `main`); healthchecks live; backup destination still gated.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`), through a `claude-obsidian.transaction.v1` bundle - never a host
  Edit. Methodology is Generic. Product root: `../claude-obsidian`.
- **A green suite is the norm:** frontend **261 passed / 0 failed**, backend
  **866** tests green (serial `pytest -q` aborts on a pre-existing leaked
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
  three UTC attempts + local `MarketAnalysis-Sync`; remaining = backup
  destination; watch: next scheduled attempts proving `d95aaed`, Yahoo EOD
  tail, data-repo default branch still `dry-run`.
- **Watch: gauge news direction after the retag fix** - lexicon FPs possible
  on macro phrasings; the 30-day window cliff is design.
- Open, unowned: the serial `pytest -q` abort (leaked lifecycle-watchdog
  thread) - pre-existing.
