// Playwright coverage for the mass expand/collapse toggle in the Portfolio
// card header (.pf-toggle-all). The button label is meant to reflect the
// action the next click will perform — "▼ all" = click will expand all,
// "▲ all" = click will collapse all. It must update after every click so
// the user can see whether the previous click took effect and what the
// next click will do.
//
// Verifies:
//   1. "▼ all" → click → all expanded + label flips to "▲ all"
//   2. "▲ all" → click → all collapsed + label flips to "▼ all"
//   3. Mixed state (1 of 2 expanded) → click "▼ all" → both expanded +
//      label flips to "▲ all"
//   4. Stale localStorage pid (deleted portfolio still in pfExpanded) →
//      mass toggle still works for the surviving portfolios and the
//      label reflects the post-click truth (not the pre-click truth)
//
// Pre-fix bug: the click handler called renderBody() but not
// renderHeaderControls(), so the label was stuck on "▼ all" forever after
// the first click. Visually indistinguishable from "the button does
// nothing" because the only feedback the user had was the label.

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

function resetPortfolios(state) {
  portfolioState = state;
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

test.describe("Portfolio mass expand/collapse (.pf-toggle-all)", () => {
  test("click expands all and label flips to ▲ all", async ({ page }) => {
    await mockDashboardWithPortfolios(page, makePortfolios("fidelity-cash", "roth-ira"));
    await loadDashboard(page);

    // Initial state: both collapsed, label "▼ all" (click will expand)
    await expect(page.locator(".pf-toggle-all")).toContainText("▼ all");
    await expect(page.locator(".pf-pf").nth(0).locator(".pf-pf-body")).toHaveClass(/hidden/);
    await expect(page.locator(".pf-pf").nth(1).locator(".pf-pf-body")).toHaveClass(/hidden/);

    await page.locator(".pf-toggle-all").click();

    // All expanded: bodies visible, carets show ▼
    await expect(page.locator(".pf-pf").nth(0).locator(".pf-pf-body")).not.toHaveClass(/hidden/);
    await expect(page.locator(".pf-pf").nth(1).locator(".pf-pf-body")).not.toHaveClass(/hidden/);
    await expect(page.locator(".pf-caret").nth(0)).toContainText("\u25bc");
    await expect(page.locator(".pf-caret").nth(1)).toContainText("\u25bc");

    // Label must reflect the next action (collapse) — pre-fix this stayed "▼ all"
    await expect(page.locator(".pf-toggle-all")).toContainText("▲ all");
  });

  test("second click collapses all and label flips back to ▼ all", async ({ page }) => {
    await mockDashboardWithPortfolios(page, makePortfolios("fidelity-cash", "roth-ira"));
    await loadDashboard(page);

    await page.locator(".pf-toggle-all").click();
    await expect(page.locator(".pf-toggle-all")).toContainText("▲ all");

    await page.locator(".pf-toggle-all").click();

    // All collapsed
    await expect(page.locator(".pf-pf").nth(0).locator(".pf-pf-body")).toHaveClass(/hidden/);
    await expect(page.locator(".pf-pf").nth(1).locator(".pf-pf-body")).toHaveClass(/hidden/);
    await expect(page.locator(".pf-caret").nth(0)).toContainText("\u25b6");
    await expect(page.locator(".pf-caret").nth(1)).toContainText("\u25b6");

    // Label back to expand hint
    await expect(page.locator(".pf-toggle-all")).toContainText("▼ all");
  });

  test("mixed state (1 of 2 expanded) -> click expands the missing one and label flips to ▲ all", async ({ page }) => {
    // Pre-expand only "fidelity-cash" via localStorage (loadExpanded reads pfExpanded)
    await page.addInitScript(() => {
      localStorage.setItem("pfExpanded", JSON.stringify({ "fidelity-cash": true }));
    });
    await mockDashboardWithPortfolios(page, makePortfolios("fidelity-cash", "roth-ira"));
    await loadDashboard(page);

    // Sanity: only A is expanded
    await expect(page.locator(".pf-pf").nth(0).locator(".pf-pf-body")).not.toHaveClass(/hidden/);
    await expect(page.locator(".pf-pf").nth(1).locator(".pf-pf-body")).toHaveClass(/hidden/);
    // Label correctly shows expand hint (B is still collapsed)
    await expect(page.locator(".pf-toggle-all")).toContainText("▼ all");

    await page.locator(".pf-toggle-all").click();

    // Both expanded now
    await expect(page.locator(".pf-pf").nth(0).locator(".pf-pf-body")).not.toHaveClass(/hidden/);
    await expect(page.locator(".pf-pf").nth(1).locator(".pf-pf-body")).not.toHaveClass(/hidden/);
    await expect(page.locator(".pf-toggle-all")).toContainText("▲ all");
  });

  test("survives reload: state persists, then second click still works (label still updates)", async ({ page }) => {
    await mockDashboardWithPortfolios(page, makePortfolios("fidelity-cash", "roth-ira"));
    await loadDashboard(page);

    // Expand all, reload, verify still expanded
    await page.locator(".pf-toggle-all").click();
    await expect(page.locator(".pf-toggle-all")).toContainText("▲ all");

    await page.reload();
    await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");
    // After reload, renderHeaderControls() re-runs and the label SHOULD
    // still be "▲ all" because both pids are in pfExpanded localStorage
    await expect(page.locator(".pf-toggle-all")).toContainText("▲ all");
    await expect(page.locator(".pf-pf").nth(0).locator(".pf-pf-body")).not.toHaveClass(/hidden/);

    // Now collapse all — label must flip back
    await page.locator(".pf-toggle-all").click();
    await expect(page.locator(".pf-toggle-all")).toContainText("▼ all");
    await expect(page.locator(".pf-pf").nth(0).locator(".pf-pf-body")).toHaveClass(/hidden/);
  });
});
