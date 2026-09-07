# Architecture

Module map, section-to-code map, and known quirks. Read this **on demand**
when a task touches a specific module or card — it is not part of the
mandatory session-start reading list (see `AGENTS.md`).

## Stack

Python 3.12 + FastAPI + uvicorn. Frontend: vanilla HTML/CSS/JS (Chart.js
CDN). Storage: SQLite (`data/analysis.db` for the synthesis-run log) + JSON
(`data/events.json` for the news timeline, Git-synced) + filesystem cache
(`data/cache/`, `data/regime/`, `data/logs/`). Runs entirely locally on
Windows. No cloud, no API keys.

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

## Skills

Reused (installed via `npx skills add`, live in `.agents/skills/` and
auto-loaded by opencode):

- `macro-regime-detector` — real Python (6-component cross-asset regime
  classification); run via `app/regime.py`. Works in yfinance-only mode.
- `serenity-chokepoint-investing` — chokepoint framework backing
  `app/bottleneck.py`.
- `macro-rates-monitor` — instruction-only (expects MCP tools); use its
  narrative approach, not its tool calls.

Custom (`.opencode/skills/`): `data-pull`, `news-filter`,
`risk-divergence`.

## Section-to-code map

Each dashboard card's renderer + payload key, for quick lookup during audits.

| Card (data-card) | Body element       | Renderer (cards.js / \*)                       | Payload key                                                           | Refresh       |
| ---------------- | ------------------ | ---------------------------------------------- | --------------------------------------------------------------------- | ------------- |
| `risk`           | `#riskBody`        | `renderRisk`                                   | `risk`                                                                | yes           |
| `ai-sentiment`   | `#aiSentimentBody` | `renderAISentiment`                            | `ai_sentiment`                                                        | yes           |
| `analysis`       | `#analysisBody`    | `renderAnalysis` + async `loadAnalysisHistory` | `ai_analysis` + `/api/analysis/history`                               | yes           |
| `fragility`      | `#fragilityList`   | rendered inside `renderRisk`                   | (sub-card of risk)                                                    | no (sub-card) |
| `regime`         | `#regimeBody`      | `renderRegime`                                 | `regime`                                                              | yes           |
| `indicators`     | `#indicatorBody`   | `renderIndicators`                             | `indicators`                                                          | yes           |
| `indices`        | `#indicesBody`     | `renderIndices`                                | `market.indices` + `futures.index_futures`                            | yes           |
| `commodities`    | `#commoditiesBody` | `renderCommodities`                            | `market.commodities` + `spot.commodities_map` + `futures.commodities` | yes           |
| `rates`          | `#ratesBody`       | `renderQuotes`                                 | `market.rates`                                                        | yes           |
| `breadth`        | `#breadthChart`    | `renderBreadthSectorsChart`                    | `indicators.breadth`                                                  | yes           |
| `breadth-ai`     | `#breadthAIChart`  | `renderBreadthAIChart`                         | `indicators.breadth_ai`                                               | yes           |
| `bottleneck`     | `#bottleneckBody`  | `renderBottleneck`                             | `bottleneck`                                                          | yes           |
| `portfolio`      | `#portfolioBody`   | `renderPortfolio` (portfolio.js) + `renderBody`/`renderGrandHeader` | `portfolios` + `column_order` + `column_visibility`        | yes           |
| `thirteenf`      | `#thirteenfBody`   | `renderThirteenf`                              | `thirteenf`                                                           | yes           |
| `events`         | `#newsBody`        | `renderNews` (events.js)                       | `events`                                                              | yes           |

Coverage badges (`applyCoverageBadge` in cards.js) and vintage stamps
(`applyVintageStamp`) attach on every section refresh. The `fragility` card
is intentionally excluded from both — it's a derived sub-card of `risk` with
no independent payload key.

## Backend module quick-reference

| Module                | Public entry points                                                                                                                                                                     | Tested in                                          |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `app/config.py`       | symbol/feed dicts, TTLs, engine knobs                                                                                                                                                    | —                                                   |
| `app/market.py`       | `get_quotes`, `get_history`, `get_histories_bulk`, `build_market_snapshot`, `build_futures_snapshot`                                                                                     | `test_market_cache.py`                              |
| `app/indicators.py`   | `roc_at`, `pct_above_ma`, `breadth_pct_above_ma`, `breadth_pct_above_ma_at`, `vix_ma_ratio_at`, `vix_signal`, `trend_state`, `realized_vol`, `compute_indicators`                        | `test_indicators.py`                                |
| `app/regime.py`       | `get_regime`, `run_regime_detection`                                                                                                                                                     | `test_api_contract.py`, `test_regime_stale.py`      |
| `app/risk.py`         | `compute_risk`                                                                                                                                                                            | `test_risk_gates.py`                                |
| `app/bottleneck.py`   | `bottleneck_read`, `all_proxy_symbols`, `BOTTLENECK_CATEGORIES`                                                                                                                           | `test_bottleneck.py`                                |
| `app/ai_sentiment.py` | `compute_ai_sentiment`, `compute_ai_news_sentiment`, `compute_valuation_flag`                                                                                                             | `test_ai_sentiment.py`                              |
| `app/thirteenf.py`    | `build_thirteenf`, `issuer_ticker_map`, `_norm_issuer`                                                                                                                                    | `test_thirteenf.py` (mocked EDGAR)                  |
| `app/analysis.py`     | `build_analysis`                                                                                                                                                                           | `test_analysis_golden.py`                           |
| `app/news.py`         | `analyze`, `fetch_and_store`, `seed_events`, `rate_impact`                                                                                                                                | `test_news_analyze.py`                              |
| `app/seed_data.py`    | `SEED_EVENTS`                                                                                                                                                                              | — (pure data)                                       |
| `app/store.py`        | `upsert_events`, `delete_event`, `delete_events_by_source`, `update_event_tags`, `list_events`, `suppress_source`, `log_analysis_run`, `get_analysis_history`, `save_json`, `load_json`  | `test_store.py`                                     |
| `app/validation.py`   | `validate_symbol`                                                                                                                                                                          | `test_validation.py`                                |
| `app/scheduler.py`    | `install_task`, `remove_task`, `status`                                                                                                                                                   | `test_scheduler.py`                                 |
| `app/service.py`      | `get_dashboard`, `refresh_market`, `refresh_news`, `refresh_regime`, `refresh_all`, `backfill_news`, `_coverage_counts`, `_attach_coverage`, `_recompute_ai_sentiment`                  | `test_service_coverage.py`, `test_api_contract.py`  |
| `app/api.py`          | FastAPI app + middleware                                                                                                                                                                  | `test_api_contract.py`                              |
| `app/lockfile.py`     | `refresh_lock`, `RefreshBusy`                                                                                                                                                              | `test_lockfile.py`                                  |
| `app/lifecycle.py`    | `write_server_pid_file`, `remove_server_pid_file`, `start_auto_reap_watchdog`                                                                                                              | `test_lifecycle.py`                                 |
| `app/launcher_icon.py`| (icon generation)                                                                                                                                                                         | `test_launcher_icon.py`                             |
| `app/changelog.py`    | `log_change`                                                                                                                                                                              | — (file I/O, exercised via `test_lifecycle.py` etc.) |
| `app/run.py`          | CLI entrypoint                                                                                                                                                                             | `test_run.py`                                       |

## Known quirks

- Yahoo tickers for Treasury yields (`^TNX`, `^FVX`, `^IRX`, `^TYX`) are
  yield×100 (4.5 = 4.5%).
- yfinance can rate-limit or break; there is no secondary source (see
  `project_rules/DECISIONS.md`). Failed fetches surface as `null` and are never
  cached.
- Live news is a set of English-edition RSS feeds (`NEWS_FEEDS` in
  `app/config.py`: MarketWatch, BBC Business) with a 48h ingest window
  (`NEWS_INGEST_WINDOW_HOURS`); only items scoring >= 6.0
  (`IMPORTANCE_THRESHOLD`) on the keyword-weighted composite are stored
  — see "news section health check (2026-09-07)" in
  `project_rules/DECISIONS.md` for the threshold rationale and tuning
  knobs. Cross-source dedupe (Jaccard >= 0.6 / fuzzy >= 0.85 within 2 days)
  merges same-story items from different publishers; non-English feeds are
  excluded because the tokenizer + scorer are English-only.
- Caching TTLs live in `app/config.py` (`QUOTE_TTL`, `HISTORY_TTL`); bump
  them if you hit rate limits, or clear `data/cache/` to force fresh pulls.
- Each dashboard card has a vintage stamp showing its data age, in addition
  to the global **Refresh** button. The Analysis card has no per-card ↻;
  its `/api/analysis/history` history loads automatically on first render
  and after every global refresh.
- - Quotes derive price/change from daily close history, not quote
  endpoints — yfinance `fast_info` is broken in current versions.
- Index futures additionally have no fallback at all; failed futures stay
  `null` by design.
- No environment variables anywhere — every knob lives in `app/config.py`.
- News storage is a single GitHub-synced JSON file (`data/events.json`,
  sorted newest-first, atomic temp+rename writes). Auto-migrated from the
  legacy `data/news.db` on first load and renamed to `news.db.migrated`
  (kept as a rollback path — never deleted by the app). The synthesis-run
  log lives in `data/analysis.db` (SQLite, local-only, regenerable).
- **Cross-device sync model.** `data/events.json` syncs via Git; everything
  else in `data/` is local cache and stays diverged by design (`cache/`,
  `logs/`, `regime/`, `analysis.db`, `dashboard.json`). Market data
  (indices, VIX, yields, sectors) is fetched live per device from yfinance,
  so quotes and "as of" timestamps will always differ between machines.
  The AI capex-cycle gauge reads AI-tagged events from `events.json`, so it
  matches across devices only when `events.json` matches — i.e. when only
  **one** device runs `--news-refresh` (or hits Refresh) and the other
  pulls from Git. Running refresh on both devices silently diverges the
  timeline within minutes; pick one device for refreshes.
- The "ai" tag is auto-applied on insert for events matching
  `config.AI_NEWS_KEYWORDS`; updates preserve user tags as-is, so a manual
  removal of "ai" sticks across the next RSS refresh.
- Cross-source event dedupe merges different links into one row and
  escalates impact to Critical if either source scored Critical.
- Card order/layout persists per-browser in localStorage (`dashLayout`);
  "reset layout" restores defaults.
- The daily scheduled refresh fires at 09:00 **local time**, not ET.

## Design docs

`docs/superpowers/` — plans/specs for the news-section overhaul and the
AI-capex-cycle gauge.
