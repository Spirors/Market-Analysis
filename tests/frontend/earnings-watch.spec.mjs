// E2E tests for the Earnings watchlist color-tier interaction.
//
// Coverage:
//   - Left-click cycles the star through amber -> bull -> bear -> amber.
//   - Right-click clears the watch entirely.
//   - The row class + star data-color track the tiered state.
//   - Watch state persists across reloads (localStorage).
//   - Legacy `earnWatched` (array) migrates to `earnWatchColors` (amber).
//
// The dashboard is served from static/index.html with /api/* mocked (see
// mock-dashboard.mjs), so the test is deterministic and needs no backend.
//
// Each Playwright test gets a fresh browser context (empty localStorage),
// so no explicit wipe is needed in beforeEach — only the migration test
// seeds the legacy key.

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const DASH = "/static/index.html";

async function loadDashboardWith(page) {
  await mockApi(page);
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading…");
  await expect(page.locator("#earningsBody table tbody tr")).toHaveCount(1);
}

test("left-click cycles the star through amber, bull, bear, amber", async ({ page }) => {
  await loadDashboardWith(page);
  const row = page.locator("#earningsBody table tbody tr").first();
  const star = row.locator(".earn-star");

  await expect(row).not.toHaveClass(/earn-row-/);
  await expect(star).toHaveAttribute("data-color", "");
  await expect(star).toHaveText("☆");

  await star.click();
  await expect(row).toHaveClass(/earn-row-amber/);
  await expect(star).toHaveAttribute("data-color", "amber");
  await expect(star).toHaveText("★");

  await star.click();
  await expect(row).toHaveClass(/earn-row-bull/);
  await expect(star).toHaveAttribute("data-color", "bull");

  await star.click();
  await expect(row).toHaveClass(/earn-row-bear/);
  await expect(star).toHaveAttribute("data-color", "bear");

  await star.click();
  await expect(row).toHaveClass(/earn-row-amber/);
  await expect(star).toHaveAttribute("data-color", "amber");
});

test("right-click clears the watch entirely", async ({ page }) => {
  await loadDashboardWith(page);
  const row = page.locator("#earningsBody table tbody tr").first();
  const star = row.locator(".earn-star");

  await star.click();
  await expect(row).toHaveClass(/earn-row-amber/);

  await star.click({ button: "right" });
  await expect(row).not.toHaveClass(/earn-row-/);
  await expect(star).toHaveAttribute("data-color", "");
  await expect(star).toHaveText("☆");

  // After clearing, the next left-click restarts the cycle at amber.
  await star.click();
  await expect(row).toHaveClass(/earn-row-amber/);
});

test("watch tier persists across reload (localStorage)", async ({ page }) => {
  await loadDashboardWith(page);
  const star = page.locator("#earningsBody .earn-star").first();

  await star.click(); // amber
  await star.click(); // bull

  await page.reload();
  await expect(page.locator("#riskBody")).not.toHaveText("Loading…");

  const row = page.locator("#earningsBody table tbody tr").first();
  await expect(row).toHaveClass(/earn-row-bull/);
  await expect(row.locator(".earn-star")).toHaveAttribute("data-color", "bull");
});

test("legacy earnWatched (array) migrates to earnWatchColors (amber) on first load", async ({ page }) => {
  // Seed the legacy format before the dashboard JS module loads.
  await page.addInitScript(() => {
    try { localStorage.setItem("earnWatched", JSON.stringify(["NVDA"])); } catch (e) {}
  });
  await loadDashboardWith(page);

  const row = page.locator("#earningsBody table tbody tr").first();
  await expect(row).toHaveClass(/earn-row-amber/);
  await expect(row.locator(".earn-star")).toHaveAttribute("data-color", "amber");

  // A subsequent click should advance to bull (proving the migration is a
  // real tiered state, not a stuck "watched" boolean).
  await row.locator(".earn-star").click();
  await expect(row).toHaveClass(/earn-row-bull/);
});
