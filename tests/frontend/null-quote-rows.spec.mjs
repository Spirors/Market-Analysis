// tests/frontend/null-quote-rows.spec.mjs
//
// FIX-05-B: an unavailable quote must still render its row, with "—" in the
// missing cells. The canonical symbol/key list drives the rows; nothing is
// silently dropped. Covers the Commodities and Rates cards (the Indices card
// already renders every pair with per-cell dashes).

import { test, expect } from "@playwright/test";
import { installMockDashboard } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

test("commodities: unavailable symbols keep their row and render — cells", async ({ page }) => {
  await installMockDashboard(page);
  await page.goto(DASH);
  await page.waitForSelector('[data-card="commodities"] table');

  // All three canonical groups render, even where every row is unavailable
  // (the "Other" group has no data in the base payload).
  const heads = await page.locator('[data-card="commodities"] .subhead').allTextContents();
  expect(heads).toEqual(["Energy", "Metals", "Other"]);

  // BZ=F (Brent) has neither spot nor futures in the base payload: it used to
  // be dropped entirely; it must now render as a full row of dashes.
  const brent = page.locator('[data-card="commodities"] tbody tr', { hasText: "BZ=F" });
  await expect(brent).toHaveCount(1);
  await expect(brent.locator("td")).toHaveCount(4);
  await expect(brent.locator("td").nth(1)).toHaveText("—");
  await expect(brent.locator("td").nth(2)).toHaveText("—");
  await expect(brent.locator("td").nth(3)).toHaveText("—");

  // A symbol with data still renders normally alongside it.
  const wti = page.locator('[data-card="commodities"] tbody tr', { hasText: "WTI Crude" });
  await expect(wti).toHaveCount(1);
  await expect(wti.locator("td").nth(1)).toHaveText("78.2");
});

test("rates: a null quote keeps its row and renders — cells", async ({ page }) => {
  // The rates payload carries ^TYX with a null quote (one key per canonical
  // rate symbol); the row must survive the missing value.
  await installMockDashboard(page, { market: { rates: { "^TYX": null } } });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="rates"] table');

  // ^TNX + ^FVX from the base payload, plus the null-valued ^TYX.
  const rows = page.locator('[data-card="rates"] tbody tr');
  await expect(rows).toHaveCount(3);

  const tyx = page.locator('[data-card="rates"] tbody tr', { hasText: "^TYX" });
  await expect(tyx).toHaveCount(1);
  await expect(tyx.locator("td").nth(1)).toHaveText("—");
  await expect(tyx.locator("td").nth(2)).toHaveText("—");
});
