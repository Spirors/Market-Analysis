// tests/frontend/earnings.spec.mjs
// Regression coverage for the Earnings watchlist after the tickerTable.js
// refactor. Exercises the real column-controls UI (Columns dropdown,
// checkbox toggle, ↑ reorder) because Earnings uses the shared
// tickerTable.js framework.

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const DASH = "/static/index.html";

async function loadDashboardWith(page) {
  await mockApi(page);
  // Mock the column prefs endpoint (tickerTable.js PUTs here on toggle/reorder)
  await page.route("**/api/portfolios/columns/**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
  );
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading…");
  await expect(page.locator("#earningsBody table tbody tr")).toHaveCount(1);
}

test("default columns are visible", async ({ page }) => {
  await loadDashboardWith(page);
  // CSS text-transform:uppercase makes innerText return uppercase strings
  const headers = await page.locator("#earningsBody thead th").allInnerTexts();
  const lower = headers.map((h) => h.toLowerCase());
  expect(lower).toContain("ticker");
  expect(lower).toContain("daily %");
  expect(lower).toContain("7-day %");
  expect(lower).toContain("ai rec");
});

test("toggling a column hides its body cells", async ({ page }) => {
  await loadDashboardWith(page);
  const initialCount = await page.locator("#earningsBody thead th").count();
  await page.locator("#earnControls .tt-cols-btn").click();
  await page.locator("input[data-col='forward_pe']").click();
  const newCount = await page.locator("#earningsBody thead th").count();
  expect(newCount).toBeLessThan(initialCount);
});

test("column reorder moves left in the table", async ({ page }) => {
  await loadDashboardWith(page);
  const before = await page.locator("#earningsBody thead th").nth(1).innerText();
  await page.locator("#earnControls .tt-cols-btn").click();
  // Use a specific data-key rather than .first() — the first button
  // targets _star (index 0, can't move left). "date" is index 2, so
  // clicking its ↑ swaps it with symbol (index 1).
  await page.locator("button.tt-col-up[data-key='date']").click();
  const after = await page.locator("#earningsBody thead th").nth(1).innerText();
  expect(after).not.toBe(before);
});

test("star click applies earn-row-amber class and a tinted row background", async ({ page }) => {
  await loadDashboardWith(page);
  const row = page.locator("#earningsBody table tbody tr").first();
  const star = row.locator(".earn-star");

  // Unwatched: no row tint
  await expect(row).not.toHaveClass(/earn-row-/);
  const beforeBg = await row.locator("td").first().evaluate((td) => getComputedStyle(td).backgroundColor);
  expect(beforeBg).toBe("rgba(0, 0, 0, 0)");

  // Cycle once → amber: row class + tinted background must appear
  await star.click();
  await expect(row).toHaveClass(/earn-row-amber/);
  await expect(star).toHaveAttribute("data-color", "amber");
  const afterBg = await row.locator("td").first().evaluate((td) => getComputedStyle(td).backgroundColor);
  expect(afterBg).not.toBe("rgba(0, 0, 0, 0)");
});
