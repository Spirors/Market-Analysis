// Playwright coverage for the bottleneck category reorder feature — per-row
// up/down chevrons in each category header (.bn-move-up / .bn-move-down).
// The backend endpoint is POST /api/bottleneck/categories/reorder
// (body: { order: ["canonical", ...] }); the frontend computes the new order
// locally (a single swap), POSTs it, and re-renders so the boundary
// disabled-state updates.

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

const CANONICAL_CATEGORIES = [
  "Agentic AI",
  "Autonomous Driving",
  "AI gadgets",
  "Power / data-center infrastructure",
  "Robots",
];

function makeBottleneckPayload(categories) {
  return {
    thesis: "Test thesis",
    categories: categories.map((c) => ({
      category: c,
      category_original: c,
      streams: {
        upstream: { layers: [], proxy_40d_roc_pct: null },
        downstream: { layers: [], proxy_40d_roc_pct: null },
      },
      proxy_40d_roc_pct: null,
    })),
    strongest_signal: null,
    note: "Test note",
  };
}

let bnCategories = [...CANONICAL_CATEGORIES];
let reorderRequests = [];

function resetBn(categories) {
  bnCategories = categories;
  reorderRequests = [];
}

async function mockBottleneckApi(page) {
  await page.route("**/api/bottleneck/**", async (route) => {
    const reqUrl = new URL(route.request().url());
    const method = route.request().method();
    const pathname = reqUrl.pathname.replace(/\/+$/, "");

    if (pathname === "/api/bottleneck/categories/reorder" && method === "POST") {
      const body = JSON.parse(route.request().postData() || "{}");
      reorderRequests.push(body);
      if (Array.isArray(body.order)) {
        bnCategories = body.order;
      }
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ order: bnCategories }) });
    }

    return route.fallback();
  });
}

async function mockDashboardWithBottleneck(page, categories) {
  await mockApi(page);
  await mockBottleneckApi(page);
  resetBn(categories);
  await page.route("**/api/dashboard", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        as_of: new Date().toISOString(),
        market: { indices: {}, rates: {}, commodities: {} },
        futures: { index_futures: [], commodities: [] },
        indicators: { breadth: { breadth_pct: 50, detail: {} }, breadth_ai: { breadth_pct: 50, detail: {} }, spy: { trend: { state: "Uptrend", sma_short: "above", sma_long: "above", drawdown_pct: 0 }, realized_vol_annual_pct: 15 }, vix: { level: 15, signal: "Normal" } },
        risk: { risk_level: "YELLOW", verdict: "Neutral", color: "#B9860B", counts: { bullish: 3, bearish: 3, neutral: 3 }, thesis: "Test", signals: [], fragility_flags: [] },
        ai_sentiment: { score: 0, verdict: "Neutral", spread_pct: 0, news: { tone: "neutral" }, valuation: { median_pe: null, stretched: false, note: "" }, cohorts: [], flip_conditions: [] },
        ai_analysis: { stance: "Neutral", confidence: 50, headline: "Test", bullets: [], divergences: [], watch: [] },
        regime: { regime: { regime_label: "Test", regime_description: "Test", confidence: "Medium", portfolio_posture: "Balanced" }, composite: { composite_score: 50, zone: "Neutral", guidance: "Test", component_scores: {} }, transition_probability: { probability_range: "50%" } },
        bottleneck: makeBottleneckPayload(categories),
        thirteenf: { funds: [], errors: [] },
        events: [],
        portfolios: {},
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

async function getCategoryOrder(page) {
  return await page.locator(".bn-category").evaluateAll((els) => els.map((e) => e.dataset.catOriginal));
}

test.describe("Bottleneck move up/down (.bn-move-up / .bn-move-down)", () => {
  test("up button is disabled on the first row, enabled on others; down button is disabled on the last row", async ({ page }) => {
    await mockDashboardWithBottleneck(page, [...CANONICAL_CATEGORIES]);
    await loadDashboard(page);

    const order = await getCategoryOrder(page);
    expect(order).toEqual(CANONICAL_CATEGORIES);

    // First row: up disabled, down enabled
    const firstUp = page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-move-up');
    const firstDown = page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-move-down');
    await expect(firstUp).toBeDisabled();
    await expect(firstDown).toBeEnabled();

    // Middle row (Autonomous Driving): both enabled
    const midUp = page.locator('.bn-category[data-cat-original="Autonomous Driving"] .bn-move-up');
    const midDown = page.locator('.bn-category[data-cat-original="Autonomous Driving"] .bn-move-down');
    await expect(midUp).toBeEnabled();
    await expect(midDown).toBeEnabled();

    // Last row: up enabled, down disabled
    const lastUp = page.locator('.bn-category[data-cat-original="Robots"] .bn-move-up');
    const lastDown = page.locator('.bn-category[data-cat-original="Robots"] .bn-move-down');
    await expect(lastUp).toBeEnabled();
    await expect(lastDown).toBeDisabled();
  });

  test("clicking 'up' on a middle row swaps it with the row above", async ({ page }) => {
    await mockDashboardWithBottleneck(page, [...CANONICAL_CATEGORIES]);
    await loadDashboard(page);

    await page.locator('.bn-category[data-cat-original="Autonomous Driving"] .bn-move-up').click();
    await expect.poll(() => getCategoryOrder(page)).toEqual([
      "Autonomous Driving", "Agentic AI", "AI gadgets",
      "Power / data-center infrastructure", "Robots",
    ]);

    expect(reorderRequests).toHaveLength(1);
    expect(reorderRequests[0].order).toEqual([
      "Autonomous Driving", "Agentic AI", "AI gadgets",
      "Power / data-center infrastructure", "Robots",
    ]);

    // Boundary updated: Autonomous Driving is now first → up disabled
    await expect(page.locator('.bn-category[data-cat-original="Autonomous Driving"] .bn-move-up')).toBeDisabled();
    await expect(page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-move-down')).toBeEnabled();
  });

  test("clicking 'down' on a middle row swaps it with the row below", async ({ page }) => {
    await mockDashboardWithBottleneck(page, [...CANONICAL_CATEGORIES]);
    await loadDashboard(page);

    await page.locator('.bn-category[data-cat-original="Autonomous Driving"] .bn-move-down').click();
    await expect.poll(() => getCategoryOrder(page)).toEqual([
      "Agentic AI", "AI gadgets", "Autonomous Driving",
      "Power / data-center infrastructure", "Robots",
    ]);

    expect(reorderRequests).toHaveLength(1);
    expect(reorderRequests[0].order).toEqual([
      "Agentic AI", "AI gadgets", "Autonomous Driving",
      "Power / data-center infrastructure", "Robots",
    ]);

    // AI gadgets is now middle → both enabled
    await expect(page.locator('.bn-category[data-cat-original="AI gadgets"] .bn-move-up')).toBeEnabled();
    await expect(page.locator('.bn-category[data-cat-original="AI gadgets"] .bn-move-down')).toBeEnabled();
    // Robots is now last → down disabled
    await expect(page.locator('.bn-category[data-cat-original="Robots"] .bn-move-down')).toBeDisabled();
  });

  test("move button does NOT collapse/expand the category (stopPropagation)", async ({ page }) => {
    await mockDashboardWithBottleneck(page, [...CANONICAL_CATEGORIES]);
    await loadDashboard(page);

    // Pre-expand the first category
    await page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-cat-header').click();
    await expect(page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-cat-body')).not.toHaveClass(/hidden/);

    // Click up on Autonomous Driving — should NOT collapse Agentic AI
    await page.locator('.bn-category[data-cat-original="Autonomous Driving"] .bn-move-up').click();
    await expect.poll(() => getCategoryOrder(page)).toEqual([
      "Autonomous Driving", "Agentic AI", "AI gadgets",
      "Power / data-center infrastructure", "Robots",
    ]);

    // Agentic AI is still expanded
    await expect(page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-cat-body')).not.toHaveClass(/hidden/);
    // Autonomous Driving should also still be collapsed (its own header wasn't clicked)
    await expect(page.locator('.bn-category[data-cat-original="Autonomous Driving"] .bn-cat-body')).toHaveClass(/hidden/);
  });

  test("reorder persists across page reload", async ({ page }) => {
    await mockDashboardWithBottleneck(page, [...CANONICAL_CATEGORIES]);
    await loadDashboard(page);

    // Move Agentic AI to the bottom (two down clicks)
    await page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-move-down').click();
    await expect.poll(() => getCategoryOrder(page)).toEqual([
      "Autonomous Driving", "AI gadgets", "Agentic AI",
      "Power / data-center infrastructure", "Robots",
    ]);
    await page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-move-down').click();
    await expect.poll(() => getCategoryOrder(page)).toEqual([
      "Autonomous Driving", "AI gadgets", "Power / data-center infrastructure",
      "Agentic AI", "Robots",
    ]);

    // Reload — the server mock now returns the new order
    await page.reload();
    await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");
    await expect.poll(() => getCategoryOrder(page)).toEqual([
      "Autonomous Driving", "AI gadgets", "Power / data-center infrastructure",
      "Agentic AI", "Robots",
    ]);
  });

  test("single-category list: both buttons disabled", async ({ page }) => {
    await mockDashboardWithBottleneck(page, ["Agentic AI"]);
    await loadDashboard(page);

    const up = page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-move-up');
    const down = page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-move-down');
    await expect(up).toBeDisabled();
    await expect(down).toBeDisabled();
  });

  test("chained swaps produce correct order", async ({ page }) => {
    await mockDashboardWithBottleneck(page, [...CANONICAL_CATEGORIES]);
    await loadDashboard(page);

    // Agentic AI down (positions 0→1)
    await page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-move-down').click();
    await expect.poll(() => getCategoryOrder(page)).toEqual([
      "Autonomous Driving", "Agentic AI", "AI gadgets",
      "Power / data-center infrastructure", "Robots",
    ]);

    // Agentic AI down again (positions 1→2)
    await page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-move-down').click();
    await expect.poll(() => getCategoryOrder(page)).toEqual([
      "Autonomous Driving", "AI gadgets", "Agentic AI",
      "Power / data-center infrastructure", "Robots",
    ]);

    // Robots up (positions 4→3)
    await page.locator('.bn-category[data-cat-original="Robots"] .bn-move-up').click();
    await expect.poll(() => getCategoryOrder(page)).toEqual([
      "Autonomous Driving", "AI gadgets", "Agentic AI",
      "Robots", "Power / data-center infrastructure",
    ]);

    expect(reorderRequests).toHaveLength(3);
    expect(reorderRequests[0].order).toEqual([
      "Autonomous Driving", "Agentic AI", "AI gadgets",
      "Power / data-center infrastructure", "Robots",
    ]);
    expect(reorderRequests[1].order).toEqual([
      "Autonomous Driving", "AI gadgets", "Agentic AI",
      "Power / data-center infrastructure", "Robots",
    ]);
    expect(reorderRequests[2].order).toEqual([
      "Autonomous Driving", "AI gadgets", "Agentic AI",
      "Robots", "Power / data-center infrastructure",
    ]);
  });
});
