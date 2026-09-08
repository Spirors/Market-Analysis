# 2026-09-06 — ΓÇö Three regressions from the first round fixed in a follow-up loop

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

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


