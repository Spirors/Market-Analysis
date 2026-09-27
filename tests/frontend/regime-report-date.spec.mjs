// tests/frontend/regime-report-date.spec.mjs
//
// The regime card's date is the detector report's own generated_at stamp
// (audit 03-B/C/D), NOT the generic refresh vintage. The refresh vintage is
// stamped even when a cached report was served, so it could contradict the
// mtime-based stale banner; the card opts out of it (CARD_VINTAGE_KEY) and
// renders the report stamp instead. The fixture carries vintage.regime on
// purpose, so these tests prove the card ignores it.
//
// Also covers the explicit missing-component-scores fallback (audit 03-E):
// an absent component grid states that in a muted row instead of vanishing.

import { test, expect } from "@playwright/test";
import { installMockDashboard } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

test("regime card shows the detector report stamp and drops the generic vintage note", async ({ page }) => {
  await installMockDashboard(page);
  await page.goto(DASH);
  await page.waitForSelector('[data-card="regime"]');
  const card = page.locator('[data-card="regime"]');

  // The detector's own stamp, rendered verbatim (no zone conversion, no ET).
  await expect(card.locator(".asof-note")).toHaveText("Report generated 2026-08-28 14:30:00");

  // The generic refresh vintage is suppressed even though vintage.regime is
  // present in the fixture — the card renders its own report date instead.
  await expect(card.locator(".vintage-note")).toHaveCount(0);

  // Control: another card in the same fixture still carries its vintage note.
  await expect(page.locator('[data-card="risk"] .vintage-note')).toHaveCount(1);
});

test("regime card renders the amber stale banner and the report stamp together", async ({ page }) => {
  await installMockDashboard(page, { regime: { stale: true, age_days: 2 } });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="regime"]');
  const card = page.locator('[data-card="regime"]');

  // mtime-based staleness, kept as-is: amber, with the age in days.
  const stale = card.locator(".regime-desc", { hasText: "Stale report" });
  await expect(stale).toHaveCount(1);
  await expect(stale).toContainText("(2d old)");
  await expect(stale).toHaveCSS("color", "rgb(185, 134, 11)");

  // ...and the report's own date still renders alongside it.
  await expect(card.locator(".asof-note")).toHaveText("Report generated 2026-08-28 14:30:00");
  await expect(card.locator(".vintage-note")).toHaveCount(0);
});

test("regime card states missing component scores explicitly instead of vanishing", async ({ page }) => {
  // component_scores: null clears the grid (deep-merge cannot empty an object).
  await installMockDashboard(page, { regime: { composite: { component_scores: null } } });
  await page.goto(DASH);
  await page.waitForSelector('[data-card="regime"]');
  const card = page.locator('[data-card="regime"]');

  await expect(card.locator(".regime-grid")).toHaveCount(0);
  const fallback = card.locator(".kv", { hasText: "Component scores" });
  await expect(fallback).toHaveCount(1);
  await expect(fallback.locator("b")).toHaveText("—");
});
