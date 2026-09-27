// tests/frontend/ai-sentiment-null.spec.mjs
//
// DATA-integrity guards for the AI-sentiment card when its inputs are missing.
// The producer encodes "unavailable" as explicit nulls (e.g. a valuation of
// {median_pe: null, stretched: false}); the card must render those as "—", not
// promote them into an affirmative "ok" or a fabricated midpoint needle.
//
// Style mirrors breadth-ai-valuation.spec.mjs: the static server fixture is
// started by the playwright config, and every case overrides the dashboard
// payload per-test via installMockDashboard() rather than editing the shared
// fixture.

import { test, expect } from "@playwright/test";
import { installMockDashboard } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

test("AI gauge — null valuation median_pe renders — with no '· ok' suffix", async ({ page }) => {
  await installMockDashboard(page, {
    ai_sentiment: {
      valuation: { median_pe: null, stretched: false, note: "" },
    },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const card = page.locator('[data-card="ai-sentiment"]');
  const meta = card.locator(".ai-gauge-meta");
  await expect(meta).toContainText(/Valuation \(Beneficiary\)/);
  await expect(meta).toContainText(/Valuation \(Beneficiary\) —/);
  // "unavailable" must never be promoted into an affirmative "ok".
  await expect(card).not.toContainText("· ok");
});

test("AI gauge — null score renders no marker and 'Score —'", async ({ page }) => {
  await installMockDashboard(page, {
    ai_sentiment: { score: null },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const card = page.locator('[data-card="ai-sentiment"]');
  await expect(card.locator(".ai-gauge-marker")).toHaveCount(0);
  await expect(card.locator(".ai-gauge-meta")).toContainText(/Score\s*—/);
});

test("AI gauge — vintage.ai_sentiment renders the card's 'As of … ET' stamp", async ({ page }) => {
  await installMockDashboard(page, {
    vintage: { ai_sentiment: "2026-08-30T15:45:00Z" },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const note = page.locator('[data-card="ai-sentiment"] .vintage-note');
  await expect(note).toBeVisible();
  await expect(note).toHaveText(/As of \d{4}-\d{2}-\d{2} \d{2}:\d{2} ET/);
});
