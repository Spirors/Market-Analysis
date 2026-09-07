# Handoff

`Last updated`: 2026-09-07 01:00 UTC (per-portfolio column state + restored earnings-derived columns; 376 Python tests + 20 portfolio.spec.mjs Playwright tests pass; pre-existing star-scope + dash-layout failures unrelated; no python processes, port 8000/8123 free).

## Current state

**Per-portfolio column state + restored columns** (user-driven scope,
this session). The 8 columns stripped when the Earnings watchlist
section was removed are back (7-day %, 30-day %, Earnings date,
Marketcap, Forward PE, Forward PEG, 52W high, Sector), all visible
by default. Each portfolio's column visibility/order is now
independent — `pfVisible.portfolio.<pid>` /
`pfOrder.portfolio.<pid>` / backend `column_order['portfolio.<pid>']`
instead of a single shared set. Two commits:
- Backend (`75b7c70`): `enrich_portfolios` derives pct_7d/pct_30d/
  high_52w from a 260-day bulk history; pulls sector/marketcap/
  forward_pe/forward_peg/next_earnings from per-symbol Ticker.info
  + calendar (5-min lru_cache). `columns_put` accepts
  `portfolio.<pid>`. `DEFAULT_COLUMN_ORDER/VISIBILITY` grows from
  8 to 16 entries.
- Frontend (`a8b60d2`): `tickerTable._assertValidSection` accepts
  `portfolio.*` prefix; new `controlsMode: 'columnsOnly'` flag;
  `PORTFOLIO_COLUMNS` grows from 8 to 16; Columns dropdown moves
  INSIDE each expanded portfolio (was in card header); per-portfolio
  `section: 'portfolio.<pid>'` so localStorage + backend keys
  namespace per portfolio. Card header keeps only '+ Create
  portfolio' + '▼ all / ▲ all'.

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
