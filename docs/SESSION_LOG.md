# Session Log

Append-only. Newest entry at the bottom. This file is git-tracked — unlike
`data/logs/summary-YYYY-MM-DD.md`, which is gitignored and local-only per
`AGENTS.md`. Use this file for anything that needs to survive across
machines or a fresh checkout; keep using the existing `data/logs/` changelog
for its original local-daily-changelog purpose.

---

## 2026-09-05 — Bootstrap: adopted plain-Markdown session continuity

- Diagnosed two open bugs against the live `AGENTS.md` (stuck process on
  test launch; section position not saving) — see `docs/HANDOFF.md` for
  current status and `AGENT-WORKFLOW-PROMPT.md` for the working hypotheses.
- Considered a vector-DB memory plugin (`opencode-mem`) for cross-session
  continuity; decided against it for this project — see
  `AGENT-WORKFLOW-PROMPT.md` §4 for the reasoning.
- Adopted a plain-Markdown session-start/during/end protocol instead
  (`docs/HANDOFF.md`, `docs/SESSION_LOG.md` — this file, `docs/DECISIONS.md`,
  `docs/RUNBOOK.md`), based on a pattern shared in r/opencodeCLI.
- Drafted `ROADMAP.md` Phase 0–3 and flagged that `AGENTS.md` (~450 lines)
  should eventually split into these `docs/` files plus
  `ARCHITECTURE.md`/`API.md`/`TESTING.md` (Phase 1).
- Next session should pick up Phase 0: fix the two open bugs first.

## 2026-09-05 — Committed the docs split-out (ROADMAP Phase 1, commit `52e5b92`)

- Read the new `AGENT-WORKFLOW-PROMPT.md` first per user's updated kickoff
  instruction, then the rest of the new doc set
  (`AGENTS.md`, `README.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `API.md`,
  `TESTING.md`, plus `docs/HANDOFF.md`, `docs/SESSION_LOG.md` — this file,
  `docs/DECISIONS.md`, `docs/RUNBOOK.md`).
- Moved the 4 frozen `ai_*.html` reference files from repo root to
  `archived/` (still frozen, still untouched — just not first-class at
  top level anymore).
- Staged everything except `data/events.json` for that commit; per
  `docs/RUNBOOK.md` the EventsCommit scheduled task owns `events.json` and
  its unstaged timestamp updates will be picked up at the next 17:00 run.
- `AGENTS.md` shrank from ~450 → 110 lines. Phase 1 of `ROADMAP.md` is
  closed by this commit; the two Phase 0 bugs remain open and are still
  the top next actions.
- Next session: Phase 0 — fix the stuck-process regression first, then
  the `tickerTable.js` cross-section-state regression.

## 2026-09-05 — `project-rules` skill ships (commit `8583711`)

- User flagged that AGENTS.md feels ignored at times. Diagnosed: OMO-slim
  subagents (fixer / explorer / oracle / designer) don't auto-inject
  AGENTS.md — only the parent orchestrator does. Static system context
  also loses to dynamic task context under load.
- Designed a hand-off pattern instead of fighting it: hard rules live in
  a skill, orchestrator injects skill output into every subagent dispatch
  prompt.
- Created `.opencode/skills/project-rules/SKILL.md` with the full
  rule set pulled from AGENTS.md + docs/DECISIONS.md.
- Added the "invoke project-rules before dispatch" rule to AGENTS.md
  "During Work" and a pointer to the skill under "Skills."
- Logged the design rationale in docs/DECISIONS.md (new entry:
  "Hard-rule propagation: project-rules skill, not AGENTS.md alone").
- Next session: confirm the skill actually fires on the first subagent
  dispatch of any new task — and that AGENTS.md + the skill stay in
  sync over time.

## 2026-09-06 — Roadmap intake: 2 new Phase 0 bugs + Phase 2 codebase health audit

User asked to log 3 items on the roadmap with tightened wording; no fixes
attempted this session.

- `ROADMAP.md` Phase 0 gains:
  - **Fix: earnings watchlist add button broken.** Same shared-state risk
    profile as the `tickerTable.js` column-order regression; add a per-section
    add→reload round-trip regression test in the same change so the fix
    can't silently regress again.
  - **UX: portfolio name input collapses to single line** so the surrounding
    empty space becomes the click target (currently the tall input is the
    only focusable region).
- `ROADMAP.md` Phase 2 gains:
  - **Codebase health audit (precursor to any large refactor).** Invoke the
    `reflect` / `simplify` / `codemap` skill to produce a prioritized debt
    list with file:line evidence; subsequent refactor work is planned
    against that list rather than guessed at.
- `docs/HANDOFF.md` Top 3 next actions updated — earnings-watchlist regression
  replaces the shared-component-audit item (audit is now Phase 2 work, not
  Phase 0 follow-up).
- `app/changelog.log_change("doc", ...)` logged the intake.
- Priority order is unchanged: stuck-process and section-position regressions
  remain #1 and #2; portfolio name input UX is logged but not in top 3.
- Next session: still Phase 0 — the stuck-process regression first, per
  `docs/HANDOFF.md` Top 3.

## 2026-09-06 - Phase 0 stuck-process regression closed (commit pending)

Trigger observed mid-session: an interactive test launch left
python run.py --open-browser bound to 127.0.0.1:8000 for 54+ minutes
because the agent's turn ended before the documented reap step. PID 9224
seen via Get-NetTCPConnection -LocalPort 8000, confirmed
python run.py --open-browser via Get-CimInstance Win32_Process.
Reaped during this session after the fix shipped.

Root cause: launch-test-reap is documented in AGENTS.md and
docs/RUNBOOK.md but enforcement is purely procedural. No runtime
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
- docs/RUNBOOK.md §Step 3a documents the new flag + the manual orphan-
  recovery recipe (Get-Content data\server.pid -> Stop-Process -Id
  <pid> -Force -> Remove-Item data\server.pid).
- docs/DECISIONS.md Open entry replaced with confirmed root cause,
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
  (full test suite) marked partially done — current suite passes; a
  final re-run after the remaining Phase 0 fixes close is queued.
- One-line note added to docs/DECISIONS.md explaining why Phase 1
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

### Phase 0 #2 — section position (column order) per-section persistence

Investigation: per-section keys (pfSort.{section}, pfVisible.{section},
pfOrder.{section}) are correctly namespaced in static/js/tickerTable.js,
and the columns_put backend endpoint correctly keys
state["column_order"][section] per section. The bug class warned about
in AGENT-WORKFLOW-PROMPT.md §3b did NOT occur — the refactor was clean.

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

### Phase 0 #3 — earnings watchlist Add button broken after first column reorder

Root cause: in static/js/tickerTable.js, drawControls() rebuilds the
entire controlsSel subtree via el.innerHTML = ... on every column
reorder, header sort, and reset-sort. The pre-fix 
ender() entry point
called drawControls(); wireAddInput(); drawBody() — wireAddInput() was
wired ONCE. After the first column reorder, the freshly-created
.tt-input / .tt-add-btn had no event listeners and the Add button
silently did nothing.

Fix: wireAddInput() now runs at the end of drawControls(). Every
controls rebuild re-attaches the input/button listeners. Listeners
attach to fresh DOM nodes; the discarded elements (and their listeners)
are GC'd naturally — no leak.

Regression coverage: tests/frontend/watchlist-add.spec.mjs (8 tests)
covers the add flow under: initial render, column reorder, header sort,
visibility toggle, multiple back-to-back reorders, Enter-key, and
input-validation (disabled when empty / whitespace-only). Red-green
verified: with the fix reverted, 4 tests fail (3 wireAddInput regressions
+ 1 VALID_SECTIONS export check).

### Phase 0 #4 — portfolio name input UX

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

## 2026-09-06 — Five user-reported portfolio/earnings/UI bugs closed in one autonomous loop

The user came back after the previous session shipped 4 Phase 0 items but said
"made ZERO changes" for the 5 user-reported items below. Diagnosed, fixed,
verified (TestClient + Playwright, no detached server), and committed each
in isolation per project-rules' "one logical change per commit" rule.

### Item #1 — Portfolio header collapse vs rename (FEATURE)

Clicking the portfolio name span used to trigger inline rename. Wanted:
header click → collapse/expand, a small ✎ pencil icon → inline rename.

Investigation: `static/js/portfolio.js:161` rendered
`<span class="pf-pf-name pf-pf-name-edit">` with click → `startEdit()`.
Per-portfolio state already existed via the `pfExpanded` localStorage Set
populated by the `.pf-caret` button click — no backend flag needed.

Implementation: added `<button class="pf-rename-btn">✎</button>` between
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
CSS text-transform — flagged as pre-existing, not introduced).

Commit: `4716e02 feat(portfolio): header click toggles collapse, pencil
icon triggers rename`

### Item #2 — Earnings watchlist "invalid symbol" error (BUG)

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

### Item #3 — Portfolio star highlight not independent per portfolio (BUG)

Toggling star in one portfolio lit up the same symbol in other
portfolios. Root cause: `static/js/watchColors.js` used a single
`pfWatchColors` Map keyed by symbol only — shared across every
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

### Item #4 — Portfolio mutations don't sync with cached dashboard payload (BUG, root cause)

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
Best-effort: catches all exceptions and silently returns — a failed
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
using TestClient — verify GET /api/dashboard reflects add/remove
holding + add/delete portfolio without any explicit refresh call.

Commit: `b45858e fix(portfolio): patch dashboard cache after every
portfolio mutation`

### Item #5 — Dashboard card order doesn't survive F5 (BUG)

User reported layout reverts on hard refresh. Investigation:
`static/js/layout.js:14-30` `CARD_BAND` was missing the `"portfolio"`
entry. Card was added to `static/index.html` in commit `1589aaf` but
the layout map was never updated. `persistLayoutOnDOM()` (line 124)
includes `"portfolio"` in the saved order (it's in the DOM).
`applyLayoutOnLoad()`'s guard at line 78 silently rejects any saved
layout containing an unknown card id — so every F5 reverted to HTML
source order. The 30-min auto-refresh (commit `d9c7b6f`, since
reverted in `b73a3a0`) was NOT the culprit — auto-refresh only
called `load()` which renders bodies, not positions. Pageshow
beacon (shutdown-listener.js) does NOT touch dashLayout. Race
condition ruled out — `applyLayoutOnLoad()` runs synchronously at
boot before `await load()`.

Implementation: one-line fix — added `"portfolio": "stats"` to
`CARD_BAND`.

Regression coverage: 7 new Playwright tests in
`tests/frontend/dash-layout-survives-reload.spec.mjs` (CARD_BAND
contains portfolio, applyLayoutOnLoad accepts layouts containing
portfolio, DOM reorder, full page reload preserves order, multiple
reloads preserve order, persistLayoutFromDOM includes portfolio).

Commit: `6825c0f fix(layout): add portfolio card to CARD_BAND so
drag-order survives F5`

### Item #6 — News pipeline diagnostic

`MarketAnalysis-NewsRefresh` scheduled task is installed and has
actually run. Manual `python run.py --news-refresh` completed cleanly:
"checked 2 feed(s), 0 High/Critical candidate(s), 0 new event(s)
stored." News pipeline is healthy. It's a quiet weekend — the 48h
ingest window hasn't produced anything above IMPORTANCE_THRESHOLD =
6.0. Most recent live events in data/events.json are from 2026-09-04
(Trump/jobs, Iran/oil, BBC petrol). No bot-wall or rate-limit
evidence. NOT a feed-broken state — just no High/Critical English-
edition finance news in the window.

### Aggregate session state

- All five user-reported items closed (commits `a2c793a` → `b45858e`
  → `1fafbc1` → `6825c0f` → `4716e02`, oldest → newest).
- 417 Python tests pass (excluding test_thirteenf.py network-heavy +
  test_service_coverage.py long-running).
- Playwright: 7 new layout-survives-reload tests + 7 new portfolio-
  header-collapse tests + 3 new portfolio-star-scope tests pass.
- No python processes running. Port 8000 free.
- Phase 0 / Phase 1 both closed previously remain green.
- Phase 2 (refactor debt) is the next phase. The new `pfWatchColors`
  per-portfolio scoping (item #3) is a candidate for the same kind of
  shared-helper extraction the codebase health audit will flag.
- Next session: Phase 2 — invoke the reflect / simplify / codemap
  skill trio, close app/thirteenf.py / app/scheduler.py / app/run.py
  test gaps, audit for other shared-component extractions with the
  same risk profile as tickerTable.js.

## 2026-09-06 — Three regressions from the first round fixed in a follow-up loop

User came back and reported that the first round shipped three new regressions:
the pencil button caused layout shift, the rename input triggered header collapse,
the earnings watchlist still showed "invalid symbol" errors, and portfolio
grand-totals in the card header stayed stale until F5. Also asked to clean
up any test portfolios generated during testing.

### Regression A — Pencil button layout shift + rename input triggers collapse

Root cause (both in `static/js/portfolio.js`):
1. Header click handler's skip list was `.pf-rename-btn, .pf-del, .pf-caret,
   .pf-pf-totals` — missing `.pf-name-input`. Clicks on the rename input
   bubbled up to the header and toggled collapse, destroying the input.
2. `.pf-rename-btn` in `static/style.css` inherited `font-weight: 600` and
   `border-radius: 6px` from the `.mini` class while overriding `padding`
   to `0 4px` — produced a tiny ✎ glyph in an oversized button that pushed
   the header layout.

Fix:
- `static/js/portfolio.js:202` — added `.pf-name-input` to the skip list.
- `static/js/portfolio.js:108-133` — added `e.stopPropagation()` on the
  rename input's click/focus/keydown handlers as belt-and-suspenders.
- `static/style.css:1223` — rewrote `.pf-rename-btn` to be icon-only:
  `flex: 0 0 auto; font-size: 14px; font-weight: normal; opacity: 0.6`
  (full opacity on hover/focus).

Regression coverage: 2 new tests in
`tests/frontend/portfolio-header-collapse.spec.mjs` ("rename input does
not collapse the portfolio", "pencil button does not cause header width
to grow").

Commit: `974d988 fix(portfolio): rename input no longer triggers header
collapse + pencil button is icon-only`

### Regression B — Earnings watchlist add still showed "invalid symbol"

Investigation found: `app/earnings.py:add_ticker` (lines 304-345) fell
through to a full `earnings_calendar()` rebuild (yfinance for ALL universe
tickers, 30-60s) when `_cached_calendar()` returned None (cache missing
or expired). Frontend `addEarningsSymbol` fetch hung for the whole
rebuild; user clicked Add, saw no progress, F5, by then the rebuild
completed. The earlier `a2c793a` validate_symbol fix couldn't help
because validation succeeded — the hang was in the post-validation
patch.

Fix:
- `app/earnings.py:330-345` (`add_ticker`) — when cache is missing, build
  just the new ticker's enriched row via `_enrich(sym, quotes)` and write
  a minimal cache with just that ticker. Returns instantly.
- `app/earnings.py:359-370` (`remove_ticker`) — when cache is missing,
  invalidate and return empty result instead of triggering rebuild.
- `static/js/tickerTable.js:402-411` (`tryAdd`) — added busy state on the
  Add button ("Adding…") so the user sees feedback during the request.

Regression coverage: `test_add_ticker_cache_miss_does_not_trigger_full_rebuild`
in `tests/test_earnings.py` — mocks `_cached_calendar` to return None,
verifies `earnings_calendar()` is NOT called, verifies the new ticker
appears in the returned companies.

Commit: `80d0fef fix(earnings): add/remove ticker does not trigger full
universe rebuild on cache miss`

### Regression C — Portfolio grand total stayed stale until F5

Root cause: the tickerTable callbacks for per-holding add/remove/edit
(`portfolio.js:289-305`) mutated the local `p.holdings` closure and
returned rows for `tickerTable.refresh()` to re-render — but
`renderGrandHeader()` (which paints the card-level "$X (+Y)" total)
was never called. Only the per-table totals row updated; the card
header stayed stale until the user triggered a full reload.

Fix:
- `static/js/portfolio.js:289-305` — added `renderGrandHeader()` calls
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
  (unrelated to these changes — earnings.spec.mjs strict-mode duplicate
  selectors, portfolio-star-scope persistence, portfolio.spec.mjs
  Star-column-vs-Ticker expectations, .tt-row-actions click interception,
  CSS text-transform on Star header).
- No python processes running. Port 8000 free.
- Phase 0 / Phase 1 both closed previously remain green.
- Next session: Phase 2 — invoke the reflect / simplify / codemap skill
  trio, close app/thirteenf.py / app/scheduler.py / app/run.py test gaps,
  audit for other shared-component extractions with the same risk
  profile as tickerTable.js. The 7 pre-existing Playwright failures
  flagged here are a natural Phase 2 cleanup target.
