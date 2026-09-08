# Session Log

Append-only. Newest entry at the bottom. This file is git-tracked -- unlike
`data/logs/summary-YYYY-MM-DD.md`, which is gitignored and local-only per
`AGENTS.md`. Use this file for anything that needs to survive across
machines or a fresh checkout; keep using the existing `data/logs/` changelog
for its original local-daily-changelog purpose.

> Older logs rotate to `project_rules/archive/SESSION_LOG_ARCHIVE.md` once this file exceeds `{{SESSION_LOG_ROTATION_ENTRIES}}` entries (currently 5 for this project; updated 2026-09-08).

---
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


