# API

HTTP routes and dashboard payload shape. Read this **on demand** when a task
touches an endpoint or the payload contract — not part of mandatory
session-start reading (see `AGENTS.md`).

## HTTP API

Routes are declared in `app/api.py`. FastAPI auto-generates OpenAPI at
`/openapi.json`.

| Method        | Path                              | Purpose                                                                                                                                                                                                  |
| ------------- | ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET           | `/`                                | Serves `static/index.html` (the dashboard).                                                                                                                                                              |
| GET           | `/static/<path>`                  | Static files (CSS, JS, assets) — `app.mount("/static", StaticFiles(...))`.                                                                                                                                |
| GET           | `/api/dashboard`                  | Cached-or-refreshed dashboard payload. Reads `data/dashboard.json`; falls back to `refresh_all()` on staleness.                                                                                          |
| POST          | `/api/refresh?full=`              | Refresh data + news. `full=true` also runs regime detection. Returns the refreshed dashboard payload; if another process holds the refresh lock, returns `{"error": "another refresh is already running"}`. |
| GET           | `/api/meta`                       | Read-only frontend label metadata derived from `app/config.py` (ticker labels + tracked symbol groups).                                                                                                  |
| GET           | `/api/events?limit=`              | List stored market events (newest first, default `limit=500`).                                                                                                                                           |
| DELETE        | `/api/events?link=` or `?source=` | Delete one event (by `link`) or every event from a source. Mutually exclusive — 400 if both provided; 400 if neither.                                                                                    |
| POST          | `/api/events/tags`                | Add/remove user tags on one event. Body: `{"link": "...", "add": ["tag"], "remove": ["tag"]}`. The auto-tag "ai" cannot be removed manually. Returns the updated event + full list. 404 if `link` unknown. |
| POST          | `/api/events/suppress?source=`    | Blocklist a source and purge its events.                                                                                                                                                                  |
| GET           | `/api/analysis/history?limit=`    | Logged synthesis runs (newest first, default `limit=20`).                                                                                                                                                |
| GET           | `/api/portfolios`                 | Load portfolios + enrich with live prices via `market.get_quotes`.                                                                                                                                        |
| POST          | `/api/portfolios?name=`           | Create a portfolio. `name` required; 400 on empty. Returns `{id, portfolio}`.                                                                                                                            |
| DELETE        | `/api/portfolios/{pid}`           | Delete a portfolio (204 No Content on success; 404 if unknown).                                                                                                                                          |
| POST          | `/api/portfolios/{pid}/holdings?symbol=&shares=&total_cost=` | Add a holding to a portfolio. Returns the new holding (with live price enrichment via `market.get_quotes`). 404 if portfolio unknown; 400 on bad input. |
| PUT           | `/api/portfolios/{pid}/holdings/{symbol}?shares=&total_cost=` | Edit a holding's shares and/or total_cost. Returns the updated holding. 404 if either unknown.                                                                                                            |
| DELETE        | `/api/portfolios/{pid}/holdings/{symbol}` | Remove a holding (204 No Content; 404 if unknown).                                                                                                                                                        |
| POST          | `/api/portfolios/{pid}/cash?label=&total_cost=&total_value=` | Add the cash row to a portfolio (one per portfolio). Returns the new cash row. 400 if a cash row already exists; 404 if portfolio unknown.                                                                  |
| PUT           | `/api/portfolios/{pid}/cash?label=&total_cost=&total_value=` | Edit the cash row. `label` selects the row (one per portfolio, so usually null). Returns the updated cash row. 404 if no cash row exists.                                                                    |
| DELETE        | `/api/portfolios/{pid}/cash`      | Remove the cash row. Returns `{"removed": true}`; 404 if no cash row exists.                                                                                                                              |
| PUT           | `/api/portfolios/columns/{section}` | Persist column order + visibility for a section. `section` is either the default `"portfolio"` or a per-portfolio `"portfolio.<pid>"` (404 if pid unknown). Body: `{"order": [...], "visibility": {...}}`. |
| GET           | `/api/portfolios/validate?symbol=` | Validate a ticker before adding (wraps `app.validation.validate_symbol`). Returns `{valid, symbol, name, sector, ...}`.                                                                                       |
| GET           | `/api/regime`                     | Latest regime report (delegates to `app.regime.get_regime`).                                                                                                                                              |
| POST          | `/api/bottleneck/categories/reorder` | Reorder bottleneck categories. Body: `{"order": ["canonical", ...]}`. The new order must be a permutation of the canonical category names. Returns `{"order": [...]}`. 400 on invalid input.           |
| PUT           | `/api/bottleneck/categories/{name}?new_name=` | Rename a bottleneck category's display name. `{name}` is the canonical name (URL-encoded). `new_name` is the new display name. Returns `{"original": "...", "display": "..."}`. 400 on empty `new_name`; 404 if `name` unknown. |
| POST / GET    | `/api/shutdown`                   | Schedule `os._exit(0)` ~300 ms out (called by the dashboard's `pagehide` / `beforeunload` beacons — keeps the desktop launcher from leaking a lingering cmd window). The next page's `pageshow` beacon to `/api/cancel-shutdown` aborts the exit, so F5 / link-nav / bfcache restore never kill the server. |
| POST / GET    | `/api/cancel-shutdown`            | Cancel a pending `/api/shutdown` exit. Idempotent. Sent by the dashboard on `pageshow` so a page reload survives without taking down the local server.                                                   |

### Removed endpoints

The following were removed with the Earnings watchlist section on
2026-09-06. They are listed here so a stale doc reference can be cleaned
up — do **not** re-add them:

- `GET /api/earnings` (replaced by the per-holding `next_earnings` column
  in `GET /api/portfolios`)
- `GET /api/earnings/validate` (replaced by `GET /api/portfolios/validate`)
- `POST/DELETE /api/earnings/watchlist` (no replacement — earnings-derived
  columns are computed from the user's portfolio holdings directly)

## Dashboard payload sections

Top-level keys produced by `service.get_dashboard()` (refresh path) or
read from `data/dashboard.json` (cache path), then enriched by
`service._enrich()` on every serve.

- `as_of` — global ISO-8601 timestamp of the last full refresh.
- `market` — `{indices, volatility, rates, commodities, sectors}`. Each is
  `{symbol: {price, change, pct_change}}` where `price` is the daily close
  (yfinance `fast_info` is broken in current versions; the renderer
  derives from 7d history). Null on fetch failure.
- `futures` — `{index_futures: [...], commodities: [...]}`. Each item has
  `{last, change, pct_change}` (or null on failure).
- `spot` — real cash-market spot map for the Commodities card's Spot
  column. FRED public CSV (energy) + Minted Metal public JSON (precious
  metals), keyed by the matching Yahoo futures ticker via
  `spot.commodities_map`. Fed into the Commodities renderer; not its own
  card. Per-row `source_date` carries provenance.
- `indicators` — `{breadth: {breadth_pct, detail}, breadth_ai: {detail},
  spy: {trend, realized_vol_annual_pct}, vix: {level, signal}}`.
- `risk` — `app/risk.compute_risk()` output: `{signals: [9], verdict,
  fragility_flags: [...], flip_conditions: [...], ...}`. RED fires on
  consensus optimism (>=2 optimism-side fragility flags), washout / trend
  break, or broad risk-off; GREEN when signals stay divided.
- `bottleneck` — serenity-style chokepoint map (`{categories: [{streams:
  {upstream/midstream/downstream: {layers: [...]}}}]}`). Each layer
  carries `proxy_40d_roc_pct`.
- `thirteenf` — `{funds: [{name, holdings: [...]}]}`. Weight-% only;
  dollar values deliberately never shown (EDGAR changed $ units across
  years).
- `ai_sentiment` — AI capex-cycle gauge: `{score, verdict, news: {tone,
  note}, valuation: {forward_pe, forward_peg, stretched, note},
  cohorts: [...], spread_pct, flip_conditions, as_of}`. Recomputed on
  every serve from current events.
- `portfolios` — `{pid: portfolio}` keyed map (not the full
  `portfolios.json` state — just the inner dict so the renderer can
  consume `data.portfolios` directly). Each portfolio has
  `{id, name, holdings: [...]}` with enriched `last_price`, `pct_daily`,
  `pct_7d`, `pct_30d`, `next_earnings`, `marketcap`, `forward_pe`,
  `forward_peg`, `high_52w`, `sector`.
- `column_order` / `column_visibility` — per-section prefs (keyed
  `"portfolio"` for the default + `"portfolio.<pid>"` for per-portfolio
  overrides).
- `news` — `{feeds_checked, per_feed: {source: {http_status, parsed,
  kept, ...}}, collected, inserted}` from the most recent news refresh.
- `regime` — `{regime: {regime_label, regime_description, confidence,
  portfolio_posture}, composite: {composite_score, zone, guidance,
  component_scores}, transition_probability: {probability_range}}`.
  Reports older than `REGIME_MAX_AGE_DAYS` (3) are flagged stale.
- `ai_analysis` — `{stance, confidence, headline, bullets, divergences,
  watch, generated_at}`. Sourced from the synthesis-run log between
  refreshes.
- `events` — `[event, ...]` from `store.list_events(limit=500)`. Each
  event: `{title, link, summary, source, published, tags, impact,
  direction, category, actor, region, first_seen, updated_at, ...}`.
- `coverage` — `{section: {ok, total}}` from
  `service._coverage_counts()`. The frontend renders a muted "n/m" badge
  only when a section is incomplete.
- `vintage` — `{section: iso_ts}` per-card data-age stamps (separate from
  the global `as_of`). The Portfolio card's vintage is bumped by
  `_patch_dashboard_cache` after every mutation.
