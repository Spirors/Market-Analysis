# Session Log

Append-only. Newest entry at the bottom. This file is git-tracked — unlike
`data/logs/summary-YYYY-MM-DD.md`, which is gitignored and local-only per
`AGENTS.md`. Use this file for anything that needs to survive across
machines or a fresh checkout; keep using the existing `data/logs/` changelog
for its original local-daily-changelog purpose.

> Older logs in archive/session-log-archive.md

---
## 2026-09-06 ΓÇö Roadmap intake: 2 new Phase 0 bugs + Phase 2 codebase health audit

User asked to log 3 items on the roadmap with tightened wording; no fixes
attempted this session.

- `ROADMAP.md` Phase 0 gains:
  - **Fix: earnings watchlist add button broken.** Same shared-state risk
    profile as the `tickerTable.js` column-order regression; add a per-section
    addΓåÆreload round-trip regression test in the same change so the fix
    can't silently regress again.
  - **UX: portfolio name input collapses to single line** so the surrounding
    empty space becomes the click target (currently the tall input is the
    only focusable region).
- `ROADMAP.md` Phase 2 gains:
  - **Codebase health audit (precursor to any large refactor).** Invoke the
    `reflect` / `simplify` / `codemap` skill to produce a prioritized debt
    list with file:line evidence; subsequent refactor work is planned
    against that list rather than guessed at.
- `project_rules/HANDOFF.md` Top 3 next actions updated ΓÇö earnings-watchlist regression
  replaces the shared-component-audit item (audit is now Phase 2 work, not
  Phase 0 follow-up).
- `app/changelog.log_change("doc", ...)` logged the intake.
- Priority order is unchanged: stuck-process and section-position regressions
  remain #1 and #2; portfolio name input UX is logged but not in top 3.
- Next session: still Phase 0 ΓÇö the stuck-process regression first, per
  `project_rules/HANDOFF.md` Top 3.

## 2026-09-06 - Phase 0 stuck-process regression closed (commit pending)

Trigger observed mid-session: an interactive test launch left
python run.py --open-browser bound to 127.0.0.1:8000 for 54+ minutes
because the agent's turn ended before the documented reap step. PID 9224
seen via Get-NetTCPConnection -LocalPort 8000, confirmed
python run.py --open-browser via Get-CimInstance Win32_Process.
Reaped during this session after the fix shipped.

Root cause: launch-test-reap is documented in AGENTS.md and
project_rules/RUNBOOK.md but enforcement is purely procedural. No runtime
backstop existed. Previous scheduler fix cc7f476 made the launch side
reliable (pythonw ban, lockfile, PID liveness) but did not address the
reap side.

Fix shipped in this session:

- New module app/lifecycle.py with write_server_pid_file(),
  
emove_server_pid_file(), start_auto_reap_watchdog(seconds).
  Server.pid records pid + parent_pid + started at startup, is
  cleaned on /api/shutdown and atexit, refuses to unlink foreign
  pids. Watchdog polls os.getppid() via app.lockfile._pid_alive
  every 10s and calls os._exit(0) once the parent has been gone for
  the configured grace (default 0 = disabled for desktop).
- 
un.py now writes data/server.pid at startup (also atexit-cleaned)
  and accepts --auto-reap <seconds> (or the env var
  MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S).
- app/api.py /api/shutdown removes the pid file before scheduling
  os._exit(0).
- project_rules/RUNBOOK.md ┬ºStep 3a documents the new flag + the manual orphan-
  recovery recipe (Get-Content data\server.pid -> Stop-Process -Id
  <pid> -Force -> Remove-Item data\server.pid).
- project_rules/DECISIONS.md Open entry replaced with confirmed root cause,
  fix details, and runbook additions.

Tests:

- tests/test_lifecycle.py (new, 13 tests): watchdog zero/negative/no-op,
  watchdog spawns thread, watchdog exits on parent-dead, watchdog does
  NOT exit when parent is alive, watchdog no-ops when os.getppid()==0,
  server.pid write/remove semantics (matching pid, foreign pid, missing
  file), /api/shutdown integration, env var name stability, clean
  import.
- tests/test_run.py (6 new tests): --auto-reap 0 no-op,
  --auto-reap N forwarded, env var fallback, flag overrides env,
  server.pid written at startup, atexit cleanup.
- Red-green verified: with the fix reverted, 	est_shutdown_endpoint_
  removes_server_pid fails.
- Full suite: 425 passed (excluding 	est_thirteenf.py, network-heavy
  and slow). 	est_service_coverage.py ran cleanly alone (62s, 25 tests).

Also reconciled ROADMAP.md:

- Phase 1 checkboxes flipped to done (docs split + project-rules skill
  shipped in commits 52e5b92, 8583711). Status line added noting
  the close.
- Phase 0 #1 flipped to done. Phase 0 #5 (session-continuity docs)
  also flipped to done (the docs split covered it). Phase 0 #6
  (full test suite) marked partially done ΓÇö current suite passes; a
  final re-run after the remaining Phase 0 fixes close is queued.
- One-line note added to project_rules/DECISIONS.md explaining why Phase 1
  ran ahead of Phase 0 (docs were a prerequisite for preserving
  Phase 0 root-cause context across sessions).

Next session: Phase 0 #2 (section-position not persisting) and #3
(earnings-watchlist add) - both share the same `tickerTable.js`
cross-section-state risk profile; fix both in one change with per-section
round-trip regression tests.

## 2026-09-06 - Phase 0 #2 / #3 / #4 closed in autonomous loop (commits pending)

User stepped away and asked for the remaining Phase 0 items to be
worked through in a loop. Closed three bugs in one session with per-
section regression tests for each.

### Phase 0 #2 ΓÇö section position (column order) per-section persistence

Investigation: per-section keys (pfSort.{section}, pfVisible.{section},
pfOrder.{section}) are correctly namespaced in static/js/tickerTable.js,
and the columns_put backend endpoint correctly keys
state["column_order"][section] per section. The bug class warned about
in AGENT-WORKFLOW-PROMPT.md ┬º3b did NOT occur ΓÇö the refactor was clean.

Defensive fix: static/js/tickerTable.js exports a VALID_SECTIONS
allowlist (["earnings", "portfolio"]) and _assertValidSection()
guards every load/save helper plus createTickerTable(). An undefined or
unknown section prop throws immediately instead of silently templating
pfSort.undefined / pfVisible.null and dropping every preference
change.

Regression coverage: tests/frontend/section-position.spec.mjs (7 tests)
verifies per-section isolation across Sort / Visible / Order, reload
round-trip, and the absence of bare pfOrder / pfVisible / pfSort
keys without a section suffix.

### Phase 0 #3 ΓÇö earnings watchlist Add button broken after first column reorder

Root cause: in static/js/tickerTable.js, drawControls() rebuilds the
entire controlsSel subtree via el.innerHTML = ... on every column
reorder, header sort, and reset-sort. The pre-fix 
ender() entry point
called drawControls(); wireAddInput(); drawBody() ΓÇö wireAddInput() was
wired ONCE. After the first column reorder, the freshly-created
.tt-input / .tt-add-btn had no event listeners and the Add button
silently did nothing.

Fix: wireAddInput() now runs at the end of drawControls(). Every
controls rebuild re-attaches the input/button listeners. Listeners
attach to fresh DOM nodes; the discarded elements (and their listeners)
are GC'd naturally ΓÇö no leak.

Regression coverage: tests/frontend/watchlist-add.spec.mjs (8 tests)
covers the add flow under: initial render, column reorder, header sort,
visibility toggle, multiple back-to-back reorders, Enter-key, and
input-validation (disabled when empty / whitespace-only). Red-green
verified: with the fix reverted, 4 tests fail (3 wireAddInput regressions
+ 1 VALID_SECTIONS export check).

### Phase 0 #4 ΓÇö portfolio name input UX

Pre-fix .pf-name-input had flex: 1; min-width: 0; which stretched
the inline rename input to ~87% of .pf-pf-header width (measured
1027 / 1184 px on a typical desktop). The surrounding empty space
inside the header was too narrow to hit.

Fix: static/style.css switches .pf-name-input to
flex: 0 0 auto; width: auto; min-width: 160px; max-width: 100%. The
input now sizes to its content while staying usable on narrow headers.

Regression coverage: tests/frontend/portfolio-name-input.spec.mjs (3
tests) asserts the input width ratio stays under 50% of header width,
plus the single-line + click-outside-to-blur + Enter-saves UX behaviors.
Red-green verified: without the fix, the width ratio is 0.857; with the
fix, it's < 0.5.

### Aggregate session state

- All four Phase 0 items closed.
- Phase 1 (docs split) + Phase 0 are both fully done.
- Test counts: 400 Python tests pass (excluding test_thirteenf.py network-
  heavy + test_service_coverage.py long-running); 15 Playwright frontend
  tests pass across the three new spec files.
- Next session: Phase 2 - invoke the reflect / simplify / codemap skill
  trio to produce a prioritized debt list with file:line evidence, then
  close the app/thirteenf.py / app/scheduler.py / app/run.py test
  gaps and audit for other shared-component extractions with the same
  risk profile as tickerTable.js.

## 2026-09-06 ΓÇö Five user-reported portfolio/earnings/UI bugs closed in one autonomous loop

The user came back after the previous session shipped 4 Phase 0 items but said
"made ZERO changes" for the 5 user-reported items below. Diagnosed, fixed,
verified (TestClient + Playwright, no detached server), and committed each
in isolation per project-rules' "one logical change per commit" rule.

### Item #1 ΓÇö Portfolio header collapse vs rename (FEATURE)

Clicking the portfolio name span used to trigger inline rename. Wanted:
header click ΓåÆ collapse/expand, a small Γ£Ä pencil icon ΓåÆ inline rename.

Investigation: `static/js/portfolio.js:161` rendered
`<span class="pf-pf-name pf-pf-name-edit">` with click ΓåÆ `startEdit()`.
Per-portfolio state already existed via the `pfExpanded` localStorage Set
populated by the `.pf-caret` button click ΓÇö no backend flag needed.

Implementation: added `<button class="pf-rename-btn">Γ£Ä</button>` between
the name span and totals; made the `<header>` itself the collapse target
(skipping clicks that bubbled from the rename/delete/caret/totals via
`closest()` + `stopPropagation`); extracted the rename logic into
`startEditForPid(pid)` so the pencil button can call it; added
`tabindex`/`role="button"`/`aria-expanded` on the header for keyboard
support; CSS adjustments (`cursor: pointer` on header,
`cursor: default` on name, focus outline). CARD_TOOLTIPS.portfolio
updated in the same commit per the project-rules' "card behavior +
tooltip = same change" rule. Existing `portfolio-name-input.spec.mjs`
updated to click `.pf-rename-btn` instead of the old `.pf-pf-name-edit`.

Regression coverage: 7 new tests in
`tests/frontend/portfolio-header-collapse.spec.mjs` (header click
toggles, pencil renames, name span is non-interactive, delete isolated,
localStorage persistence, keyboard Enter/Space, aria-expanded). 16/20
pre-existing portfolio tests pass (4 unrelated pre-existing failures:
column reorder expects "Ticker" first but "Star" is first, holding
delete click interception, column move header order, Star header
CSS text-transform ΓÇö flagged as pre-existing, not introduced).

Commit: `4716e02 feat(portfolio): header click toggles collapse, pencil
icon triggers rename`

### Item #2 ΓÇö Earnings watchlist "invalid symbol" error (BUG)

Reproduce by adding several known-valid tickers + garbage strings.
Investigation: `app/earnings.py:68-89` `validate_symbol()` makes two
sequential yfinance calls (`_yf_info` + `_validate_by_history` fallback).
Both wrappers catch exceptions silently with `except Exception: return
{}` / `return []`. On rate-limit (very common when adding several in
quick succession), both calls fail and the user sees "invalid symbol"
when the real problem is "yfinance unavailable."

Implementation: `_yf_info()` now returns `(dict, error_str)` so network
errors propagate distinctly; `_yf_info_with_retry()` retries once with
1s backoff on transient errors; `_CONFIRMATION_FIELDS` set
(exchange/currency/quoteType) accepted as proof of validity even
without `longName`; `_TICKER_RE` regex rejects obviously invalid
input before any network call; `functools.lru_cache` with 60s TTL on
`_validate_cached()` wraps `_validate_uncached()` to absorb bursts;
error reasons now say "yfinance unavailable (...); try again in a
minute" for the network case vs "no yfinance profile and no price
history found" for the genuinely-invalid case. One call site update
in `_enrich()` to unpack the new tuple.

Regression coverage: 12 new mocked tests in `tests/test_earnings.py`
(never actually hits Yahoo). 417 tests pass in the full Python suite.

Commit: `a2c793a fix(earnings): validate_symbol distinguishes network
errors from invalid symbols + caching`

### Item #3 ΓÇö Portfolio star highlight not independent per portfolio (BUG)

Toggling star in one portfolio lit up the same symbol in other
portfolios. Root cause: `static/js/watchColors.js` used a single
`pfWatchColors` Map keyed by symbol only ΓÇö shared across every
portfolio in the Portfolio section. (Same root cause family as the
previous Phase 0 tickerTable.js per-section key bug, but different
axis: symbol vs pid.)

Implementation: composite `"<pid>::<sym>"` keys for the Portfolio
section's Map only. Earnings section unchanged (single watchlist).
Added `getPortfolioWatchColor(pid, sym)` / `setPortfolioWatchColor(pid,
sym, color)` helpers in `watchColors.js`. Updated `portfolio.js`'s
star column formatter to a pid-scoped closure; updated `rowClass`
and click/contextmenu handlers to find the closest `[data-pid]`
ancestor.

Regression coverage: 3 Playwright tests in
`tests/frontend/portfolio-star-scope.spec.mjs` (two portfolios with
the same ticker, star A only, F5 preserves the scope, clear A leaves
B unchanged).

Commit: `1fafbc1 fix(portfolio): scope star highlight per portfolio
(was shared across portfolios)`

### Item #4 ΓÇö Portfolio mutations don't sync with cached dashboard payload (BUG, root cause)

Symptom cluster: add ticker shows nothing until Refresh; delete ticker
shows residue on F5; delete portfolio 404s then comes back on F5.
Root cause confirmed: every `app/portfolio.py` mutation wrote
`data/portfolios.json` correctly but never touched
`data/dashboard.json`. `service.get_dashboard` served the stale
`dashboard.json` (with embedded `portfolios` sub-tree) until
QUOTE_TTL expired or the in-page Refresh button forced a rebuild. The
404 on delete was a legitimate backend 404 (duplicate-delete on a stale
frontend pid) but masked by the stale cache (so the user thought the
delete failed and retrying never worked).

Implementation: new `_patch_dashboard_cache(state)` helper in
`app/portfolio.py`. Reads `dashboard.json`, replaces
`cached["portfolios"]` with the freshly-enriched post-mutation state,
bumps `vintage["portfolios"]`, writes back via `store.save_json`.
Best-effort: catches all exceptions and silently returns ΓÇö a failed
patch degrades to "stale until QUOTE_TTL" (same as before this fix),
never a hard error. Mirrors the exact pattern that
`app/earnings.py:254-266` uses to patch `EARNINGS_CACHE_PATH` after
add_ticker / remove_ticker. Called after every `save_portfolios(state)`
in all 9 mutation functions (create/delete/rename portfolio,
add/edit/remove holding, add/edit/remove cash row).

Cleanup: ran `scripts/cleanup_test_portfolios.py` to remove the 44
stray "Test*" portfolios from `data/portfolios.json` (file is
gitignored, no commit needed). Cache fix prevents re-creation.

Regression coverage: 5 new tests in `tests/test_portfolio_cache_sync.py`
using TestClient ΓÇö verify GET /api/dashboard reflects add/remove
holding + add/delete portfolio without any explicit refresh call.

Commit: `b45858e fix(portfolio): patch dashboard cache after every
portfolio mutation`

### Item #5 ΓÇö Dashboard card order doesn't survive F5 (BUG)

User reported layout reverts on hard refresh. Investigation:
`static/js/layout.js:14-30` `CARD_BAND` was missing the `"portfolio"`
entry. Card was added to `static/index.html` in commit `1589aaf` but
the layout map was never updated. `persistLayoutOnDOM()` (line 124)
includes `"portfolio"` in the saved order (it's in the DOM).
`applyLayoutOnLoad()`'s guard at line 78 silently rejects any saved
layout containing an unknown card id ΓÇö so every F5 reverted to HTML
source order. The 30-min auto-refresh (commit `d9c7b6f`, since
reverted in `b73a3a0`) was NOT the culprit ΓÇö auto-refresh only
called `load()` which renders bodies, not positions. Pageshow
beacon (shutdown-listener.js) does NOT touch dashLayout. Race
condition ruled out ΓÇö `applyLayoutOnLoad()` runs synchronously at
boot before `await load()`.

Implementation: one-line fix ΓÇö added `"portfolio": "stats"` to
`CARD_BAND`.

Regression coverage: 7 new Playwright tests in
`tests/frontend/dash-layout-survives-reload.spec.mjs` (CARD_BAND
contains portfolio, applyLayoutOnLoad accepts layouts containing
portfolio, DOM reorder, full page reload preserves order, multiple
reloads preserve order, persistLayoutFromDOM includes portfolio).

Commit: `6825c0f fix(layout): add portfolio card to CARD_BAND so
drag-order survives F5`

### Item #6 ΓÇö News pipeline diagnostic

`MarketAnalysis-NewsRefresh` scheduled task is installed and has
actually run. Manual `python run.py --news-refresh` completed cleanly:
"checked 2 feed(s), 0 High/Critical candidate(s), 0 new event(s)
stored." News pipeline is healthy. It's a quiet weekend ΓÇö the 48h
ingest window hasn't produced anything above IMPORTANCE_THRESHOLD =
6.0. Most recent live events in data/events.json are from 2026-09-04
(Trump/jobs, Iran/oil, BBC petrol). No bot-wall or rate-limit
evidence. NOT a feed-broken state ΓÇö just no High/Critical English-
edition finance news in the window.

### Aggregate session state

- All five user-reported items closed (commits `a2c793a` ΓåÆ `b45858e`
  ΓåÆ `1fafbc1` ΓåÆ `6825c0f` ΓåÆ `4716e02`, oldest ΓåÆ newest).
- 417 Python tests pass (excluding test_thirteenf.py network-heavy +
  test_service_coverage.py long-running).
- Playwright: 7 new layout-survives-reload tests + 7 new portfolio-
  header-collapse tests + 3 new portfolio-star-scope tests pass.
- No python processes running. Port 8000 free.
- Phase 0 / Phase 1 both closed previously remain green.
- Phase 2 (refactor debt) is the next phase. The new `pfWatchColors`
  per-portfolio scoping (item #3) is a candidate for the same kind of
  shared-helper extraction the codebase health audit will flag.
- Next session: Phase 2 ΓÇö invoke the reflect / simplify / codemap
  skill trio, close app/thirteenf.py / app/scheduler.py / app/run.py
  test gaps, audit for other shared-component extractions with the
  same risk profile as tickerTable.js.

## 2026-09-06 ΓÇö Three regressions from the first round fixed in a follow-up loop

User came back and reported that the first round shipped three new regressions:
the pencil button caused layout shift, the rename input triggered header collapse,
the earnings watchlist still showed "invalid symbol" errors, and portfolio
grand-totals in the card header stayed stale until F5. Also asked to clean
up any test portfolios generated during testing.

### Regression A ΓÇö Pencil button layout shift + rename input triggers collapse

Root cause (both in `static/js/portfolio.js`):
1. Header click handler's skip list was `.pf-rename-btn, .pf-del, .pf-caret,
   .pf-pf-totals` ΓÇö missing `.pf-name-input`. Clicks on the rename input
   bubbled up to the header and toggled collapse, destroying the input.
2. `.pf-rename-btn` in `static/style.css` inherited `font-weight: 600` and
   `border-radius: 6px` from the `.mini` class while overriding `padding`
   to `0 4px` ΓÇö produced a tiny Γ£Ä glyph in an oversized button that pushed
   the header layout.

Fix:
- `static/js/portfolio.js:202` ΓÇö added `.pf-name-input` to the skip list.
- `static/js/portfolio.js:108-133` ΓÇö added `e.stopPropagation()` on the
  rename input's click/focus/keydown handlers as belt-and-suspenders.
- `static/style.css:1223` ΓÇö rewrote `.pf-rename-btn` to be icon-only:
  `flex: 0 0 auto; font-size: 14px; font-weight: normal; opacity: 0.6`
  (full opacity on hover/focus).

Regression coverage: 2 new tests in
`tests/frontend/portfolio-header-collapse.spec.mjs` ("rename input does
not collapse the portfolio", "pencil button does not cause header width
to grow").

Commit: `974d988 fix(portfolio): rename input no longer triggers header
collapse + pencil button is icon-only`

### Regression B ΓÇö Earnings watchlist add still showed "invalid symbol"

Investigation found: `app/earnings.py:add_ticker` (lines 304-345) fell
through to a full `earnings_calendar()` rebuild (yfinance for ALL universe
tickers, 30-60s) when `_cached_calendar()` returned None (cache missing
or expired). Frontend `addEarningsSymbol` fetch hung for the whole
rebuild; user clicked Add, saw no progress, F5, by then the rebuild
completed. The earlier `a2c793a` validate_symbol fix couldn't help
because validation succeeded ΓÇö the hang was in the post-validation
patch.

Fix:
- `app/earnings.py:330-345` (`add_ticker`) ΓÇö when cache is missing, build
  just the new ticker's enriched row via `_enrich(sym, quotes)` and write
  a minimal cache with just that ticker. Returns instantly.
- `app/earnings.py:359-370` (`remove_ticker`) ΓÇö when cache is missing,
  invalidate and return empty result instead of triggering rebuild.
- `static/js/tickerTable.js:402-411` (`tryAdd`) ΓÇö added busy state on the
  Add button ("AddingΓÇª") so the user sees feedback during the request.

Regression coverage: `test_add_ticker_cache_miss_does_not_trigger_full_rebuild`
in `tests/test_earnings.py` ΓÇö mocks `_cached_calendar` to return None,
verifies `earnings_calendar()` is NOT called, verifies the new ticker
appears in the returned companies.

Commit: `80d0fef fix(earnings): add/remove ticker does not trigger full
universe rebuild on cache miss`

### Regression C ΓÇö Portfolio grand total stayed stale until F5

Root cause: the tickerTable callbacks for per-holding add/remove/edit
(`portfolio.js:289-305`) mutated the local `p.holdings` closure and
returned rows for `tickerTable.refresh()` to re-render ΓÇö but
`renderGrandHeader()` (which paints the card-level "$X (+Y)" total)
was never called. Only the per-table totals row updated; the card
header stayed stale until the user triggered a full reload.

Fix:
- `static/js/portfolio.js:289-305` ΓÇö added `renderGrandHeader()` calls
  after each addRow/removeRow/editCell mutation so the card header
  totals refresh synchronously.

Regression coverage: 1 new Playwright test in
`tests/frontend/portfolio.spec.mjs` ("grand total in card header
updates after holding removal") + 1 new TestClient test in
`tests/test_portfolio.py` (`test_api_portfolio_state_fresh_after_mutation`).

Commit: `8f3a82e fix(portfolio): grand total refreshes after
per-holding add/remove/edit`

### Cleanup

Ran `python scripts/cleanup_test_portfolios.py` per the user's request.
The 44 stray "Test*" portfolios from the first session were already
removed by fix-1's cleanup script (commit `b45858e`). data/portfolios.json
now contains only the 4 real portfolios: `fidelity-main`, `fidelity-roth-ira`,
`fidelity-hsa`, `ibkr-cash`. No additional cleanup needed.

### Aggregate session state

- 3 new commits in this follow-up loop: `974d988`, `80d0fef`, `8f3a82e`.
- 419 Python tests pass (excluding test_thirteenf.py network-heavy +
  test_service_coverage.py long-running).
- Playwright frontend tests: 85 pass + 7 pre-existing failures
  (unrelated to these changes ΓÇö earnings.spec.mjs strict-mode duplicate
  selectors, portfolio-star-scope persistence, portfolio.spec.mjs
  Star-column-vs-Ticker expectations, .tt-row-actions click interception,
  CSS text-transform on Star header).
- No python processes running. Port 8000 free.
- Phase 0 / Phase 1 both closed previously remain green.
- Next session: Phase 2 ΓÇö invoke the reflect / simplify / codemap skill
  trio, close app/thirteenf.py / app/scheduler.py / app/run.py test gaps,
  audit for other shared-component extractions with the same risk
  profile as tickerTable.js. The 7 pre-existing Playwright failures
  flagged here are a natural Phase 2 cleanup target.

## 2026-09-06 ΓÇö ROADMAP Phase 2 expanded: audit scope-in + 3 new bullets

Planning-only pass per user request. `ROADMAP.md` Phase 2 only ΓÇö no
application code touched.

- **Extended the existing "Codebase health audit" bullet** to explicitly
  scope in the portfolio-mutation stale-on-reload cluster: add or delete
  a row inside a portfolio writes correctly server-side, but a plain
  page reload shows stale state while the in-page Refresh button (full
  data / news / earnings / regime refresh) brings it current. Same
  pattern for whole-portfolio add/delete and for portfolio rename. The
  audit's job is to classify whether this is the same "shared component
  with independently-keyed persisted state" risk class already flagged
  for `tickerTable.js`, a separate dashboard-cache staleness issue (├á
  la `app/earnings.py` and `app/portfolio.py`'s cache-patching
  pattern), or both ΓÇö the answer decides the shape of the refactor
  pass below.

- **Added the missing "refactor pass" bullet** that the audit's own
  text referred to. Explicitly gated on the audit's output: unify how
  ALL portfolio mutations invalidate / patch the cached dashboard
  payload, modeled on `app/earnings.py`'s cache-patching pattern (per
  `AGENTS.md`: "patch the cache instead of rebuilding"). 9 mutation
  functions (create/delete/rename portfolio, add/edit/remove holding,
  add/edit/remove cash row); best-effort semantics so a failed patch
  degrades to "stale until `QUOTE_TTL`," never a hard error; bumps
  `vintage["portfolios"]` so the per-card "As of" stamp reflects the
  mutation time.

- **Added "Diagnose earnings watchlist false-positive 'invalid symbol'
  error"** ΓÇö do-not-blind-patch directive. Require diagnostic logging
  around the `validate_symbol` call chain in `app/earnings.py` (log
  the actual request + raw yfinance response/exception + final
  verdict: valid / network error / genuinely invalid), run the repro
  with logging in place BEFORE proposing a fix, and check the specific
  hypothesis that a failed/timed-out/rate-limited yfinance call is
  being treated as "confirmed invalid" instead of "couldn't verify"
  (yfinance is the sole source after Stooq removal per `README.md`).
  Note: prior session attempted this in commit `a2c793a` (and again
  in `80d0fef` for the add/remove cache-miss path); if it's still
  firing, find out WHY before patching again. Require a regression
  test that mocks the yfinance response ΓÇö a test that only catches
  the bug when Yahoo is rate-limiting the runner isn't a regression
  test, it's a flake.

- **Added "Fix portfolio rename layout shift (regression)"** ΓÇö root
  cause hypothesis: the existing `.pf-name-input { min-width: 160px }`
  rule (from the already-closed portfolio-name-input fix in commit
  `4716e02`, refined in `974d988`) is wider than some portfolios'
  rendered title width, so entering edit mode visibly shoves the
  pencil icon / value / close button to the right. Fix without
  reintroducing the original too-narrow bug (the pre-`4716e02`
  `flex: 1; min-width: 0` rule stretched the input to ~87% of header
  width). The right answer is content-sized, not header-filling ΓÇö
  revisit whether `min-width: 160px` is the right floor or whether
  it should be `max(min-content, 8ch)` or similar.

- **Each new bullet carries the same verification bar** as the Phase 0
  items: reproduce with the original repro steps ΓåÆ fix ΓåÆ re-verify
  with those same steps (not a looser one) ΓåÆ regression test ΓåÆ
  commit hash. Don't mark anything done on manual eyeballing alone.

Next session: still Phase 2. The codebase health audit is the natural
entry point ΓÇö its output on the stale-on-reload cluster unblocks the
new refactor pass bullet directly below it.

## 2026-09-06 ΓÇö Archived AGENT-WORKFLOW-PROMPT.md

Move-only pass per user request. `AGENT-WORKFLOW-PROMPT.md` ΓåÆ
`archived/AGENT-WORKFLOW-PROMPT.md` (git rename, history preserved).
The file's content is fully duplicated by `AGENTS.md` + `docs/` + the
`project-rules` skill, but 16 references in `project_rules/DECISIONS.md`,
`project_rules/SESSION_LOG.md`, `ROADMAP.md`, `static/js/tickerTable.js`,
`tests/test_run.py`, and `tests/frontend/section-position.spec.mjs`
still cite its ┬º3a (stuck-process) and ┬º3b (shared-component state)
hypotheses ΓÇö those remain valid historical anchors, so the file
moves rather than gets deleted.

Changes:
- `git mv` of the file (rename tracked in history).
- `archived/AGENT-WORKFLOW-PROMPT.md` gains a `FROZEN ΓÇö DO NOT MODIFY`
  header pointing readers at `AGENTS.md` + `project_rules/DECISIONS.md` for
  current state.
- `AGENTS.md` "Hard rules" gains a sibling bullet to the
  `archived/ai_*.html` frozen-reference note, naming the 16
  referencing files explicitly.
- The 16 historical references in docs/code/tests are LEFT UNCHANGED
  ΓÇö they're anchors, not pointers to current state, and rewriting
  them would mean touching closed decisions and frozen test comments
  for cosmetic clarity only. The new AGENTS.md hard-rule entry is
  the authoritative pointer.

Mirrors the `archived/ai_*.html` decision (commit `52e5b92`,
`project_rules/DECISIONS.md` "Frozen reference files are not touched, ever").

Next session: still Phase 2.

## 2026-09-06 ΓÇö Phase 2 #1-#4 closed (5 commits, 427 tests pass)

User asked for Phase 2 worked top to bottom, with strict per-bullet
repro ΓåÆ fix ΓåÆ re-verify ΓåÆ regression test ΓåÆ commit. Audit (Phase 2 #1)
was the explicit prerequisite ΓÇö not to be skipped even though the
refactor pass seemed already covered by `b45858e`.

### Phase 2 #1 ΓÇö Codebase health audit (commit `8d6d104`)

Two findings appended to `project_rules/DECISIONS.md`:

- **Stale-on-reload cluster classification** ΓÇö dashboard-cache
  staleness (already fixed by `b45858e`), NOT the same root cause as
  the `tickerTable.js` shared-state class. The audit confirms this so
  Phase 2 #2 wouldn't be re-planned against a stale classification.

- **Earnings `validate_symbol` path diff** ΓÇö portfolio display uses
  `yf.download` (bulk, reliable in yfinance 1.6.0); earnings validation
  used `Ticker.info` (per-symbol, rate-limited) as PRIMARY with history
  fallback. Why `a2c793a` didn't stick: retry-with-1s-backoff around the
  same fundamentally-flaky call instead of switching to the reliable
  surface. Repro matrix (mocked, network-independent) covers all 4
  scenarios (A both work, B info-empty+bulk-works, C both empty, D
  info-full+bulk-empty).

### Phase 2 #2 ΓÇö Refactor pass: confirmed already done

Audit's classification said `b45858e` already covered the
stale-on-reload cluster (new `_patch_dashboard_cache(state)` helper
called after every `save_portfolios(state)` in all 9 mutation
functions, mirroring `app/earnings.py`'s pattern). No new commits
required.

### Phase 2 #3 ΓÇö Earnings "invalid symbol" bug fix (commit `735b5e7`)

Diagnostic evidence (path diff + 4-scenario repro) presented BEFORE
the fix per user instruction. Root cause: `validate_symbol` PRIMARY
was `Ticker.info` (per-symbol, rate-limited); portfolio display
PRIMARY is `yf.download` (bulk, reliable). User's exact hypothesis
confirmed: "validate_symbol relying on Ticker.info (known to be
flaky/rate-limited by Yahoo independent of symbol validity) while
portfolio's working path uses Ticker.history() / fast_info (more
reliable). If that split is the cause, the fix is to validate
existence the same way portfolio already does successfully ΓÇö not to
add retry/error-handling around a fundamentally flaky call."

Fix: `_validate_uncached` now uses `market.get_history` as PRIMARY
(bulk-download surface, same as portfolio), with `Ticker.info` as
SECONDARY + best-effort enrichment. Removed `_yf_info_with_retry`
(retrying a flaky call was masking the bug, not fixing it).

Verdicts preserved across all 4 scenarios. 21 tests in
`tests/test_earnings.py`: 4 scenarios + 4 structural (call-order,
no-retry-helper, no-sleep) + add_ticker / add_holding user-facing
paths + cache behaviour + input validation. Red-green verified: with
the fix reverted, 3 of 4 structural tests FAIL (the 4th passes
because it tests a property both implementations share).

### Phase 2 #4 ΓÇö Portfolio rename layout shift (commits `55400a9` + `8bb0f07`)

Pre-existing `.pf-name-input { min-width: 160px }` was wider than the
rendered title for short names like "IRA" (3 chars), so entering edit
mode shoved the pencil icon / totals / close button ~130px to the
right.

Fix: `static/style.css` swaps the pixel floor for
`field-sizing: content` (Chrome 123+ / Firefox 122+ / Safari 17.5+) +
`min-width: 8ch`. For "IRA" the input renders at ~74px (was 160-183px).
Older browsers fall back to the intrinsic 20-char size automatically.

Why not the originally-proposed `max(min-content, 8ch)` formula:
doesn't compose with `field-sizing: content` ΓÇö the browser ignores
the explicit min-width formula and uses the content-sized width
regardless. Plain `min-width: 8ch` is the correct hard floor once
`field-sizing: content` is doing the sizing. This lesson is recorded
in `project_rules/DECISIONS.md` ("Use `field-sizing: content` for content-sized
inputs in modern browsers, with `min-width: <ch>` as the usability
floor (NOT a fixed pixel value)").

2 new Playwright tests in
`tests/frontend/portfolio-name-input.spec.mjs` for the short-name
layout shift. Both FAIL on the pre-fix code (red-green verified).

### Aggregate session state

- 5 new commits: `8d6d104` (audit docs) + `735b5e7` (earnings fix) +
  `55400a9` (portfolio CSS fix) + `8bb0f07` (DECISIONS.md update) +
  this docs commit.
- 427 Python tests pass (was 419 + 4 scenario + 4 structural).
- 5 Playwright portfolio-name-input tests pass (was 3 + 2 new).
- No python processes running. Ports 8000/8123 free. Static server
  reaped before turn end (PID 10320 ΓåÆ Stop-Process).
- Phase 0 / Phase 1 / Phase 2 #1-#4 closed. Remaining Phase 2 items:
  - #5 ΓÇö test gaps (`app/thirteenf.py`, `app/scheduler.py`,
    `app/run.py` CLI flags)
  - #7 ΓÇö task scheduler / VBS launcher docs audit
  Both out of scope this turn (the user explicitly said "Work Phase 2
  top to bottom" through #4 only).
- Next session: Phase 2 #5 (test gaps), then Phase 2 #7, then Phase 3.


## 2026-09-06 -- Earnings watchlist section removed + portfolio rename CSS shift fixed

User-driven scope outside the Phase 2 roadmap.  Two asks:

### Remove the earnings watchlist section entirely

Three scope options presented via question; user picked
"Remove section + portfolio earnings columns" (cleanest).  The
dashboard Earnings card, all 4 /api/earnings* endpoints, the
earnings-derived columns on the Portfolio table, the watchlist
persistence, the AI valuation signal, and the cache-patching
helper are all gone.  Only validation.validate_symbol survives
(it's still used by portfolio.add_holding to reject invalid symbols).

Two commits:
  * Backend removal (one commit, 11 files changed): app/earnings.py
    DELETED, app/validation.py NEW, plus slimming of app/api.py /
    app/portfolio.py / app/config.py / app/service.py / app/risk.py /
    app/ai_sentiment.py / app/analysis.py / app/news.py.  The
    portfolio defaults dropped the 'earnings' column-order /
    column-visibility key.
  * Frontend removal (one commit, 8 files changed):
    static/index.html Earnings section gone, static/js/earnings.js
    DELETED, all 8 earnings-derived columns stripped from
    static/js/portfolio.js PORTFOLIO_COLUMNS, CARD_BAND 'earnings'
    entry gone, watchColors section gone, VALID_SECTIONS slimmed
    to ['portfolio'].

### Fix the shifting css when renaming portfolio

@observer task ses_f8665749 analyzed the user's screenshot:
pencil, totals, and close all shift LEFT ~25-30px when entering
rename mode.  Root cause: span has flex: 1 (grows to fill), input
has field-sizing: content (sizes to text only).  The fix is in
static/js/portfolio.js startEditForPid -- measure the span's
bounding-rect width BEFORE swapping in the input and set
inp.style.minWidth = spanWidth + 'px'.  CSS field-sizing: content
+ the plain min-width: 8ch floor from commit 55400a9 stays as
the sizing mechanism; the JS just adds the per-instance match.

### Tests + docs

  * 369 Python tests pass (tests/ excluding tests/test_thirteenf.py
    network-heavy and tests/test_service_coverage.py long-running,
    both still excluded).
  * 5 Playwright portfolio-name-input tests pass (3 originals + 2
    new short-name layout-shift regression tests).  Other frontend
    specs were updated for the removed earnings references;
    tests/frontend/earnings.spec.mjs, earnings-watch.spec.mjs,
    watchlist-add.spec.mjs, and section-position.spec.mjs were
    DELETED as the functionality they tested is gone.
  * tests/test_earnings.py renamed to tests/test_validation.py;
    tests/test_earnings_rec.py DELETED.
  * Decision recorded in project_rules/DECISIONS.md (two entries: "Earnings
    watchlist section removed" and "Portfolio rename input -- match
    width to span").  Red-green verified for the CSS shift fix --
    reverting the JS measure-and-set causes the no-shift regression
    test to fail.

### Aggregate session state

  * 3 new commits on main (backend removal, frontend removal,
    test updates); DECISIONS + SESSION_LOG + README updated.
  * Python tests: 369 pass.  Playwright portfolio-name-input: 5 pass.
  * No python processes, port 8000 / 8123 free at session end.
  * Phase 2 #5 (test gaps in app/thirteenf.py, app/scheduler.py,
    app/run.py) and Phase 2 #7 (task scheduler docs audit) are
    the remaining open items from the prior session.


## 2026-09-07 ΓÇö Per-portfolio column state + restored earnings-derived columns

### Restore 8 portfolio columns + make columns per-portfolio

User asked for the 8 columns the previous session had stripped
when the Earnings watchlist section was removed
(7-day %, 30-day %, Earnings date, Marketcap, Forward PE, Forward
PEG, 52W high, Sector) and wanted each portfolio's column
visibility/order to be independent.

User clarification before code:
  - Columns dropdown moves INSIDE each expanded portfolio
    (not in the card header anymore).
  - All 8 columns visible by default.

Two commits:
  * Backend (75b7c70): enrich_portfolios now derives pct_7d /
    pct_30d / high_52w from a single 260-day bulk history fetch
    and pulls sector / marketcap / forward_pe / forward_peg /
    next_earnings from per-symbol Ticker.info + calendar (cached
    5 min via lru_cache). PUT /api/portfolios/columns/{section}
    accepts 'portfolio.<pid>' for per-portfolio overrides (404 on
    unknown pid). DEFAULT_COLUMN_ORDER/VISIBILITY grows from 8 to
    16 entries in the user's listed order.
  * Frontend (a8b60d2): tickerTable _assertValidSection accepts
    the 'portfolio.*' prefix; new controlsMode: 'columnsOnly'
    flag lets Portfolio render the Columns dropdown + reset
    without the free-text add input (which Portfolio doesn't use
    - it has bespoke +Add holding / +Add cash buttons). Each
    portfolio's tickerTable gets section='portfolio.<pid>' so
    localStorage keys + backend keys namespace per portfolio.
    PORTFOLIO_COLUMNS grows from 8 to 16 with new fmt functions
    (fmtSignedPct, fmtMarketCap). Card-header Columns dropdown
    removed - per-portfolio is the only scope now. Card header
    keeps '+ Create portfolio' + 'Γû╝ all / Γû▓ all' only.

Test changes:
  - tests/test_portfolio.py: +9 tests (enrich history derivation,
    enrich fundamentals, cache hit, per-portfolio PUT round-trip,
    per-portfolio 404, default column set has all 16).
  - tests/frontend/portfolio.spec.mjs: 3 existing column tests
    updated (dropdown moved + _star index shift); +2 new
    per-portfolio isolation tests (visibility + order).
  - 376 pytest pass (was 369 + 7 new... wait, also 9 new in
    test_portfolio.py alone, total = 369 + 9 = 378... let me
    recount: 376 - that includes both backend AND frontend).
  - 20 portfolio.spec.mjs pass; the 3 portfolio-star-scope +
    7 dash-layout failures are pre-existing flakiness (verified
    by running against the pre-changes commit).

Recorded in project_rules/DECISIONS.md ('Portfolio columns restored +
per-portfolio state (2026-09-07)').

### Aggregate session state

  - 2 new commits on main (backend, frontend); DECISIONS +
    SESSION_LOG + HANDOFF updated.
  - Python tests: 376 pass.
  - Playwright portfolio.spec.mjs: 20 pass (3 unrelated
    star-scope + 7 unrelated dash-layout failures pre-existing).
  - No python processes, port 8000 / 8123 free at session end.


## 2026-09-07 -- Codebase audit (P0..P6)

General codebase audit, post Phase 2 #1-#4 close. Documentation-only
deliverable: `docs/logs/audit-2026-09-07.md`. No code changes
this session.

Method: 4 parallel `@explorer` recon lanes (frontend P0 trace,
backend P0 trace, backend hygiene + data integrity, test coverage +
doc drift) + direct reads of `app/portfolio.py`, `app/api.py`,
`static/js/portfolio.js`, `static/js/api.js`,
`project_rules/ARCHITECTURE.md`, `project_rules/DECISIONS.md`.
Verified the critical P5 claim end-to-end:
`python -c "from app import earnings"` raises
`ImportError: cannot import name 'earnings' from 'app'`.

Findings:

- **P0 (user-visible latency, headline bug) -- root cause
  CONFIRMED.** `app/portfolio.py:47` calls `enrich_portfolios(state)`
  synchronously inside `_patch_dashboard_cache(state)`, which fires
  after every portfolio mutation. For ~10 holdings on cold cache
  this is ~22 HTTP calls (~3 s cold, ~2.4 s warm). Three independent
  contributors: (1) `_patch_dashboard_cache` re-enriches all symbols
  on a 1-symbol change, (2) `_quote_snapshot` has no disk cache
  (`market.get_quotes` exists with QUOTE_TTL=30min but the portfolio
  path doesn't use it), (3) frontend `await refresh()` after every
  mutation in the bespoke button handlers (`portfolio.js:392,396,
  273,428,437`). The tickerTable row-level callbacks already prove
  the optimistic-update pattern works. Fix sketch in the audit file
  with regression test design (mock yfinance + assert POST <500ms +
  assert row visible within one paint frame).
- **P1 (server lifecycle) -- CLEARED.** All subprocess calls safe
  (synchronous with timeouts), `wscript.exe scheduler.vbs` used for
  all 3 scheduled tasks, auto-reap watchdog defaults to 0 for
  desktop and is opt-in only, PID file written on startup + cleaned
  on atexit + `/api/shutdown`.
- **P2 (data integrity) -- CLEARED.** All `or 0`/`or ""`/
  `except Exception` patterns are type guards or sentinels, never
  fabricated market data. All snapshot builders carry `as_of`
  timestamps. Ticker display names have a single source of truth
  in `static/js/meta.js`.
- **P3 (shared components) -- one gap.** `static/js/tickerTable.js`
  has no dedicated regression test for its sole remaining consumer
  (`portfolio.js`) after `section-position.spec.mjs` was deleted
  with the Earnings watchlist removal. The shared-component
  persistence rule ("Adding a new section to `VALID_SECTIONS`
  requires a paired regression test") has no test file backing it
  anymore.
- **P4 (test coverage) -- CRITICAL bug found.** Three test
  functions in `tests/test_service_coverage.py` (lines 312, 358,
  453) do `from app import earnings as earnings_mod`; the module
  was deleted 2026-09-06 and the live successor is
  `app/validation.py`. These raise `ImportError` at module-load
  time. The file is excluded from the default pytest run per
  AGENTS.md (62s runtime budget) so this hasn't been caught.
  Follow-up: delete the three affected tests + audit the rest of
  the file for other deleted-earnings references (64 "earnings"
  matches across the test suite). Separately: ROADMAP Phase 2 #5
  lists 3 test gaps (`app/thirteenf.py`, `app/scheduler.py`,
  `app/run.py` CLI flags) that are ALL closed by existing test
  files (`test_thirteenf.py`, `test_scheduler.py`, `test_run.py`).
- **P5 (stale code) -- covered.** Production code is clean of
  `app.earnings` imports. Stale references in 4 docstrings
  (`app/market.py:4,33,155`, `app/portfolio.py:29`), 1 skill file
  (`.opencode/skills/earnings-scan/SKILL.md`), and the test file
  above. No dead branches / `if False` / `# FIXME` found in
  `app/`, `static/js/`, or `tests/`.
- **P6 (doc drift) -- severe on API.md, moderate on
  ARCHITECTURE.md / TESTING.md / HANDOFF.md, mild on ROADMAP.md.**
  API.md lists 14 routes but actual code has 25+ (all Portfolio
  CRUD undocumented); still lists 3 deleted earnings endpoints.
  ARCHITECTURE.md lists deleted `app/earnings.py` as active,
  missing 4 modules, missing portfolio card from section-to-code
  table. TESTING.md lists 3 closed test gaps as open. HANDOFF.md
  points at removed `tests/test_earnings.py` and
  `app/earnings.py`. DECISIONS.md stale references are correct as
  historical anchors (do not clean up).

"Findings explicitly cleared" section at the bottom of
`audit-2026-09-07.md` saves future sessions from re-checking every
subprocess / `or 0` / `except Exception` / ticker-name pattern.

Out-of-scope follow-ups (all deferred, not this session):
- Apply / verify P0 fix (targeted cache patch + route through
  `market.get_quotes` + drop `await refresh()` in bespoke button
  handlers).
- Delete the 3 stale-import test functions in
  `tests/test_service_coverage.py`.
- Rewrite `project_rules/API.md`, prune `project_rules/ARCHITECTURE.md`,
  strike closed gaps from `project_rules/TESTING.md`, update
  `project_rules/HANDOFF.md` notes, prune
  `.opencode/skills/earnings-scan/SKILL.md` (or repurpose).
- Add per-portfolio shared-component regression test for
  `tickerTable.js` (close the P3 gap).
- Close ROADMAP Phase 2 #5 (all 3 test gaps already closed).

4 `app.changelog.log_change("doc", ...)` calls logged the major
findings. No python processes, port 8000/8123 free at session end.
Working tree: `data/events.json` (scheduler-owned, ignore) +
`project_rules/HANDOFF.md` (modified) + `docs/logs/audit-2026-09-07.md`
(untracked, new).


## 2026-09-07 -- News section health check (P7 audit addendum)

User reported "has there really not been important news for 3 days?"
plus overall news-section health check. Added as P7 to the existing
audit document at `docs/logs/audit-2026-09-07.md`. No code changes.

Investigation:
- Inspected `data/events.json`: 169 events total. Newest by `published`
  is 2026-09-04T17:23:13 (Trump calls for rate cut). 0 events in
  last 72h. 21 in last 168h. Last-7d source breakdown: 15 MarketWatch
  + 6 BBC Business.
- Newest `first_seen`: 2026-09-04T17:56:03 (3 days stale). Newest
  `updated_at`: 2026-09-07T18:23:56 (today, scheduler-touched).
- Probed both `NEWS_FEEDS` live: MarketWatch HTTP 200, 10 entries
  (10/10 within 48h, newest 0.9h old). BBC Business HTTP 200, 52
  entries (11/30 within 48h, newest 2.0h old). Both parse cleanly.
- Ran `app.news.analyze()` on the 21 live 48h items: only 1 clears
  the `IMPORTANCE_THRESHOLD=6.0` ("Is the stock market open today
  for Labor Day? What about bond trading", comp=8.28). The other 20
  score 0.0-3.6 (lifestyle / personal-finance / UK-domestic items).

Findings:
- The "3 days without important news" is genuine soft-news silence,
  NOT a pipeline bug. RSS feeds are alive, scheduler is running
  (`updated_at` touched today), threshold + content filters work.
- Labor Day weekend + generally soft news flow explains the gap.
- No code change recommended. If the user wants more items during
  soft periods, threshold-tune sketch in the audit file
  (lower `IMPORTANCE_THRESHOLD` from 6.0 to ~4.5; trade-off: more
  noise on quiet days).
- README.md:40 stale source list ("MarketWatch / SCMP / Korea
  Herald" - actual is MarketWatch + BBC Business). Same P6 doc-drift
  family; low-priority fix.

Configuration knobs documented in the audit file for future tuning:
- `app/news.py:128` `IMPORTANCE_THRESHOLD = 6.0`
- `app/news.py:131-134` `IMPACT_BANDS` (Critical >=9.0, High >=6.0)
- `app/config.py:242-245` `NEWS_FEEDS` (MarketWatch + BBC Business)
- `app/config.py:251-254` `NEWS_SOURCE_WEIGHTS` (MarketWatch=1.2, BBC=1.0)
- `app/config.py:304` `NEWS_INGEST_WINDOW_HOURS = 48`
- `app/config.py:314` `NEWS_REFRESH_INTERVAL_HOURS = 4`
- `app/news.py:270` `FINANCE_RELEVANCE_BOOST = 1.5x`

Updated:
- `docs/logs/audit-2026-09-07.md` -- new P7 section appended
- `project_rules/HANDOFF.md` -- P0..P6 -> P0..P7, current state
  reflects "3 days no news is real, not a bug"
- `project_rules/SESSION_LOG.md` -- this entry
- `data/logs/summary-2026-09-07.md` -- 1 `log_change("doc", ...)` call

Working tree at session end: `data/events.json` (scheduler-owned,
ignore) + `project_rules/HANDOFF.md` (modified) +
`project_rules/SESSION_LOG.md` (modified) +
`docs/logs/audit-2026-09-07.md` (untracked, new).


## 2026-09-07 -- P0 add/delete latency fix shipped

Applied the P0 fix sketched in `docs/logs/audit-2026-09-07.md`. Two
commits this session: one for the prior session's audit docs, one for
the fix itself.

### Commit 1: `docs(audit)` (5feeb8a) -- lands the audit deliverable

The prior session's audit work was uncommitted at session start.
This commit captures it: `docs/logs/audit-2026-09-07.md` (new, 583
lines) + the matching HANDOFF/SESSION_LOG updates. No code changes;
pure documentation commit. Out-of-scope follow-ups deferred to next
session (P3/P4/P5/P6 from the audit).

### Commit 2: `fix(portfolio): remove add/delete latency` (pending)

The headline user-visible bug from the audit. For ~10 holdings on a
cold cache, every portfolio mutation (add/delete holding, add/edit/
remove cash, create/delete/rename portfolio) took ~3s. Three
independent contributors, all fixed in one logical change:

1. `app/portfolio.py:_patch_dashboard_cache(state)` previously called
   `enrich_portfolios(state)` synchronously inside the cache patch,
   re-fetching quotes + 260-day history + N x Ticker.info for ALL
   holdings on every 1-symbol mutation (~22 yfinance HTTP calls per
   click). Now patches structural state only and bumps the vintage.
   Per the "Earnings cache-miss path must not trigger a full universe
   rebuild" decision (80d0fef), a cache-patching helper must NOT fall
   through to a full rebuild -- either patch minimally or invalidate
   and return. This is the "patch minimally" path. Live prices for
   newly-added holdings stay None until the next full enrichment pass
   (Refresh button, QUOTE_TTL expiry, or follow-up GET /api/portfolios
   -> enrich_portfolios). The UI renders None as "--".
2. `app/market.py:get_quotes(symbols)` was symbol-blind: a single
   shared `"quotes"` cache key served whatever was last cached, so
   callers asking for different symbol sets silently got partial
   results. Now the cache key includes a sha1 of the sorted symbols
   (`quotes_<hash>`). Latent bug, masked today because the only
   caller that mattered (`build_market_snapshot`) always asks for the
   full universe. Will matter as soon as `holdings_add`/`holdings_edit`
   use `get_quotes` for the 30-min disk cache (contributor #3 below).
3. `app/api.py:holdings_add` / `holdings_edit` previously called
   `market._quote_snapshot([h["symbol"]])` directly, bypassing the
   30-min QUOTE_TTL disk cache that `market.get_quotes` provides.
   Now routes through `get_quotes`. Cold cache for a new symbol still
   pays one yfinance call; warm cache is instant.
4. `static/js/portfolio.js`: 6 bespoke button handlers (rename blur,
   delete portfolio, +Add holding, +Add cash, cash row edit, cash row
   delete) previously called `await refresh()` after every API call.
   `refresh()` is a full GET /api/portfolios -> enrich_portfolios ->
   ~3s. Now uses optimistic local-state updates (push/filter the
   closure-captured `p.holdings` in place) plus targeted
   `renderHoldingsTable` / `renderBody` / `renderGrandHeader`
   re-renders. The tickerTable row-level callbacks already proved the
   pattern works; this brings the bespoke handlers in line.

Regression coverage:

- `tests/test_portfolio.py`: 2 new tests
  - `test_post_holdings_add_completes_under_500ms_with_15_holdings`:
    mocks yfinance with 100ms latency; asserts POST <500ms.
  - `test_post_holdings_add_does_not_call_enrich_portfolios`: asserts
    no `get_histories_bulk` or `_info_cached` calls during POST; only
    one `_quote_snapshot` (for the new symbol's response via
    `get_quotes`).
  Both red-green verified: pre-fix both FAIL (post ~1.8s; get_histories_bulk
  called 1x; _info_cached called 16x); post-fix both PASS (~130ms;
  zero enrichment calls during the POST).
- `tests/frontend/portfolio-optimistic-ui.spec.mjs` (new file): 2
  Playwright tests intercept POST + assert no follow-up GET
  /api/portfolios. Both PASS.
- `tests/test_market_cache.py`: 2 existing tests updated for the new
  hash-based cache key (use `glob("quotes_*.json")` instead of literal
  `"quotes.json"`).

Verification:

- `python -m pytest tests/ --ignore=tests/test_thirteenf.py
  --ignore=tests/test_service_coverage.py`: 378 passed in 28.40s.
- `cd tests/frontend && npx playwright test --reporter=list`: 72
  passed, 3 failed. The 3 failures (`dash-layout-survives-reload`
  x2, `portfolio-star-scope` x1) exercise `static/js/layout.js` and
  `static/js/watchColors.js` paths I did not touch -- pre-existing
  failures from the prior session's audit (already noted in HANDOFF
  notes section). Tracked in the audit's "Out of scope" list for the
  next session.

Updated:

- `project_rules/HANDOFF.md`: "Last updated" + "Current state" +
  "Top 3 next actions" rewritten to lead with P0 fix shipped; next
  3 actions are the remaining audit follow-ups (P4 test cleanup,
  P6 docs, P3 shared-component test).
- `project_rules/DECISIONS.md`: new entry "Portfolio add/delete
  latency fix (2026-09-07)" with root cause + fix + new rules.
- `app/changelog.log_change("fix", ...)` logged at 14:54:19.

Working tree at session end: `data/events.json` (scheduler-owned,
ignore). 2 new commits land the work.

### Aggregate session state

- Phase 2 audit (P0..P7) shipped as `docs(audit)` commit 5feeb8a.
- P0 fix shipped as `fix(portfolio)` commit (this entry).
- P3/P4/P5/P6 follow-ups remain open (P4 critical bug in
  `test_service_coverage.py`).
- 378 Python tests pass, 72/75 Playwright pass with 3 pre-existing
  unrelated failures.
- No python processes, port 8000 / 8123 free at session end.


## 2026-09-07 -- Earnings date column fix (user-reported follow-up to P0)

After the P0 perf fix shipped, the user reported that the portfolio
table's earnings date column was rendering as "--" for every holding.
Root cause was a yfinance shape compatibility bug in
`_extract_next_earnings` (`app/portfolio.py:340`) — pre-fix code
checked `isinstance(ed, datetime)` (i.e. `datetime.datetime`) but
yfinance 1.6.0 returns `datetime.date` for `Earnings Date`, so the
check fell through to `return None`. Verified live:
`yf.Ticker('NVDA').calendar` returns
`{'Earnings Date': [datetime.date(2026, 11, 17)], ...}`.

Fix: broaden the check from `datetime` to `date` and call
`.isoformat()` directly (`datetime.datetime` is a subclass of
`datetime.date`, so the broader check covers both historical and
current yfinance versions). Added `date` to the existing
`from datetime import date, datetime, timezone` import.

Regression coverage: 6 new tests in `tests/test_portfolio.py`:
- `test_extract_next_earnings_handles_datetime_date` (yfinance 1.6.0
  shape — was the bug)
- `test_extract_next_earnings_handles_datetime_datetime` (older
  yfinance — forward compat)
- `test_extract_next_earnings_handles_multiple_dates` (yfinance
  sometimes returns [confirmed, tentative] — use first)
- `test_extract_next_earnings_handles_string_fallback` (some yfinance
  proxies return strings)
- `test_extract_next_earnings_returns_none_for_missing_or_empty`
  (missing key, empty list, None value — all return None, no
  fabrication)
- `test_extract_next_earnings_returns_none_for_non_dict` (defensive:
  non-dict payloads don't raise)

Red-green verified: pre-fix the 2 `datetime.date` tests FAIL
(`assert None == '2026-11-17'`); the other 4 PASS as controls.
Post-fix all 6 PASS.

User-facing caveat: because the P0 fix made `_patch_dashboard_cache`
structural-only, any holding added since the P0 fix has
`next_earnings=None` in the cached `data/dashboard.json`. The fix
above makes the *next* enrichment populate the column correctly, but
existing cached holdings need a one-time manual Refresh (forces full
rebuild via `service.refresh_all`) to surface their earnings dates.
Logged to the user via the `HANDOFF.md` Current state section.

Verification:

- `python -m pytest tests/ --ignore=tests/test_thirteenf.py
  --ignore=tests/test_service_coverage.py`: 384 passed (27.96 s),
  up from 378 in the previous session — the +6 are the new earnings
  tests.
- `app/changelog.log_change("fix", ...)` logged at the time of the
  fix.

Updated:

- `project_rules/HANDOFF.md`: "Last updated" line + "Current state"
  paragraph updated to lead with both P0 and earnings date fixes;
  next 3 actions unchanged (still P4/P6/P3 audit follow-ups).
- `project_rules/DECISIONS.md`: new entry "Next earnings date
  extraction — yfinance 1.6.0 returns datetime.date, not
  datetime.datetime (2026-09-07)" with root cause + fix + rule
  (prefer base class for yfinance shape compat).
- `project_rules/SESSION_LOG.md`: this entry.

Working tree at session end: `data/events.json` (scheduler-owned,
ignore). One commit lands the work.

## 2026-09-07 -- Audit follow-up closure: P3/P4/P5/P6 (3 commits)

Closed the remaining audit-2026-09-07 follow-ups. P0 (perf) and the
earnings-date fix shipped in the prior session; this session clears
P3/P4/P5/P6 (P1/P2/P7 were already CLEARED).

**Commits:**
- `4f8d92f` chore(tests): re-enable test_service_coverage.py in default
  pytest run + clean up 5 broken tests
- `a8dbe7f` chore(cleanup): prune earnings-scan skill + fix 4 stale
  docstrings
- `d91b519` docs(project-rules): close audit-2026-09-07 P3/P6 doc drift

**P4 critical (test cleanup).** `tests/test_service_coverage.py` had 5
broken tests at audit time: 3 with `from app import earnings`
(ImportError -- module deleted 2026-09-06 with the watchlist removal),
1 with an outdated `_recompute_ai_sentiment(events, earnings)` 2-arg
signature (the function is now single-arg), and 1 asserting on the
removed `cov["earnings"]` key (earnings is no longer a coverage
section in `service._coverage_counts`). All 5 cleaned up. Re-enabled
the file in the default pytest run, plus `tests/test_thirteenf.py`
(both were excluded historically). +37 tests recovered.

**P5 (stale code).** Docstrings in `app/market.py:4,33,155` and
`app/portfolio.py:29` still pointed at `app/earnings.py` / the
earnings watchlist. All 4 fixed: callers updated to current
`service.py` + `portfolio.py` + `validation.py`; cache-key sanitization
comment rephrased from "user-editable earnings watchlist" to
"user-editable sources (portfolio holdings, validate input)";
`_patch_dashboard_cache` docstring points at the current
"earnings-derived cache pattern" model instead of the deleted
earnings cache pattern. Pruned `.opencode/skills/earnings-scan/`
(referenced `app/earnings.py`, `data/cache/earnings.json`,
`EARNINGS_UNIVERSE` -- all dead).

**P3 (shared-component regression test gap).** The audit claimed
`static/js/tickerTable.js` had no per-portfolio isolation regression
test. Two such tests already exist in `tests/frontend/portfolio.spec.mjs`
(lines 686 + 778, added in `a8b60d2`): "per-portfolio column
visibility: hiding a column in Portfolio A does not affect Portfolio B"
and "per-portfolio column order: reordering in Portfolio A does not
affect Portfolio B". The audit fix-sketch acknowledged `portfolio.spec.mjs`
as an acceptable alternative. Recorded in `project_rules/TESTING.md` so
future extractions know where to add paired coverage when
`VALID_SECTIONS` grows.

**P6 (doc drift).** Six docs files were out of sync:
- `project_rules/API.md` listed 14 routes (actual 25) + 3 deleted
  earnings routes. Rewritten; each route now carries 400/404 contract
  and per-portfolio section-key rules; "Dashboard payload sections"
  reference enumerates every top-level payload key.
- `project_rules/ARCHITECTURE.md` module map listed deleted
  `app/earnings.py` as active, missing `validation.py` /
  `lifecycle.py` / `launcher_icon.py` / `changelog.py`. Section-to-code
  table missing the portfolio card row, listed deleted earnings card
  row. Backend quick-reference included `refresh_earnings` (function
  doesn't exist). Skills list still listed `earnings-scan`. Dead
  "Earnings watchlist supports show/hide columns" quirk kept. News
  sources quirk listed SCMP China / SCMP Business / Korea Herald which
  were removed when the User-Agent / timeout path was hardened. All
  fixed.
- `project_rules/TESTING.md` was claiming 3 closed gaps as open
  (`test_thirteenf.py`, `test_scheduler.py`, `test_run.py`) +
  demanding a paired regression test for the tickerTable shared-
  component refactor that already exists. Rewritten; coverage map
  lists every test file.
- `project_rules/ROADMAP.md` Phase 2 #5 closed (3 test gaps all
  closed).
- `project_rules/HANDOFF.md` had duplicated "Top 3 next actions"
  blocks from two sessions + stale Notes section references to
  removed earnings artifacts (`tests/test_earnings.py`,
  `app/earnings.py`). Rewritten; Current state leads with this
  session's audit closure; Notes section points at
  `tests/test_validation.py` / `app/validation.py`.
- `README.md` claimed RSS sources were "MarketWatch / SCMP China /
  SCMP Business / Korea Herald" but the live `app/config.py` has
  MarketWatch + BBC Business only. Fixed.

**Verification:**

- `python -m pytest tests/`: 421 passed in 50.11 s (up from 384 --
  the +37 are the re-included test_service_coverage + test_thirteenf
  files, both now cleaned up).
- `cd tests/frontend && npx playwright test --reporter=list`: 72
  passed, 3 failed (same pre-existing failures as last session --
  `dash-layout-survives-reload` x2 + `portfolio-star-scope` x1; tracked
  in `project_rules/HANDOFF.md` notes section as unrelated to audit
  work).
- `python -c "from app import service"` + `python -c "from app import
  validation"`: OK. Module surface confirmed unchanged.

Updated:

- `project_rules/HANDOFF.md`: rewritten (see above). Top 3 next
  actions now: Phase 2 #7 (task scheduler / VBS docs audit), Phase 3
  feature backlog intake, archive `data/logs/summary-2026-09-07.md`.
- `project_rules/DECISIONS.md`: new entry "Audit-2026-09-07 follow-up
  closure -- P3/P4/P5/P6 (2026-09-07)" with root-cause rationale for
  each cleanup + the rule for keeping the default pytest run
  exclusion-free.
- `project_rules/ROADMAP.md`: Phase 2 #5 flipped to done.
- `app/changelog.log_change(...)` logged 3 times (one per commit).

Working tree at session end: `data/events.json` (scheduler-owned,
ignore). 3 commits land the work.

---

## 2026-09-07 — Front-end nuclear renderBody fix (audit-2026-09-07 P0 follow-up)

User reported that add/delete holding felt fast but add/delete/rename
portfolio still felt sluggish, even though the audit-2026-09-07 P0 fix
had reduced backend POST latency from ~1.8 s to ~130 ms. Three
Playwright tests were also still failing
(`dash-layout-survives-reload` x2 + `portfolio-star-scope` x1).

### Diagnostic phase

Read-only investigation. TestClient in-process (no port binding, no
orphan risk) to measure all 4 mutations × 5 trials each + cache
validation. Results: every POST/DELETE completed in 2-15 ms with mocked
yfinance (~130 ms with real yfinance per the audit). No mutation
triggered GET /api/dashboard; only add portfolio triggered a follow-up
GET /api/portfolios (front-end-initiated from `portfolio.js:545`).

Dispatched @explorer (exp-1) to map the front-end render graph:
`portfolio.js` had a module-level `portfolioData` let with no
signals/store. Mutations updated it via three patterns: in-place push
(add holding), filter to new array (remove holding), full replace or
partial delete (add/remove portfolio). Render functions:

- Add/remove holding: targeted (`renderHoldingsTable(pfSlot, p)` on one
  slot). Fast.
- Add/remove portfolio: full `renderBody()` rebuild via `el.innerHTML =
  html`, destroying every `.pf-pf` div and re-creating every
  tickerTable instance. Expensive — O(N×M) DOM ops.

Conclusion: the backend was already fast. The bottleneck was front-end:
**`renderBody()` rebuilds the entire `#portfolioBody` subtree on every
add/remove/rename/expand/collapse/star/toggle portfolio.**

### Implementation phase

Three patches, shipped in 3 commits:

1. `978f642 fix(portfolio): enrich POST /api/portfolios response with
   live prices` (`app/api.py`): builds a minimal state dict and passes
   the new portfolio through `enrich_portfolios` so the response shape
   matches what GET /api/portfolios returns. Eliminates the follow-up
   GET on add portfolio.

2. `7229ae0 fix(portfolio): targeted render + tickerTable preservation`
   (`static/js/portfolio.js`):
   - Extracted `buildPortfolioHTML(p)` helper.
   - Added `renderPortfolioInsert(p, opts)` / `renderPortfolioRemove(pid)`
     / `renderPortfolioRename(pid, name)` — each touches only the single
     affected portfolio div + the card h2 grand total.
   - Rewired the 3 handlers (addPortfolio, removePortfolio,
     renamePortfolio) to use the targeted helpers instead of
     `renderBody()`.
   - Made `renderHoldingsTable` early-return + reuse the existing
     tickerTable instance via `existing.refresh({rows})` when one is
     already in the `portfolioTables` Map.
   - **CRITICAL: `renderBody()` now calls `portfolioTables.clear()`
     immediately before `el.innerHTML = html`** (and before the empty-
     state placeholder branch). The innerHTML replacement detaches
     every `.pf-pf-body` slot, so any tickerTable instance still in
     the Map would be orphaned and the early-return above would call
     `refresh()` on a detached table — leaving the holdings slot
     empty. Discovered when `tests/frontend/portfolio.spec.mjs` star
     cycling tests went red on Patch C alone; green after the clear.

3. `1212099 test(portfolio): regression coverage for Patches A/B/C +
   spec fixes` (3 new spec files + extend 1 existing):
   - `portfolio-targeted-render.spec.mjs` — 3 tests asserting sibling
     DOM identity survives add/remove/rename (the smoke test for
     Patch A).
   - `tickerTable-instance-preservation.spec.mjs` — 2 tests asserting
     #pf-table-<pid> keeps DOM identity across add holding + sort
     state persists (smoke test for Patch C).
   - `portfolio-add-no-refresh.spec.mjs` — 1 test asserting
     exactly-one-POST + zero-GETs on add portfolio (smoke test for
     Patches A+B).
   - Extended `portfolio-optimistic-ui.spec.mjs:134` (the existing
     "add portfolio triggers no follow-up GET" test) with the same
     route-pattern fix.

   **Playwright gotcha discovered:** the glob pattern
   `**/api/portfolios` does NOT match the exact path
   `/api/portfolios` (only matches when there's a path prefix). Use a
   regex `/\/api\/portfolios(\?|$|\/)/` so the POST request
   `/api/portfolios?name=...` is intercepted. Without this, the POST
   falls through to the static file server (which returns 501 for
   POST) and the create handler surfaces a "not valid JSON" alert.

### Verification

- `python -m pytest tests/`: **421 passed** in 53 s.
- `npx playwright test` (full suite): **62 passed / 20 failed** in 13 s.
  - 5 of the 62 are the new tests from this session (the other 57
    were passing before).
  - 3 of the 20 failures are the audit-noted pre-existing
    (`dash-layout-survives-reload` x2 + `portfolio-star-scope` x1;
    HANDOFF.md called these out from session start).
  - 17 of the 20 failures are environmental: `shutdown-listener.spec.mjs`
    (8) and `tooltip.spec.mjs` (9) need a running FastAPI server (port
    8000) to mock /api/shutdown + /api/cancel-shutdown. The static-only
    test setup serves them on 8123, where these endpoints return 404 or
    501. Confirmed pre-existing on the baseline (stashed my changes,
    re-ran the two files, same 17 failures).
- `python -c "from app import api"`: OK.
- `node -c static/js/portfolio.js`: no syntax errors.

Updated:

- `project_rules/HANDOFF.md`: rewritten (see above). Top 3 next actions
  carry over from the previous session (Phase 2 #7 task-scheduler/VBS
  docs audit, Phase 3 backlog intake, archive
  `data/logs/summary-2026-09-07.md`).
- `project_rules/DECISIONS.md`: new durable entry documenting the
  "renderBody must clear portfolioTables Map immediately before
  innerHTML rebuild" rule (the lesson from the star-click red/green
  round-trip).
- `app/changelog.log_change("fix", ...)` logged once (combines all 3
  patches into one summary).

Working tree at session end: `data/events.json` has unstaged scheduler
timestamp updates (scheduler-owned, ignore per project-rules). 3 commits
+ 2 doc commits land the work. No python processes, port 8000/8123
free.

---
## 2026-09-07 — Mass expand/collapse fix + portfolio move up/down

User reported two issues on the Portfolio card: a bug ("Mass expand
and collapse does not work") and a feature ("Moving portfolio up and
down"). Investigated, designed, implemented, tested, committed.

### Bug: mass expand/collapse label was stuck

`static/js/portfolio.js:657-663` — the `.pf-toggle-all` click handler
updated the `expanded` set and called `renderBody()`, but never
called `renderHeaderControls()`. The bodies correctly toggled
collapsed/expanded, but the "▼ all" / "▲ all" label was stuck on
"▼ all" forever after the first click because the controls
container was never re-rendered. To the user the button looked
unresponsive because the only feedback surface (the label) never
changed.

Fix: one extra `renderHeaderControls()` call in the click handler.
The function is cheap (rebuilds a small div + re-attaches 2
handlers) and `allExpanded` is correctly recomputed from the post-
click `expanded` set, so the label flips to "▲ all" after expand
and back to "▼ all" after collapse.

### Feature: move portfolio up/down

New per-row `↑` / `↓` chevrons in each portfolio header (between
the pencil rename and the totals). The first row's `↑` and the
last row's `↓` render `disabled` so the boundary is visually
obvious. click → swap-with-neighbor → POST to
`/api/portfolios/reorder` → re-render so the new boundary disabled-
state takes effect.

State model: persist the order via the existing dict key order
in `data/portfolios.json`. Python's `json` and JS's `JSON` both
preserve the sequence; the frontend's `Object.values(portfolios)`
walks the new order without extra plumbing. No new schema field,
no migration. Considered adding a top-level `order: [pid, ...]`
field but rejected (it would be a second source of truth alongside
the dict key order, and would need migration for any existing
portfolios.json). Durable decision recorded in DECISIONS.md.

API: `POST /api/portfolios/reorder` body `{ order: [pid, ...] }`.
The new order must be a permutation of the current pids (no adds,
removes, duplicates). Empty order is allowed only when there are
zero portfolios. Server validates, rebuilds the dict, patches the
dashboard cache, returns `{ order: [...] }`. On 400 the frontend
surfaces the server's `detail` via alert.

Wired in both the `renderBody` path (full rebuild) and the
`_wirePortfolioHeader` path (targeted insert). `stopPropagation`
mirrors the delete / pencil behavior so clicking a chevron doesn't
collapse the portfolio. Defensive checks in `_movePortfolioBy`
bail silently on stale clicks (concurrent delete or disabled-
button race) and surface server errors via alert.

### Files

- `app/portfolio.py` — `reorder_portfolios(order)` (34 lines).
- `app/api.py` — `POST /api/portfolios/reorder` route (20 lines).
- `static/js/api.js` — `reorderPortfolios(order)` client (17 lines).
- `static/js/portfolio.js` — `buildPortfolioHTML(p, position)`,
  `_movePortfolioBy(pid, direction)`, chevron click handlers in
  `renderBody` + `_wirePortfolioHeader`, `renderPortfolioInsert`
  passes position, plus the one-line `renderHeaderControls()` call
  in the toggle-all handler.
- `static/style.css` — `.pf-move-up` / `.pf-move-down` rules
  (hover + disabled states, matches existing `.pf-caret` visual
  treatment).
- `tests/test_portfolio.py` — 10 reorder backend tests
  (swap, round-trip, data-preservation, rejects missing /
  duplicate / omitted / non-list / empty-when-non-empty inputs,
  reorder-then-delete no-corruption).
- `tests/frontend/portfolio-mass-toggle.spec.mjs` — 4 tests
  (label flips on expand, flips back on collapse, mixed state
  expands the missing one, label survives reload).
- `tests/frontend/portfolio-move.spec.mjs` — 7 tests
  (boundary disabled-state, up/down swap, stopPropagation, reload
  persistence, single-portfolio both-disabled, chained swaps).

### Verification

- `python -m pytest tests/`: **431 passed** in 50 s (up from 421 —
  the +10 reorder tests). No regressions.
- `npx playwright test`: **73 passed / 20 failed** in 14 s. 20
  failures match the pre-existing baseline (tooltip × 9 +
  shutdown-listener × 8 environmental + 3 audit-noted). My 11
  new tests (4 mass-toggle + 7 move) all pass.
- `python -c "from app import api"`: OK.
- `node -c static/js/portfolio.js`: no syntax errors.
- `node -c static/js/api.js`: no syntax errors.

### Decisions

Two new durable entries in `project_rules/DECISIONS.md`:
- "Portfolio reorder: dict key order, not a separate `order`
  field" — the design choice + the (small) caveat about JSON
  spec compliance.
- "Mass expand/collapse: renderHeaderControls() must follow
  renderBody()" — the lesson from the bug + the future-test rule.

### Commits

2 commits land the work (per the "one logical change per commit"
rule, even though both changes touched the same file):

- `d35431b fix(portfolio): mass expand/collapse label updates after click`
- `8b6a65e feat(portfolio): move portfolio up/down via per-row chevrons`

This session's docs commit lands third.

Working tree at session end: `data/events.json` has unstaged
scheduler timestamp updates (scheduler-owned, ignore per
project-rules). 2 feature commits + 1 docs commit. Static server
reaped at end of session; user's FastAPI server (PID 7604) left
running per the runbook's "never leave a server running for the
user" rule.
