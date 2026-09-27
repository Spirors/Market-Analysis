// tests/frontend/rates-yield-labels.spec.mjs
//
// Rates card unit labelling contract.
//
// The Rates card renders percent yields (e.g. ^TNX: 4.32 = 4.32%), so its
// value column must be labelled as a yield, not the generic "Price" that the
// shared quotesTable helper defaults to. Index and commodity cards render
// price levels through their own renderers and must keep their existing
// headers untouched.

import { test, expect } from "@playwright/test";
import { installMockDashboard } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

test("rates table labels its value column as a percent yield", async ({ page }) => {
  await installMockDashboard(page);
  await page.goto(DASH);
  await page.waitForSelector('[data-card="rates"] table');

  const headers = await page
    .locator('[data-card="rates"] table thead th')
    .allTextContents();
  expect(headers).toContain("Yield (%)");
  expect(headers).not.toContain("Price");

  // Value formatting is unchanged (fmtPrice): the unit lives in the header.
  const firstCell = page.locator('[data-card="rates"] table tbody tr').first().locator("td").nth(1);
  await expect(firstCell).toHaveText("4.32");
});

test("indices table keeps its own (non-yield) headers", async ({ page }) => {
  await installMockDashboard(page);
  await page.goto(DASH);
  await page.waitForSelector('[data-card="indices"] table');

  const headers = await page
    .locator('[data-card="indices"] table thead th')
    .allTextContents();
  expect(headers).toEqual(["Index", "Spot", "Spot %", "Futures", "Fut %"]);
  expect(headers).not.toContain("Yield (%)");
});
