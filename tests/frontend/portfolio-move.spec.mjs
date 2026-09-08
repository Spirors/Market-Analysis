// Playwright coverage for the portfolio reorder feature — per-row up/down
// chevrons in each portfolio header (.pf-move-up / .pf-move-down). The
// backend endpoint is POST /api/portfolios/reorder (body: { order: [..pids] });
// the frontend computes the new order locally (a single swap), POSTs it,
// and re-renders so the boundary disabled-state updates.
//
// Verifies:
//   1. Up button is disabled on the first row, enabled on every other row
//   2. Down button is disabled on the last row, enabled on every other row
//   3. Clicking "up" on a middle row swaps it with the row above
//   4. Clicking "down" on a middle row swaps it with the row below
//   5. Boundary state updates after a swap (the row that just took the
//      first slot has its up button now disabled, etc.)
//   6. Click on a move button does NOT collapse/expand the portfolio
//      (stopPropagation mirrors the delete / pencil behavior)
//   7. POST /api/portfolios/reorder is called with the swapped order
//   8. Reorder persists across page reload (the persisted JSON order
//      is what drives the next render)

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

const EMPTY_PORTFOLIOS = {
  version: 1,
  portfolios: {},
  column_order: {
    portfolio: ["symbol", "shares", "total_cost", "last_price", "total_value", "gain_loss", "pct_daily"],
  },
  column_visibility: {
    portfolio: { symbol: true, shares: true, total_cost: true, last_price: true, total_value: true, gain_loss: true, pct_daily: true },
  },
};

function makePortfolios(...ids) {
  const state = JSON.parse(JSON.stringify(EMPTY_PORTFOLIOS));
  for (const id of ids) {
    state.portfolios[id] = {
      id,
      name: id.replace(/-/g, " "),
      holdings: [
        { symbol: "NVDA", shares: 10, total_cost: 1500.0, last_price: 145.2, pct_daily: 2.1 },
      ],
    };
  }
  return state;
}

let portfolioState = EMPTY_PORTFOLIOS;
let reorderRequests = [];

function resetPortfolios(state) {
  portfolioState = state;
  reorderRequests = [];
}

async function mockPortfolioApi(page) {
  await page.route("**/api/portfolios**", async (route) => {
    const reqUrl = new URL(route.request().url());
    const method = route.request().method();
    const pathname = reqUrl.pathname.replace(/\/+$/, "");

    if (pathname === "/api/portfolios" && method === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(portfolioState) });
    }

    if (pathname === "/api/portfolios" && method === "POST") {
      const name = reqUrl.searchParams.get("name") || "";
      if (!name.trim()) {
        return route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: "name is required" }) });
      }
      const id = name.trim().toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
      portfolioState.portfolios[id] = { id, name: name.trim(), holdings: [] };
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id, portfolio: portfolioState.portfolios[id] }) });
    }

    if (pathname === "/api/portfolios/reorder" && method === "POST") {
      // Capture the body for assertion in test #7.
      const body = JSON.parse(route.request().postData() || "{}");
      reorderRequests.push(body);
      // Apply the reorder server-side (rebuild dict in the new key order)
      // so subsequent GETs return the new order.
      if (Array.isArray(body.order)) {
        portfolioState.portfolios = Object.fromEntries(
          body.order.map((id) => [id, portfolioState.portfolios[id]]).filter(([id]) => portfolioState.portfolios[id] != null),
        );
      }
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ order: body.order }) });
    }

    if (pathname === "/api/portfolios/validate" && method === "GET") {
      const symbol = reqUrl.searchParams.get("symbol") || "";
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ valid: true, symbol: symbol.toUpperCase(), name: symbol.toUpperCase(), sector: "Test" }) });
    }

    if (pathname.startsWith("/api/portfolios/columns/") && method === "PUT") {
      const section = pathname.split("/").pop();
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ order: [], visibility: {} }) });
    }

    return route.fallback();
  });
}

async function mockDashboardWithPortfolios(page, portfolios) {
  await mockApi(page);
  await mockPortfolioApi(page);
  resetPortfolios(portfolios);
  await page.route("**/api/dashboard", (route) => {
    const base = JSON.parse(JSON.stringify(portfolios));
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        as_of: new Date().toISOString(),
        portfolios: base.portfolios,
        column_order: base.column_order,
        column_visibility: base.column_visibility,
        market: { indices: {}, rates: {}, commodities: {} },
        futures: { index_futures: [], commodities: [] },
        indicators: { breadth: { breadth_pct: 50, detail: {} }, breadth_ai: { breadth_pct: 50, detail: {} }, spy: { trend: { state: "Uptrend", sma_short: "above", sma_long: "above", drawdown_pct: 0 }, realized_vol_annual_pct: 15 }, vix: { level: 15, signal: "Normal" } },
        risk: { risk_level: "YELLOW", verdict: "Neutral", color: "#B9860B", counts: { bullish: 3, bearish: 3, neutral: 3 }, thesis: "Test", signals: [], fragility_flags: [] },
        ai_sentiment: { score: 0, verdict: "Neutral", spread_pct: 0, news: { tone: "neutral" }, valuation: { note: "" }, cohorts: [], flip_conditions: [] },
        ai_analysis: { stance: "Neutral", confidence: 50, headline: "Test", bullets: [], divergences: [], watch: [] },
        regime: { regime: { regime_label: "Test", regime_description: "Test", confidence: "Medium", portfolio_posture: "Balanced" }, composite: { composite_score: 50, zone: "Neutral", guidance: "Test", component_scores: {} }, transition_probability: { probability_range: "50%" } },
        bottleneck: { thesis: "Test", categories: [], strongest_signal: null },
        thirteenf: { funds: [], errors: [] },
        events: [],
        coverage: {},
        vintage: { risk: new Date().toISOString() },
      }),
    });
  });
}

async function loadDashboard(page) {
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");
}

async function getPortfolioOrder(page) {
  // Read the data-pid attributes in DOM order — what the user sees.
  return await page.locator(".pf-pf").evaluateAll((els) => els.map((e) => e.dataset.pid));
}

test.describe("Portfolio move up/down (.pf-move-up / .pf-move-down)", () => {
  test("up button is disabled on the first row, enabled on others; down button is disabled on the last row", async ({ page }) => {
    await mockDashboardWithPortfolios(page, makePortfolios("alpha", "beta", "gamma"));
    await loadDashboard(page);

    const order = await getPortfolioOrder(page);
    expect(order).toEqual(["alpha", "beta", "gamma"]);

    // First row (alpha): up disabled, down enabled
    const alphaUp = page.locator('.pf-pf[data-pid="alpha"] .pf-move-up');
    const alphaDown = page.locator('.pf-pf[data-pid="alpha"] .pf-move-down');
    await expect(alphaUp).toBeDisabled();
    await expect(alphaDown).toBeEnabled();

    // Middle row (beta): both enabled
    const betaUp = page.locator('.pf-pf[data-pid="beta"] .pf-move-up');
    const betaDown = page.locator('.pf-pf[data-pid="beta"] .pf-move-down');
    await expect(betaUp).toBeEnabled();
    await expect(betaDown).toBeEnabled();

    // Last row (gamma): up enabled, down disabled
    const gammaUp = page.locator('.pf-pf[data-pid="gamma"] .pf-move-up');
    const gammaDown = page.locator('.pf-pf[data-pid="gamma"] .pf-move-down');
    await expect(gammaUp).toBeEnabled();
    await expect(gammaDown).toBeDisabled();
  });

  test("clicking 'up' on a middle row swaps it with the row above", async ({ page }) => {
    await mockDashboardWithPortfolios(page, makePortfolios("alpha", "beta", "gamma"));
    await loadDashboard(page);

    // Move beta up
    await page.locator('.pf-pf[data-pid="beta"] .pf-move-up').click();
    await expect.poll(() => getPortfolioOrder(page)).toEqual(["beta", "alpha", "gamma"]);

    // POST was called once with the new order
    expect(reorderRequests).toHaveLength(1);
    expect(reorderRequests[0].order).toEqual(["beta", "alpha", "gamma"]);

    // Boundary state updated: beta is now first, so its up button is
    // disabled; alpha is now second, so its down button is enabled.
    await expect(page.locator('.pf-pf[data-pid="beta"] .pf-move-up')).toBeDisabled();
    await expect(page.locator('.pf-pf[data-pid="alpha"] .pf-move-down')).toBeEnabled();
  });

  test("clicking 'down' on a middle row swaps it with the row below", async ({ page }) => {
    await mockDashboardWithPortfolios(page, makePortfolios("alpha", "beta", "gamma"));
    await loadDashboard(page);

    await page.locator('.pf-pf[data-pid="beta"] .pf-move-down').click();
    await expect.poll(() => getPortfolioOrder(page)).toEqual(["alpha", "gamma", "beta"]);

    expect(reorderRequests).toHaveLength(1);
    expect(reorderRequests[0].order).toEqual(["alpha", "gamma", "beta"]);

    // gamma is now middle, so both its buttons are enabled.
    await expect(page.locator('.pf-pf[data-pid="gamma"] .pf-move-up')).toBeEnabled();
    await expect(page.locator('.pf-pf[data-pid="gamma"] .pf-move-down')).toBeEnabled();
    // beta is now last, so its down button is disabled.
    await expect(page.locator('.pf-pf[data-pid="beta"] .pf-move-down')).toBeDisabled();
  });

  test("move button does NOT collapse/expand the portfolio (stopPropagation)", async ({ page }) => {
    // Pre-expand alpha via localStorage so we start from an expanded state.
    await page.addInitScript(() => {
      localStorage.setItem("pfExpanded", JSON.stringify({ alpha: true, beta: true, gamma: true }));
    });
    await mockDashboardWithPortfolios(page, makePortfolios("alpha", "beta", "gamma"));
    await loadDashboard(page);

    // Sanity: alpha is expanded
    await expect(page.locator('.pf-pf[data-pid="alpha"] .pf-pf-body')).not.toHaveClass(/hidden/);

    // Click up on beta — should NOT collapse alpha (the portfolio that
    // "swapped" into beta's slot doesn't exist; the test is that the
    // click on beta's chevron doesn't bubble to the header click handler
    // and collapse beta itself).
    await page.locator('.pf-pf[data-pid="beta"] .pf-move-up').click();
    await expect.poll(() => getPortfolioOrder(page)).toEqual(["beta", "alpha", "gamma"]);

    // alpha is still expanded
    await expect(page.locator('.pf-pf[data-pid="alpha"] .pf-pf-body')).not.toHaveClass(/hidden/);
    // beta is still expanded too (we only swapped positions, not toggled state)
    await expect(page.locator('.pf-pf[data-pid="beta"] .pf-pf-body')).not.toHaveClass(/hidden/);
  });

  test("reorder persists across page reload", async ({ page }) => {
    await mockDashboardWithPortfolios(page, makePortfolios("alpha", "beta", "gamma"));
    await loadDashboard(page);

    // Move alpha to the bottom
    await page.locator('.pf-pf[data-pid="alpha"] .pf-move-down').click();
    await page.locator('.pf-pf[data-pid="alpha"] .pf-move-down').click();
    await expect.poll(() => getPortfolioOrder(page)).toEqual(["beta", "gamma", "alpha"]);

    // Reload — the server mock now returns the new order (it was applied
    // by the POST handler), so the page should render in the new order.
    await page.reload();
    await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");
    await expect.poll(() => getPortfolioOrder(page)).toEqual(["beta", "gamma", "alpha"]);
  });

  test("single-portfolio list: both up and down are disabled", async ({ page }) => {
    await mockDashboardWithPortfolios(page, makePortfolios("solo"));
    await loadDashboard(page);

    const up = page.locator('.pf-pf[data-pid="solo"] .pf-move-up');
    const down = page.locator('.pf-pf[data-pid="solo"] .pf-move-down');
    await expect(up).toBeDisabled();
    await expect(down).toBeDisabled();
  });

  test("multiple swaps chain correctly: alpha -> end via two down clicks, then gamma -> top via up click", async ({ page }) => {
    await mockDashboardWithPortfolios(page, makePortfolios("alpha", "beta", "gamma"));
    await loadDashboard(page);

    // alpha down (alpha, beta, gamma) -> (beta, alpha, gamma)
    await page.locator('.pf-pf[data-pid="alpha"] .pf-move-down').click();
    await expect.poll(() => getPortfolioOrder(page)).toEqual(["beta", "alpha", "gamma"]);
    // alpha down again (beta, alpha, gamma) -> (beta, gamma, alpha)
    await page.locator('.pf-pf[data-pid="alpha"] .pf-move-down').click();
    await expect.poll(() => getPortfolioOrder(page)).toEqual(["beta", "gamma", "alpha"]);

    // gamma up (beta, gamma, alpha) -> (gamma, beta, alpha)
    await page.locator('.pf-pf[data-pid="gamma"] .pf-move-up').click();
    await expect.poll(() => getPortfolioOrder(page)).toEqual(["gamma", "beta", "alpha"]);

    // Three POSTs in order, each carrying the new order
    expect(reorderRequests).toHaveLength(3);
    expect(reorderRequests[0].order).toEqual(["beta", "alpha", "gamma"]);
    expect(reorderRequests[1].order).toEqual(["beta", "gamma", "alpha"]);
    expect(reorderRequests[2].order).toEqual(["gamma", "beta", "alpha"]);
  });
});
