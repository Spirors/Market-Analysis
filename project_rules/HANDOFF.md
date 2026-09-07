# Handoff

`Last updated`: 2026-09-07 (Audit P3/P4/P5/P6 closure shipped this session:
re-enabled `tests/test_service_coverage.py` + `tests/test_thirteenf.py` in
the default pytest run (was excluded; +37 tests → 421 Python pass); rewrote
`project_rules/API.md` to match `app/api.py` route decorators;
updated `project_rules/ARCHITECTURE.md` (deleted `app/earnings.py` /
`earnings-scan` skill / earnings card row / `refresh_earnings`, added
`validation.py` / `lifecycle.py` / `launcher_icon.py` / `changelog.py`
modules + portfolio card row + correct RSS sources); rewrote
`project_rules/TESTING.md` (was claiming 3 closed gaps as open + a missing
tickerTable test that exists in `portfolio.spec.mjs` lines 686-852);
pruned `.opencode/skills/earnings-scan/` (deleted module); fixed 3 stale
docstrings in `app/market.py` + 1 in `app/portfolio.py`; fixed
`README.md` RSS sources claim. Audit P3/P4/P5/P6/P7 closed. P1/P2 already
cleared. P0 fixed last session. No python processes, port 8000/8123 free.)

## Current state

**Audit follow-up closure** — every P3..P7 follow-up item from
`docs/logs/audit-2026-09-07.md` is now addressed:

- **P3 (shared components).** The audit flagged that `tickerTable.js`
  had no regression test for its sole remaining consumer. Two such
  tests already exist in `tests/frontend/portfolio.spec.mjs`:
  `per-portfolio column visibility: hiding a column in Portfolio A does
  not affect Portfolio B` (line 686) and `per-portfolio column order:
  reordering in Portfolio A does not affect Portfolio B` (line 778).
  Both assert `pfVisible.portfolio.<pid>` / `pfOrder.portfolio.<pid>`
  isolation. Recorded in `project_rules/TESTING.md` so a future
  extraction knows where to add the paired regression test.

- **P4 (test coverage gaps — CRITICAL bug).** `tests/test_service_coverage.py`
  had 5 broken tests: 3 with `from app import earnings` (`ImportError` —
  module deleted 2026-09-06), 1 with an outdated `_recompute_ai_sentiment`
  2-arg signature, and 1 with an assertion on the removed
  `cov["earnings"]` key. Cleaned up:
  - Removed the `earnings` field from `_complete_payload()`.
  - Removed the `cov["earnings"]` assertion from
    `test_coverage_counts_complete_payload`.
  - Replaced `test_get_dashboard_returns_enriched_data` with
    `test_get_dashboard_serves_events_regime_coverage` (no earnings
    assertions; current events/regime/coverage keys only).
  - Deleted `test_get_dashboard_recomputes_ai_sentiment_from_current_events`
    (was an end-to-end mock of the entire pipeline; the
    `test_recompute_ai_sentiment_filters_ai_only` test below covers the
    same surface more directly).
  - Fixed `test_recompute_ai_sentiment_filters_ai_only` to call
    `_recompute_ai_sentiment(events)` with the single-arg signature the
    function has today (it took `(events, earnings)` when earnings was a
    payload section).
  - Deleted `test_enrich_rebuilds_earnings_when_cache_is_all_null`
    (the `earnings` rebuild path was tied to the deleted `app/earnings.py`).
  - Re-added `tests/test_service_coverage.py` AND `tests/test_thirteenf.py`
    to the default `python -m pytest tests/` invocation. Both files
    were excluded historically per the prior AGENTS.md note; the
    exclusion is no longer needed. **+37 tests → 421 Python tests pass
    in 50 s, up from 384 last session.**

- **P5 (stale code).**
  - Docstrings: `app/market.py:4,33` now name the current callers
    (`service.py`, `portfolio.py`, `validation.py`); `app/market.py:155`
    rephrased from "user-editable earnings watchlist" to
    "user-editable sources (portfolio holdings, validate input)";
    `app/portfolio.py:29` rephrased from "earnings cache pattern" to
    "earnings-derived cache pattern" (the audit-suggested rephrase).
  - Deleted `.opencode/skills/earnings-scan/` (skill referenced
    `app/earnings.py`, `data/cache/earnings.json`, and
    `EARNINGS_UNIVERSE` — all deleted with the watchlist removal).

- **P6 (doc drift).**
  - `project_rules/API.md` fully rewritten. The audit listed 19
    undocumented routes and 3 stale earnings routes — all corrected.
    Each route now carries its 400/404 contract and the per-portfolio
    section-key rules. Added a "Dashboard payload sections" reference
    enumerating every top-level key.
  - `project_rules/ARCHITECTURE.md` module map updated: removed
    `app/earnings.py`, added `app/validation.py` /
    `app/lifecycle.py` / `app/launcher_icon.py` / `app/changelog.py`.
    Section-to-code table: removed the `#earningsBody` /
    `renderEarnings` row, added the `portfolio` card row.
    Backend quick-reference table updated to drop `refresh_earnings` and
    add the new module entries (each with the matching test file).
    Skills list: removed `earnings-scan`. Known quirks: removed the
    "Earnings watchlist supports show/hide columns" bullet;
    fixed the news-sources list (MarketWatch + BBC Business; the prior
    text listed SCMP China / SCMP Business / Korea Herald which were
    removed when the UA / timeout path was hardened).
  - `project_rules/TESTING.md` fully rewritten. The three
    "open test gaps" bullets (`test_thirteenf.py`, `test_scheduler.py`,
    `test_run.py`) are all closed — replaced with a coverage map
    pointing at each test file. Added the P3 regression-test note.
  - `README.md` news sources list updated to match the live
    `NEWS_FEEDS` (MarketWatch + BBC Business; the prior SCMP/Korea
    Herald list was stale per the audit P7 doc-drift family).

- **P7 (news section health check).** Already CLEARED last session. No
  code change; just the doc-drift family above.

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

## Top 3 next actions

1. **Phase 2 #7 — task scheduler / VBS launcher docs audit.** Revisit
   whether the 3-scheduled-task setup and the VBS-wrapper launch pattern
   are documented clearly enough that "stuck launch" incidents can't
   recur through a different code path than the one fixed in Phase 0.
2. **Phase 3 — feature work.** Once Phase 2 is fully closed, the
   roadmap says "(Add next features here once the above is stable —
   don't let this section grow while Phase 0 items are still open)."
   Currently empty. Suggest a backlog intake session before kicking
   off Phase 3 work.
3. **Archive `data/logs/summary-2026-09-07.md`** (gitignored daily
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

- **One frontend test file was DELETED this session (2026-09-07):**
  none — the audit's "Add a new spec file for per-portfolio
  tickerTable isolation" was already covered by the two tests at the
  bottom of `portfolio.spec.mjs` (added in `a8b60d2`). The fix sketch
  in the audit acknowledged `portfolio.spec.mjs` as an acceptable
  alternative location.
