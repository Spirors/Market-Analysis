// tests/frontend/commodities-provenance.spec.mjs
//
// Commodities card foot provenance (audit 05-D/05-E). The "As of" note means
// the daily spot source date when one is known, otherwise the fetch time; a
// source date that is older than the fetch must not read as "as of now".
// The source attribution renders as its own muted line when present.

import { test, expect } from "@playwright/test";
import { installMockDashboard } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

test("commodities foot shows the source date and the attribution line", async ({ page }) => {
  await installMockDashboard(page);
  await page.goto(DASH);
  await page.waitForSelector('[data-card="commodities"] table');

  const notes = page.locator('[data-card="commodities"] .asof-note');
  await expect(notes).toHaveCount(2);
  // Source date when known — and no "ET"/fetch-time wording on that line.
  await expect(notes.nth(0)).toHaveText("As of 2026-08-28 (source date)");
  await expect(notes.nth(1)).toContainText("Minted Metal (mintedmetal.com) — CC BY 4.0");
});

test("commodities foot shows a compact range when source dates differ", async ({ page }) => {
  await installMockDashboard(page, {
    spot: { commodities_map: { "CL=F": { source_date: "2026-08-27" } } },
  });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="commodities"] table');

  await expect(page.locator('[data-card="commodities"] .asof-note').first())
    .toHaveText("As of 2026-08-27–2026-08-28 (source date)");
});

test("commodities foot falls back to the fetch time when no source date exists", async ({ page }) => {
  await installMockDashboard(page, { spot: null });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="commodities"] table');

  const notes = page.locator('[data-card="commodities"] .asof-note');
  await expect(notes).toHaveCount(1);
  await expect(notes.first()).toHaveText(/As of \d{4}-\d{2}-\d{2} \d{2}:\d{2} ET/);
});
