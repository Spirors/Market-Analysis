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

test("Portfolio prices are not blank after refresh", async ({ page }) => {
  // Mock dashboard with portfolio holdings that have live prices.
  await installMockDashboard(page, {
    portfolios: {
      pid1: {
        id: "pid1",
        name: "Test Portfolio",
        holdings: [
          { symbol: "NVDA", shares: 10, total_cost: 1000, last_price: 150.0, pct_daily: 2.0 },
        ],
      },
    },
    cooldown_skip: [],
    vintage: { portfolios: minutesAgoISO(1) },
  });
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");

  // Expand the portfolio to see holdings.
  await page.locator('.pf-pf[data-pid="pid1"] .pf-caret').click();
  await expect(page.locator('.pf-pf[data-pid="pid1"] .pf-holdings-table')).toBeVisible();

  // The holding row must show the live price — not "—".
  // fmtPrice returns raw numbers (no $), so 150.0 renders as "150".
  const row = page.locator('.pf-pf[data-pid="pid1"] .pf-holdings-table tr[data-symbol="NVDA"]');
  await expect(row).toContainText("150");
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

test("Refresh button tooltip shows 'Last refresh' info on hover and focus", async ({ page }) => {
  // Use a fixed as_of so we can predict the tooltip text.
  const asOf = minutesAgoISO(5);
  await installMockDashboard(page, {
    as_of: asOf,
    cooldown_skip: ["portfolio"],
    vintage: { portfolios: minutesAgoISO(10) },
  });
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");

  // The old mouseenter-only native `title` hack is gone (FIX-00-D): the button
  // is wired to the unified tooltip surface via aria-describedby instead.
  const btn = page.locator("#refreshBtn");
  expect(await btn.getAttribute("title")).toBeNull();
  const describedBy = await btn.getAttribute("aria-describedby");
  expect(describedBy).toBeTruthy();
  const tooltip = page.locator(`#${describedBy}`);
  await expect(tooltip).toHaveAttribute("role", "tooltip");

  // Hover the refresh button to open the live tooltip.
  await btn.hover();
  await expect(tooltip).toBeVisible();
  await expect(tooltip).toContainText("Last refresh");
  await expect(tooltip).toContainText("Next refresh");

  // Keyboard path — the new behaviour this wiring exists for: moving the mouse
  // off the button closes the hover tooltip, and focusing the button alone
  // re-opens the same surface with the same live copy.
  await page.mouse.move(10, 10); // off the trigger and tooltip
  await expect(tooltip).toBeHidden();
  await btn.focus();
  await expect(tooltip).toBeVisible();
  await expect(tooltip).toContainText("Last refresh");
  await expect(tooltip).toContainText("Next refresh");

  // Escape dismisses the tooltip while the trigger keeps focus.
  await page.keyboard.press("Escape");
  await expect(tooltip).toBeHidden();
});
