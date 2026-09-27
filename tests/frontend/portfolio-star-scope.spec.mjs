// Regression: star highlight must be independent per portfolio.
//
// Before the fix, starring NVDA in "Fidelity Main" also starred NVDA in
// "Fidelity Roth IRA" because the portfolio Map used plain symbol-only
// keys. The fix changes the Map to use composite "<pid>::<sym>" keys so
// each (portfolio, ticker) pair has independent star state.
//
// The dashboard is served from static/index.html with /api/* mocked (see
// mock-dashboard.mjs + mock helpers in this file).

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

// ---- Mock helpers ----------------------------------------------------------

const TWO_PORTFOLIOS = {
  version: 1,
  portfolios: {
    "portfolio-a": {
      id: "portfolio-a",
      name: "Portfolio A",
      holdings: [
        { symbol: "NVDA", shares: 10, total_cost: 1500.0, last_price: 145.2, pct_daily: 2.1 },
      ],
    },
    "portfolio-b": {
      id: "portfolio-b",
      name: "Portfolio B",
      holdings: [
        { symbol: "NVDA", shares: 5, total_cost: 750.0, last_price: 145.2, pct_daily: 2.1 },
      ],
    },
  },
};

let portfolioState;

function resetPortfolios() {
  portfolioState = JSON.parse(JSON.stringify(TWO_PORTFOLIOS));
}

async function mockPortfolioApi(page) {
  resetPortfolios();
  await page.route("**/api/portfolios**", async (route) => {
    const reqUrl = new URL(route.request().url());
    const method = route.request().method();
    const pathname = reqUrl.pathname.replace(/\/+$/, "");

    if (pathname === "/api/portfolios" && method === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(portfolioState) });
    }
    if (pathname === "/api/portfolios" && method === "POST") {
      const name = reqUrl.searchParams.get("name") || "";
      if (!name.trim()) return route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: "name required" }) });
      const id = name.trim().toLowerCase().replace(/\s+/g, "-");
      portfolioState.portfolios[id] = { id, name: name.trim(), holdings: [] };
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id, portfolio: portfolioState.portfolios[id] }) });
    }
    return route.fallback();
  });
}

async function mockDashboardWithTwoPortfolios(page) {
  await mockApi(page);
  await mockPortfolioApi(page);
  await page.route("**/api/dashboard", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        as_of: new Date().toISOString(),
        portfolios: portfolioState.portfolios,
        market: { indices: {}, rates: {}, commodities: {} },
        futures: { index_futures: [], commodities: [] },
        indicators: { breadth: { breadth_pct: 50 }, spy: { trend: { state: "Uptrend" } }, vix: { level: 15 } },
        risk: { risk_level: "YELLOW", verdict: "Neutral", color: "#B9860B", counts: { bullish: 3, bearish: 3, neutral: 3 }, thesis: "Test", signals: [] },
        ai_sentiment: { score: 0, verdict: "Neutral", news: { tone: "neutral" }, valuation: { median_pe: null, stretched: false, note: "" }, cohorts: [] },
        ai_analysis: { stance: "Neutral", confidence: 50, headline: "Test", bullets: [], divergences: [], watch: [] },
        regime: { regime: { regime_label: "Test", confidence: "Medium", portfolio_posture: "Balanced" }, composite: { composite_score: 50, zone: "Neutral" } },
        bottleneck: { thesis: "Test", topics: [] },
        earnings: { companies: [] },
        thirteenf: { funds: [] },
        events: [],
        vintage: { risk: new Date().toISOString() },
      }),
    });
  });
}

async function loadDashboard(page) {
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading…");
}

// Each portfolio's expanded/collapsed state is persisted in localStorage
// (`pfExpanded`), so after a reload both portfolios may ALREADY be expanded;
// a blind "click each caret" then COLLAPSES them and collapsed portfolios
// render no holdings rows. Normalise every portfolio to EXPANDED first (no-op
// when already expanded) so the row/star assertions below run against rendered
// holdings — without weakening the per-portfolio independence checks.
async function expandAllPortfolios(page) {
  const carets = page.locator(".pf-caret");
  const n = await carets.count();
  for (let i = 0; i < n; i++) {
    const caret = carets.nth(i);
    const collapsed = await caret.evaluate((el) => {
      const body = el.closest(".pf-pf")?.querySelector(".pf-pf-body");
      return !body || body.classList.contains("hidden");
    });
    if (collapsed) await caret.click();
  }
}

// ---- Tests -----------------------------------------------------------------

test.describe("Portfolio star scoping", () => {
  test("starring NVDA in portfolio A does NOT star NVDA in portfolio B", async ({ page }) => {
    await mockDashboardWithTwoPortfolios(page);
    await loadDashboard(page);

    // Both portfolios should be visible
    await expect(page.locator(".pf-pf")).toHaveCount(2);

    // Expand both portfolios (normalises any persisted expanded state).
    await expandAllPortfolios(page);

    // Find the NVDA star in each portfolio
    const pfA = page.locator('.pf-pf[data-pid="portfolio-a"]');
    const pfB = page.locator('.pf-pf[data-pid="portfolio-b"]');
    const starA = pfA.locator('.earn-star[data-sym="NVDA"]');
    const starB = pfB.locator('.earn-star[data-sym="NVDA"]');

    await expect(starA).toBeVisible();
    await expect(starB).toBeVisible();

    // Both should start unstarred
    await expect(starA).toHaveAttribute("data-color", "");
    await expect(starB).toHaveAttribute("data-color", "");

    // Click star in portfolio A
    await starA.click();

    // Portfolio A's star should be amber, portfolio B's should stay empty
    const rowA = pfA.locator('tr[data-symbol="NVDA"]');
    const rowB = pfB.locator('tr[data-symbol="NVDA"]');
    await expect(rowA).toHaveClass(/earn-row-amber/);
    await expect(rowB).not.toHaveClass(/earn-row-/);
    await expect(starA).toHaveAttribute("data-color", "amber");
    await expect(starB).toHaveAttribute("data-color", "");
  });

  test("star state persists across reload independently", async ({ page }) => {
    await mockDashboardWithTwoPortfolios(page);
    await loadDashboard(page);

    // Expand both portfolios (normalises any persisted expanded state).
    await expandAllPortfolios(page);

    const pfA = page.locator('.pf-pf[data-pid="portfolio-a"]');
    const pfB = page.locator('.pf-pf[data-pid="portfolio-b"]');

    // Star NVDA in portfolio A only
    await pfA.locator('.earn-star[data-sym="NVDA"]').click();
    await expect(pfA.locator('tr[data-symbol="NVDA"]')).toHaveClass(/earn-row-amber/);

    // Reload the page
    await page.reload();
    await expect(page.locator("#riskBody")).not.toHaveText("Loading…");

    // Re-expand both portfolios (reload restored `pfExpanded`, so both may
    // already be expanded — normalise instead of blindly toggling).
    await expandAllPortfolios(page);

    const pfAAfter = page.locator('.pf-pf[data-pid="portfolio-a"]');
    const pfBAfter = page.locator('.pf-pf[data-pid="portfolio-b"]');

    // Portfolio A's NVDA should still be starred (amber)
    await expect(pfAAfter.locator('tr[data-symbol="NVDA"]')).toHaveClass(/earn-row-amber/);
    // Portfolio B's NVDA should NOT be starred
    await expect(pfBAfter.locator('tr[data-symbol="NVDA"]')).not.toHaveClass(/earn-row-/);
  });

  test("clearing star in portfolio A does NOT affect portfolio B", async ({ page }) => {
    await mockDashboardWithTwoPortfolios(page);
    await loadDashboard(page);

    // Expand both portfolios (normalises any persisted expanded state).
    await expandAllPortfolios(page);

    const pfA = page.locator('.pf-pf[data-pid="portfolio-a"]');
    const pfB = page.locator('.pf-pf[data-pid="portfolio-b"]');

    // Star NVDA in BOTH portfolios
    await pfA.locator('.earn-star[data-sym="NVDA"]').click();
    await pfB.locator('.earn-star[data-sym="NVDA"]').click();
    await expect(pfA.locator('tr[data-symbol="NVDA"]')).toHaveClass(/earn-row-amber/);
    await expect(pfB.locator('tr[data-symbol="NVDA"]')).toHaveClass(/earn-row-amber/);

    // Right-click to clear star in portfolio A
    await pfA.locator('.earn-star[data-sym="NVDA"]').click({ button: "right" });

    // Portfolio A should be cleared, portfolio B should remain starred
    await expect(pfA.locator('tr[data-symbol="NVDA"]')).not.toHaveClass(/earn-row-/);
    await expect(pfB.locator('tr[data-symbol="NVDA"]')).toHaveClass(/earn-row-amber/);
  });
});
