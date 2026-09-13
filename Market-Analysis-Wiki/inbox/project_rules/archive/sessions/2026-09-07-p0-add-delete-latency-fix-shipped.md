# 2026-09-07 — P0 add/delete latency fix shipped

Full text of the entry from `project_rules/SESSION_LOG.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds the full text for the
latest entry and a pointer for older entries).

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


