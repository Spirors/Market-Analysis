// Regression: adding a portfolio fires exactly one POST and zero follow-up
// GETs (Patch A + Patch B).
//
// Pre-fix: the + Create portfolio button handler calls `await refresh()`
// after the POST, which fires GET /api/portfolios (a ~3s server round-trip
// to yfinance). The new portfolio appears only after that slow refresh.
//
// Post-fix: the create handler pushes the enriched portfolio from the POST
// response directly into the closure-captured state and calls
// renderPortfolioInsert() — no follow-up GET.
//
// This test verifies:
//   1. Exactly one POST /api/portfolios is sent.
//   2. Zero GET /api/portfolios requests follow.
//   3. Zero /api/dashboard requests are triggered.
//   4. The new portfolio appears in the DOM.

import { test, expect } from "@playwright/test";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

const EMPTY_PORTFOLIOS = {
  version: 1,
  portfolios: {},
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
        market: {},
        indicators: {},
        risk: { risk_level: "YELLOW", signals: [] },
        ai_analysis: [],
        regime: { regime: "Unknown", components: [], as_of: "2026-09-07T00:00:00" },
        bottleneck: {},
        ai_sentiment: {},
        thirteenf: {},
        events: [],
        portfolios: {},
        column_order: {},
        column_visibility: {},
      }),
    })
  );
  // Mock GET /api/portfolios (initial empty state).
  await page.route("**/api/portfolios", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(EMPTY_PORTFOLIOS) })
  );
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");
}

test.describe("portfolio add — no follow-up network requests", () => {
  test("add portfolio fires exactly one POST /api/portfolios and zero GETs", async ({ page }) => {
    await setupDashboard(page);

    // Track all requests. Attach AFTER setupDashboard so the initial
    // /api/dashboard load isn't counted (the assertion checks for no
    // follow-up dashboard calls during the create flow, not no dashboard
    // calls ever).
    const reqLog = [];
    page.on("request", (req) => reqLog.push({ method: req.method(), url: req.url() }));

    // Intercept the POST and return an enriched response (simulates Patch B).
    // NOTE: Playwright's glob pattern "**/api/portfolios" does NOT match the
    // exact path "/api/portfolios" (only matches with a prefix); use a regex
    // so the POST request "/api/portfolios?name=..." is intercepted.
    await page.route(/\/api\/portfolios(\?|$|\/)/, async (route) => {
      const method = route.request().method();
      const url = new URL(route.request().url());

      if (url.pathname === "/api/portfolios" && method === "POST") {
        const name = url.searchParams.get("name") || "";
        const id = name.trim().toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
        const portfolio = { id, name: name.trim(), holdings: [] };
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ id, portfolio }),
        });
      }
      // Let the base route handle GETs (should never be hit).
      return route.continue();
    });

    // Intercept the prompt() dialog to feed the portfolio name.
    page.on("dialog", (d) => {
      if (d.type() === "prompt") d.accept("Test Portfolio");
      else d.accept();
    });

    await page.locator("#portfolioControls .pf-create").click();

    // Wait for the POST to complete.
    await expect.poll(() => {
      return reqLog.filter((r) => r.url.includes("/api/portfolios") && r.method === "POST").length;
    }, { timeout: 5000 }).toBe(1);

    // Give the optimistic update one tick to render.
    await page.waitForTimeout(300);

    // The critical assertions:
    expect(reqLog.filter((r) => r.url.includes("/api/portfolios") && r.method === "GET").length).toBe(0);
    expect(reqLog.filter((r) => r.url.includes("/api/dashboard")).length).toBe(0);

    // The new portfolio should appear in the DOM.
    await expect(page.locator(".pf-pf-name")).toContainText("Test Portfolio");
  });
});
