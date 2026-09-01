# AGENTS.md

AI-readable reference for the Market Analysis Tool. For a plain-English
project overview (what it does, what's been built, what's been fixed), see
[`Summary.md`](./Summary.md). For audit-grade fix/improvement detail, see
[`docs/`](./docs/) (`fix-log-2026-08-22.md`, `improvements-log-2026-08-22.md`,
`park-log-2026-08-23.md`, `audit-2026-08-26.md`).

## What this is

Local webapp for macro-trend market analysis. Outputs: regime classification,
breadth/vol/yield indicators, serenity-style chokepoint bottlenecks, filtered
news timeline, and a trend-shift **risk-divergence engine**. Browser dashboard
+ free no-key data sources.

**Stack:** Python 3.12 + FastAPI + uvicorn. Frontend: vanilla HTML/CSS/JS
(Chart.js CDN). Storage: SQLite (`data/analysis.db` for synthesis-run log)
+ JSON (`data/events.json` for news timeline, Git-synced) + filesystem cache
(`data/cache/`, `data/regime/`, `data/logs/`). Runs entirely locally on
Windows. No cloud, no API keys.

## Run it

```bash
python -m pip install -r requirements.txt
python run.py                      # serve at http://127.0.0.1:8000
python run.py --refresh            # run a full refresh once and exit
python run.py --news-refresh       # fast news-only ingest once and exit
python run.py --backfill           # seed the curated event timeline once and exit
python run.py --schedule-install   # install TWO Windows scheduled tasks (see scheduler.py below)
python run.py --schedule-remove    # remove both scheduled tasks
python run.py --schedule-status    # check whether the scheduled tasks are installed
python run.py --install-shortcut   # create the desktop launch.bat + .lnk (auto-opens browser)
python run.py --remove-shortcut    # remove the desktop launch.bat + .lnk
```

The first `/api/dashboard` load pulls data (slow, ~1 min); a full refresh
(POST `/api/refresh?full=true`) also runs the slower regime detection.

## Hard rules

- **Never fabricate market data.** Every number must trace to a fetched source
  (yfinance / SEC EDGAR / RSS) and be stamped with an "as of" timestamp. If a
  source is unavailable, mark it `null`/`—` — never invent a value.
- **Free, no-key sources only** (yfinance, MarketWatch / SCMP / Korea Herald
  RSS, SEC EDGAR via `curl_cffi`). The data layer (`app/market.py`) is
  designed so paid API keys can be plugged in later, but do not introduce a
  hard key dependency.
- **Keep the same fact consistent across views.** Numbers and company names
  that appear in multiple cards/tables must agree.
- **The 4 archived `ai_*.html` files are frozen reference material.** Do not
  modify them. They document the analysis framework and design system that
  seeded this tool (see below).

## Workflow conventions

These rules apply to every change, whether by a human or an AI agent.

- **Tooltips.** When card behavior changes, update the matching tooltip
  in the same change. Card-header tooltips live in
  `static/js/cards.js` under `CARD_TOOLTIPS` (the `initCardTooltips`
  function attaches them). Per-element tooltips use HTML `title=`
  attributes in `static/js/events.js` (badges) and `static/js/earnings.js`
  (recommendation, watch buttons). The reusable tooltip component is
  `static/js/tooltip.js` (`attachTooltip()`).
- **Summary log.** Every meaningful change must call
  `app.changelog.log_change(category, message)` so it is appended to
  `data/logs/summary-YYYY-MM-DD.md`. Categories: `scheduler`, `commit`,
  `shortcut`, `ui`, `doc`, `config`, `chore`. The file is gitignored
  under `data/*`; do not commit it. Read today's log with
  `app.changelog.read_day()`. The orchestrator decides what counts as
  "meaningful" — structural changes, user-visible behavior changes, and
  scheduler/install/remove events all qualify; routine fetches do not.
- **Commits.**
  - `data/events.json` changes are batched and committed once daily by
    the `MarketAnalysis-EventsCommit` scheduled task (17:00 local,
    `StartWhenAvailable=true` so missed days fire on next wake). Do not
    commit `events.json` from interactive sessions — let the scheduler
    own it.
  - Code, config, AGENTS.md, and docs changes are committed by the
    AI agent (or human) immediately after the change is verified
    (tests pass, no obvious regressions). Use a scope-prefixed message:
    `feat(scope): ...`, `fix(scope): ...`, `chore(scope): ...`,
    `docs(scope): ...`. Match the repo's existing commit style (see
    `Recent activity` below).
  - Never amend an existing commit unless explicitly asked.

## Architecture / module map

- `app/config.py` — tracked symbols, the live news feeds, paths, TTLs.
  **Add a new symbol here; feeds are English-edition RSS only.**
- `app/market.py` — quotes + bulk histories (yfinance only; the Stooq
  fallback was removed 2026-08-23 — bot-wall), cached in `data/cache/`.
- `app/spot.py` — **Real cash-market spot** for the Commodities card's Spot
  column. FRED public CSV for energy (WTI/Brent/Henry Hub NG, daily),
  Minted Metal public JSON for precious metals (LBMA gold/silver, twice-daily
  after the fix; CC BY 4.0 — attribution rendered in the card footer).
  Shared cache key (`spot_quotes`), `SPOT_TTL` (12h). One Minted Metal fetch
  covers all precious metals; FRED fetches are per-series. The snapshot
  emits a `commodities_map` keyed by the matching Yahoo futures ticker
  (CL=F, BZ=F, GC=F, NG=F, SI=F) so the Commodities renderer is oblivious
  to the FRED / Minted Metal source family. The Commodities card universe
  is intentionally narrow — just energy, gold, silver, NG, and bitcoin —
  so the spot map covers every row that has a free daily source. FRED's
  LBMA gold series was removed in January 2022 (IBA license change) — see
  https://news.research.stlouisfed.org/2022/01/ice-benchmark-administration-ltd-iba-data-to-be-removed-from-fred/.
- `app/indicators.py` — breadth, moving averages, realized vol, VIX signal.
- `app/regime.py` — subprocess wrapper around the reused `macro-regime-detector`
  skill (writes JSON to `data/regime/`); reports older than
  `REGIME_MAX_AGE_DAYS` (3) are served flagged stale.
- `app/risk.py` — the **risk-divergence engine** (crown jewel). Scores 9
  cross-asset signals (breadth %>50DMA, RSP/SPY concentration, VIX vs its own
  MA, credit HYG/LQD momentum, small caps IWM/SPY, SPY-TLT correlation, SPY
  trend/drawdown, AI-theme extension, valuation stretch) and outputs a
  GREEN/YELLOW/RED read with per-signal evidence, side-tagged fragility flags
  (`optimism`/`distress`), and flip conditions. RED fires on consensus optimism
  (+≥2 optimism-side flags), washout / trend break, or broad risk-off; GREEN
  when signals stay divided.
- `app/bottleneck.py` — serenity-style chokepoint framework mapped to proxy
  tickers; ranks every layer by average 40-day proxy ROC (most-stressed first).
- `app/ai_sentiment.py` — AI capex-cycle gauge: cohort momentum/breadth across
  the 8 `AI_CAPEX_COHORTS`, AI-news sentiment score, valuation stretch →
  −100..100 score with verdict (Euphoric → Cycle under pressure).
- `app/thirteenf.py` — SEC EDGAR 13F holdings for the 13 tracked
  `SUPERINVESTORS`. Weight-% only — dollar values deliberately never shown
  (EDGAR changed $ units across years). Declared User-Agent per SEC policy,
  paced requests, cached ~20 days (`THIRTEENF_TTL`).
- `app/analysis.py` — deterministic, NO-LLM weighted-vote synthesis of every
  engine above → stance (Risk-On / Neutral / Cautious / Risk-Off) + confidence
  capped by input coverage (weights documented in its docstring). Runs last in
  a full refresh and is logged to the `analysis_runs` table (Run Log card).
- `app/news.py` — market-event ingestion: curated seed loading + multi-feed
  English-edition RSS flow (`config.NEWS_FEEDS`). Live events must score >= `IMPORTANCE_THRESHOLD` (6.0,
  High/Critical — defined in `app/news.py`) AND be published within
  `NEWS_INGEST_WINDOW_HOURS` (48h, set in `app/config.py`) —
  no backlog backfill. Five-dimension tagging (category / actor / direction /
  region / impact).
- `app/seed_data.py` — the curated 2026 event timeline (1/1/2026 → now),
  hand-tagged and deduped from the frozen gauge file, Wikipedia, and
  researched news. Seed once via `python run.py --backfill` (idempotent).
- `app/store.py` — SQLite persistence for events: explicit tag columns,
  link + cross-source similarity dedupe, manual removal (delete event with
  confirmation / hide source).
- `app/earnings.py` — earnings watchlist for the tracked universe. Users can add/remove any ticker (including the default mega-caps), toggle visible columns, and see enriched pre-earnings data: price, daily %, 7-day %, 52-week high, forward PE, forward PEG, market cap, sector, and a local rule-based "AI" recommendation. Add/remove update the persisted list and patch the cache instead of rebuilding, so the UI stays fast.
- `app/scheduler.py` — Windows Task Scheduler helper. Installs **two** tasks
  (no admin required): `MarketAnalysis-DailyRefresh` (daily 09:00 **local**
  time, runs `--refresh`) and `MarketAnalysis-NewsRefresh` (every 4 hours,
  runs `--news-refresh`). Logs to `data/logs/`.
- `app/service.py` — refresh orchestration + dashboard aggregation.
- `app/lockfile.py` — cross-process refresh lock (`data/refresh.lock`); the
  server and the scheduled tasks never refresh simultaneously.
- `app/api.py` — FastAPI routes; `run.py` — entrypoint. A Host-header
  allowlist middleware (`config.ALLOWED_HOSTS`) blocks DNS rebinding.

### HTTP API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/dashboard` | Cached-or-refreshed dashboard payload |
| POST | `/api/refresh?full=` | Refresh data (+ regime detection when `full=true`) |
| GET | `/api/events?limit=` | List stored market events |
| DELETE | `/api/events?link=` or `?source=` | Delete one event, or all from a source |
| POST | `/api/events/suppress?source=` | Blocklist a source and purge its events |
| GET | `/api/analysis/history?limit=` | Logged synthesis runs (newest first) |
| GET | `/api/earnings` | Enriched earnings calendar |
| GET | `/api/earnings/validate?symbol=` | Validate a ticker before adding |
| POST / DELETE | `/api/earnings/watchlist?symbol=` | Add / remove a ticker |
| GET | `/api/regime` | Latest regime report |

Dashboard payload sections: `as_of`, `market` (indices / volatility / rates /
commodities / sectors), `indicators`, `risk`, `bottleneck`, `futures`,
`spot` (fed into the Commodities card via `spot.commodities_map`; not its
own card), `thirteenf`, `earnings`, `ai_sentiment`, `news`, `regime`,
`ai_analysis`, `events`.

## Tests & design docs

- `tests/` — pytest suites (`test_bottleneck.py`, `test_ai_sentiment.py`);
  run with `python -m pytest`.
- `docs/superpowers/` — plans/specs for the news-section overhaul and the
  AI-capex-cycle gauge.

## Skills

Reused (installed via `npx skills add`, live in `.agents/skills/` and
auto-loaded by opencode):

- `macro-regime-detector` — real Python (6-component cross-asset regime
  classification); run via `app/regime.py`. Works in yfinance-only mode.
- `serenity-chokepoint-investing` — chokepoint framework backing
  `app/bottleneck.py`.
- `macro-rates-monitor` — instruction-only (expects MCP tools); use its
  narrative approach, not its tool calls.

Custom (`.opencode/skills/`): `data-pull`, `news-filter`, `earnings-scan`,
`risk-divergence`.

## Playwright stealth guidance

Playwright is currently used only for frontend tests
(`tests/frontend/playwright.config.mjs`, `tests/frontend/*.spec.mjs`).
The app itself scrapes no JavaScript-rendered pages; data sources are
yfinance, RSS, and SEC EDGAR via `curl_cffi` with browser-TLS
impersonation (`app/thirteenf.py`). If you ever add browser automation
to the app or extend tests to scrape third-party sites, follow this
pattern to avoid bot detection:

- Use `playwright.chromium.launch(headless=True, channel="chrome")`
  rather than the bundled Chromium when possible — production Chrome's
  TLS fingerprint is less bot-flagged.
- Pass `--disable-blink-features=AutomationControlled` via
  `chromium.launch(args=[...])` to suppress the `navigator.webdriver`
  flag.
- Override the user agent to a real recent Chrome/Firefox string
  (rotating per session if scraping multiple sites).
- Realistic viewport (`{width: 1280, height: 800}` or
  `{width: 1920, height: 1080}`), realistic locale (`en-US`) and
  timezone (`America/New_York`).
- Disable webdriver flag via `addInitScript`:
  ```js
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });
  ```
- Avoid detection tells: don't navigate faster than a human could
  click; add small randomized delays between actions; respect
  `robots.txt` and rate-limit headers; never reuse the same session
  across unrelated sites.
- For the existing test suite (`tests/frontend/`), these are not
  needed — tests run against `http://127.0.0.1:8000` with no anti-bot
  middleware.

## Gauge gotcha (legacy, still relevant)

In the archived `ai_market_sentiment_gauge.html`, a card's `col` is fixed for
layout; the signed `weight` is what moves the needle. The new risk engine
encodes the same intuition in code (`app/risk.py`): divided signals = healthy,
unanimous optimism = fragility. The gauge's ~70 events are now also part of
the news timeline seed (`app/seed_data.py`), with direction mapped from its
bear/neutral/bull columns.

## Section-to-code map (audit 2026-08-26)

Each dashboard card's renderer + payload key, for quick lookup during audits.

| Card (data-card) | Body element | Renderer (cards.js / *) | Payload key | Refresh |
|---|---|---|---|---|
| `risk` | `#riskBody` | `renderRisk` | `risk` | yes |
| `ai-sentiment` | `#aiSentimentBody` | `renderAISentiment` | `ai_sentiment` | yes |
| `analysis` | `#analysisBody` | `renderAnalysis` + async `loadAnalysisHistory` | `ai_analysis` + `/api/analysis/history` | yes |
| `fragility` | `#fragilityList` | rendered inside `renderRisk` | (sub-card of risk) | no (sub-card) |
| `regime` | `#regimeBody` | `renderRegime` | `regime` | yes |
| `indicators` | `#indicatorBody` | `renderIndicators` | `indicators` | yes |
| `indices` | `#indicesBody` | `renderIndices` | `market.indices` + `futures.index_futures` | yes |
| `commodities` | `#commoditiesBody` | `renderCommodities` | `market.commodities` + `spot.commodities_map` + `futures.commodities` | yes |
| `rates` | `#ratesBody` | `renderQuotes` | `market.rates` | yes |
| `breadth` | `#breadthChart` | `renderBreadthSectorsChart` | `indicators.breadth` | yes |
| `breadth-ai` | `#breadthAIChart` | `renderBreadthAIChart` | `indicators.breadth_ai` | yes |
| `bottleneck` | `#bottleneckBody` | `renderBottleneck` | `bottleneck` | yes |
| `earnings` | `#earningsBody` | `renderEarnings` (earnings.js) | `earnings` | yes |
| `thirteenf` | `#thirteenfBody` | `renderThirteenf` | `thirteenf` | yes |
| `events` | `#newsBody` | `renderNews` (events.js) | `events` | yes |

Coverage badges (`applyCoverageBadge` in cards.js) and vintage stamps
(`applyVintageStamp`) attach on every section refresh. The `fragility` card
is intentionally excluded from both — it is a derived sub-card of risk and
has no independent payload key.

## Backend module quick-reference

| Module | Public entry points | Tested in |
|---|---|---|
| `app/config.py` | symbol/feed dicts, TTLs, engine knobs | — |
| `app/market.py` | `get_quotes`, `get_history`, `get_histories_bulk`, `build_market_snapshot`, `build_futures_snapshot` | `test_market_cache.py` |
| `app/indicators.py` | `roc_at`, `pct_above_ma`, `breadth_pct_above_ma`, `breadth_pct_above_ma_at`, `vix_ma_ratio_at`, `vix_signal`, `trend_state`, `realized_vol`, `compute_indicators` | `test_indicators.py` |
| `app/regime.py` | `get_regime`, `run_regime_detection` | `test_api_contract.py`, `test_regime_stale.py` |
| `app/risk.py` | `compute_risk` | `test_risk_gates.py` |
| `app/bottleneck.py` | `bottleneck_read`, `all_proxy_symbols`, `BOTTLENECK_CATEGORIES` | `test_bottleneck.py` |
| `app/ai_sentiment.py` | `compute_ai_sentiment`, `compute_ai_news_sentiment`, `compute_valuation_flag` | `test_ai_sentiment.py` |
| `app/thirteenf.py` | `build_thirteenf`, `issuer_ticker_map`, `_norm_issuer` | — (network-heavy, isolated) |
| `app/analysis.py` | `build_analysis` | `test_analysis_golden.py` |
| `app/news.py` | `analyze`, `fetch_and_store`, `seed_events`, `rate_impact` | `test_news_analyze.py` |
| `app/seed_data.py` | `SEED_EVENTS` | — (pure data) |
| `app/store.py` | `upsert_events`, `delete_event`, `delete_events_by_source`, `update_event_tags`, `list_events`, `suppress_source`, `log_analysis_run`, `get_analysis_history`, `save_json`, `load_json` | `test_store.py` |
| `app/earnings.py` | `earnings_calendar`, `validate_symbol`, `add_ticker`, `remove_ticker`, `lookup_ticker`, `earnings_force_refresh` | `test_earnings_rec.py` (helpers) |
| `app/scheduler.py` | `install_task`, `remove_task`, `status` | — (Windows-only) |
| `app/service.py` | `get_dashboard`, `refresh_market`, `refresh_news`, `refresh_earnings`, `refresh_regime`, `refresh_all`, `backfill_news`, `_coverage_counts`, `_attach_coverage` | `test_service_coverage.py`, `test_api_contract.py` |
| `app/api.py` | FastAPI app + middleware | `test_api_contract.py` |
| `app/lockfile.py` | `refresh_lock`, `RefreshBusy` | `test_lockfile.py` |
| `app/run.py` | CLI entrypoint | — |

## Known test gaps (after audit)

- `app/thirteenf.py` has no isolated tests (network-heavy; tested indirectly via API contract).
- `app/scheduler.py` has no tests (Windows-only `schtasks.exe` wrapper; would need a mock).
- `app/run.py` CLI flags are not exercised by tests.
- `app/seed_data.py` is pure data (hand-tagged events).

## Key quirks

- Yahoo tickers for Treasury yields (`^TNX`, `^FVX`, `^IRX`, `^TYX`) are
  yield×100 (4.5 = 4.5%).
- yfinance can rate-limit or break; there is **no secondary source** — the
  former Stooq CSV fallback was removed (2026-08-23) because Stooq now serves
  a JavaScript bot-wall to non-browser clients. Failed fetches surface as
  `null` and are never cached.
- Live news is a set of English-edition RSS feeds (`NEWS_FEEDS` in
  `app/config.py`: MarketWatch, SCMP China, SCMP Business, Korea Herald) with a
  48h ingest window (`NEWS_INGEST_WINDOW_HOURS`); only High/Critical items are
  stored. Cross-source dedupe (Jaccard >= 0.6 / fuzzy >= 0.85 within 2 days)
  merges same-story items from different publishers; non-English feeds are
  excluded because the tokenizer + scorer are English-only.
- Caching TTLs live in `app/config.py` (`QUOTE_TTL`, `HISTORY_TTL`); bump them
  if you hit rate limits, or clear `data/cache/` to force fresh pulls.
- Each dashboard card has a vintage stamp showing its data age, in addition
  to the global **Refresh** button. The Analysis card has no per-card ↻;
  its `/api/analysis/history` history loads automatically on first render
  and after every global refresh.
- The Earnings watchlist supports show/hide columns and validates tickers via
  `/api/earnings/validate` before adding.
- Quotes derive price/change from daily close history, not quote endpoints —
  yfinance `fast_info` is broken in current versions (`app/market.py`).
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
- Cross-source event dedupe merges different links into one row and escalates
  impact to Critical if either source scored Critical.
- Card order/layout persists per-browser in localStorage (`dashLayout`);
  "reset layout" restores defaults.
- The daily scheduled refresh fires at 09:00 **local time**, not ET.

## Recent activity (last 10 commits)

`git log --oneline -10` is authoritative; the snapshot is here for fast scan:

| When | Scope | Commit | Note |
|---|---|---|---|
| 2026-08-31 | docs(agents) | `5d951e5` | document workflow conventions + Playwright stealth |
| 2026-08-31 | feat(ui) | `d9c7b6f` | 30-min auto-refresh with visibility-pause |
| 2026-08-31 | feat(scheduler+cli) | `eef4cac` | per-day changelog, EventsCommit task, desktop-shortcut CLI |
| 2026-08-31 | feat(earnings+ai-capex) | `783b508` | star highlight, news tag cleanup, Memory cohort expansion |
| 2026-08-30 | chore(news) | `7ef3351` | purge SCMP China / SCMP Business / Korea Herald entries from history |
| 2026-08-30 | polish | `4498c00` | fragility tooltip, full-date as_of, single global refresh, news feed governance |
| 2026-08-30 | docs | `3f67219` | refactor metrics + migration guide + runnable example |
| 2026-08-30 | feat(frontend) | `a469326` | tooltip system + global refresh + news filter chips |
| 2026-08-30 | feat(news) | `6a6b714` | finance-relevance scoring + source governance + audit tool |
| 2026-08-30 | chore(refactor) | `81bccdf` | Strategy/Repository/Adapter/Factory patterns + test-gap closure |
