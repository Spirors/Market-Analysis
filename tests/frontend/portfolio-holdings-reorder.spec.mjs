// Playwright coverage for the per-row holdings reorder inside each
// Portfolio — the ▲/▼ chevrons and "↺ Default order" button rendered by
// tickerTable.js for each per-portfolio tickerTable instance.
//
// Why this spec exists
// --------------------
// tickerTable.js wires reorder buttons only when `section === "portfolio"`
// (see reorderEnabled at static/js/tickerTable.js:166). After the
// per-portfolio scoping refactor, every portfolio's tickerTable instance
// is created with `section: "portfolio.<pid>"`, so the strict equality
// never matches — neither the ▲/▼ buttons nor the "↺ Default order"
// button render for any portfolio. This spec asserts the buttons
// exist + work for the per-portfolio sections.
//
// Verifies:
//   1. ▲/▼ buttons render on every holdings row in an expanded portfolio
//   2. ▲ moves a row up; ▼ moves a row down; boundary disable works
//   3. "↺ Default order" button renders inside each portfolio's controls
//   4. "↺ Default order" resets the view after a column-header sort
//   5. "↺ Default order" resets the view after a manual ▲/▼ move
//   6. Sort state is per-portfolio: sorting Portfolio A does not affect
//      Portfolio B
//
// Manual row order is session-only by design (tickerTable.js does not
// persist moveRow results), so the "↺ Default order" button is exactly
// what gets you back to the insertion order after sorting by any
// sortable column.

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

function makePortfolio(id, symbols) {
  return {
    version: 1,
    portfolios: {
      [id]: {
        id,
        name: id.replace(/-/g, " "),
        holdings: symbols.map((sym) => ({
          symbol: sym,
          shares: 10,
          total_cost: 1000.0,
          last_price: 110.0,
          pct_daily: 1.0,
        })),
      },
    },
    column_order: {
      portfolio: ["symbol", "shares", "total_cost", "last_price"],
    },
    column_visibility: {
      portfolio: { symbol: true, shares: true, total_cost: true, last_price: true },
    },
  };
}

async function mockPortfolios(page, state) {
  await mockApi(page);
  // Portfolio endpoints
  await page.route("**/api/portfolios**", async (route) => {
    const reqUrl = new URL(route.request().url());
    const method = route.request().method();
    const pathname = reqUrl.pathname.replace(/\/+$/, "");
    if (pathname === "/api/portfolios" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(state),
      });
    }
    return route.fallback();
  });
  // Dashboard payload that embeds the same portfolios
  await page.route("**/api/dashboard", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        as_of: new Date().toISOString(),
        portfolios: state.portfolios,
        column_order: state.column_order,
        column_visibility: state.column_visibility,
        market: { indices: {}, rates: {}, commodities: {} },
        futures: { index_futures: [], commodities: [] },
        indicators: {
          breadth: { breadth_pct: 50, detail: {} },
          breadth_ai: { breadth_pct: 50, detail: {} },
          spy: { trend: { state: "Uptrend", sma_short: "above", sma_long: "above", drawdown_pct: 0 }, realized_vol_annual_pct: 15 },
          vix: { level: 15, signal: "Normal" },
        },
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
    })
  );
}

async function loadDashboard(page) {
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");
}

async function getHoldingSymbols(page, pid) {
  // Returns symbols in DOM order inside this portfolio's holdings table.
  return await page
    .locator(`.pf-pf[data-pid="${pid}"] .pf-holdings-table tr[data-symbol]`)
    .evaluateAll((rows) => rows.map((r) => r.getAttribute("data-symbol")));
}

test.describe("Portfolio holdings row reorder (.tt-up / .tt-down + .tt-reset-order)", () => {
  test("▲/▼ buttons render on every holding row in an expanded portfolio", async ({ page }) => {
    await mockPortfolios(page, makePortfolio("alpha", ["NVDA", "AAPL", "MSFT"]));
    await loadDashboard(page);

    // The portfolio must be expanded for the holdings table to render.
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();
    await expect(page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table')).toBeVisible();

    // Three rows -> three ▲/▼ pairs.
    const ups = page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table .tt-up');
    const downs = page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table .tt-down');
    await expect(ups).toHaveCount(3);
    await expect(downs).toHaveCount(3);

    // Boundary: first row's ▲ disabled, last row's ▼ disabled, middles enabled.
    await expect(page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table tr[data-symbol="NVDA"] .tt-up')).toBeDisabled();
    await expect(page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table tr[data-symbol="MSFT"] .tt-down')).toBeDisabled();
    await expect(page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table tr[data-symbol="AAPL"] .tt-up')).toBeEnabled();
    await expect(page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table tr[data-symbol="AAPL"] .tt-down')).toBeEnabled();
  });

  test("▲ on a middle row swaps it with the row above", async ({ page }) => {
    await mockPortfolios(page, makePortfolio("alpha", ["NVDA", "AAPL", "MSFT"]));
    await loadDashboard(page);
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();

    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["NVDA", "AAPL", "MSFT"]);

    // force: bypass Playwright's actionability stability check — after the
    // swap the row moves and the button changes position.
    await page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table tr[data-symbol="AAPL"] .tt-up').click({ force: true });
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["AAPL", "NVDA", "MSFT"]);
  });

  test("▼ on a middle row swaps it with the row below", async ({ page }) => {
    await mockPortfolios(page, makePortfolio("alpha", ["NVDA", "AAPL", "MSFT"]));
    await loadDashboard(page);
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();

    await page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table tr[data-symbol="AAPL"] .tt-down').click({ force: true });
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["NVDA", "MSFT", "AAPL"]);
  });

  test("\"↺ Default order\" button renders inside each portfolio's controls", async ({ page }) => {
    await mockPortfolios(page, makePortfolio("alpha", ["NVDA", "AAPL"]));
    await loadDashboard(page);
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();

    const resetBtn = page.locator('.pf-pf[data-pid="alpha"] .pf-reset-order, .pf-pf[data-pid="alpha"] .tt-reset-order');
    await expect(resetBtn).toBeVisible();
    await expect(resetBtn).toHaveText(/Default order/);
  });

  test("\"↺ Default order\" resets view after a column-header sort", async ({ page }) => {
    await mockPortfolios(page, makePortfolio("alpha", ["NVDA", "AAPL", "MSFT"]));
    await loadDashboard(page);
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();

    // Initial insertion order: NVDA, AAPL, MSFT.
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["NVDA", "AAPL", "MSFT"]);

    // Sort by symbol asc -> AAPL, MSFT, NVDA.
    await page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table th[data-key="symbol"]').click();
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["AAPL", "MSFT", "NVDA"]);

    // Reset -> back to insertion order.
    await page.locator('.pf-pf[data-pid="alpha"] .tt-reset-order').click();
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["NVDA", "AAPL", "MSFT"]);
  });

  test("\"↺ Default order\" resets a column-header sort back to the manual order", async ({ page }) => {
    // The "↺ Default order" button clears the column-header sort; manual
    // ▲/▼ moves survive (data.rows is not touched). With no prior manual
    // moves, the result is the insertion order — covered above. Here we
    // first move a row manually, then sort by a column, then click reset,
    // and verify the manual order comes back (the column sort is cleared,
    // the ▲/▼ swap is preserved).
    await mockPortfolios(page, makePortfolio("alpha", ["NVDA", "AAPL", "MSFT"]));
    await loadDashboard(page);
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();

    // Manual ▲/▼: move AAPL down.
    await page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table tr[data-symbol="AAPL"] .tt-down').click({ force: true });
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["NVDA", "MSFT", "AAPL"]);

    // Column sort by symbol: changes the visible order, but data.rows still
    // holds the manually-swapped order under the hood.
    await page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table th[data-key="symbol"]').click();
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["AAPL", "MSFT", "NVDA"]);

    // Reset: clears the column sort, returns to the manual order.
    await page.locator('.pf-pf[data-pid="alpha"] .tt-reset-order').click();
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["NVDA", "MSFT", "AAPL"]);
  });

  test("sort state is per-portfolio: sorting Portfolio A doesn't affect Portfolio B", async ({ page }) => {
    // Two portfolios with disjoint symbols so a column sort produces a
    // different DOM order in each.
    const state = {
      version: 1,
      portfolios: {
        alpha: {
          id: "alpha",
          name: "alpha",
          holdings: [
            { symbol: "NVDA", shares: 10, total_cost: 1000.0, last_price: 110.0, pct_daily: 1.0 },
            { symbol: "AAPL", shares: 10, total_cost: 1000.0, last_price: 110.0, pct_daily: 1.0 },
            { symbol: "MSFT", shares: 10, total_cost: 1000.0, last_price: 110.0, pct_daily: 1.0 },
          ],
        },
        beta: {
          id: "beta",
          name: "beta",
          holdings: [
            { symbol: "TSLA", shares: 10, total_cost: 1000.0, last_price: 110.0, pct_daily: 1.0 },
            { symbol: "GOOG", shares: 10, total_cost: 1000.0, last_price: 110.0, pct_daily: 1.0 },
          ],
        },
      },
      column_order: { portfolio: ["symbol", "shares", "total_cost", "last_price"] },
      column_visibility: { portfolio: { symbol: true, shares: true, total_cost: true, last_price: true } },
    };
    await mockPortfolios(page, state);
    await loadDashboard(page);
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();
    await page.locator('.pf-pf[data-pid="beta"] .pf-caret').click();

    // Sort Portfolio A by symbol asc.
    await page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table th[data-key="symbol"]').click();
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["AAPL", "MSFT", "NVDA"]);

    // Portfolio B's order is unaffected (still in insertion order).
    await expect.poll(() => getHoldingSymbols(page, "beta")).toEqual(["TSLA", "GOOG"]);

    // Resetting Portfolio A doesn't touch Portfolio B.
    await page.locator('.pf-pf[data-pid="alpha"] .tt-reset-order').click();
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["NVDA", "AAPL", "MSFT"]);
    await expect.poll(() => getHoldingSymbols(page, "beta")).toEqual(["TSLA", "GOOG"]);
  });
});
