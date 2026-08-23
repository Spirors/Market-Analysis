# AGENTS.md

## What this is

A local webapp for macro-trend market analysis: regime classification,
indicators, bottleneck identification (serenity-style chokepoint investing),
news filtering, and a trend-shift **risk-divergence engine**. It serves a
dashboard in the browser and pulls market data from free, no-key sources.

Stack: Python 3.12 + FastAPI + uvicorn backend, vanilla HTML/CSS/JS frontend
(Chart.js from CDN), SQLite for events, JSON for cached data. Runs entirely
locally on Windows. No cloud, no API keys required.

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
```

The first `/api/dashboard` load pulls data (slow, ~1 min); a full refresh
(POST `/api/refresh?full=true`) also runs the slower regime detection.

## Hard rules

- **Never fabricate market data.** Every number must trace to a fetched source
  (yfinance / Stooq / RSS) and be stamped with an "as of" timestamp. If a
  source is unavailable, mark it `null`/`—` — never invent a value.
- **Free, no-key sources only** (yfinance, Stooq, MarketWatch RSS, SEC EDGAR,
  public feeds). The
  data layer (`app/market.py`) is designed so paid API keys can be plugged in
  later, but do not introduce a hard key dependency.
- **Keep the same fact consistent across views.** Numbers and company names
  that appear in multiple cards/tables must agree.
- **The 4 archived `ai_*.html` files are frozen reference material.** Do not
  modify them. They document the analysis framework and design system that
  seeded this tool (see below).

## Architecture / module map

- `app/config.py` — tracked symbols, the single live news feed, paths, TTLs.
  **Add a new symbol here; the live feed is intentionally a single source.**
- `app/market.py` — quotes + bulk histories (yfinance only; the Stooq
  fallback was removed 2026-08-23 — bot-wall), cached in `data/cache/`.
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
- `app/news.py` — market-event ingestion: curated seed loading + a single
  MarketWatch RSS flow. Live events must score >= `IMPORTANCE_THRESHOLD` (6.0,
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
`thirteenf`, `earnings`, `ai_sentiment`, `news`, `regime`, `ai_analysis`,
`events`.

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

## Gauge gotcha (legacy, still relevant)

In the archived `ai_market_sentiment_gauge.html`, a card's `col` is fixed for
layout; the signed `weight` is what moves the needle. The new risk engine
encodes the same intuition in code (`app/risk.py`): divided signals = healthy,
unanimous optimism = fragility. The gauge's ~70 events are now also part of
the news timeline seed (`app/seed_data.py`), with direction mapped from its
bear/neutral/bull columns.

## Key quirks

- Yahoo tickers for Treasury yields (`^TNX`, `^FVX`, `^IRX`, `^TYX`) are
  yield×100 (4.5 = 4.5%).
- yfinance can rate-limit or break; there is **no secondary source** — the
  former Stooq CSV fallback was removed (2026-08-23) because Stooq now serves
  a JavaScript bot-wall to non-browser clients. Failed fetches surface as
  `null` and are never cached.
- Live news is a single MarketWatch feed with a 48h ingest window
  (`NEWS_INGEST_WINDOW_HOURS` in `app/config.py`); only High/Critical items
  are stored, so the timeline doesn't fill with low-signal headlines.
- Caching TTLs live in `app/config.py` (`QUOTE_TTL`, `HISTORY_TTL`); bump them
  if you hit rate limits, or clear `data/cache/` to force fresh pulls.
- Each dashboard card has a small ↻ refresh icon to re-fetch `/api/dashboard`
  and re-render just that section, in addition to the global **Refresh** button.
- The Earnings watchlist supports show/hide columns and validates tickers via
  `/api/earnings/validate` before adding.
- Quotes derive price/change from daily close history, not quote endpoints —
  yfinance `fast_info` is broken in current versions (`app/market.py`).
- Index futures additionally have no fallback at all; failed futures stay
  `null` by design.
- No environment variables anywhere — every knob lives in `app/config.py`.
- `store.init_db()` rebuilds any legacy `events` table lacking tag columns
  (destructive one-time migration).
- Cross-source event dedupe merges different links into one row and escalates
  impact to Critical if either source scored Critical.
- Card order/layout persists per-browser in localStorage (`dashLayout`);
  "reset layout" restores defaults.
- The daily scheduled refresh fires at 09:00 **local time**, not ET.
