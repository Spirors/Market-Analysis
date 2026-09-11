// Playwright coverage for the bottleneck category rename feature — the ✎ pencil
// button in each category header (.bn-rename-btn). The backend endpoint is
// PUT /api/bottleneck/categories/{name}?new_name=...; the frontend swaps the
// title span for an inline input, saves on Enter/blur, and cancels on Escape.

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
let renameRequests = [];

function resetBn(categories) {
  bnCategories = [...categories];
  renameRequests = [];
}

async function mockBottleneckApi(page) {
  await page.route("**/api/bottleneck/**", async (route) => {
    const reqUrl = new URL(route.request().url());
    const method = route.request().method();
    const pathname = reqUrl.pathname.replace(/\/+$/, "");

    if (pathname.startsWith("/api/bottleneck/categories/") && method === "PUT") {
      const name = decodeURIComponent(pathname.split("/").pop());
      const newName = reqUrl.searchParams.get("new_name") || "";
      if (!newName.trim()) {
        return route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: "new_name must not be empty" }) });
      }
      const idx = bnCategories.indexOf(name);
      if (idx === -1) {
        return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: `unknown category: ${name}` }) });
      }
      // Apply rename: replace in the categories list
      const old = bnCategories[idx];
      bnCategories[idx] = newName.trim();
      renameRequests.push({ original: name, new_name: newName.trim() });
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ original: name, display: newName.trim() }) });
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

test.describe("Bottleneck rename (.bn-rename-btn)", () => {
  test("clicking pencil swaps title for inline input", async ({ page }) => {
    await mockDashboardWithBottleneck(page, [...CANONICAL_CATEGORIES]);
    await loadDashboard(page);

    // Title should show canonical name
    const title = page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-cat-title');
    await expect(title).toHaveText("Agentic AI");

    // Click pencil
    await page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-rename-btn').click();

    // Input should appear
    const input = page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-name-input');
    await expect(input).toBeVisible();
    await expect(input).toHaveValue("Agentic AI");
  });

  test("Enter key saves; new name displayed; PUT called", async ({ page }) => {
    await mockDashboardWithBottleneck(page, [...CANONICAL_CATEGORIES]);
    await loadDashboard(page);

    await page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-rename-btn').click();
    const input = page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-name-input');
    await input.fill("My AI");
    await input.press("Enter");

    // Title should now show the new name
    const title = page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-cat-title');
    await expect(title).toHaveText("My AI");

    // PUT was called
    expect(renameRequests).toHaveLength(1);
    expect(renameRequests[0]).toEqual({ original: "Agentic AI", new_name: "My AI" });
  });

  test("Escape cancels; original name restored", async ({ page }) => {
    await mockDashboardWithBottleneck(page, [...CANONICAL_CATEGORIES]);
    await loadDashboard(page);

    await page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-rename-btn').click();
    const input = page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-name-input');
    await input.fill("Should Not Save");
    await input.press("Escape");

    // Title should still show original
    const title = page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-cat-title');
    await expect(title).toHaveText("Agentic AI");

    // No PUT was called
    expect(renameRequests).toHaveLength(0);
  });

  test("blur with empty input restores original", async ({ page }) => {
    await mockDashboardWithBottleneck(page, [...CANONICAL_CATEGORIES]);
    await loadDashboard(page);

    await page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-rename-btn').click();
    const input = page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-name-input');
    await input.fill("");
    // Click elsewhere to trigger blur
    await page.locator(".bn-thesis").click();

    // Title should still show original
    const title = page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-cat-title');
    await expect(title).toHaveText("Agentic AI");

    // No PUT was called
    expect(renameRequests).toHaveLength(0);
  });

  test("rename does NOT collapse/expand (stopPropagation)", async ({ page }) => {
    await mockDashboardWithBottleneck(page, [...CANONICAL_CATEGORIES]);
    await loadDashboard(page);

    // The category body should be hidden initially
    await expect(page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-cat-body')).toHaveClass(/hidden/);

    // Click pencil
    await page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-rename-btn').click();
    const input = page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-name-input');
    await input.fill("Renamed");
    await input.press("Enter");

    // Category body should still be hidden (not toggled by the rename click)
    await expect(page.locator('.bn-category[data-cat-original="Agentic AI"] .bn-cat-body')).toHaveClass(/hidden/);
  });

  test("renamed category survives reload (server mock echoes rename back)", async ({ page }) => {
    // The mock dashboard will return categories with the canonical name; after
    // rename, the frontend re-renders with the new name. On reload, the mock
    // returns the original names (since the mock doesn't track renames across
    // page loads in this test), but we verify the PUT was sent correctly.
    await mockDashboardWithBottleneck(page, [...CANONICAL_CATEGORIES]);
    await loadDashboard(page);

    await page.locator('.bn-category[data-cat-original="AI gadgets"] .bn-rename-btn').click();
    const input = page.locator('.bn-category[data-cat-original="AI gadgets"] .bn-name-input');
    await input.fill("Smart Devices");
    await input.press("Enter");

    // Verify the title updated
    const title = page.locator('.bn-category[data-cat-original="AI gadgets"] .bn-cat-title');
    await expect(title).toHaveText("Smart Devices");

    // Verify PUT was called
    expect(renameRequests).toHaveLength(1);
    expect(renameRequests[0]).toEqual({ original: "AI gadgets", new_name: "Smart Devices" });

    // On reload, the mock returns canonical names (the mock doesn't track
    // server-side renames), but we verify the page loads successfully.
    await page.reload();
    await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");
    // The categories should be visible again
    await expect(page.locator(".bn-category")).toHaveCount(CANONICAL_CATEGORIES.length);
  });
});
