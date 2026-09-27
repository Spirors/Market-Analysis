// Playwright coverage for FIX-07-D — keyboard operability + ARIA state on the
// shared tickerTable.js column headers and Columns dropdown.
//
// Why this spec exists
// --------------------
// The sortable <th> the tickerTable factory emits was mouse-only: it carried no
// tabindex/role/aria-sort and the only sort handler was a `click` listener, so
// keyboard users could not sort at all (a <th> is not focusable). The Columns
// button likewise never reported its open/closed state to assistive tech.
//
// Verifies:
//   1. A sortable <th> is focusable (tabindex="0") and Enter/Space performs the
//      same sort toggle as a mouse click.
//   2. aria-sort tracks the live sort state ("none" → "ascending" →
//      "descending"), including after the ↺ Default order reset.
//   3. The Columns button's aria-expanded is "false" initially, "true" on open,
//      and "false" again after an outside click — and its aria-controls points
//      at the menu it toggles.
//
// Existing sort specs all drive the header with `.click()`; this is the
// keyboard/a11y counterpart.

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

function symbolTh(page, pid) {
  return page.locator(`.pf-pf[data-pid="${pid}"] .pf-holdings-table th[data-key="symbol"]`);
}

test.describe("tickerTable keyboard + ARIA", () => {
  test("a sortable <th> sorts on Enter/Space and reports aria-sort", async ({ page }) => {
    await mockPortfolios(page, makePortfolio("alpha", ["NVDA", "AAPL", "MSFT"]));
    await loadDashboard(page);
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();

    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["NVDA", "AAPL", "MSFT"]);
    // Not sorted yet: focusable, and ARIA says "none".
    await expect(symbolTh(page, "alpha")).toHaveAttribute("tabindex", "0");
    await expect(symbolTh(page, "alpha")).toHaveAttribute("aria-sort", "none");

    // Enter = ascending sort (same toggle as a mouse click).
    await symbolTh(page, "alpha").focus();
    await page.keyboard.press("Enter");
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["AAPL", "MSFT", "NVDA"]);
    // drawBody() re-renders the row, so re-query the header.
    await expect(symbolTh(page, "alpha")).toHaveAttribute("aria-sort", "ascending");
    await expect(symbolTh(page, "alpha")).toHaveClass(/asc/);

    // Space = descending sort.
    await symbolTh(page, "alpha").focus();
    await page.keyboard.press("Space");
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["NVDA", "MSFT", "AAPL"]);
    await expect(symbolTh(page, "alpha")).toHaveAttribute("aria-sort", "descending");
    await expect(symbolTh(page, "alpha")).toHaveClass(/desc/);

    // ↺ Default order clears the sort — aria-sort returns to "none".
    await page.locator('.pf-pf[data-pid="alpha"] .tt-reset-order').click();
    await expect.poll(() => getHoldingSymbols(page, "alpha")).toEqual(["NVDA", "AAPL", "MSFT"]);
    await expect(symbolTh(page, "alpha")).toHaveAttribute("aria-sort", "none");
  });

  test("the Columns button reports aria-expanded across open/close", async ({ page }) => {
    await mockPortfolios(page, makePortfolio("alpha", ["NVDA", "AAPL", "MSFT"]));
    await loadDashboard(page);
    await page.locator('.pf-pf[data-pid="alpha"] .pf-caret').click();

    const btn = page.locator('.pf-pf[data-pid="alpha"] .pf-controls .tt-cols-btn');
    await expect(btn).toHaveAttribute("aria-expanded", "false");

    // aria-controls points at the menu this button toggles.
    const menuId = await btn.getAttribute("aria-controls");
    expect(menuId).toBeTruthy();
    const menu = page.locator(`#${menuId}`);
    await expect(menu).toHaveCount(1);
    await expect(menu).toHaveClass(/hidden/);

    // Open → aria-expanded flips true.
    await btn.click();
    await expect(btn).toHaveAttribute("aria-expanded", "true");
    await expect(menu).not.toHaveClass(/hidden/);

    // Outside click closes the menu → aria-expanded must reset to false.
    await page.mouse.click(2, 2);
    await expect(menu).toHaveClass(/hidden/);
    await expect(btn).toHaveAttribute("aria-expanded", "false");
  });
});
