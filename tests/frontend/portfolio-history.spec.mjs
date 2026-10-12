// Playwright coverage for the Portfolio Performance panel (gain-over-time
// chart) and its per-portfolio multi-select.
//
// Runs against the static file server (python -m http.server 8123) with all
// /api/* mocked via page.route(). No FastAPI server is started, and no real
// Chart.js is loaded: mockApi aborts the jsdelivr CDN, so this spec installs a
// tiny `window.Chart` stub via addInitScript that records each instance by its
// canvas id. The panel's real render path then runs unchanged, and the tests
// read the dataset config straight off the recorded instance — the same object
// the chart would have drawn.
//
// Frozen contract GET /api/portfolios/history is mocked with the payload from
// the feature brief (two portfolios, a null gain day = gap, a retrospective
// series, empty-portfolio cases).

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

const META_TEXT = "Gain over time \u00b7 as of close 2026-10-10";
const RETRO_NOTE = "Dashed = retrospective: current holdings applied backwards (not actual history)";
const EMPTY_HISTORY = "History starts with your first snapshot \u2014 it builds after the next scheduled refresh.";
const EMPTY_SELECTION = "Select at least one portfolio to plot.";

// pf_b carries data too (the brief's example left it empty) so the selector
// has a line to add and remove; pf_a keeps the null-gain day and the retro
// series.
function historyPayload() {
  return {
    portfolios: [
      { id: "pf_a", name: "Main" },
      { id: "pf_b", name: "Trading" },
    ],
    snapshots: {
      pf_a: [
        { date: "2026-10-09", value: 10420.0, cost: 10000.0, gain: 420.0, coverage: { ok: 8, total: 8 } },
        { date: "2026-10-10", value: null, cost: 10000.0, gain: null, coverage: { ok: 7, total: 8 } },
      ],
      pf_b: [
        { date: "2026-10-09", value: 5100.0, cost: 5000.0, gain: 100.0, coverage: { ok: 4, total: 4 } },
        { date: "2026-10-10", value: 5250.0, cost: 5000.0, gain: 250.0, coverage: { ok: 4, total: 4 } },
      ],
    },
    retrospective: {
      pf_a: [{ date: "2025-11-03", value: 9800.0, cost: 10000.0, gain: -200.0, coverage: { ok: 8, total: 8 } }],
      pf_b: [],
    },
    meta: { as_of: "2026-10-12T07:00:12Z" },
  };
}

// Six portfolios, enough to force palette pressure: pf_a and beta both hash to
// palette slot 0 under the old hash-only scheme, so they collided. Includes two
// retrospective series so both solid and dashed datasets are exercised.
function historyPayloadSix() {
  return {
    portfolios: [
      { id: "pf_a", name: "Main" },
      { id: "beta", name: "Beta" },
      { id: "pf_c", name: "Growth" },
      { id: "pf_d", name: "Income" },
      { id: "pf_e", name: "Spec" },
      { id: "pf_f", name: "Reserve" },
    ],
    snapshots: {
      pf_a: [{ date: "2026-10-10", value: 10420.0, cost: 10000.0, gain: 420.0, coverage: { ok: 8, total: 8 } }],
      beta: [{ date: "2026-10-10", value: 2100.0, cost: 2000.0, gain: 100.0, coverage: { ok: 2, total: 2 } }],
      pf_c: [{ date: "2026-10-10", value: 5300.0, cost: 5000.0, gain: 300.0, coverage: { ok: 3, total: 3 } }],
      pf_d: [{ date: "2026-10-10", value: 8100.0, cost: 8000.0, gain: 100.0, coverage: { ok: 3, total: 3 } }],
      pf_e: [{ date: "2026-10-10", value: 6200.0, cost: 6000.0, gain: 200.0, coverage: { ok: 3, total: 3 } }],
      pf_f: [{ date: "2026-10-10", value: 3100.0, cost: 3000.0, gain: 100.0, coverage: { ok: 3, total: 3 } }],
    },
    retrospective: {
      pf_a: [{ date: "2025-11-03", value: 9800.0, cost: 10000.0, gain: -200.0, coverage: { ok: 8, total: 8 } }],
      beta: [{ date: "2025-11-03", value: 1950.0, cost: 2000.0, gain: -50.0, coverage: { ok: 2, total: 2 } }],
    },
    meta: { as_of: "2026-10-12T07:00:12Z" },
  };
}

function dashboardPayload() {
  return {
    as_of: new Date().toISOString(),
    // Root-level portfolios: cards.js -> renderPortfolio(data) reads these so
    // the card renders without triggering its own GET /api/portfolios.
    portfolios: {
      pf_a: { id: "pf_a", name: "Main", holdings: [] },
      pf_b: { id: "pf_b", name: "Trading", holdings: [] },
    },
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
  };
}

// Minimal Chart.js stub: records each instance by its canvas id so tests can
// read the exact data/options the panel handed to Chart.js.
async function installChartStub(page) {
  await page.addInitScript(() => {
    window.__chartInstances = {};
    window.Chart = class {
      constructor(canvas, config) {
        this.canvas = canvas;
        this.config = config;
        window.__chartInstances[canvas.id] = this;
      }
      destroy() { delete window.__chartInstances[this.canvas.id]; }
    };
  });
}

async function setup(page, history = historyPayload()) {
  await mockApi(page); // dashboard/meta/bottleneck + CDN abort
  await installChartStub(page);
  // Generic collection route first, the specific history route last (Playwright
  // matches the most recently registered handler first), so /history is not
  // swallowed by the collection glob.
  await page.route("**/api/portfolios", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ version: 1, portfolios: {} }) })
  );
  await page.route("**/api/dashboard", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(dashboardPayload()) })
  );
  await page.route("**/api/portfolios/history", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(history) })
  );
}

async function loadDashboard(page) {
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");
  await expect(page.locator("#portfolioHistory")).toBeVisible();
}

async function chartConfig(page) {
  return page.evaluate(() => {
    const inst = window.__chartInstances && window.__chartInstances["portfolioHistoryChart"];
    if (!inst) return null;
    return {
      labels: inst.config.data.labels,
      datasets: inst.config.data.datasets.map((d) => ({
        label: d.label,
        data: d.data,
        borderDash: d.borderDash || null,
        borderColor: d.borderColor,
        spanGaps: d.spanGaps,
      })),
    };
  });
}

const hasChart = (page) =>
  page.evaluate(() => !!(window.__chartInstances && window.__chartInstances["portfolioHistoryChart"]));

test.describe("Portfolio Performance panel", () => {
  test("renders a line chart from the payload, with meta + selector defaulting to all", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);

    await expect.poll(() => hasChart(page)).toBe(true);

    const cfg = await chartConfig(page);
    // x = union of trading days across selected portfolios, ascending.
    expect(cfg.labels).toEqual(["2025-11-03", "2026-10-09", "2026-10-10"]);

    // One solid line per portfolio + one dashed retrospective line for pf_a.
    expect(cfg.datasets.map((d) => d.label).sort()).toEqual(
      ["Main", "Main (retrospective)", "Trading"].sort()
    );

    // Meta + retro note.
    await expect(page.locator("#portfolioHistoryMeta")).toHaveText(META_TEXT);
    await expect(page.locator("#portfolioHistoryNote")).toHaveText(RETRO_NOTE);

    // Selector lists both portfolios, both checked by default.
    const boxes = page.locator("#portfolioHistorySelect input[type=checkbox]");
    await expect(boxes).toHaveCount(2);
    await expect(page.locator('#portfolioHistorySelect input[data-pid="pf_a"]')).toBeChecked();
    await expect(page.locator('#portfolioHistorySelect input[data-pid="pf_b"]')).toBeChecked();
  });

  test("a null-gain day is a GAP, not a zero (spanGaps off)", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);

    const cfg = await chartConfig(page);
    const main = cfg.datasets.find((d) => d.label === "Main");
    expect(main).toBeTruthy();
    // 2026-10-10 has gain: null -> null data point (gap). Never 0.
    const gapIndex = cfg.labels.indexOf("2026-10-10");
    expect(main.data[gapIndex]).toBeNull();
    expect(main.data[cfg.labels.indexOf("2026-10-09")]).toBe(420);
    expect(main.spanGaps).toBe(false);
  });

  test("the retrospective series is dashed and shares the portfolio's solid colour", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);

    const cfg = await chartConfig(page);
    const solid = cfg.datasets.find((d) => d.label === "Main");
    const retro = cfg.datasets.find((d) => d.label === "Main (retrospective)");
    expect(solid).toBeTruthy();
    expect(retro).toBeTruthy();
    // Dashed line, same stable colour as its solid counterpart.
    expect(retro.borderDash).toEqual([5, 4]);
    expect(retro.borderColor).toBe(solid.borderColor);
    // It sits on the earlier retrospective date only.
    expect(retro.data[cfg.labels.indexOf("2025-11-03")]).toBe(-200);
    expect(retro.spanGaps).toBe(false);
  });

  test("unchecking a portfolio removes its line", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);
    expect((await chartConfig(page)).datasets).toHaveLength(3);

    await page.locator('#portfolioHistorySelect input[data-pid="pf_b"]').uncheck();

    await expect.poll(async () => (await chartConfig(page))?.datasets.length).toBe(2);
    const cfg = await chartConfig(page);
    expect(cfg.datasets.some((d) => d.label.startsWith("Trading"))).toBe(false);
    // pf_a's own datasets are untouched.
    expect(cfg.datasets.some((d) => d.label === "Main")).toBe(true);
  });

  test("the selection persists across a reload", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);

    await page.locator('#portfolioHistorySelect input[data-pid="pf_b"]').uncheck();
    await expect.poll(() => page.evaluate(() => localStorage.getItem("pfHistorySelected"))).toContain("pf_a");

    await page.reload();
    await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");
    await expect(page.locator("#portfolioHistory")).toBeVisible();
    await expect.poll(() => hasChart(page)).toBe(true);

    await expect(page.locator('#portfolioHistorySelect input[data-pid="pf_b"]')).not.toBeChecked();
    await expect(page.locator('#portfolioHistorySelect input[data-pid="pf_a"]')).toBeChecked();
    const cfg = await chartConfig(page);
    expect(cfg.datasets.some((d) => d.label.startsWith("Trading"))).toBe(false);
  });

  test("deselecting every portfolio shows the select-at-least-one state", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);

    await page.locator('#portfolioHistorySelect input[data-pid="pf_a"]').uncheck();
    await page.locator('#portfolioHistorySelect input[data-pid="pf_b"]').uncheck();

    await expect(page.locator("#portfolioHistoryEmpty")).toBeVisible();
    await expect(page.locator("#portfolioHistoryEmpty")).toHaveText(EMPTY_SELECTION);
    await expect.poll(() => hasChart(page)).toBe(false);
  });

  test("no history yet shows the empty state", async ({ page }) => {
    const empty = {
      portfolios: [{ id: "pf_a", name: "Main" }],
      snapshots: { pf_a: [] },
      retrospective: { pf_a: [] },
      meta: { as_of: "2026-10-12T07:00:12Z" },
    };
    await setup(page, empty);
    await loadDashboard(page);

    // Panel is shown (a portfolio exists) but nothing is plotted.
    await expect(page.locator("#portfolioHistoryEmpty")).toBeVisible();
    await expect(page.locator("#portfolioHistoryEmpty")).toHaveText(EMPTY_HISTORY);
    expect(await hasChart(page)).toBe(false);
    await expect(page.locator("#portfolioHistoryMeta")).toHaveText("");
  });

  test("six portfolios all get distinct swatch colours (no palette collision)", async ({ page }) => {
    await setup(page, historyPayloadSix());
    await loadDashboard(page);

    const boxes = page.locator("#portfolioHistorySelect input[type=checkbox]");
    await expect(boxes).toHaveCount(6);

    // Read each swatch's resolved colour. pf_a and beta collide under the old
    // hash-only scheme (both slot 0), so a revert to hashing alone fails here.
    const colours = await page.$$eval("#portfolioHistorySelect .pf-hist-swatch", (els) =>
      els.map((el) => getComputedStyle(el).backgroundColor)
    );
    expect(colours).toHaveLength(6);
    expect(new Set(colours).size).toBe(6);
  });
});
