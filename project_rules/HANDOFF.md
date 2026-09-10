# Handoff

`Last updated`: 2026-09-10 23:00 UTC (News section overhaul — commit
`4734cc9`. Three coordinated changes shipped as one feature commit:
Week/Month grouping toggle on the timeline toolbar (both views,
persisted per browser via `tlGroupingMode` + `tlSelectedMonth`);
`user_edited` lock on news events so manual tag edits survive RSS
refresh; AI capex-cycle gauge auto-refreshes after a manual AI tag
via the new `ai_sentiment` field in `POST /api/events/tags`. Targeted:
443 backend + 7 new Playwright pass. `data/events.json` NOT committed
— scheduler-owned. SESSION_LOG + DECISIONS + archive file at
`archive/sessions/2026-09-10-news-section-overhaul-week-month-user-edit-ai-gauge.md`
and `archive/decisions/news-user-edited-lock-2026-09-10.md`. **Earlier
(2026-09-09):** AI gauge lookback window = 30 days + tooltip +
one-shot retag; news heuristic keyword expansion. **Earlier
(2026-09-08):** Bottleneck reorder + rename shipped; test isolation
autouse landed; scheduler + VBS launcher docs audit closed; holdings
row reorder + "↺ Default order" restored.)

## Current state

**News timeline gained three coordinated features** (commit `4734cc9`):

- **Week / Month grouping toggle.** Both views, persisted per browser
  via `tlGroupingMode` + `tlSelectedMonth` localStorage keys (week path
  unchanged at `tlSelectedWeek`). The toggle is a segmented control
  inside `.tl-toolbar`; the period dropdown adapts its label and options
  to the active mode. Implemented via a generic `buildGroups(items, mode)`
  in `static/js/events.js`. Month buckets use `YYYY-MM`; the undated
  bucket is preserved.
- **`user_edited` lock on news events.** New `bool` field on every
  event row, set to `True` by `update_event_tags()`. Once set,
  `upsert_events()` skips overwrite entirely on RSS refresh (only
  `updated_at` is touched) — manual tag edits survive manual +
  scheduled refreshes. Auto-AI-tag is still applied on insert for new
  rows; user edits win on existing rows.
- **AI capex-cycle gauge auto-refresh after a manual AI tag.** The
  `POST /api/events/tags` response now includes a recomputed
  `ai_sentiment` payload. The endpoint recomputes inside a defensive
  `try/except` so a transient market failure returns `ai_sentiment: null`
  rather than 500-ing the tag save. The frontend re-renders only when
  the edit actually touched `"ai"` — other tag edits skip the gauge
  refresh (cheap `O(1)` check).

**Bottleneck section is interactive** — still green from prior session.
↑ / ↓ chevrons + ✎ rename pencil, prefs in `data/bottleneck_prefs.json`,
canonical `BOTTLENECK_CATEGORIES` untouched.

**From prior sessions — still green and unaffected:**

- **P0 perf fix** (commit `25e5c06`). 3 s add/delete latency → <500 ms
  via `_patch_dashboard_cache` structural-only patch + symbol-aware
  `market.get_quotes` + optimistic UI in `static/js/portfolio.js`.
- **Earnings-date column fix** (commit `f32adeb`).
  `_extract_next_earnings` handles yfinance 1.6.0's `datetime.date`
  shape. Cached holdings need a one-time manual Refresh to repopulate
  (per the P0 fix's "patch minimally" rule).
- **P1** (server lifecycle) and **P2** (data integrity) cleared by the
  audit.
- **Audit follow-up closure** — every P3..P7 follow-up item from
  `docs/logs/audit-2026-09-07.md` addressed in prior session.

## Top 3 next actions

1. **Phase 3 backlog.** News overhaul landed; Bottleneck reorder +
   rename shipped earlier. Roadmap Phase 3 has two completed entries.
   Next candidates: any remaining Phase 3 item the user requests, or
   a new feature. No fresh backlog has been started.
2. **Module-graph discipline** — when extending events.js ↔ cards.js
   imports, do NOT add a `?v=…` query to one side without the other.
   The JS spec creates a fresh module record per URL; a mismatch
   silently duplicates the module and splits its state (this is
   exactly what bit the news overhaul — see the entry in
   `project_rules/DECISIONS.md` and the verification log in
   `archive/sessions/2026-09-10-news-section-overhaul-…md`).
3. **Archive `data/logs/summary-2026-09-10.md`** (gitignored daily
   changelog) once the session is well past — these files grow fast
   and are local-only per `AGENTS.md`. Not urgent.

## Blockers

None. `data/events.json` has unstaged scheduler timestamp updates —
per `project_rules/RUNBOOK.md` the `MarketAnalysis-EventsCommit` task owns
that file, not interactive sessions, so they will be picked up at the
next 17:00 scheduled run.

## Notes for the next session

- **`app/validation.py` is the only surviving earnings artifact.** It's
  the slim `validate_symbol` helper extracted from the old
  `app/earnings.py` — keeps the yfinance history-primary /
  Ticker.info-fallback ordering per the Phase 2 path diff. Used by
  `portfolio.add_holding` and by `app/api.portfolio_validate`. Tested in
  `tests/test_validation.py` (not `tests/test_earnings.py`, which was
  renamed in 2026-09-06).

- **Portfolio table is back to 16 columns.** `static/js/portfolio.js
  PORTFOLIO_COLUMNS` is star + 7 base portfolio columns + 8
  restored earnings-derived columns. The 8 restored columns come from
  `enrich_portfolios` (260-day bulk history for pct_7d/ pct_30d/
  high_52w, per-symbol Ticker.info + calendar for sector / marketcap /
  forward_pe / forward_peg / next_earnings). Anyone adding new columns:
  extend `enrich_portfolios` first so the data is available.

- **Bottleneck prefs live in `data/bottleneck_prefs.json`** (separate from
  `BOTTLENECK_CATEGORIES`). The canonical list is the source of truth;
  prefs are layered on at serve time. Empty/invalid `prefs["order"]`
  falls back to canonical order (graceful degradation if a category is
  added/removed). `category_original` is always included in the output
  so the frontend can track canonical names after renames.

- **Per-portfolio column state keys are `pfVisible.portfolio.<pid>` /
  `pfOrder.portfolio.<pid>` / backend `column_order['portfolio.<pid>']`.**
  The bare `portfolio` key remains the default that new portfolios
  inherit. `tickerTable.js _assertValidSection` accepts both canonical
  `"portfolio"` and the `"portfolio.*"` prefix; passing anything else
  throws immediately (per the project's shared-component persistence
  rule).

- **Columns dropdown lives INSIDE the expanded portfolio** now
  (`controlsMode: 'columnsOnly'`). The card-header dropdown is gone —
  there's no single "active" portfolio. The bespoke +Add holding /
  +Add cash buttons stay in the portfolio body alongside the new
  dropdown.

- **Cold-cache load is slower than last week.** `enrich_portfolios`
  does up to N+1 HTTP calls (one bulk history + one Ticker.info per
  unique symbol). With ~10 holdings this is ~10-15 s on first load;
  the 5-min lru_cache amortizes repeated reads. If UX becomes a
  problem, the next step is an async
  `/api/portfolios/fundamentals/{pid}` endpoint that fires only on
  portfolio expand.

- **The Portfolio rename CSS shift fix lives in JS, not CSS.** The
  match between input width and span width comes from
  `startEditForPid` reading the span's box width and setting
  `inp.style.minWidth`. The CSS `field-sizing: content` + `min-width:
  8ch` stays as the sizing mechanism. Any future attempt to move
  sizing into CSS alone will re-introduce the shift — CSS can't
  express "match a sibling's box width".

- **The auto-reap watchdog (`app/lifecycle.py`)** is the runtime backstop
  for any future stuck-process regression. Agent terminal launches MUST
  use `--auto-reap 60` (or set
  `$env:MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S=60`). Documented in
  `project_rules/RUNBOOK.md` §Step 3a.

- **Playwright frontend tests need a static server on port 8123**
  (`python -m http.server 8123 --bind 127.0.0.1` from the repo root).
  Reap before the turn ends per the runbook — pytest's playwright
  harness auto-starts/reuses the server but interactive runs need it
  started manually and reaped explicitly.

- **Default pytest run is the full suite now.** Last session the
  default excluded `tests/test_thirteenf.py` (network-heavy, historical)
  and `tests/test_service_coverage.py` (long-running, historical).
  Both are now cleaned up and pass — the audit found the
  `test_service_coverage.py` exclusion had been hiding 5 broken tests
  for months. Re-include both going forward.

- **Four frontend test files were DELETED earlier (2026-09-06)** as no
  longer applicable: `earnings.spec.mjs`, `earnings-watch.spec.mjs`,
  `watchlist-add.spec.mjs`, `section-position.spec.mjs`. They
  exercised removed functionality.
