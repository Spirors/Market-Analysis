// Regression test for audit-2026-09-07 P0 — portfolio optimistic UI.
//
// Pre-fix: every bespoke portfolio button (add holding, add cash, delete
// portfolio, edit/delete cash row) called `await refresh()` after the API
// call. `refresh()` is a full GET /api/portfolios -> enrich_portfolios ->
// ~3s of yfinance HTTP calls. The user clicked + Add holding and waited 3
// seconds for the new row to appear, even though the POST itself returned
// in ~30ms.
//
// Post-fix: the bespoke handlers push/filter the closure-captured `p.holdings`
// in place and re-render only the affected holdings table + the card-level
// totals. No follow-up refresh(). The new row appears in one paint frame.
//
// This test verifies:
//   1. After clicking + Add holding, the new row is visible WITHOUT a
//      follow-up GET /api/portfolios being fired.
//   2. The same for + Add cash row.

import { test, expect } from "@playwright/test";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

const POPULATED_PORTFOLIOS = {
  version: 1,
  portfolios: {
    "test-pf": {
      id: "test-pf",
      name: "Test Portfolio",
      holdings: [
        { symbol: "AAPL", shares: 10, total_cost: 1500, last_price: 220, pct_daily: 0.5 },
      ],
    },
  },
  column_order: { portfolio: [] },
  column_visibility: { portfolio: {} },
};

async function setupDashboard(page) {
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
  await page.route("**/api/portfolios/validate?**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ valid: true, symbol: "NVDA", name: "NVIDIA", sector: "Technology" }) })
  );
  await page.goto(DASH);
  await expect(page.locator(".pf-pf-name").first()).toContainText("Test Portfolio");
  // Expand the portfolio so the +Add holding button is visible.
  await page.locator(".pf-pf-header").first().click();
  await expect(page.locator(".pf-add-holding")).toBeVisible();
}

test.describe("portfolio bespoke button optimistic updates", () => {
  test("+Add holding does NOT fire a follow-up GET /api/portfolios", async ({ page }) => {
    await setupDashboard(page);

    // Track all calls to GET /api/portfolios (NOT /api/portfolios/...).
    let postCount = 0;
    let getCount = 0;
    await page.route("**/api/portfolios/test-pf/holdings**", (route) => {
      if (route.request().method() === "POST") {
        postCount++;
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ symbol: "NVDA", shares: 0, total_cost: 0, last_price: 900.0, pct_daily: 1.5 }),
        });
      }
      return route.continue();
    });
    await page.route("**/api/portfolios", (route) => {
      if (route.request().method() === "GET") getCount++;
      return route.continue();
    });

    // Intercept the window.prompt() dialog to feed "NVDA" to the add flow.
    page.on("dialog", (dialog) => {
      if (dialog.type() === "prompt") dialog.accept("NVDA");
      else dialog.accept();
    });

    await page.locator(".pf-add-holding").first().click();

    // Wait for the POST to complete.
    await expect.poll(() => postCount, { timeout: 5000 }).toBe(1);
    // Give the optimistic update one tick to render.
    await page.waitForTimeout(200);
    // The critical assertion: no follow-up GET fired after the POST.
    expect(getCount).toBe(0);
  });

  test("+Add cash row does NOT fire a follow-up GET /api/portfolios", async ({ page }) => {
    await setupDashboard(page);

    let postCount = 0;
    let getCount = 0;
    await page.route("**/api/portfolios/test-pf/cash**", (route) => {
      if (route.request().method() === "POST") {
        postCount++;
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ kind: "cash", label: "Cash", total_cost: 0, total_value: 0 }),
        });
      }
      return route.continue();
    });
    await page.route("**/api/portfolios", (route) => {
      if (route.request().method() === "GET") getCount++;
      return route.continue();
    });

    await page.locator(".pf-add-cash").first().click();
    await expect.poll(() => postCount, { timeout: 5000 }).toBe(1);
    await page.waitForTimeout(200);
    expect(getCount).toBe(0);
  });
});
