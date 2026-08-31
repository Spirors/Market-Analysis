// E2E test for the global refresh + news chips + card tooltips.
//
// The dashboard is served from static/index.html with /api/* mocked (see
// mock-dashboard.mjs), so the test is deterministic and needs no backend.

import { test, expect } from "@playwright/test";
import { mockApi, dashboardCallCount } from "./mock-dashboard.mjs";

const DASH = "/static/index.html";

const ALL_CARDS = [
  "risk", "ai-sentiment", "analysis", "fragility", "regime", "indicators",
  "indices", "commodities", "rates", "breadth", "breadth-ai", "bottleneck",
  "earnings", "thirteenf", "events",
];

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto(DASH);
  // Wait for the initial dashboard render (risk body stops being "Loading…").
  await expect(page.locator("#riskBody")).not.toHaveText("Loading…");
});

test("every major card carries an info tooltip button", async ({ page }) => {
  for (const id of ALL_CARDS) {
    const card = page.locator(`[data-card="${id}"]`);
    await expect(card.locator(".card-info")).toHaveCount(1, { timeout: 5000 });
    await expect(card.locator(".card-info")).toHaveAttribute("aria-label", `About the ${id} card`);
  }
});

test("no card carries a per-card refresh icon — global Refresh is the only affordance", async ({ page }) => {
  await expect(page.locator(".section-refresh")).toHaveCount(0);
  // The header Refresh button is present and is the single refresh control.
  await expect(page.locator("#refreshBtn")).toBeVisible();
});

test("global Refresh re-fetches /api/dashboard and re-renders", async ({ page }) => {
  expect(dashboardCallCount()).toBe(1); // initial load
  const asofBefore = await page.locator("#asof").textContent();

  await page.locator("#refreshBtn").click();
  await expect(page.locator("#refreshBtn")).toHaveText("Refresh"); // done spinning

  expect(dashboardCallCount()).toBe(2); // re-fetched
  const asofAfter = await page.locator("#asof").textContent();
  expect(asofAfter).not.toBe(asofBefore);

  // Cards re-rendered with fresh content.
  await expect(page.locator("#riskBody")).toContainText("YELLOW");
  await expect(page.locator("#analysisBody")).toContainText("Cautious");
});

test("coverage badges and vintage stamps survive (no regression)", async ({ page }) => {
  // Risk coverage is 2/3 in the mock -> the "2/3" badge must render.
  await expect(page.locator('[data-card="risk"] .cov-badge')).toHaveText("2/3");
  // Vintage stamps render the full date + HH:MM, matching the header format.
  await expect(page.locator('[data-card="risk"] .vintage-note')).toHaveText(/As of \d{4}-\d{2}-\d{2} \d{2}:\d{2} ET/);
  await expect(page.locator('[data-card="events"] .vintage-note')).toHaveText(/As of \d{4}-\d{2}-\d{2} \d{2}:\d{2} ET/);
});

test("news rows carry region pill, source-weight badge, relevance chip", async ({ page }) => {
  const first = page.locator(".tl-item").first();
  await expect(first.locator(".tl-meta .pill.region")).toHaveCount(1);
  await expect(first.locator(".tl-meta .sw-badge")).toHaveCount(1);
  await expect(first.locator(".tl-meta .rel-chip")).toHaveCount(1);
});

test("region chip filters the timeline (multi-select)", async ({ page }) => {
  await expect(page.locator("#tlRegionChips .chip")).toHaveCount(10);
  // Click the US chip.
  await page.locator('#tlRegionChips .chip[data-key="us"]').click();
  await expect(page.locator('#tlRegionChips .chip[data-key="us"]')).toHaveClass(/active/);
  // Only the US event remains.
  const titles = await page.locator(".tl-item .tl-body a, .tl-item .tl-body .tl-plain").allTextContents();
  expect(titles).toHaveLength(1);
  expect(titles[0]).toContain("Fed holds rates steady");
});

test("source-weight chip is single-select", async ({ page }) => {
  await page.locator('#tlWeightChips .chip[data-key="high"]').click();
  await expect(page.locator('#tlWeightChips .chip[data-key="high"]')).toHaveClass(/active/);
  // Only the high-weight (1.2) event remains.
  let titles = await page.locator(".tl-item .tl-body a, .tl-item .tl-body .tl-plain").allTextContents();
  expect(titles).toHaveLength(1);
  expect(titles[0]).toContain("Fed holds rates steady");

  // Clicking med replaces high (single-select, not additive).
  await page.locator('#tlWeightChips .chip[data-key="med"]').click();
  await expect(page.locator('#tlWeightChips .chip[data-key="high"]')).not.toHaveClass(/active/);
  await expect(page.locator('#tlWeightChips .chip[data-key="med"]')).toHaveClass(/active/);
  titles = await page.locator(".tl-item .tl-body a, .tl-item .tl-body .tl-plain").allTextContents();
  expect(titles).toHaveLength(1);
  expect(titles[0]).toContain("Nvidia earnings beat");
});

test("topic chip filters by derived topic", async ({ page }) => {
  // "rates" topic: the Fed event mentions rates.
  await page.locator('#tlTopicChips .chip[data-key="rates"]').click();
  const titles = await page.locator(".tl-item .tl-body a, .tl-item .tl-body .tl-plain").allTextContents();
  expect(titles).toHaveLength(1);
  expect(titles[0]).toContain("Fed holds rates steady");
});

test("seed-only toggle preserves the Wikipedia/curated view", async ({ page }) => {
  await page.locator("#tlSeedOnly").check();
  await expect(page.locator("#tlSeedOnly")).toBeChecked();
  const titles = await page.locator(".tl-item .tl-body a, .tl-item .tl-body .tl-plain").allTextContents();
  expect(titles).toHaveLength(2);
  expect(titles.join(" ")).toContain("Fed holds rates steady");
  expect(titles.join(" ")).toContain("China unveils stimulus");
  expect(titles.join(" ")).not.toContain("Nvidia");
});

test("news filter state persists across reloads", async ({ page }) => {
  // US is a seed event (Wikipedia), so it composes with the seed-only toggle.
  await page.locator('#tlRegionChips .chip[data-key="us"]').click();
  await page.locator("#tlSeedOnly").check();

  await page.reload();
  await expect(page.locator("#riskBody")).not.toHaveText("Loading…");

  await expect(page.locator('#tlRegionChips .chip[data-key="us"]')).toHaveClass(/active/);
  await expect(page.locator("#tlSeedOnly")).toBeChecked();
  const titles = await page.locator(".tl-item .tl-body a, .tl-item .tl-body .tl-plain").allTextContents();
  expect(titles).toHaveLength(1);
  expect(titles[0]).toContain("Fed holds rates steady");
});

test("filters compose with the existing tag chips", async ({ page }) => {
  // Tag chip "ai" (existing) + region "us" (new) both apply.
  await page.locator('#tlFilters .chip[data-tag="ai"]').click();
  await page.locator('#tlRegionChips .chip[data-key="us"]').click();
  const titles = await page.locator(".tl-item .tl-body a, .tl-item .tl-body .tl-plain").allTextContents();
  expect(titles).toHaveLength(1);
  expect(titles[0]).toContain("Fed holds rates steady");
});

test("legacy dashLayout migrates on read, existing order survives", async ({ page }) => {
  // Seed an old {bands, cards} layout (pre-v2 shape) before the app boots.
  await page.evaluate(() => {
    localStorage.setItem("dashLayout", JSON.stringify({ bands: ["sentiment"], cards: ["events", "risk", "analysis"] }));
  });
  await page.reload();
  await expect(page.locator("#riskBody")).not.toHaveText("Loading…");

  // The migrated order is applied: events sits before risk.
  const order = await page.locator("#bands [data-card]:not(.hidden)").evaluateAll(
    (els) => els.map((el) => el.dataset.card)
  );
  expect(order.indexOf("events")).toBeLessThan(order.indexOf("risk"));

  // And the upgraded v2 shape is written back for next time.
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem("dashLayout")));
  expect(saved.v).toBe(2);
  expect(saved.order).toContain("events");
});