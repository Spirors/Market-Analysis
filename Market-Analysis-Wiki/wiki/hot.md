---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-09-25
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-09-25T00:00:00Z - Removed the "AI Analysis · Run Log" and
"Superinvestors · 13F" dashboard sections (hardly used). Recon showed they
were a closed pair: nothing surviving consumed `ai_analysis` or `thirteenf`,
so both backends were deleted wholesale (`app/analysis.py`,
`app/thirteenf.py`, the `analysis_runs` run-log, `/api/analysis/history`,
`THIRTEENF_TTL`, `SUPERINVESTORS`). Commit 8dedc18 (23 files, +48/-1518).

## Key Recent Facts

- The project is a local-first FastAPI + vanilla-JS webapp for macro-trend
  market analysis, free no-key sources (yfinance + English-edition RSS),
  running locally on Windows.
- The wiki vault is the project's persistent memory. Durable decisions live
  as source pages under `wiki/sources/`; 95 live source pages and 47 durable
  decisions under `### decision (47)` in [[wiki/index.md]].
- Vault writes require WSL on this machine (`wsl -d Ubuntu-22.04`; always
  pass explicit `--vault` because the vault config is unreadable by the WSL
  identity). The product root is the durable sibling checkout
  `../claude-obsidian` (v2.2.0).
- All 19 project skills live in `.agents/skills/`: the 15 claude-obsidian
  skills (`wiki*`, save, think, autoresearch, defuddle, obsidian-*, canvas)
  plus the 4 project domain skills (data-pull, financial-deep-research,
  news-filter, risk-divergence).

## Recent Changes

- refactor(dashboard) 8dedc18 - removed the AI Analysis Run Log and
  Superinvestors 13F sections and their backends. The legacy `news.db`
  events migration in `store.py` is preserved; `data/analysis.db` and
  `data/thirteenf_snapshot.json` were left on disk; the stale
  `data/dashboard.json` oracle was regenerated.
- fix(dashboard) 4af86f1 - `store.json_safe()` coerces NaN/Infinity to null
  at the JSON-serving boundaries; the dashboard no longer 500s on NaN.
- fix(portfolio) 534fd5f - registered the missing PUT
  `/api/portfolios/{pid}` rename route.
- fix(ai-valuation) 1ba5288 - Fwd PE data re-wired outside indicator
  compute time.

## Active Threads

- Watch: `static/style.css.orig` is a stale tracked backup that still holds
  the deleted `.tf-holdings` / `.ana-*` rules - a candidate `chore` commit.
- Watch: `tests/test_lifecycle.py` spawns a watchdog thread that can call
  `os._exit(0)` ~60s later, truncating a single-process full-suite run; run
  the backend suite as `--ignore=tests/test_lifecycle.py` plus a separate
  lifecycle invocation.
- Watch: 6 frontend Playwright failures pre-date this work (bottleneck-move
  x2, news-row chips, portfolio-star-scope, and two dash-layout tests
  already broken by the earlier earnings-card removal).
- Watch: the macro-regime-detector skill emits NaN component values when its
  price source is unavailable; sanitised at the serve boundary.
- Watch: the 9 ETF-type tickers that have no forward PE (verify the hover
  reads acceptably).
