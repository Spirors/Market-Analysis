// Regression: the portfolio star must document its full interaction model to
// keyboard and screen-reader users.
//
// Clearing a star is only possible through the context menu (`contextmenu` in
// portfolio.js) — there is no dedicated clear control. That route (right-click,
// or the keyboard equivalent Shift+F10 / the ContextMenu key) was previously
// documented nowhere. The fix puts the complete instruction — symbol, current
// state, colour cycle, and how to clear — into both `title` and `aria-label`
// for the starred and unstarred states.
//
// The dashboard is served from static/index.html with /api/* mocked (see
// mock-dashboard.mjs).

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

const ONE_PORTFOLIO = {
  version: 1,
  portfolios: {
    "portfolio-a": {
      id: "portfolio-a",
      name: "Portfolio A",
      holdings: [
        { symbol: "NVDA", shares: 10, total_cost: 1500.0, last_price: 145.2, pct_daily: 2.1 },
      ],
    },
  },
  column_order: {
    portfolio: ["symbol", "shares", "total_cost", "last_price", "total_value", "gain_loss", "pct_daily"],
  },
  column_visibility: {
    portfolio: { symbol: true, shares: true, total_cost: true, last_price: true, total_value: true, gain_loss: true, pct_daily: true },
  },
};

async function mockDashboard(page) {
  await mockApi(page);
  const state = JSON.parse(JSON.stringify(ONE_PORTFOLIO));
  await page.route("**/api/portfolios**", (route) => {
    const pathname = new URL(route.request().url()).pathname.replace(/\/+$/, "");
    if (pathname === "/api/portfolios" && route.request().method() === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(state) });
    }
    return route.fallback();
  });
  await page.route("**/api/dashboard", (route) => {
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

// `pfExpanded` persists in localStorage, so after a reload the portfolio may
// already be expanded; normalise to EXPANDED (no-op when already expanded).
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

async function starFor(page, sym) {
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading…");
  await expandAllPortfolios(page);
  const star = page.locator(`.earn-star[data-sym="${sym}"]`);
  await expect(star).toBeVisible();
  return star;
}

test.describe("Portfolio star accessibility copy", () => {
  test("unstarred star documents cycle + keyboard-clear route", async ({ page }) => {
    await mockDashboard(page);
    const star = await starFor(page, "NVDA");

    await expect(star).toHaveAttribute("aria-pressed", "false");
    const label = await star.getAttribute("aria-label");
    const title = await star.getAttribute("title");

    expect(label).toBe(title);
    for (const text of [label, title]) {
      expect(text).toContain("NVDA");
      expect(text).toContain("not starred");
      expect(text).toContain("Enter or Space");
      expect(text).toContain("cycles the colour");
      expect(text).toContain("context menu");
      expect(text).toContain("right-click");
      expect(text).toContain("Shift+F10");
      expect(text).toContain("ContextMenu key");
      // Accessible name must not be the bare glyph.
      expect(text).not.toBe("☆");
      expect(text.trim()).not.toBe("");
    }
  });

  test("starred star documents current colour + keyboard-clear route", async ({ page }) => {
    await mockDashboard(page);
    const star = await starFor(page, "NVDA");

    await star.click();
    await expect(star).toHaveAttribute("data-color", "amber");
    await expect(star).toHaveAttribute("aria-pressed", "true");

    const label = await star.getAttribute("aria-label");
    const title = await star.getAttribute("title");

    expect(label).toBe(title);
    for (const text of [label, title]) {
      expect(text).toContain("NVDA");
      expect(text).toContain("starred amber");
      expect(text).toContain("Enter or Space");
      expect(text).toContain("cycles the colour");
      expect(text).toContain("context menu");
      expect(text).toContain("right-click");
      expect(text).toContain("Shift+F10");
      expect(text).toContain("ContextMenu key");
      expect(text).not.toBe("★");
    }
  });
});
