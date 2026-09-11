# Handoff

`Last updated`: 2026-09-11 19:25 UTC (Portfolio follow-up fixes —
1 commit `bfb118f` addressing two regressions from the morning's
session: (1) Portfolio live-price columns are now populated on every
refresh (the cooldown skip that reused the unenriched cached payload
is removed for portfolios; `enrich_portfolios` always runs). Breadth
— AI proxies cooldown is unchanged. (2) ▲/▼ reorder now mirrors the
new order into the closure's `p.holdings` AND the module-level
`portfolioData.portfolios[pid].holdings` before the POST, so
collapse + expand preserves the new order without a refresh. Backend:
104 passed. Frontend: 19 passed (15 portfolio-holdings-reorder + 4
refresh-cooldown). SESSION_LOG entry at the bottom; archive at
`archive/sessions/2026-09-11-followup-fix-prices-collapse-reorder.md`.)

**Earlier (2026-09-11, same day):** Portfolio holdings reorder
persistence + per-section refresh cooldowns — 6 commits across two
parallel lanes. Backend: new `POST /api/portfolios/<pid>/holdings/reorder`
endpoint + `app.config.REFRESH_SECTION_COOLDOWNS` gating
`refresh_market()` on cached `vintage` stamps. Frontend: ▲/▼ persists
via the new endpoint, ▲/▼ greyed out when `sort.key !== "default"`,
`applyCooldownBadge` + refresh-button hover tooltip showing
"Last refresh: X min ago — Next refresh available in: N min".
Backend: 104 passed (10 portfolio + 4 api_contract + 6 service_cooldown
+ existing). Frontend: 17 passed (extended portfolio-holdings-reorder +
new refresh-cooldown). SESSION_LOG entry at the bottom; archive at
`archive/sessions/2026-09-11-portfolio-reorder-persistence-refresh-cooldowns.md`. (Note: the Portfolio portion of the per-section cooldown was removed later same day; see the follow-up entry above and DECISIONS.md "Portfolio enrichment always runs (no cooldown skip) — 2026-09-11".)
**Earlier (2026-09-10, same day):** Two stale-UI bug fixes from the
2026-09-06 earnings-watchlist removal: risk tooltip signal count
9 → 7 (NOT 8 — user caught the miscount; the 8th strategy
`_signal_ai_theme` only produces fragility flags, not a named signal);
AI capex-cycle gauge dead Valuation cell removed
(`compute_valuation_flag` was already gone, the cell always rendered a
dashline). 1 file touched: `static/js/cards.js`. No backend changes; no
new tests; the cell removal was reversed later today by the AI Valuation
feature. Changelog at `data/logs/summary-2026-09-10.md`.
**Earlier (2026-09-10):** News section overhaul — two follow-up
corrections to commit `4734cc9` landed in commit `fa2c976`:
1) every pill on a news row is now editable (fixed-dimension pills
open a `<select>`-based popover that overrides the column via the new
`POST /api/events/dimensions` endpoint; user / `ai` tags keep the
free-text rename popover); 2) the AI capex-cycle gauge no longer
auto-refreshes on tag edits — the user clicks the global Refresh
button to pick up their changes. Backend: 459 passed (+16). Frontend
news section: 12 passed (+5). `data/events.json` NOT committed —
scheduler-owned. SESSION_LOG + DECISIONS + archive file at
`archive/sessions/2026-09-11-news-overhaul-followups-editable-tags-no-auto-ai-gauge.md`
and `archive/decisions/news-dimension-edit-endpoint-2026-09-11.md`.
**Earlier (2026-09-10, earlier):** News section overhaul (commit
`4734cc9`) —
auto-refresh was wrong; corrected by today's commit).
**Earlier (2026-09-09):** AI gauge lookback window = 30 days + tooltip +
one-shot retag; news heuristic keyword expansion.
**Earlier (2026-09-08):** Bottleneck reorder + rename shipped; test
isolation autouse landed; scheduler + VBS launcher docs audit closed;
holdings row reorder + "↺ Default order" restored.)

## Current state

## Current state

**Portfolio holdings reorder now persists to `data/portfolios.json`**
(commits `9f6eac1` + `4392797`). The new
`POST /api/portfolios/<pid>/holdings/reorder` endpoint mirrors the
existing portfolios/bottleneck reorder pattern (dict-key insertion
order, `save_portfolios` + `_patch_dashboard_cache`). Cash rows stay
last. Frontend `tickerTable.js:moveRow` POSTs optimistically and
reverts on error.

**▲/▼ greyed out when view is in column-header sort** (commit
`b0e9789`). Buttons render with `disabled` + tooltip `"Reset to
default order (↺) before reordering rows"` when `sort.key !== "default"`.
`moveRow` also has a defensive guard.

**Per-section refresh cooldowns** (commits `5e00482` + `040c409`).
Portfolio: 15 min (`vintage["portfolios"]`). Breadth — AI proxies:
30 min (the card displays `vintage["indicators"]`, so the indicators
computation is the one that's skipped). `app.service.refresh_market()`
reads the cached `vintage` stamp at the top and reuses the cached
section data when within cooldown; unrelated sections (risk, bottleneck,
ai_sentiment) still run. Result payload gains a
`cooldown_skip: list[str]` field (always present, `[]` when nothing
skipped). Frontend renders a `cached Xm` pill in the card h2 + sets a
live `"Last refresh: X min ago — Next refresh available in: N min"`
title on the global `#refreshBtn` on hover.

**News timeline — every pill is editable for manual fix** (commit
`fa2c976`, follow-up to `4734cc9`). Two popover modes:

- **Fixed-dimension pills** (category / actor / direction / region).
  Click → popover shows a `<select>` of valid values for that dimension
  (+ a "(clear)" option to null it out) and a Remove button. Saving
  POSTs to `/api/events/dimensions` which calls
  `store.update_event_dimensions()`. The override arms the `user_edited`
  lock so the next RSS refresh doesn't re-derive the column from text.
- **User-added / `ai` tags.** Click → popover shows the existing
  free-text rename input + Remove. Saving POSTs to `/api/events/tags`.

The AI capex-cycle gauge does NOT auto-refresh on tag edits — only the
global Refresh button triggers the recompute (which happens via
`/api/dashboard` → `_enrich` → `_recompute_ai_sentiment`). The tag-edit
endpoint no longer returns `ai_sentiment`.

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
   rename shipped earlier; Portfolio reorder persistence + per-section
   cooldowns shipped this session. Roadmap Phase 3 has three completed
   entries. Next candidates: any remaining Phase 3 item the user
   requests, or a new feature. No fresh backlog has been started.
2. **Module-graph discipline** — when extending events.js ↔ cards.js
   imports, do NOT add a `?v=…` query to one side without the other.
   The JS spec creates a fresh module record per URL; a mismatch
   silently duplicates the module and splits its state (this is
   exactly what bit the news overhaul — see the entry in
   `project_rules/DECISIONS.md` and the verification log in
   `archive/sessions/2026-09-10-news-section-overhaul-…md`).
3. **Archive `data/logs/summary-2026-09-11.md`** (gitignored daily
   changelog) once the session is well past — these files grow fast
   and are local-only per `AGENTS.md`. Not urgent.

## Blockers

None. `data/events.json` has unstaged scheduler timestamp updates —
per `project_rules/RUNBOOK.md` the `MarketAnalysis-EventsCommit` task owns
that file, not interactive sessions, so they will be picked up at the
next 17:00 scheduled run.

## Notes for the next session

- **Per-section refresh cooldowns are gated on `vintage` stamps in
  `data/dashboard.json`** — there is no separate `data/refresh_state.json`.
  The cached payload's `vintage` dict (already populated by
  `app/service.refresh_market`) is the single source of truth for "how
  old is this section's data?". `app.config.REFRESH_SECTION_COOLDOWNS`
  is the gating map keyed by **vintage key** (`portfolios`,
  `indicators`); the frontend-visible `cooldown_skip` field uses the
  card-key form (`portfolio`, `breadth_ai`). The mapping
  (`breadth-ai` card → `indicators` vintage) is intentionally
  asymmetric — the card's displayed age is `vintage.indicators` per
  `CARD_VINTAGE_KEY` in `static/js.cards`, but the underlying
  computation that "ages out" is the indicators computation itself.

- **Holdings reorder persistence uses `app.portfolio.reorder_holdings`
  + `POST /api/portfolios/<pid>/holdings/reorder`**. The cash row is
  filtered OUT of the request body (cash rows are identified by
  `kind == "cash"`) and re-attached at the end on the server side.
  This mirrors the existing `reorder_portfolios` pattern (dict-key
  insertion order, `save_portfolios` + `_patch_dashboard_cache`). The
  ▲/▼ click handler in `tickerTable.js:moveRow` is optimistic — swap
  + re-render first, POST second, revert + `setStatus("bad")` on
  error.

- **The `cooldown_skip` field is always present in the dashboard
  payload** (default `[]` on cold cache / no skip). The frontend
  renders the `cached Xm` badge only when the array includes the
  section's card key. The pill carries a `title` tooltip `"Last
  refreshed X min ago — next refresh in N min"` — N is computed live
  on hover using the cached `vintage` stamp + the hard-coded cooldown
  constants in `static/js.cards` (15 min / 30 min). Cooldown constants
  live in **two** places — `app.config` for the server-side gate and
  `static/js.cards.applyCooldownBadge` for the badge / tooltip. If
  one changes, change both.

- **Global `#refreshBtn` tooltip is now dynamic** — on hover it shows
  the live `"Refresh dashboard. Last refresh: X min ago. Next refresh
  available in: N min"` text; on unhover it reverts to the static
  `"Refresh"`. The "next refresh" N is the MAX across all cooldowned
  sections (the longest wait of any section determines when the next
  refresh can move all sections forward).

- **Test isolation fixture (`tests/conftest.py`) did NOT need a new
  monkeypatch line for the cooldown logic** — the existing
  `_isolate_data_files` autouse fixture already redirects
  `config.DATA_DIR` (which `app.service` uses to load
  `data/dashboard.json`), and `tests/test_service_cooldown.py` uses
  tmp_path for the cached payload via `monkeypatch.setattr(config,
  "DATA_DIR", tmp_path)`. No new user-data paths were added.

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
