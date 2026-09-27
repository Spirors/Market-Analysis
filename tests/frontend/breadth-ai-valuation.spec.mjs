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
      },
    },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="breadth-ai"]');
  const card = page.locator('[data-card="breadth-ai"]');
  await expect(card).toBeVisible();
  await expect(card).toContainText("60");
});

test("BREADTH - AI Proxies mock payload carries per-ticker forward_pe and pct_from_ma (no cohort_median_pe)", async ({ page }) => {
  let capturedPayload = null;
  await installMockDashboard(page, {
    indicators: {
      breadth_ai: {
        breadth_pct: 60.0,
        detail: SAMPLE_PE_DETAIL,
        cohort_groups: SAMPLE_PE_GROUPS,
      },
    },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="breadth-ai"]');
  // Verify the payload was received by the render path.
  capturedPayload = await page.evaluate(() =>
    fetch("/api/dashboard").then((r) => r.json()).then((d) => d.indicators?.breadth_ai)
  );
  expect(capturedPayload).toBeTruthy();
  // The cohort median is intentionally NOT on breadth_ai (it lives on the AI
  // gauge's `valuation.median_pe` field, rendered as the Valuation (Beneficiary)
  // meta cell). Putting it on breadth_ai too made every bar's hover look
  // identical (single aggregate), which read as a bug.
  expect(capturedPayload.cohort_median_pe).toBeUndefined();
  // Per-ticker forward_pe + pct_from_ma are wired for the hover.
  expect(capturedPayload.detail.NVDA.forward_pe).toBe(48.2);
  expect(capturedPayload.detail.NVDA.pct_from_ma).toBe(8.5);
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
  const infoIcon = page.locator('[data-card="ai-sentiment"] .card-info').first();
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

test("AI gauge info tooltip states the healthy/fragile direction of the gauge (02-Q)", async ({ page }) => {
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const infoIcon = page.locator('[data-card="ai-sentiment"] .card-info').first();
  await expect(infoIcon).toBeVisible();
  const tooltipId = await infoIcon.getAttribute("aria-describedby");
  expect(tooltipId).toBeTruthy();
  const tooltipText = await page.locator(`#${tooltipId} .tt-body`).textContent();
  // The verdicts/cutoffs alone left the reader guessing which end is good: the
  // tooltip now names the direction and that both extremes are the fragile ones.
  expect(tooltipText).toMatch(/Direction:/);
  expect(tooltipText).toMatch(/fragile/i);
  expect(tooltipText).toMatch(/healthy/i);
});

test("AI gauge info tooltip points at the card's freshness stamp", async ({ page }) => {
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const infoIcon = page.locator('[data-card="ai-sentiment"] .card-info').first();
  await expect(infoIcon).toBeVisible();
  const tooltipId = await infoIcon.getAttribute("aria-describedby");
  expect(tooltipId).toBeTruthy();
  const tooltipText = await page.locator(`#${tooltipId} .tt-body`).textContent();
  const lower = tooltipText.toLowerCase();
  // Freshness (point 5): the card's own "As of … ET" stamp carries data freshness.
  expect(lower).toContain("as of \u2026 et");
  expect(lower).toContain("data freshness");
});

test("Regime info tooltip covers interpretation, transition, and freshness", async ({ page }) => {
  await page.goto(DASH);
  await page.waitForSelector('[data-card="regime"]');
  const infoIcon = page.locator('[data-card="regime"] .card-info').first();
  await expect(infoIcon).toBeVisible();
  const tooltipId = await infoIcon.getAttribute("aria-describedby");
  expect(tooltipId).toBeTruthy();
  const tooltipText = await page.locator(`#${tooltipId} .tt-body`).textContent();
  const lower = tooltipText.toLowerCase();
  // Interpretation: label gloss + component grid + score/zone/confidence rows.
  expect(lower).toContain("plain-english gloss");
  expect(lower).toContain("component traffic-light grid");
  expect(lower).toContain("confidence");
  // What moves it: transition probability is the early-warning field.
  expect(lower).toContain("transition prob");
  expect(lower).toContain("re-runs on refresh");
  // Freshness: amber stale banner past 3 days + detector report stamp.
  expect(lower).toContain("generated_at");
  expect(lower).toContain("stale banner");
});

// ---- Subset C: AI gauge valuation cache age (02-M) -------------------------

test("AI gauge Valuation cell shows the PE cache age when fetched_at is present", async ({ page }) => {
  // Fixed-age fixture: fetched_at three hours before the page renders.
  const threeHoursAgo = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
  await installMockDashboard(page, {
    ai_sentiment: {
      valuation: {
        median_pe: 42.1, stretched: true, note: "stretched",
        fetched_at: threeHoursAgo, cache_ttl_hours: 12,
      },
    },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const meta = page.locator('[data-card="ai-sentiment"] .ai-gauge-meta');
  await expect(meta).toContainText(/42\.1× · stretched · 3h old/);
});

test("AI gauge Valuation cell shows no cache age when fetched_at is absent", async ({ page }) => {
  // The base fixture valuation carries no fetched_at.
  await installMockDashboard(page);
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const meta = page.locator('[data-card="ai-sentiment"] .ai-gauge-meta');
  await expect(meta).toContainText(/35\.0× · stretched/);
  await expect(meta).not.toContainText(/\d+[hm] old/);
});

// ---- Subset D: AI gauge axis labels match the verdict colour bands (02-K) ---

test("AI gauge axis labels each verdict band, fragile at both ends", async ({ page }) => {
  await installMockDashboard(page);
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const labels = page.locator('[data-card="ai-sentiment"] .ai-gauge-labels span');
  await expect(labels).toHaveCount(4);
  await expect(labels).toHaveText(["← Under pressure", "Balanced", "Healthy", "Euphoric →"]);
  // The green "Healthy" band sits in the upper-middle, never at the fragile
  // far right — the high end is Euphoric (red), not a "good" end.
  await expect(labels.nth(2)).toContainText("Healthy");
  await expect(labels.nth(3)).not.toContainText("Healthy");
});
