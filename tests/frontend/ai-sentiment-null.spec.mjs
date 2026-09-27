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
      valuation: { median_pe: null, stretched: false, note: "", fetched_at: null, cache_ttl_hours: null },
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
  // ...nor into a fabricated cache age when the backend sent no fetched_at.
  await expect(meta).not.toContainText(/\d+[hm] old/);
});

test("AI gauge — an unavailable PE renders — alone (no '· ok', no cache age)", async ({ page }) => {
  // The producer can return a null median_pe alongside a real fetched_at
  // (an empty/torn cache), but "unavailable" must stay "—" alone — neither an
  // affirmative "· ok" nor a cache age beside the dash.
  const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
  await installMockDashboard(page, {
    ai_sentiment: {
      valuation: { median_pe: null, stretched: false, note: "", fetched_at: twoHoursAgo, cache_ttl_hours: 12 },
    },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const card = page.locator('[data-card="ai-sentiment"]');
  const meta = card.locator(".ai-gauge-meta");
  await expect(meta).toContainText(/Valuation \(Beneficiary\) —/);
  await expect(card).not.toContainText("· ok");
  await expect(meta).not.toContainText(/\d+[hm] old/);
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

test("AI gauge — an empty payload renders —, no marker/cohorts/flips, and the unavailable line (02-L)", async ({ page }) => {
  // installMockDashboard() deep-merges into basePayload(), so a bare `{}` would
  // leave the base ai_sentiment in place. Every render-driving key is nulled
  // explicitly to reach the all-empty branch the card defends against.
  await installMockDashboard(page, {
    ai_sentiment: {
      score: null,
      verdict: null,
      spread_pct: null,
      news: null,
      valuation: null,
      cohorts: [],
      flip_conditions: [],
    },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const card = page.locator('[data-card="ai-sentiment"]');

  // A missing verdict is an explicit "—", never a fabricated label or colour.
  await expect(card.locator(".ai-gauge-verdict")).toHaveText("\u2014");
  // No score means no needle.
  await expect(card.locator(".ai-gauge-marker")).toHaveCount(0);
  // No header-only cohort table and no empty flip block.
  await expect(card.locator("table.table-gap tbody tr")).toHaveCount(0);
  await expect(card.locator(".flip-block")).toHaveCount(0);
  await expect(card.locator(".flip-block li")).toHaveCount(0);
  // One explicit "unavailable" line stands in for the missing reading.
  const reading = card.locator(".kv").filter({ hasText: "AI sentiment reading" });
  await expect(reading).toHaveCount(1);
  await expect(reading).toContainText("unavailable");
  await expect(reading).toContainText("no score, verdict, cohorts, or flip conditions");
});
