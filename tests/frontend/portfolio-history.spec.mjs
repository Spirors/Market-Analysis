// Playwright coverage for the Portfolio Performance panel: ONE aggregate
// gain-over-time line for the selected set of portfolios, plus its
// per-portfolio selector and its 1W/1M/3M/6M/1Y/ALL range control.
//
// Runs against the static file server (python -m http.server 8123) with all
// /api/* mocked via page.route(). No FastAPI server is started, and no real
// Chart.js is loaded: mockApi aborts the jsdelivr CDN, so this spec installs a
// tiny `window.Chart` stub via addInitScript that records each instance by its
// canvas id. The panel's real render path then runs unchanged, and the tests
// read the dataset config straight off the recorded instance — the same object
// the chart would have drawn.
//
// Frozen contract GET /api/portfolios/history is mocked: two portfolios with a
// null-gain day (gap), overlapping snapshot/retrospective dates (snapshot must
// win), and enough retrospective dates to exercise every time window.

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

const META_TEXT = "Gain over time \u00b7 as of close 2026-10-12";
const ALL_NOTE = "Solid = recorded settled-close snapshots; dashed = retrospective estimate from current holdings. Snapshots begin 2026-10-09. Gaps are missing closes.";
const SHORT_NOTE = "Recorded settled-close snapshots. Snapshots begin 2026-10-09. Gaps are missing closes.";
const EMPTY_HISTORY = "History starts with your first snapshot \u2014 it builds after the next scheduled refresh.";
const EMPTY_SELECTION = "Select at least one portfolio to plot.";
const CDN_MISSING = "Chart unavailable \u2014 Chart.js could not load.";
const RETRO_ONLY_NOTE = "Retrospective estimate from current holdings \u2014 no recorded settled-close snapshots yet. Gaps are missing closes.";

// Two portfolios. pf_a carries a null-gain day (a gap) and a retrospective
// series that overlaps pf_a's own snapshot dates (2026-10-09) so snapshot-wins
// precedence is observable. Both carry retrospective points on the same early
// dates, so the pre-snapshot stretch sums cleanly instead of nulling out.
// 2026-10-11 exists only to give the solid stretch a drawn segment.
function historyPayload() {
  const retro = (d, gain) => ({ date: d, value: null, cost: null, gain, coverage: { ok: 1, total: 1 } });
  const snap = (d, gain) => ({ date: d, value: null, cost: null, gain, coverage: { ok: 1, total: 1 } });
  return {
    portfolios: [
      { id: "pf_a", name: "Main" },
      { id: "pf_b", name: "Trading" },
    ],
    snapshots: {
      pf_a: [snap("2026-10-09", 420), snap("2026-10-10", null), snap("2026-10-11", 480), snap("2026-10-12", 500)],
      pf_b: [snap("2026-10-09", 100), snap("2026-10-10", 250), snap("2026-10-11", 280), snap("2026-10-12", 300)],
    },
    retrospective: {
      pf_a: [retro("2025-11-03", -200), retro("2026-09-01", -60), retro("2026-09-20", -30), retro("2026-10-01", -10), retro("2026-10-09", -50)],
      pf_b: [retro("2025-11-03", -50), retro("2026-09-01", -20), retro("2026-09-20", -20), retro("2026-10-01", -15), retro("2026-10-09", -10)],
    },
    meta: { as_of: "2026-10-12T07:00:12Z" },
  };
}

// Six portfolios, enough to force palette pressure: pf_a and beta both hash to
// palette slot 0 under a hash-only scheme, so they used to collide. Only the
// selector swatches are exercised here.
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

async function setup(page, history = historyPayload(), { stub = true } = {}) {
  await mockApi(page); // dashboard/meta/bottleneck + CDN abort
  if (stub) await installChartStub(page);
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
      legend: inst.config.options.plugins.legend,
      datasets: inst.config.data.datasets.map((d) => ({
        label: d.label,
        data: d.data,
        borderDash: d.borderDash || null,
        borderColor: d.borderColor,
        spanGaps: d.spanGaps,
        hasSegmentDash: !!(d.segment && typeof d.segment.borderDash === "function"),
      })),
    };
  });
}

// Evaluate the single dataset's scriptable segment.borderDash at the given
// segment start indices (p0DataIndex).
async function segmentDashes(page, indices) {
  return page.evaluate((idxs) => {
    const inst = window.__chartInstances["portfolioHistoryChart"];
    const fn = inst.config.data.datasets[0].segment.borderDash;
    return idxs.map((i) => fn({ p0DataIndex: i }));
  }, indices);
}

const hasChart = (page) =>
  page.evaluate(() => !!(window.__chartInstances && window.__chartInstances["portfolioHistoryChart"]));

const rangeBtn = (page, key) => page.locator(`#portfolioHistoryRange .pf-range-btn[data-range="${key}"]`);

test.describe("Portfolio Performance panel", () => {
  test("renders ONE aggregate line, with meta + note + selector + ALL range default", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);

    const cfg = await chartConfig(page);
    // x = union of trading days across the two selected portfolios, ascending.
    expect(cfg.labels).toEqual([
      "2025-11-03", "2026-09-01", "2026-09-20", "2026-10-01",
      "2026-10-09", "2026-10-10", "2026-10-11", "2026-10-12",
    ]);

    // Exactly one dataset, no legend, self-evident label.
    expect(cfg.datasets).toHaveLength(1);
    expect(cfg.datasets[0].label).toBe("Total gain");
    expect(cfg.legend.display).toBe(false);
    expect(cfg.datasets[0].hasSegmentDash).toBe(true);

    // Meta + note describe the new semantics.
    await expect(page.locator("#portfolioHistoryMeta")).toHaveText(META_TEXT);
    await expect(page.locator("#portfolioHistoryNote")).toHaveText(ALL_NOTE);

    // Selector lists both portfolios, both checked by default.
    const boxes = page.locator("#portfolioHistorySelect input[type=checkbox]");
    await expect(boxes).toHaveCount(2);
    await expect(page.locator('#portfolioHistorySelect input[data-pid="pf_a"]')).toBeChecked();
    await expect(page.locator('#portfolioHistorySelect input[data-pid="pf_b"]')).toBeChecked();

    // Range control present, ALL active by default.
    await expect(page.locator("#portfolioHistoryRange .pf-range-btn")).toHaveCount(6);
    await expect(rangeBtn(page, "ALL")).toHaveAttribute("aria-pressed", "true");
    await expect(rangeBtn(page, "1W")).toHaveAttribute("aria-pressed", "false");
  });

  test("the total sums the selected portfolios: snapshot beats retro on shared dates", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);

    const cfg = await chartConfig(page);
    const data = cfg.datasets[0].data;
    const at = (d) => data[cfg.labels.indexOf(d)];

    // Retrospective-only dates are the sum of both retrospectives.
    expect(at("2025-11-03")).toBe(-250); // -200 + -50
    expect(at("2026-09-20")).toBe(-50);  // -30 + -20
    // 2026-10-09 exists in BOTH series for both portfolios: snapshot wins.
    // If retro had won this would be -60 (-50 + -10); the snapshots give 520.
    expect(at("2026-10-09")).toBe(520);  // 420 + 100
    expect(at("2026-10-11")).toBe(760);  // 480 + 280
    expect(at("2026-10-12")).toBe(800);  // 500 + 300
  });

  test("a missing or null portfolio point nulls the TOTAL for that date (gap, spanGaps off)", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);

    const cfg = await chartConfig(page);
    const gapIndex = cfg.labels.indexOf("2026-10-10"); // pf_a snapshot value is null
    expect(cfg.datasets[0].data[gapIndex]).toBeNull(); // never a partial sum of 250
    expect(cfg.datasets[0].spanGaps).toBe(false);

    // Whereas an earlier date where BOTH have a point is summed normally.
    expect(cfg.datasets[0].data[cfg.labels.indexOf("2026-10-11")]).toBe(760);
  });

  test("the line is dashed for the retrospective-only stretch, solid from the first snapshot", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);

    // firstSnap = 2026-10-09 -> index 4 in the full window. Every segment that
    // leaves the pre-snapshot region (p0 < 4) is dashed; from 4 on it is solid.
    const dashes = await segmentDashes(page, [0, 3, 4, 6]);
    expect(dashes[0]).toEqual([5, 4]);
    expect(dashes[1]).toEqual([5, 4]); // 2026-10-01 -> 2026-10-09 transition
    expect(dashes[2]).toEqual([]);     // 2026-10-09 onward -> solid
    expect(dashes[3]).toEqual([]);

    // The dataset itself carries no static borderDash — the dash is per-segment.
    const cfg = await chartConfig(page);
    expect(cfg.datasets[0].borderDash).toBeNull();
  });

  test("the range buttons filter the window to the last N days", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);
    expect((await chartConfig(page)).labels).toHaveLength(8); // ALL default

    await rangeBtn(page, "1W").click();
    await expect.poll(async () => (await chartConfig(page))?.labels.length).toBe(4);
    expect((await chartConfig(page)).labels).toEqual(["2026-10-09", "2026-10-10", "2026-10-11", "2026-10-12"]);
    // No retrospective stretch in this window -> the note drops the dashed clause.
    await expect(page.locator("#portfolioHistoryNote")).toHaveText(SHORT_NOTE);

    await rangeBtn(page, "1M").click();
    await expect.poll(async () => (await chartConfig(page))?.labels.length).toBe(6);
    expect((await chartConfig(page)).labels).toEqual([
      "2026-09-20", "2026-10-01", "2026-10-09", "2026-10-10", "2026-10-11", "2026-10-12",
    ]);

    await rangeBtn(page, "ALL").click();
    await expect.poll(async () => (await chartConfig(page))?.labels.length).toBe(8);
    await expect(page.locator("#portfolioHistoryNote")).toHaveText(ALL_NOTE);
  });

  test("clicking a range updates aria-pressed and persists it", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);

    await rangeBtn(page, "1M").click();
    await expect(rangeBtn(page, "1M")).toHaveAttribute("aria-pressed", "true");
    await expect(rangeBtn(page, "ALL")).toHaveAttribute("aria-pressed", "false");
    await expect.poll(() => page.evaluate(() => localStorage.getItem("pfHistoryRange"))).toBe("1M");

    await page.reload();
    await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");
    await expect(page.locator("#portfolioHistory")).toBeVisible();
    await expect.poll(() => hasChart(page)).toBe(true);

    await expect(rangeBtn(page, "1M")).toHaveAttribute("aria-pressed", "true");
    await expect.poll(async () => (await chartConfig(page))?.labels.length).toBe(6);
  });

  test("unchecking a portfolio recomputes the aggregate", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);
    const before = await chartConfig(page);
    expect(before.datasets[0].data[before.labels.indexOf("2026-10-12")]).toBe(800);

    await page.locator('#portfolioHistorySelect input[data-pid="pf_b"]').uncheck();

    await expect.poll(async () => {
      const c = await chartConfig(page);
      return c && c.labels.indexOf("2026-10-12") >= 0 ? c.datasets[0].data[c.labels.indexOf("2026-10-12")] : null;
    }).toBe(500); // now pf_a alone
    const after = await chartConfig(page);
    expect(after.datasets).toHaveLength(1); // still one aggregate line
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
    expect(cfg.datasets).toHaveLength(1);
    expect(cfg.datasets[0].data[cfg.labels.indexOf("2026-10-12")]).toBe(500);
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

  test("a portfolio with only retrospective data is labelled an estimate", async ({ page }) => {
    const only = {
      portfolios: [{ id: "pf_a", name: "Main" }],
      snapshots: { pf_a: [] },
      retrospective: { pf_a: [{ date: "2025-11-03", value: null, cost: null, gain: 120, coverage: { ok: 1, total: 1 } }] },
      meta: { as_of: "2026-10-12T07:00:12Z" },
    };
    await setup(page, only);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);

    const cfg = await chartConfig(page);
    expect(cfg.datasets).toHaveLength(1);
    expect(cfg.datasets[0].data).toEqual([120]);
    // No recorded snapshot exists yet -> the note says so, not "solid = ...".
    await expect(page.locator("#portfolioHistoryNote")).toHaveText(RETRO_ONLY_NOTE);
    await expect(page.locator("#portfolioHistoryMeta")).toHaveText("Gain over time");
  });

  test("when Chart.js is missing, an honest note replaces the chart", async ({ page }) => {
    await setup(page, historyPayload(), { stub: false });
    await loadDashboard(page);

    await expect(page.locator("#portfolioHistoryEmpty")).toBeVisible();
    await expect(page.locator("#portfolioHistoryEmpty")).toHaveText(CDN_MISSING);
    // Meta/note are still set (the numbers are not fabricated, the canvas is).
    await expect(page.locator("#portfolioHistoryMeta")).toHaveText(META_TEXT);
    expect(await hasChart(page)).toBe(false);
  });

  test("six portfolios all get distinct swatch colours (no palette collision)", async ({ page }) => {
    await setup(page, historyPayloadSix());
    await loadDashboard(page);

    const boxes = page.locator("#portfolioHistorySelect input[type=checkbox]");
    await expect(boxes).toHaveCount(6);

    // Read each swatch's resolved colour. pf_a and beta collide under a
    // hash-only scheme (both slot 0), so a revert to hashing alone fails here.
    const colours = await page.$$eval("#portfolioHistorySelect .pf-hist-swatch", (els) =>
      els.map((el) => getComputedStyle(el).backgroundColor)
    );
    expect(colours).toHaveLength(6);
    expect(new Set(colours).size).toBe(6);
  });

  test("long ranges tick once per calendar month (no duplicated or skipped months)", async ({ page }) => {
    await setup(page);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);

    // ym ranges filter ticks to month starts in afterBuildTicks and drop the
    // capped autoSkip sampling that could duplicate or skip a month label.
    const initial = await page.evaluate(() => {
      const x = window.__chartInstances["portfolioHistoryChart"].config.options.scales.x;
      return { hasAfter: typeof x.afterBuildTicks === "function", autoSkip: x.ticks.autoSkip };
    });
    expect(initial.hasAfter).toBe(true); // ALL is the default range (ym)
    expect(initial.autoSkip).toBe(false);

    // Exercise the filter against the full label set: only month starts survive,
    // strictly one per month, ascending.
    const kept = await page.evaluate(() => {
      const inst = window.__chartInstances["portfolioHistoryChart"];
      const labels = inst.config.data.labels;
      const axis = { ticks: labels.map((_, i) => ({ value: i })) };
      inst.config.options.scales.x.afterBuildTicks(axis);
      return axis.ticks.map((t) => labels[t.value].slice(0, 7));
    });
    expect(kept).toEqual(["2025-11", "2026-09", "2026-10"]);
    expect(new Set(kept).size).toBe(kept.length);

    // Short (md) windows keep sampled ticks and carry no month filter.
    await rangeBtn(page, "1M").click();
    await expect.poll(async () => (await chartConfig(page))?.labels.length).toBe(6);
    const short = await page.evaluate(() => {
      const x = window.__chartInstances["portfolioHistoryChart"].config.options.scales.x;
      return { hasAfter: typeof x.afterBuildTicks === "function", autoSkip: x.ticks.autoSkip };
    });
    expect(short.hasAfter).toBe(false);
    expect(short.autoSkip).toBe(true);
  });

  test("a crowded leading month label is dropped (Sep 30 stub before Oct 1)", async ({ page }) => {
    const crowded = {
      portfolios: [{ id: "pf_a", name: "Main" }],
      snapshots: { pf_a: [] },
      retrospective: {
        pf_a: ["2025-09-30", "2025-10-01", "2025-10-02", "2025-10-03", "2025-10-06"].map((d) => ({
          date: d, value: null, cost: null, gain: 1, coverage: { ok: 1, total: 1 },
        })),
      },
      meta: { as_of: "2026-10-12T07:00:12Z" },
    };
    await setup(page, crowded);
    await loadDashboard(page);
    await expect.poll(() => hasChart(page)).toBe(true);

    const kept = await page.evaluate(() => {
      const inst = window.__chartInstances["portfolioHistoryChart"];
      const labels = inst.config.data.labels;
      const axis = { ticks: labels.map((_, i) => ({ value: i })) };
      inst.config.options.scales.x.afterBuildTicks(axis);
      return axis.ticks.map((t) => labels[t.value].slice(0, 7));
    });
    // Sep 30 sits one slot before the Oct 1 boundary, so it is dropped and the
    // clean Oct tick remains instead of two overlapping labels.
    expect(kept).toEqual(["2025-10"]);
  });
});
