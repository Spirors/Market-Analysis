// Playwright coverage for the RESTORE half of the per-portfolio holdings
// column sort — the path that was dead before FIX-07-A.
//
// Why this spec exists
// --------------------
// tickerTable.js persists a column-header sort to
// `localStorage["pfSort.portfolio.<pid>"]` (saveSort, called from the header
// click handler), but the load side was short-circuited: portfolio.js passed a
// hard-coded `initialSort: { key: "default", dir: 1 }`, and tickerTable does
// `initialSort || loadSort(section)`, so `loadSort()` was never consulted. A
// saved sort was therefore written but never applied after a re-mount.
//
// Existing sort coverage (portfolio-holdings-reorder.spec.mjs) only exercises
// the in-session path (sort → DOM order changes, ↺ resets). This spec covers
// the previously-untested persistence path.
//
// Verifies:
//   1. Sort a column, force a re-mount (collapse → expand, which clears
//      portfolioTables and recreates the tickerTable), and the same sort is
//      re-applied.
//   2. With nothing saved, a re-mount leaves rows in insertion order — the
//      default is unchanged.

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

function makeState(id, symbols) {
  return {
    version: 1,
    portfolios: {
      [id]: {
        id,
        name: id,
        holdings: symbols.map((sym) => ({
          symbol: sym,
          shares: 10,
          total_cost: 1000.0,
          last_price: 110.0,
          pct_daily: 1.0,
        })),
      },
    },
  };
}

async function mockPortfolios(page, state) {
  await mockApi(page);
  await page.route("**/api/portfolios**", (route) => {
    const reqUrl = new URL(route.request().url());
    const pathname = reqUrl.pathname.replace(/\/+$/, "");
    if (pathname === "/api/portfolios" && route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(state),
      });
    }
    return route.fallback();
  });
  await page.route("**/api/dashboard", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        as_of: new Date().toISOString(),
        portfolios: state.portfolios,
        market: { indices: {}, rates: {}, commodities: {} },
        futures: { index_futures: [], commodities: [] },
        indicators: {
          breadth: { breadth_pct: 50, detail: {} },
          breadth_ai: { breadth_pct: 50, detail: {} },
          spy: { trend: { state: "Uptrend", sma_short: "above", sma_long: "above", drawdown_pct: 0 }, realized_vol_annual_pct: 15 },
          vix: { level: 15, signal: "Normal" },
        },
        risk: { risk_level: "YELLOW", verdict: "Neutral", color: "#B9860B", counts: { bullish: 3, bearish: 3, neutral: 3 }, thesis: "Test", signals: [], fragility_flags: [] },
        ai_sentiment: { score: 0, verdict: "Neutral", spread_pct: 0, news: { tone: "neutral" }, valuation: { median_pe: null, stretched: false, note: "" }, cohorts: [], flip_conditions: [] },
        ai_analysis: { stance: "Neutral", confidence: 50, headline: "Test", bullets: [], divergences: [], watch: [] },
        regime: { regime: { regime_label: "Test", regime_description: "Test", confidence: "Medium", portfolio_posture: "Balanced" }, composite: { composite_score: 50, zone: "Neutral", guidance: "Test", component_scores: {} }, transition_probability: { probability_range: "50%" } },
        bottleneck: { thesis: "Test", topics: [], strongest_signal: null },
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

function getHoldingSymbols(page, pid) {
  return page
    .locator(`.pf-pf[data-pid="${pid}"] .pf-holdings-table tr[data-symbol]`)
    .evaluateAll((rows) => rows.map((r) => r.getAttribute("data-symbol")));
}

test.describe("Portfolio holdings column sort persisting across a re-mount", () => {
  test("a saved column sort is re-applied after collapse → expand", async ({ page }) => {
    await mockPortfolios(page, makeState("alpha", ["NVDA", "AAPL", "MSFT"]));
    await loadDashboard(page);

    // Expand the portfolio so its holdings table mounts.
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["NVDA", "AAPL", "MSFT"]);

    // Sort by symbol ascending; this saves pfSort.portfolio.alpha.
    await page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table th[data-key="symbol"]').click();
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["AAPL", "MSFT", "NVDA"]);
    await expect(page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table th[data-key="symbol"]')).toHaveClass(/asc/);

    // Force a re-mount: collapse (drops the tickerTable handle) then expand
    // (renderHoldingsTable builds a fresh instance).
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();
    await expect(page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table')).toHaveCount(0);
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();

    // The persisted sort is applied again on the fresh instance.
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["AAPL", "MSFT", "NVDA"]);
    await expect(page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table th[data-key="symbol"]')).toHaveClass(/asc/);
  });

  test("with nothing saved, a re-mounted table stays in insertion order", async ({ page }) => {
    await mockPortfolios(page, makeState("alpha", ["NVDA", "AAPL", "MSFT"]));
    await loadDashboard(page);

    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["NVDA", "AAPL", "MSFT"]);

    // Collapse + expand without ever sorting.
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();
    await expect(page.locator('.pf-pf[data-pid="alpha"] .pf-holdings-table')).toHaveCount(0);
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();

    // No saved sort → default insertion order, exactly as before the fix.
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["NVDA", "AAPL", "MSFT"]);
  });
});
