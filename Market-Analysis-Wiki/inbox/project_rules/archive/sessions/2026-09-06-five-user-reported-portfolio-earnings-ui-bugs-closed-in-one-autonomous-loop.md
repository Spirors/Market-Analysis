# 2026-09-06 — ΓÇö Five user-reported portfolio/earnings/UI bugs closed in one autonomous loop

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

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


