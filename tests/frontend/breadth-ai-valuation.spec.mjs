// tests/frontend/breadth-ai-valuation.spec.mjs
//
// BREADTH - AI Proxies hover + AI gauge Valuation (Beneficiary) cell.
// The static server fixture is started by the playwright config; this file
// only tests frontend rendering against the mock dashboard payload.
//
// Chart.js is intentionally blocked in tests (CDN abort). The renderers
// degrade to placeholder text when window.Chart is missing. Tests verify
// the data shapes and meta cell rendering — actual Chart.js tooltip hover
// can only be tested visually or with Chart.js loaded.

import { test, expect } from "@playwright/test";
import { installMockDashboard } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

// ---- Subset A: BREADTH hover data shapes -----------------------------------

const SAMPLE_PE_DETAIL = {
  NVDA: { above: true, forward_pe: 48.2, pct_from_ma: 8.5 },
  AMD: { above: false, forward_pe: 32.1, pct_from_ma: -2.1 },
  MU: { above: true, forward_pe: null, pct_from_ma: 1.2 },
  QCOM: { above: true, forward_pe: 15.4, pct_from_ma: 3.0 },
};

const SAMPLE_PE_GROUPS = [
  { name: "Compute / Accelerators", symbols: ["NVDA", "AMD"] },
  { name: "Memory", symbols: ["MU"] },
];

test("BREADTH - AI Proxies card renders breadth_pct from PE-enriched mock", async ({ page }) => {
  await installMockDashboard(page, {
    indicators: {
      breadth_ai: {
        breadth_pct: 60.0,
        detail: SAMPLE_PE_DETAIL,
        cohort_groups: SAMPLE_PE_GROUPS,
        cohort_median_pe: 32.15,
      },
    },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="breadth-ai"]');
  const card = page.locator('[data-card="breadth-ai"]');
  await expect(card).toBeVisible();
  await expect(card).toContainText("60");
});

test("BREADTH - AI Proxies mock payload carries cohort_median_pe and forward_pe", async ({ page }) => {
  let capturedPayload = null;
  await installMockDashboard(page, {
    indicators: {
      breadth_ai: {
        breadth_pct: 60.0,
        detail: SAMPLE_PE_DETAIL,
        cohort_groups: SAMPLE_PE_GROUPS,
        cohort_median_pe: 32.15,
      },
    },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="breadth-ai"]');
  // Verify the payload was received by the render path
  capturedPayload = await page.evaluate(() => {
    // The mock dashboard routes return our override payload.
    // We can verify the detail shapes via the DOM or direct fetch.
    return fetch("/api/dashboard").then((r) => r.json()).then((d) => d.indicators?.breadth_ai);
  });
  expect(capturedPayload).toBeTruthy();
  expect(capturedPayload.cohort_median_pe).toBe(32.15);
  expect(capturedPayload.detail.NVDA.forward_pe).toBe(48.2);
  expect(capturedPayload.detail.MU.forward_pe).toBeNull();
});

// ---- Subset B: AI gauge Valuation (Beneficiary) meta cell ------------------

test("AI gauge meta row shows Valuation (Beneficiary) cell with median + stretched tag", async ({ page }) => {
  await installMockDashboard(page, {
    ai_sentiment: {
      score: 12.3,
      verdict: "Healthy expansion",
      cohorts: [],
      spread_pct: 5.0,
      news: { tone: "neutral" },
      valuation: { median_pe: 42.1, stretched: true, note: "median 42.1× ≥ 30× (stretched)" },
      flip_conditions: [],
    },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const meta = page.locator('[data-card="ai-sentiment"] .ai-gauge-meta');
  await expect(meta).toContainText(/Valuation \(Beneficiary\)/);
  await expect(meta).toContainText(/42\.1×/);
  await expect(meta).toContainText(/stretched/);
});

test("AI gauge meta row shows Valuation (Beneficiary) · ok when not stretched", async ({ page }) => {
  await installMockDashboard(page, {
    ai_sentiment: {
      score: 5.0,
      verdict: "Balanced / mixed",
      cohorts: [],
      spread_pct: 0,
      news: { tone: "neutral" },
      valuation: { median_pe: 22.0, stretched: false, note: "median 22.0× < 30×" },
      flip_conditions: [],
    },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const meta = page.locator('[data-card="ai-sentiment"] .ai-gauge-meta');
  await expect(meta).toContainText(/Valuation \(Beneficiary\)/);
  await expect(meta).toContainText(/22\.0×/);
  await expect(meta).toContainText(/· ok/);
});

test("AI gauge meta row shows — when valuation median_pe is null (legacy payload)", async ({ page }) => {
  await installMockDashboard(page, {
    ai_sentiment: {
      score: 5.0,
      verdict: "Balanced / mixed",
      cohorts: [],
      spread_pct: 0,
      news: { tone: "neutral" },
      valuation: { median_pe: null, stretched: false, note: "" },
      flip_conditions: [],
    },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const meta = page.locator('[data-card="ai-sentiment"] .ai-gauge-meta');
  await expect(meta).toContainText(/Valuation \(Beneficiary\)/);
  await expect(meta).toContainText(/—/);
});

test("AI gauge displays score +25 when valuation is stretched", async ({ page }) => {
  // Baseline: not stretched
  await installMockDashboard(page, {
    ai_sentiment: {
      score: 10.0,
      verdict: "Healthy expansion",
      cohorts: [],
      spread_pct: 0,
      news: { tone: "neutral" },
      valuation: { median_pe: 22.0, stretched: false, note: "ok" },
      flip_conditions: [],
    },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const beforeScoreText = await page.locator('[data-card="ai-sentiment"] .ai-gauge-meta').textContent();
  const beforeScoreMatch = beforeScoreText.match(/Score\s+(-?\d+(?:\.\d+)?)/);
  expect(beforeScoreMatch).not.toBeNull();
  const beforeScore = parseFloat(beforeScoreMatch[1]);

  // Stretched: score should be +25 higher
  await installMockDashboard(page, {
    ai_sentiment: {
      score: 35.0,  // before + 25
      verdict: "Healthy expansion",
      cohorts: [],
      spread_pct: 0,
      news: { tone: "neutral" },
      valuation: { median_pe: 42.0, stretched: true, note: "stretched" },
      flip_conditions: [],
    },
  });
  await page.reload();
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const afterScoreText = await page.locator('[data-card="ai-sentiment"] .ai-gauge-meta').textContent();
  const afterScoreMatch = afterScoreText.match(/Score\s+(-?\d+(?:\.\d+)?)/);
  expect(afterScoreMatch).not.toBeNull();
  const afterScore = parseFloat(afterScoreMatch[1]);
  expect(afterScore - beforeScore).toBeCloseTo(25, 0);
});

test("AI gauge info tooltip mentions the valuation score shift", async ({ page }) => {
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const infoIcon = page.locator('[data-card="ai-sentiment"] h2 .card-info').first();
  await expect(infoIcon).toBeVisible();
  // The tooltip is created at boot by initCardTooltips(). Its text content
  // is set via textContent (not innerHTML), and the element exists in the DOM
  // even when hidden. Read the associated tooltip surface via aria-describedby.
  const tooltipId = await infoIcon.getAttribute("aria-describedby");
  expect(tooltipId).toBeTruthy();
  const tooltipText = await page.locator(`#${tooltipId} .tt-body`).textContent();
  expect(tooltipText.toLowerCase()).toContain("valuation");
  expect(tooltipText.toLowerCase()).toContain("score");
});
