// Tests for the per-section "cached" cooldown badge and the global
// refresh button tooltip introduced in Feature C.

import { test, expect } from "@playwright/test";
import { installMockDashboard } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

// Helper: compute an ISO timestamp that is `minutesAgo` minutes before now.
function minutesAgoISO(minutesAgo) {
  const d = new Date(Date.now() - minutesAgo * 60 * 1000);
  return d.toISOString();
}

test("Portfolio card shows 'cached Xm' badge when cooldown_skip includes portfolio", async ({ page }) => {
  await installMockDashboard(page, {
    cooldown_skip: ["portfolio"],
    vintage: { portfolios: minutesAgoISO(10) },
  });
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");

  // Expand the portfolio so the card body renders (the card exists either way).
  const badge = page.locator('[data-card="portfolio"] .cov-cooldown');
  await expect(badge).toBeVisible();
  await expect(badge).toHaveText("cached 10m");
});

test("Breadth-AI card shows 'cached Xm' badge when cooldown_skip includes breadth_ai", async ({ page }) => {
  await installMockDashboard(page, {
    cooldown_skip: ["breadth_ai"],
    vintage: { indicators: minutesAgoISO(22) },
  });
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");

  const badge = page.locator('[data-card="breadth-ai"] .cov-cooldown');
  await expect(badge).toBeVisible();
  await expect(badge).toHaveText("cached 22m");
});

test("Portfolio card hides the badge when cooldown_skip is empty", async ({ page }) => {
  await installMockDashboard(page, {
    cooldown_skip: [],
  });
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");

  await expect(page.locator('[data-card="portfolio"] .cov-cooldown')).toHaveCount(0);
  await expect(page.locator('[data-card="breadth-ai"] .cov-cooldown')).toHaveCount(0);
});

test("Refresh button tooltip shows 'Last refresh' info on hover", async ({ page }) => {
  // Use a fixed as_of so we can predict the tooltip text.
  const asOf = minutesAgoISO(5);
  await installMockDashboard(page, {
    as_of: asOf,
    cooldown_skip: ["portfolio"],
    vintage: { portfolios: minutesAgoISO(10) },
  });
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");

  // Hover the refresh button to trigger the live tooltip.
  await page.locator("#refreshBtn").hover();
  // The tooltip should contain "Last refresh" and "next refresh" text.
  const title = await page.locator("#refreshBtn").getAttribute("title");
  expect(title).toContain("Last refresh");
  expect(title).toContain("Next refresh");
});
