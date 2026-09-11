## 2026-09-11 — Portfolio follow-up fixes: live prices always refresh + reorder survives collapse+expand

**Summary:** One commit (`bfb118f`) addressing two follow-up bugs from the
morning's session (`9f6eac1` / `5e00482` / `4392797` / `b0e9789` / `040c409`
/ `1254bb7`). The cooldown logic added that morning was over-aggressive for
the Portfolio section — it blanked the live-price columns on every
in-cooldown refresh — and the ▲/▼ reorder only persisted in the backend
because the closure variable `p.holdings` was never updated by the
optimistic swap.

### Bug 1 — Live prices blank after refresh (Portfolio section)

**Symptom (user-reported):** "Cache data got wiped when refreshed and now I
have to wait till cooldown is over." Clarification via clarifying questions:
portfolios + holdings still visible, but the live-price columns (Last price /
Total value / Daily % / 7-day % / 30-day % / 52W high) all showed "—".

**Root cause:** `app/service.py:refresh_market` (the morning's lane-1 code)
gated `enrich_portfolios` on the cooldown:

```python
if _in_cooldown("portfolios"):
    result["portfolios"] = (cached.get("portfolios") or {})
    vintage["portfolios"] = cached_vintage.get("portfolios", _now_iso())
    skipped.append("portfolio")
else:
    result["portfolios"] = _portfolio.enrich_portfolios(_portfolio.load_portfolios()).get("portfolios", {})
    _stamp("portfolios")
```

When in cooldown, the cached `portfolios` was reused. But the cache is
patched structurally via `_patch_dashboard_cache` (`app/portfolio.py:25-68`)
— it carries the user's `symbol / shares / total_cost` (and any other
fields set by mutations) but NOT the live-price enrichment
(`last_price / pct_daily / pct_7d / pct_30d / high_52w / sector / marketcap /
forward_pe / forward_peg / next_earnings`). The frontend rendered all of
those as "—".

**Fix:** Remove the portfolio cooldown skip. Always run `enrich_portfolios`
for the portfolios section. Keep the cooldown for the `breadth_ai` /
`indicators` section (the user only complained about portfolio, and
breadth-ai has its own price-cohort data path that benefits from the
cooldown).

**Why this is safe (and why the cooldown was over-engineered for
portfolios):**
- `enrich_portfolios` calls `get_info_snapshot` per symbol — but that's
  `lru_cache`-backed with a 5-min TTL (`_INFO_CACHE_BUCKET_S = 300`), so
  the second call within a 15-min window hits the cache.
- The bulk `quote_snapshot` + `histories_bulk` are single HTTP calls to
  yfinance — comparable to the cost of `_enrich` recomputing the rest of
  the dashboard.
- Within a 15-min window, the "savings" was at most 1 saved HTTP call
  per 15 min. Not worth blanking prices.

**Files touched:**
- `app/service.py:refresh_market` — removed the `_in_cooldown("portfolios")`
  branch; unconditional `enrich_portfolios` call. The `cooldown_skip`
  field stays in the payload (the `"portfolio"` entry will just never be
  appended now).
- `static/js/cards.js:CARD_TOOLTIPS["portfolio"]` — removed the
  "15-minute refresh cooldown" sentence.

**Tests:**
- `tests/test_service_cooldown.py`:
  - DELETED `test_refresh_market_respects_portfolio_cooldown` (no longer
    applies; the new behaviour is that portfolio enrichment always runs).
  - ADDED `test_refresh_market_always_enriches_portfolios_regardless_of_cooldown`
    — seeds the cache with a fresh `vintage["portfolios"]` so
    `_in_cooldown("portfolios")` would return True if it were called.
    Runs `refresh_market`. Asserts `result["portfolios"]` has live prices
    (the same `last_price` the mocked `enrich_portfolios` returns).
    Asserts `"portfolio"` is NOT in `cooldown_skip`. Mocks
    `enrich_portfolios` to spy on whether it was called.
  - KEPT all breadth-ai cooldown tests (unchanged).
- `tests/frontend/refresh-cooldown.spec.mjs`:
  - DELETED `test("Portfolio card shows 'cached Xm' badge when
    cooldown_skip includes portfolio")` — badge no longer shows for
    portfolio.
  - ADDED `test("Portfolio prices are not blank after refresh")` — mocks
    `/api/dashboard` with portfolios that have `last_price` set. Clicks
    the global refresh. Asserts the rendered holdings show the price.
  - KEPT all breadth-ai tests.

### Bug 2 — ▲/▼ reorder resets on collapse+expand (Portfolio section)

**Symptom (user-reported):** "Also holding position is persistent only
after refresh button (position is probably persistent in the backend).
(action such as collasping portfolio reset position in frontend)."
Confirmed: the reorder IS persistent on the backend (clicking the global
Refresh button restores the new order), but collapse + expand in the
frontend shows the OLD order.

**Root cause:** In `static/js/portfolio.js:renderHoldingsTable` (the
morning's lane-2 code), the `onReorder` callback was wired as:

```js
onReorder: async (order) => {
  await API.reorderHoldings(pid, order);
},
```

It POSTed the new order to the backend but did NOT mutate `p.holdings`
(the closure variable that the next `renderBody()` reads from).
`tickerTable.js:moveRow` only mutated the `tickerTable.data.rows` array
in memory; that array is destroyed when the next `renderBody()` clears
`portfolioTables` (line 239) and recreates a fresh `tickerTable` instance
on collapse+expand. The fresh instance reads `p.holdings`, which still
held the OLD order because nothing had propagated the swap up to
`portfolioData.portfolios[pid].holdings`.

**Fix:** Update `onReorder` in `static/js/portfolio.js:renderHoldingsTable`
to mirror the new order in both the closure's `p.holdings` AND the
module-level `portfolioData.portfolios[pid].holdings` before the POST.
Cash row stays at the end. The backend POST is unchanged.

**Files touched:**
- `static/js/portfolio.js:renderHoldingsTable` — `onReorder` callback
  now rebuilds `p.holdings` from the new symbol order, updates
  `portfolioData.portfolios[pid].holdings`, calls `renderGrandHeader()`
  (totals might have changed in some edge case), then POSTs.

**Tests:**
- `tests/frontend/portfolio-holdings-reorder.spec.mjs`:
  - ADDED `test("▲/▼ reorder persists across collapse + expand")` —
    mock `reorderHoldings` to succeed. Set up a portfolio with holdings
    [NVDA, AAPL, MSFT]. Expand the portfolio. Click ▲ on AAPL. Collapse.
    Expand. Assert holdings are now [AAPL, NVDA, MSFT] (the new order,
    not the original).
  - ADDED `test("▲/▼ reorder preserves the cash row position across
    collapse + expand")` — same shape with a cash row, verifying cash
    stays at the end.

### Verification

- `python -m pytest tests/test_service_cooldown.py tests/test_portfolio.py
  tests/test_api_contract.py` → **104 passed** in 6.84s.
- `npx playwright test --config=tests/frontend/playwright.config.mjs
  tests/frontend/portfolio-holdings-reorder.spec.mjs
  tests/frontend/refresh-cooldown.spec.mjs` → **19 passed** in 7.1s.

### Files touched (6)

`app/service.py`, `static/js/cards.js`, `static/js/portfolio.js`,
`tests/test_service_cooldown.py`, `tests/frontend/refresh-cooldown.spec.mjs`,
`tests/frontend/portfolio-holdings-reorder.spec.mjs`.

### Decision pointer

See `project_rules/DECISIONS.md` →
"Portfolio enrichment always runs (no cooldown skip) — 2026-09-11".

### Archive

Full text in
`archive/sessions/2026-09-11-followup-fix-prices-collapse-reorder.md`.

---

[Earlier entries for the 2026-09-11 morning session are above —
Portfolio holdings reorder persistence + per-section refresh cooldowns.
That session's commits `9f6eac1` / `5e00482` / `4392797` / `b0e9789` /
`040c409` / `1254bb7` are the ones this follow-up corrects.]
