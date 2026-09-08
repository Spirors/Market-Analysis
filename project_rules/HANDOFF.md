# Handoff

`Last updated`: 2026-09-08 (Two sessions today. **Earlier:** Bottleneck
reorder + rename feature shipped — per-category ↑ / ↓ chevrons and ✎
rename pencil mirroring the Portfolio section. **Latest:** New Core rule
"Test isolation" added to `.opencode/skills/project-rules/SKILL.md` and
enforced by an autouse fixture in `tests/conftest.py`. Every pytest run
now redirects every user-data path (portfolios, bottleneck prefs, events,
analysis DB, daily changelog) to a per-test `tmp_path` — the user's real
`data/portfolios.json` is unreachable from any test. User's FastAPI
server (PID 7604) left running per the runbook.)

## Current state

**Bottleneck section is now interactive** — users can reorder categories via
↑ / ↓ chevrons and rename them via the ✎ pencil button. The implementation
mirrors the Portfolio section's established patterns exactly:

- Backend persistence in `data/bottleneck_prefs.json` (separate from the
  `BOTTLENECK_CATEGORIES` module constant, which remains read-only).
- `bottleneck_read()` applies user prefs at serve time (order + renames)
  without mutating the canonical list.
- `category_original` field in the output carries the canonical name for
  API calls (rename targets moves, not display names which can collide).
- Cache-patching pattern follows `portfolio._patch_dashboard_cache()`.
- Frontend optimistic updates mirror the portfolio pattern (local swap +
  POST + re-render).

**From last session — still green and unaffected:**

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

1. **Phase 2 #7 — task scheduler / VBS launcher docs audit.** Revisit
   whether the 3-scheduled-task setup and the VBS-wrapper launch pattern
   are documented clearly enough that "stuck launch" incidents can't
   recur through a different code path than the one fixed in Phase 0.
2. **Phase 3 — continued feature work.** Bottleneck reorder + rename
   just landed. Roadmap Phase 3 now has one completed entry. Next
   candidates: any of the remaining Phase 3 backlog items, or a new
   feature request from the user.
3. **Archive `data/logs/summary-2026-09-08.md`** (gitignored daily
   changelog) once the session is well past — these files grow fast and
   are local-only per `AGENTS.md`. Not urgent.

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
