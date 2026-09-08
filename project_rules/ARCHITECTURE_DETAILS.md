# Architecture — module details

Deep-dive per-module descriptions for every file under `app/`. The
high-level overview (stack, section-to-code map, backend module
quick-reference, known quirks) lives in
[`project_rules/ARCHITECTURE.md`](ARCHITECTURE.md) — read that file
first. This file is the verbose companion for when an agent is
modifying or debugging a specific module and needs its callers,
cache layout, and design rationale spelled out.

## Module map

- `app/config.py` — tracked symbols, the live news feeds, paths, TTLs. Add a
  new symbol here; feeds are English-edition RSS only.
- `app/market.py` — quotes + bulk histories (yfinance only — see
  `project_rules/DECISIONS.md` for why the Stooq fallback was removed), cached in
  `data/cache/`.
- `app/spot.py` — real cash-market spot for the Commodities card's Spot
  column. FRED public CSV for energy (WTI/Brent/Henry Hub NG, daily), Minted
  Metal public JSON for precious metals (LBMA gold/silver, twice-daily; CC BY
  4.0 — attribution rendered in the card footer). Shared cache key
  (`spot_quotes`), `SPOT_TTL` (12h). One Minted Metal fetch covers all
  precious metals; FRED fetches are per-series. The snapshot emits a
  `commodities_map` keyed by the matching Yahoo futures ticker (CL=F, BZ=F,
  GC=F, NG=F, SI=F) so the Commodities renderer is oblivious to the FRED /
  Minted Metal source family. The Commodities card universe is intentionally
  narrow — energy, gold, silver, NG, and bitcoin — so the spot map covers
  every row that has a free daily source. FRED's LBMA gold series was
  removed in January 2022 (IBA license change).
- `app/indicators.py` — breadth, moving averages, realized vol, VIX signal.
- `app/regime.py` — subprocess wrapper around the reused
  `macro-regime-detector` skill (writes JSON to `data/regime/`); reports
  older than `REGIME_MAX_AGE_DAYS` (3) are served flagged stale.
- `app/risk.py` — the **risk-divergence engine** (crown jewel). Scores 9
  cross-asset signals (breadth %>50DMA, RSP/SPY concentration, VIX vs its
  own MA, credit HYG/LQD momentum, small caps IWM/SPY, SPY-TLT correlation,
  SPY trend/drawdown, AI-theme extension, valuation stretch) and outputs a
  GREEN/YELLOW/RED read with per-signal evidence, side-tagged fragility
  flags (`optimism`/`distress`), and flip conditions. RED fires on consensus
  optimism (+≥2 optimism-side flags), washout / trend break, or broad
  risk-off; GREEN when signals stay divided. See `project_rules/DECISIONS.md` for the
  design rationale (the "gauge gotcha").
- `app/bottleneck.py` — serenity-style chokepoint framework mapped to proxy
  tickers; ranks every layer by average 40-day proxy ROC (most-stressed
  first).
- `app/ai_sentiment.py` — AI capex-cycle gauge: cohort momentum/breadth
  across the 8 `AI_CAPEX_COHORTS`, AI-news sentiment score, valuation
  stretch → −100..100 score with verdict (Euphoric → Cycle under pressure).
- `app/thirteenf.py` — SEC EDGAR 13F holdings for the 13 tracked
  `SUPERINVESTORS`. Weight-% only — dollar values deliberately never shown
  (EDGAR changed $ units across years). Declared User-Agent per SEC policy,
  paced requests, cached ~20 days (`THIRTEENF_TTL`).
- `app/analysis.py` — deterministic, NO-LLM weighted-vote synthesis of every
  engine above → stance (Risk-On / Neutral / Cautious / Risk-Off) +
  confidence capped by input coverage (weights documented in its
  docstring). Runs last in a full refresh and is logged to the
  `analysis_runs` table (Run Log card).
- `app/news.py` — market-event ingestion: curated seed loading + multi-feed
  English-edition RSS flow (`config.NEWS_FEEDS`). Live events must score
  >= `IMPORTANCE_THRESHOLD` (6.0, High/Critical) AND be published within
  `NEWS_INGEST_WINDOW_HOURS` (48h, `app/config.py`) — no backlog backfill.
  Five-dimension tagging (category / actor / direction / region / impact).
- `app/seed_data.py` — the curated 2026 event timeline (1/1/2026 → now),
  hand-tagged and deduped from the frozen gauge file, Wikipedia, and
  researched news. Seed once via `python run.py --backfill` (idempotent).
- `app/store.py` — SQLite persistence for events: explicit tag columns,
  link + cross-source similarity dedupe, manual removal (delete event with
  confirmation / hide source).
- `app/validation.py` — slim `validate_symbol` helper extracted from the
  former `app/earnings.py` (the watchlist UI was removed 2026-09-06).
  Uses `market.get_history` (yf.download bulk, reliable) as PRIMARY with
  `Ticker.info` as SECONDARY + enrichment — per the Phase 2 audit path
  diff in `project_rules/DECISIONS.md`. Used by `portfolio.add_holding`
  and by `GET /api/portfolios/validate`.
- `app/portfolio.py` — multi-portfolio holdings tracker (Fidelity Cash, Roth
  IRA, etc.). CRUD on `data/portfolios.json` (gitignored under `data/*`).
  Live-price enrichment via `market.get_quotes` (30-min disk cache) for
  the portfolio path; `market._quote_snapshot` stays no-disk-cache by
  design for `build_market_snapshot` (the dashboard's market section
  wants fresh quotes). One cash row per portfolio (fixed position,
  manual cost + value). Per-portfolio column prefs (`column_order` +
  `column_visibility` keyed by `portfolio.<pid>` — see
  `project_rules/DECISIONS.md` "Per-portfolio column state"). Reuses
  `validation.validate_symbol` for ticker validation.
- `app/scheduler.py` — Windows Task Scheduler helper. Installs three tasks
  (no admin required): `MarketAnalysis-DailyRefresh` (daily 09:00 **local**
  time, `--refresh`), `MarketAnalysis-NewsRefresh` (every 4 hours,
  `--news-refresh`), `MarketAnalysis-EventsCommit` (daily 17:00,
  `--commit-events`). All three launch `wscript.exe scheduler.vbs` — see
  `project_rules/DECISIONS.md` for why, and `project_rules/RUNBOOK.md` for the launch
  procedure itself.
- `app/service.py` — refresh orchestration + dashboard aggregation.
  Single-flight refresh (`_refresh_lock`); cross-process refresh lock
  (`data/refresh.lock`) prevents the server and a scheduled task from
  refreshing simultaneously.
- `app/lifecycle.py` — server lifecycle helpers: PID file
  (`data/server.pid`), auto-reap watchdog for orphaned agents. See
  `project_rules/RUNBOOK.md` §Step 3a for the launch procedure.
- `app/lockfile.py` — cross-process refresh lock (`data/refresh.lock`);
  the server and the scheduled tasks never refresh simultaneously. Stale
  locks are broken two ways: (1) age-based — locks older than
  `STALE_LOCK_SECONDS` (10 min) are assumed dead, and (2) PID-based — if
  the holding PID is no longer alive (Windows `GetExitCodeProcess` via
  ctypes), the lock is broken immediately regardless of age.
- `app/launcher_icon.py` — generates / refreshes the desktop launcher's
  `.ico` icon (Windows-only; called by `run.py` and by the desktop
  install path).
- `app/changelog.py` — `log_change(category, message)` appends to
  `data/logs/summary-YYYY-MM-DD.md` (gitignored local daily changelog).
  Every meaningful change calls this.
- `app/api.py` — FastAPI routes; `run.py` — entrypoint. A Host-header
  allowlist middleware (`config.ALLOWED_HOSTS`) blocks DNS rebinding.
