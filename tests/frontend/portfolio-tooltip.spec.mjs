// tests/frontend/portfolio-tooltip.spec.mjs
//
// Portfolio card tooltip copy contract.
//
// The portfolio tooltip used to contradict itself about row reordering: it
// claimed ▲/▼ moved rows "in the current view only" while a later clause said
// the order "persists to data/portfolios.json". Only the persistence claim is
// true — onReorder (static/js/portfolio.js) POSTs to
// /api/portfolios/{pid}/holdings/reorder, which writes data/portfolios.json,
// so the moved order survives a reload. This spec pins the corrected copy: the
// order persists, column headers sort, and the ↺ control resets the sort back
// to the manual order.
//
// Uses the shared mock; the card header chrome (and its ⓘ button + tooltip) is
// injected at boot, independent of the mocked payload.

import { test, expect } from "@playwright/test";
import { installMockDashboard } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

async function tooltipText(page, cardId) {
  const infoIcon = page.locator(`[data-card="${cardId}"] .card-info`).first();
  await expect(infoIcon).toBeVisible();
  const tooltipId = await infoIcon.getAttribute("aria-describedby");
  expect(tooltipId).toBeTruthy();
  return page.locator(`#${tooltipId} .tt-body`).textContent();
}

test("portfolio tooltip states reorder persists, not view-only", async ({ page }) => {
  await installMockDashboard(page);
  await page.goto(DASH);
  await page.waitForSelector('[data-card="portfolio"]');

  const text = await tooltipText(page, "portfolio");

  // The manual ▲/▼ order persists to disk.
  expect(text).toContain("persists to data/portfolios.json");
  // The false "current view only" claim must be gone.
  expect(text).not.toContain("current view only");
  // Column headers sort; the ↺ control resets the sort (not the manual order).
  expect(text).toContain("Click column headers to sort");
  expect(text).toContain("resets the sort back to the manual order");
});
