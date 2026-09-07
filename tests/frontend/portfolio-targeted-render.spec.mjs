// Regression tests for audit-2026-09-07 — portfolio targeted render.
//
// Pre-fix: every add/remove/rename of a portfolio called `renderBody()` which
// destroyed and rebuilt the ENTIRE #portfolioBody subtree (`el.innerHTML = html`),
// discarding all sibling DOM nodes, event listeners, and tickerTable instances.
// With N expanded portfolios × M holdings, every add/remove/rename cost O(N×M)
// DOM operations even though only one portfolio was affected.
//
// Post-fix (Patches A + B): the add/remove/rename handlers call targeted
// helpers (`renderPortfolioInsert`, `renderPortfolioRemove`,
// `renderPortfolioRename`) that touch only the single affected div. Sibling
// portfolios retain DOM identity (the SAME element reference) and their
// tickerTable instances survive untouched.
//
// These tests assert DOM identity preservation by capturing a marker attribute
// on a portfolio div before the mutation and confirming the SAME element still
// owns that marker after.

import { test, expect } from "@playwright/test";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

const POPULATED_PORTFOLIOS = {
  version: 1,
  portfolios: {
    "test-pf-a": {
      id: "test-pf-a",
      name: "Portfolio A",
      holdings: [{ symbol: "AAPL", shares: 10, total_cost: 1500, last_price: 220, pct_daily: 0.5 }],
    },
    "test-pf-b": {
      id: "test-pf-b",
      name: "Portfolio B",
      holdings: [{ symbol: "MSFT", shares: 5, total_cost: 1500, last_price: 420, pct_daily: 0.3 }],
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
  // Single consolidated /api/portfolios route for both GET and POST.
  // Playwright's glob pattern "**/api/portfolios" does NOT match the exact
  // path "/api/portfolios" (only matches with a prefix); use a regex so the
  // POST request "/api/portfolios?name=..." is intercepted.
  await page.route(/\/api\/portfolios(\?|$|\/)/, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    if (url.pathname === "/api/portfolios" && req.method() === "POST") {
      const name = url.searchParams.get("name") || "New Pf";
      const id = "test-pf-c";
      const portfolio = { id, name, holdings: [] };
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id, portfolio }),
      });
    }
    if (url.pathname === "/api/portfolios" && req.method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(POPULATED_PORTFOLIOS),
      });
    }
    return route.continue();
  });
  await page.goto(DASH);
  await expect(page.locator(".pf-pf-name").first()).toBeVisible();
  // Confirm both seeded portfolios rendered.
  await expect(page.locator('.pf-pf[data-pid="test-pf-a"]')).toHaveCount(1);
  await expect(page.locator('.pf-pf[data-pid="test-pf-b"]')).toHaveCount(1);
}

test.describe("portfolio targeted render (Patch A)", () => {
  test("add portfolio inserts only the new div — siblings keep DOM identity", async ({ page }) => {
    await setupDashboard(page);

    // Mark portfolio A with a unique data attribute the dashboard never touches.
    // We also capture the live Element reference (via JS) so we can verify the
    // SAME element owns the marker after the mutation.
    const pidA = await page.evaluate(() => {
      const el = document.querySelector('.pf-pf[data-pid="test-pf-a"]');
      el.setAttribute("data-marker", "alpha");
      // Tag the live element with a JS-side identifier so we can locate it again.
      window.__markerEls = window.__markerEls || new Map();
      window.__markerEls.set("alpha", el);
      return "test-pf-a";
    });
    expect(pidA).toBe("test-pf-a");

    // (POST mock is already in setupDashboard — no extra route needed.)

    // Feed the prompt for the portfolio name.
    page.on("dialog", (d) => {
      if (d.type() === "prompt") d.accept("Portfolio C");
      else d.accept();
    });

    await page.locator("#portfolioControls .pf-create").click();

    // Wait for the new portfolio to appear.
    await expect(page.locator('.pf-pf[data-pid="test-pf-c"]')).toHaveCount(1);
    // All three portfolios are now in the DOM.
    await expect(page.locator(".pf-pf")).toHaveCount(3);

    // CRITICAL: portfolio A's marked element is the SAME object as before.
    // If renderBody() had been called, every <section> would have been
    // destroyed and rebuilt — the marker would now live on a NEW element.
    const sameElement = await page.evaluate(() => {
      const elNow = document.querySelector('.pf-pf[data-pid="test-pf-a"]');
      const elBefore = window.__markerEls.get("alpha");
      return elNow === elBefore && elNow && elNow.getAttribute("data-marker") === "alpha";
    });
    expect(sameElement).toBe(true);

    // Portfolio B is also untouched.
    const sameElementB = await page.evaluate(() => {
      const elNow = document.querySelector('.pf-pf[data-pid="test-pf-b"]');
      return !!elNow && elNow.textContent.includes("Portfolio B");
    });
    expect(sameElementB).toBe(true);
  });

  test("remove portfolio removes only the targeted div — siblings keep DOM identity", async ({ page }) => {
    await setupDashboard(page);

    // Mark portfolio B (the one that will NOT be deleted).
    await page.evaluate(() => {
      const el = document.querySelector('.pf-pf[data-pid="test-pf-b"]');
      el.setAttribute("data-marker", "bravo");
      window.__markerEls = window.__markerEls || new Map();
      window.__markerEls.set("bravo", el);
    });

    // Mock DELETE /api/portfolios/test-pf-a.
    await page.route("**/api/portfolios/test-pf-a", (route) => {
      if (route.request().method() === "DELETE") {
        return route.fulfill({ status: 204 });
      }
      return route.continue();
    });

    // Confirm dialogs default to accept.
    page.on("dialog", (d) => d.accept());

    // Click the ✕ delete button on portfolio A.
    await page.locator('.pf-pf[data-pid="test-pf-a"] .pf-del').click();

    // Wait for portfolio A to be gone.
    await expect(page.locator('.pf-pf[data-pid="test-pf-a"]')).toHaveCount(0);
    // Portfolio B remains.
    await expect(page.locator(".pf-pf")).toHaveCount(1);

    // CRITICAL: portfolio B's marked element is the SAME object as before.
    const sameElement = await page.evaluate(() => {
      const elNow = document.querySelector('.pf-pf[data-pid="test-pf-b"]');
      const elBefore = window.__markerEls.get("bravo");
      return elNow === elBefore && elNow && elNow.getAttribute("data-marker") === "bravo";
    });
    expect(sameElement).toBe(true);
  });

  test("rename portfolio updates only the header span — holdings table untouched", async ({ page }) => {
    await setupDashboard(page);

    // Expand portfolio A so its holdings table renders.
    await page.locator('.pf-pf[data-pid="test-pf-a"] .pf-pf-header').click();
    await expect(page.locator('.pf-pf[data-pid="test-pf-a"] .pf-holdings-table')).toBeVisible();

    // Capture a fingerprint of the holdings table's outerHTML.
    const tableHtmlBefore = await page.locator('.pf-pf[data-pid="test-pf-a"] .pf-holdings-table').evaluate((el) => el.outerHTML);

    // Mock PUT /api/portfolios/test-pf-a (rename endpoint) — find it by URL pattern.
    await page.route("**/api/portfolios/test-pf-a**", (route) => {
      const req = route.request();
      if (req.method() === "PUT" && !req.url().includes("/holdings") && !req.url().includes("/cash")) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ id: "test-pf-a", name: "Renamed A", holdings: POPULATED_PORTFOLIOS.portfolios["test-pf-a"].holdings }),
        });
      }
      return route.continue();
    });

    // Click the ✎ rename button.
    page.on("dialog", (d) => d.accept());
    await page.locator('.pf-pf[data-pid="test-pf-a"] .pf-rename-btn').click();

    // The rename input appears. Type new name and blur to commit.
    await page.locator(".pf-name-input").fill("Renamed A");
    await page.locator(".pf-name-input").evaluate((el) => el.blur());

    // Header span shows the new name.
    await expect(page.locator('.pf-pf[data-pid="test-pf-a"] .pf-pf-name')).toHaveText("Renamed A");

    // CRITICAL: the holdings table outerHTML is byte-identical to before the rename.
    const tableHtmlAfter = await page.locator('.pf-pf[data-pid="test-pf-a"] .pf-holdings-table').evaluate((el) => el.outerHTML);
    expect(tableHtmlAfter).toBe(tableHtmlBefore);
  });
});
