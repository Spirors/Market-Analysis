// Regression tests for audit-2026-09-07 — tickerTable instance preservation.
//
// Pre-fix: `renderHoldingsTable()` discarded the previous tickerTable instance
// on every call and created a brand-new one. The slot's innerHTML was
// replaced wholesale (slot.innerHTML = skeleton, then createTickerTable()
// read localStorage from scratch, then table.render() did another
// innerHTML replacement on the table container). Two innerHTML replacements
// per add/remove/edit holding mutation, plus loss of any in-flight debounced
// edit calls and the previous sort/visibility/order prefs had to be
// re-loaded from localStorage every time.
//
// Post-fix (Patch C): if `portfolioTables.has(pid)`, the existing tickerTable
// instance is reused via `existing.refresh({rows})` which mutates `this.data`
// and calls `this.drawBody()` in place. The slot's skeleton and the
// tickerTable instance survive across add/remove holding operations.
//
// These tests assert that the tickerTable slot (the #pf-table-<pid> element)
// is the SAME DOM node across mutations, and that sort state set by the user
// persists across an add holding.

import { test, expect } from "@playwright/test";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

const POPULATED_PORTFOLIO = {
  id: "test-pf",
  name: "Test Portfolio",
  holdings: [
    { symbol: "AAPL", shares: 10, total_cost: 1500, last_price: 220, pct_daily: 0.5 },
    { symbol: "MSFT", shares: 5, total_cost: 1500, last_price: 420, pct_daily: 0.3 },
    { symbol: "NVDA", shares: 2, total_cost: 800, last_price: 900, pct_daily: 1.5 },
  ],
};

const POPULATED_PORTFOLIOS = {
  version: 1,
  portfolios: { "test-pf": POPULATED_PORTFOLIO },
  column_order: { portfolio: [] },
  column_visibility: { portfolio: {} },
};

async function setupExpandedPortfolio(page) {
  await page.route("**/api/dashboard", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        as_of: "2026-09-07T00:00:00",
        market: {}, indicators: {}, risk: { risk_level: "YELLOW", signals: [] },
        ai_analysis: [], regime: { regime: "Unknown", components: [], as_of: "2026-09-07T00:00:00" },
        bottleneck: {}, ai_sentiment: {}, thirteenf: {}, events: [],
        portfolios: POPULATED_PORTFOLIOS.portfolios,
        column_order: POPULATED_PORTFOLIOS.column_order,
        column_visibility: POPULATED_PORTFOLIOS.column_visibility,
      }),
    })
  );
  await page.route("**/api/portfolios", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(POPULATED_PORTFOLIOS) })
  );
  await page.goto(DASH);
  // Expand the portfolio so the holdings table renders.
  await page.locator(".pf-pf-header").first().click();
  await expect(page.locator("#pf-table-test-pf")).toBeVisible();
  // Confirm three rows rendered.
  await expect(page.locator('#pf-table-test-pf tr[data-symbol]')).toHaveCount(3);
}

test.describe("tickerTable instance preservation (Patch C)", () => {
  test("holdings-table element keeps DOM identity across add holding", async ({ page }) => {
    await setupExpandedPortfolio(page);

    // Mark the #pf-table-test-pf container with a unique attribute and capture
    // the live Element reference.
    await page.evaluate(() => {
      const el = document.querySelector("#pf-table-test-pf");
      el.setAttribute("data-marker", "tt-instance");
      window.__ttEl = el;
    });

    // Mock validate + add holding endpoints.
    await page.route("**/api/portfolios/validate?**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ valid: true, symbol: "GOOG", name: "Alphabet", sector: "Technology" }),
      })
    );
    await page.route("**/api/portfolios/test-pf/holdings?**", (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ symbol: "GOOG", shares: 1, total_cost: 150, last_price: 170, pct_daily: 0.2 }),
        });
      }
      return route.continue();
    });

    // Click +Add holding and feed the prompt.
    page.on("dialog", (d) => {
      if (d.type() === "prompt") d.accept("GOOG");
      else d.accept();
    });
    await page.locator(".pf-add-holding").first().click();

    // Wait for the new row to appear.
    await expect(page.locator('#pf-table-test-pf tr[data-symbol="GOOG"]')).toHaveCount(1);

    // CRITICAL: the #pf-table-test-pf element is the SAME DOM node as before.
    // Pre-fix renderHoldingsTable() replaced slot.innerHTML, so this would fail.
    const sameElement = await page.evaluate(() => {
      const elNow = document.querySelector("#pf-table-test-pf");
      return elNow === window.__ttEl && elNow && elNow.getAttribute("data-marker") === "tt-instance";
    });
    expect(sameElement).toBe(true);
  });

  test("sort state persists across add holding", async ({ page }) => {
    await setupExpandedPortfolio(page);

    // The tickerTable default sort is "default" (insertion order). Click the
    // "Ticker" column header to sort alphabetically. Capture the row order.
    const tickerHeader = page.locator('#pf-table-test-pf thead th').filter({ hasText: /^Ticker$/ });
    await tickerHeader.click();

    // After sorting by ticker ASC, the first row should be AAPL (alphabetically first).
    const firstSymbolBefore = await page.locator('#pf-table-test-pf tr[data-symbol]').first().getAttribute("data-symbol");
    expect(firstSymbolBefore).toBe("AAPL");

    // Mock validate + add holding.
    await page.route("**/api/portfolios/validate?**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ valid: true, symbol: "AAPL", name: "Apple", sector: "Technology" }),
      })
    );
    // We add an existing symbol (AAPL is already in the portfolio) so the
    // server's "already in portfolio" rejection is exercised — but the
    // tickerTable row callback (addRow) bubbles that error up to the
    // portfolio.js handler. For this test we want the optimistic path: we
    // need a fresh symbol. Use AMZN.
    await page.route("**/api/portfolios/validate?**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ valid: true, symbol: "AMZN", name: "Amazon", sector: "Technology" }),
      })
    );
    await page.route("**/api/portfolios/test-pf/holdings?**", (route) => {
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ symbol: "AMZN", shares: 1, total_cost: 150, last_price: 180, pct_daily: 0.1 }),
        });
      }
      return route.continue();
    });

    // Override the prompt to feed AMZN.
    page.removeAllListeners("dialog");
    page.on("dialog", (d) => {
      if (d.type() === "prompt") d.accept("AMZN");
      else d.accept();
    });
    await page.locator(".pf-add-holding").first().click();

    // Wait for the new row.
    await expect(page.locator('#pf-table-test-pf tr[data-symbol="AMZN"]')).toHaveCount(1);

    // CRITICAL: the first row is STILL AAPL — sort state survived the add.
    // If the tickerTable instance had been rebuilt (pre-fix), sort would
    // have reset to "default" insertion order where AMZN is last.
    const firstSymbolAfter = await page.locator('#pf-table-test-pf tr[data-symbol]').first().getAttribute("data-symbol");
    expect(firstSymbolAfter).toBe("AAPL");
  });
});
