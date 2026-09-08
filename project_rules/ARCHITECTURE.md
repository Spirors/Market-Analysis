# Architecture

Stack, section-to-code map, backend module quick-reference, and known
quirks. Read this **on demand** when a task touches a specific module
or card — it is not part of the mandatory session-start reading list
(see `AGENTS.md`). For deep-dive per-module descriptions (each
module's callers, cache layout, and design rationale), see
[`project_rules/ARCHITECTURE_DETAILS.md`](ARCHITECTURE_DETAILS.md).

## Stack

Python 3.12 + FastAPI + uvicorn. Frontend: vanilla HTML/CSS/JS (Chart.js
CDN). Storage: SQLite (`data/analysis.db` for the synthesis-run log) + JSON
(`data/events.json` for the news timeline, Git-synced) + filesystem cache
(`data/cache/`, `data/regime/`, `data/logs/`). Runs entirely locally on
Windows. No cloud, no API keys.

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
