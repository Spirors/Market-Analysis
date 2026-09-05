# Task 11 Report — Playwright portfolio tests

**Status:** DONE
**Commit:** 225b0a0
**Date:** 2026-09-04

## Summary

Created `tests/frontend/portfolio.spec.mjs` with 7 Playwright E2E tests covering the Portfolio section. All 7 tests pass (`npx playwright test tests/frontend/portfolio.spec.mjs --config tests/frontend/playwright.config.mjs`).

## Test coverage

| # | Test | What it verifies |
|---|------|-----------------|
| 1 | empty state shows create CTA and no-portfolio message | Empty state renders "No portfolios yet" and the "+ Create portfolio" button is visible |
| 2 | create flow prompts for name and expands new section | Clicking "+ Create portfolio" triggers prompt(), the new portfolio appears expanded |
| 3 | add holding validates symbol and shows row in table | Creates a portfolio, adds NVDA holding, verifies row appears in table |
| 4 | column reorder PUT is sent when columns are reordered | PUT to `/api/portfolios/columns/portfolio` updates mock state; persisted after reload |
| 5 | populated state shows holding details and totals | Pre-populated portfolio shows NVDA, shares=10, total_cost=1500 after expanding |
| 6 | cash row can be added to a portfolio | Creates portfolio, adds cash row, verifies `.pf-cash-row` appears |
| 7 | delete portfolio removes section after confirm | Creates portfolio, clicks delete (confirm accepted), verifies empty state |

## Architecture notes

- Tests run against `python -m http.server 8123` (Playwright config's webServer), NOT FastAPI
- All `/api/portfolios**` endpoints mocked via a single catch-all `page.route("**/api/portfolios**", ...)` handler
- For populated-state tests, portfolio data is injected into the dashboard mock payload (at root level) so `cards.js → renderPortfolio(data)` picks up pre-existing portfolios on the initial render
- Dialog handlers use `page.on("dialog", d => d.accept(...))` registered BEFORE the click that triggers them
- Single dialog handler per test uses `dialogCount` to disambiguate sequential prompts (portfolio name vs ticker symbol)

## Challenges solved

1. **Playwright config path**: `npx playwright test` requires `--config tests/frontend/playwright.config.mjs` because the config lives in the `tests/frontend/` directory, not the project root
2. **Glob patterns and query strings**: `page.route("**/api/portfolios", ...)` does NOT match `POST /api/portfolios?name=X` — the `**` glob doesn't cover query strings. Solved by using `**/api/portfolios**` with a catch-all handler
3. **`request().json()` unavailable**: Playwright 1.62 doesn't have `route.request().json()` — used `route.request().postData()` + `JSON.parse()` instead
4. **Dialog handler stacking**: Multiple `page.on("dialog")` calls accumulate — "Cannot accept dialog which is already handled!" Fixed by using a single handler per test with a counter
5. **Portfolio collapsed by default**: Pre-populated portfolio renders collapsed (▶ caret) — expanded in the populated-state test by clicking `.pf-caret` before asserting NVDA visibility

## Fix round 1

**Commit:** `b036b24`
**Date:** 2026-09-04

### What changed

Replaced the raw `page.evaluate(fetch(...))` in test 4 (column reorder) with:

1. **`page.waitForResponse`** — properly intercepts the PUT to `/api/portfolios/columns/portfolio` and waits for it to resolve, instead of relying on the `page.evaluate` return value (`r.ok`).
2. **Mock state assertion** — `expect(portfolioState.column_order.portfolio).toEqual(newOrder)` verifies the mock handler actually mutated the in-memory state.
3. **Request body verification** — parses the captured request's `postData()` and asserts the sent order matches expectations.
4. **Persistence assertion** — reloads the page and re-fetches `/api/portfolios` to confirm the new order is served back.
5. **Expand portfolio first** — clicks `.pf-caret` to expand the collapsed portfolio, then verifies the initial table header renders (`Ticker`).

### Architectural note

The reviewer requested exercising the `.tt-cols-btn` / `button.tt-col-up` UI flow from `tickerTable.js`. However, the portfolio section uses a **bespoke renderer** (`buildPortfolioTableHtml` in `portfolio.js`) rather than `createTickerTable`. This is enforced by "Ruling 3" in `portfolio.js` (line 159). As a result:

- The portfolio section has **no** `.tt-cols-btn` or `.tt-col-up` buttons in the DOM.
- Column order is stored server-side (`column_order.portfolio`) but the bespoke renderer always renders columns in the hardcoded `PORTFOLIO_COLUMNS` order — it does not read `column_order` for rendering.
- The column reorder PUT endpoint exists on the backend and is correctly mocked, but no UI control triggers it in the portfolio section.

The test therefore exercises the API contract (PUT request → mock state mutation → persistence across reload) rather than a UI click flow. A true UI-driven column reorder test would require the portfolio section to adopt `tickerTable.js` for its holdings table, which is out of scope for this fix.
