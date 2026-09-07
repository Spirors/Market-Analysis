# Handoff

`Last updated`: 2026-09-07 (codebase audit complete + P7 news-section health check; P0 root cause confirmed + fix sketched; P1+P2 cleared; P4 stale test imports found; P6 doc drift inventory complete; P7 news pipeline working correctly, "3 days no news" is real soft-news silence not a bug; no code changes this session; `docs/logs/audit-2026-09-07.md` written).

## Current state

**Codebase audit (P0..P7) shipped as documentation only** — full
findings in `docs/logs/audit-2026-09-07.md`. No code changes
this session; the audit deliverable is the doc + the follow-up task
list.

- **P0 (user-visible latency):** Root cause confirmed.
  `app/portfolio.py:47` calls `enrich_portfolios(state)`
  synchronously inside `_patch_dashboard_cache(state)`, which fires
  after every mutation. For ~10 holdings on cold cache this is ~22
  HTTP calls (~3 s cold, ~2.4 s warm). Three independent
  contributors identified (cache patch re-enriches all symbols,
  `_quote_snapshot` has no disk cache, frontend `await refresh()`
  after every mutation). Fix sketch in the audit file.
- **P1 (server lifecycle) + P2 (data integrity):** CLEARED. All
  subprocess calls safe, wscript.exe used correctly, PID file
  lifecycle complete, no fabricated fallbacks, all snapshots carry
  `as_of` timestamps.
- **P3 (shared components):** `tickerTable.js` has no dedicated
  regression test for its sole remaining consumer (`portfolio.js`)
  after `section-position.spec.mjs` was deleted with the Earnings
  watchlist removal.
- **P4 (test coverage):** CRITICAL — `tests/test_service_coverage.py`
  has 3 `from app import earnings` imports that fail with
  `ImportError` (verified). The file is excluded from default pytest
  run per AGENTS.md; needs cleanup. Also: ROADMAP Phase 2 #5 lists
  3 test gaps that are all closed by existing tests
  (`test_thirteenf.py`, `test_scheduler.py`, `test_run.py`).
- **P5 (stale code):** Production code is clean of `app.earnings`
  imports. Stale references remain in 4 docstrings
  (`app/market.py:4,33,155`; `app/portfolio.py:29`), 1 skill file
  (`.opencode/skills/earnings-scan/SKILL.md`), and the test file
  above.
- **P6 (doc drift):** API.md severely outdated (14 Portfolio
  endpoints undocumented, 3 deleted earnings endpoints still
  listed). ARCHITECTURE.md lists deleted `app/earnings.py` as active,
  missing 4 modules, missing portfolio card from section-to-code
  table. TESTING.md lists 3 closed gaps as open. HANDOFF.md
  references removed `tests/test_earnings.py` and
  `app/earnings.py`.
- **P7 (news section health check, user-reported "3 days no news"):**
  Investigated end-to-end. RSS feeds (`MarketWatch`,
  `BBC Business`) are alive and returning 21 items within the
  48h window today; only 1 crosses `IMPORTANCE_THRESHOLD=6.0`
  (a Labor Day calendar explainer, comp=8.28). The "3 days no news"
  is real soft-news silence, NOT a bug. Pipeline is healthy
  (`first_seen` newest = 2026-09-04, `updated_at` touched today
  = scheduler ran). No code change needed. Threshold-tune sketch
  in the audit file for users who want more items during soft
  periods (low-importance, no fix recommended).

Previous session work (per-portfolio column state + restored
earnings-derived columns, commits `75b7c70` + `a8b60d2`) remains
green and unaffected by the audit.

## Top 3 next actions

1. **Apply / verify P0 fix from audit-2026-09-07.md.** Implement
   the targeted `_patch_dashboard_cache` patch (no full
   `enrich_portfolios`), route portfolio quote lookups through
   `market.get_quotes` (disk-cached), drop the `await refresh()`
   calls in the bespoke button handlers (optimistic local state via
   the existing tickerTable callback pattern). Regression test:
   mocked yfinance + assert `POST /api/portfolios/{pid}/holdings`
   <500 ms with N=15 holdings on a cold cache; assert row visible
   within one paint frame after the POST resolves (no follow-up
   `refresh()`).
2. **Clean up stale `from app import earnings` imports in
   `tests/test_service_coverage.py` (lines 312, 358, 453).** Delete
   the three affected test functions (`_coverage_counts["earnings"]`
   and `result["earnings"]` no longer exist in the live code). Add
   the file to the default pytest run after cleanup to catch future
   regressions.
3. **Update P6 docs** — rewrite `project_rules/API.md` to match
   `app/api.py`, prune deleted entries from
   `project_rules/ARCHITECTURE.md` (and add the 4 missing modules),
   strike the 3 closed gaps from `project_rules/TESTING.md`, update
   `project_rules/HANDOFF.md` notes section to point at
   `tests/test_validation.py` / `app/validation.py`. Optionally
   close ROADMAP Phase 2 #5 (all 3 test gaps are already closed) or
   rephrase it.

## Blockers

None. `data/events.json` has unstaged scheduler timestamp updates —
per `project_rules/RUNBOOK.md` the `MarketAnalysis-EventsCommit`
task owns that file, not interactive sessions. Working tree clean
except for that file.

## Notes for the next session

- **The audit's "Findings explicitly cleared" section
  (`audit-2026-09-07.md` bottom) saves a future session from
  re-checking every subprocess / `or 0` / `except Exception` /
  ticker-name pattern.** Do not redo that work.
- **The P0 fix must NOT re-introduce** any of the bugs documented
  in `project_rules/DECISIONS.md`: per-portfolio composite keys
  (`1fafbc1`), stuck process on test launch
  (`app/lifecycle.py`), earnings cache-miss full-universe rebuild
  (`80d0fef`), card-level totals after sub-table mutation
  (`8f3a82e`). Specifically: the new `_patch_dashboard_cache` must
  not fall through to a full rebuild on cache miss — either patch
  in place or invalidate and return.
- **`_quote_snapshot` no-disk-cache is intentional** for
  `build_market_snapshot` (the market section wants fresh quotes).
  It's only a bug in the portfolio enrichment path. Do not "fix"
  `_quote_snapshot` globally — route the portfolio path through
  `market.get_quotes` instead.
- **The auto-reap watchdog (`app/lifecycle.py`)** remains the
  runtime backstop. Agent terminal launches MUST use
  `--auto-reap 60` (or set
  `$env:MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S=60`). Documented in
  `project_rules/RUNBOOK.md` §Step 3a.

**Trade-off worth noting:** initial dashboard load is slower on a
cold cache because `enrich_portfolios` now does up to N+1 HTTP
calls (one bulk history + one Ticker.info per unique symbol).
With ~10 holdings this adds ~10-15s on first load; the 5-min cache
amortizes repeated reads within the window. If this becomes a UX
problem, the next step is to defer the per-symbol info fetch
behind an async `/api/portfolios/fundamentals/{pid}` endpoint that
the frontend calls only when a portfolio is expanded.

Recorded in `project_rules/DECISIONS.md` ("Portfolio columns restored +
per-portfolio state (2026-09-07)").

**Portfolio rename CSS shift fixed** (user-driven scope). The pencil
✎, totals, and ✕ buttons visibly shifted LEFT ~25-30px when entering
rename mode for a portfolio whose title was shorter than the
header's flex:1 span. Root cause per `@observer` task ses_f8665749:
span has `flex: 1` (grows to fill), input has `field-sizing: content`
(sizes to text only) — input was narrower than span was. Fix is in
`static/js/portfolio.js startEditForPid`: measure the span's
bounding-rect width BEFORE swapping in the input, set
`inp.style.minWidth = spanWidth + "px"`. The plain `min-width: 8ch`
CSS floor from commit `55400a9` stays. Red-green verified with the
fix reverted. Recorded in `project_rules/DECISIONS.md` ("Portfolio rename
input — match width to span (2026-09-06)").

Phase 0 / Phase 1 / Phase 2 #1-#4 closed in the prior session remain
green. Phase 2 #5 (test gaps) and Phase 2 #7 (task scheduler docs
audit) remain open.

## Top 3 next actions

1. **Phase 2 #5 — close known test gaps.** `app/thirteenf.py`
   (network-heavy, currently only indirectly tested),
   `app/scheduler.py` (Windows-only, no tests / needs a mock),
   `app/run.py` CLI flags (partially covered by the recent
   `test_run.py` additions).
2. **Phase 2 #7 — task scheduler / VBS launcher docs audit.**
   Revisit whether the 3-scheduled-task setup and the VBS-wrapper
   launch pattern are documented clearly enough that "stuck launch"
   incidents can't recur through a different code path than the one
   fixed in Phase 0.
3. **Phase 3 — feature work.** Once Phase 2 is fully closed, the
   roadmap says "(Add next features here once the above is stable —
   don't let this section grow while Phase 0 items are still open)."
   Currently empty. Suggest a backlog intake session before kicking
   off Phase 3 work.

## Blockers

None. `data/events.json` has unstaged scheduler timestamp updates —
per `project_rules/RUNBOOK.md` the `MarketAnalysis-EventsCommit` task owns
that file, not interactive sessions, so they will be picked up at
the next 17:00 scheduled run.

## Notes for the next session

- **`app/validation.py` is the only surviving earnings artifact.**
  It's the slim `validate_symbol` helper extracted from the old
  `app/earnings.py` — keeps the yfinance history-primary /
  Ticker.info-fallback ordering per the Phase 2 path diff. Used by
  `portfolio.add_holding` and by `app/api.portfolio_validate`.

- **Portfolio table is back to 16 columns.** `static/js/portfolio.js
  PORTFOLIO_COLUMNS` is star + 7 base portfolio columns + 8
  restored earnings-derived columns. The 8 restored columns come
  from `enrich_portfolios` (260-day bulk history for pct_7d/
  pct_30d/high_52w, per-symbol Ticker.info + calendar for
  sector/marketcap/forward_pe/forward_peg/next_earnings). Anyone
  adding new columns: extend `enrich_portfolios` first so the data
  is available.

- **Per-portfolio column state keys are `pfVisible.portfolio.<pid>` /
  `pfOrder.portfolio.<pid>` / backend `column_order['portfolio.<pid>']`.**
  The bare `portfolio` key remains the default that new portfolios
  inherit. `tickerTable.js _assertValidSection` accepts both
  canonical `"portfolio"` and the `"portfolio.*"` prefix; passing
  anything else throws immediately (per the project's
  shared-component persistence rule).

- **Columns dropdown lives INSIDE the expanded portfolio** now
  (`controlsMode: 'columnsOnly'`). The card-header dropdown is gone
  — there's no single "active" portfolio. The bespoke +Add holding /
  +Add cash buttons stay in the portfolio body alongside the new
  dropdown.

- **Cold-cache load is slower now.** `enrich_portfolios` does up to
  N+1 HTTP calls (one bulk history + one Ticker.info per unique
  symbol). With ~10 holdings this is ~10-15s on first load; the
  5-min lru_cache amortizes repeated reads. If UX becomes a
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

- **The auto-reap watchdog (`app/lifecycle.py`)** is the runtime
  backstop for any future stuck-process regression. Agent terminal
  launches MUST use `--auto-reap 60` (or set
  `$env:MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S=60`). Documented in
  `project_rules/RUNBOOK.md` §Step 3a.

- **Playwright frontend tests need a static server on port 8123**
  (`python -m http.server 8123 --bind 127.0.0.1` from the repo root).
  Reap before the turn ends per the runbook — pytest's playwright
  harness auto-starts/reuses the server but interactive runs need it
  started manually and reaped explicitly.

- **Four frontend test files were DELETED this session as no
  longer applicable:** `earnings.spec.mjs`, `earnings-watch.spec.mjs`,
  `watchlist-add.spec.mjs`, `section-position.spec.mjs`. They
  exercised removed functionality.


**Phase 0 / Phase 1 / Phase 2 #1-#4 all closed.** Five new commits this session
(`8d6d104` → `735b5e7` → `55400a9` → `8bb0f07` → this docs commit), all green:

- **Phase 2 #1 — Codebase health audit.** Commit `8d6d104`. Two findings
  appended to `project_rules/DECISIONS.md`:
  - **Stale-on-reload cluster classification:** dashboard-cache staleness
    issue, **already fixed by `b45858e`** — NOT the same root cause as the
    `tickerTable.js` shared-state risk class. The audit's job was to
    confirm this so the refactor pass (Phase 2 #2) wouldn't be re-planned
    against a stale classification.
  - **Earnings `validate_symbol` path diff:** portfolio display uses
    `yf.download` (bulk, reliable); earnings validation used `Ticker.info`
    (per-symbol, rate-limited) as PRIMARY with history fallback. Why
    `a2c793a` didn't stick: it added retry-with-1s-backoff around the
    same fundamentally-flaky call instead of switching to the reliable
    surface. Repro matrix (mocked, network-independent) covers all 4
    scenarios.
- **Phase 2 #2 — Refactor pass.** Already covered by `b45858e`. No
  additional work required. `app/portfolio.py:_patch_dashboard_cache(state)`
  called after every `save_portfolios(state)` in all 9 mutation functions.
- **Phase 2 #3 — Earnings "invalid symbol" diagnosis.** Commit `735b5e7`.
  `validate_symbol` now uses `market.get_history` (yf.download) as PRIMARY
  with `Ticker.info` as SECONDARY + enrichment. Removed `_yf_info_with_retry`
  (retrying a flaky call was the wrong shape of fix). 4 scenario tests +
  4 structural tests in `tests/test_earnings.py` — 3 of the structural
  tests fail on the pre-fix code (red-green verified). User-facing paths
  (`add_ticker`, `add_holding`) covered.
- **Phase 2 #4 — Portfolio rename layout shift.** Commit `55400a9` +
  docs `8bb0f07`. `.pf-name-input` swaps `min-width: 160px` (a fixed
  pixel floor wider than short rendered titles) for `field-sizing: content`
  + `min-width: 8ch`. For "IRA" the input renders at ~74px (was 160-183px).
  Older browsers fall back to the intrinsic 20-char size — no regression,
  just no improvement. 2 new Playwright tests in
  `tests/frontend/portfolio-name-input.spec.mjs` — both FAIL on the pre-fix
  code (red-green verified).
- **Phase 2 #5 — Test gaps (`app/thirteenf.py`, `app/scheduler.py`,
  `app/run.py` CLI flags).** NOT DONE — out of scope for this turn.
- **Phase 2 #6 — Shared-component audit.** Closed by the Phase 2 #1 audit —
  no new candidates found beyond the existing per-portfolio star scoping
  (`1fafbc1`).
- **Phase 2 #7 — Task scheduler / VBS launcher docs audit.** NOT DONE —
  out of scope for this turn.

Phase 0 / Phase 1 (both fully closed in prior sessions) remain green.

## Top 3 next actions

1. **Phase 2 #5 — close known test gaps.** `app/thirteenf.py`
   (network-heavy, currently only indirectly tested),
   `app/scheduler.py` (Windows-only, no tests / needs a mock),
   `app/run.py` CLI flags (partially covered by the recent
   `test_run.py` additions). The 3 remaining items in ROADMAP.md
   Phase 2.
2. **Phase 2 #7 — task scheduler / VBS launcher docs audit.**
   Revisit whether the 3-scheduled-task setup and the VBS-wrapper
   launch pattern are documented clearly enough that "stuck launch"
   incidents can't recur through a different code path than the one
   fixed in Phase 0.
3. **Phase 3 — feature work.** Once Phase 2 is fully closed, the
   roadmap says "(Add next features here once the above is stable —
   don't let this section grow while Phase 0 items are still open)."
   Currently empty. Suggest a backlog intake session before kicking
   off Phase 3 work.

## Blockers

None. `data/events.json` has unstaged scheduler timestamp updates — per
`project_rules/RUNBOOK.md` the `MarketAnalysis-EventsCommit` task owns that file,
not interactive sessions, so they will be picked up at the next 17:00
scheduled run.

## Notes for the next session

- **Earnings validation now uses yf.download as PRIMARY** (commit `735b5e7`).
  Any code that imports `earnings._yf_info_with_retry` will fail — the
  helper was removed. Use `earnings._yf_info` directly (or
  `earnings.market.get_history` for the bulk surface). The retry-with-
  backoff is intentionally gone — retrying a fundamentally-flaky call
  was masking the bug, not fixing it.
- **Portfolio rename input uses `field-sizing: content`** (commit `55400a9`).
  Any code that asserts `.pf-name-input { min-width: 160px }` will fail
  — the rule is now `field-sizing: content; min-width: 8ch;`. Older
  browsers (pre-Chrome 123 / pre-Firefox 122 / pre-Safari 17.5) fall
  back to the intrinsic 20-char size automatically.
- **Phase 2 audit decisions live in `project_rules/DECISIONS.md`** under
  "Phase 2 audit — stale-on-reload cluster classification" and
  "Phase 2 audit — earnings validate_symbol path diff". Read those
  before re-running the audit.
- **`project_rules/SESSION_LOG.md`** has accumulated ~12 dated entries — the file
  is now ~700 lines. Consider archiving pre-2026-09-06 entries to
  `docs/archive/SESSION_LOG-pre-2026-09-06.md` if size becomes a concern
  for next-session context.
- **The Playwright frontend tests need a static server on port 8123**
  (`python -m http.server 8123 --bind 127.0.0.1` from the repo root).
  Reap before the turn ends per the runbook — pytest's playwright
  harness auto-starts/reuses the server but interactive runs need it
  started manually and reaped explicitly.
- **The 5 commits this session are isolated** — each can be reverted
  individually without breaking the others. `8d6d104` (audit docs) is
  documentation only; `735b5e7` (earnings fix), `55400a9` (portfolio CSS
  fix), and the two docs commits are independent code/docs pairs.
- **The auto-reap watchdog (`app/lifecycle.py`)** is the runtime backstop
  for any future stuck-process regression. Agent terminal launches MUST
  use `--auto-reap 60` (or set `$env:MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S=60`).
  Documented in `project_rules/RUNBOOK.md` §Step 3a.
