// tests/frontend/risk-flip-conditions.spec.mjs
//
// Risk card "What would flip it" block. compute_risk() returns a top-level
// `flip_conditions` list ("what would change the call"); the risk card must
// render it with the same .flip-block markup the AI gauge uses, and must NOT
// render a block (or an empty heading) on the unavailable/error branch.

import { test, expect } from "@playwright/test";
import { installMockDashboard, mockApi, basePayload } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

test("risk card renders flip conditions in a .flip-block when the payload is healthy", async ({ page }) => {
  await installMockDashboard(page, {
    risk: {
      flip_conditions: [
        "Any 3+ signals flipping tone within a month",
        "Drawdown deepening past 15%",
      ],
    },
  });
  await page.goto(DASH);
  const block = page.locator('[data-card="risk"] #riskBody .flip-block');
  await expect(block).toBeVisible();
  await expect(block).toContainText("What would flip it:");
  await expect(block.locator("li")).toHaveCount(2);
  await expect(block).toContainText("Any 3+ signals flipping tone within a month");
  await expect(block).toContainText("Drawdown deepening past 15%");
});

test("risk card renders no flip block on the unavailable/error branch", async ({ page }) => {
  await installMockDashboard(page, { risk: { error: "insufficient data" } });
  await page.goto(DASH);
  const body = page.locator('[data-card="risk"] #riskBody');
  await expect(body).toContainText("Risk engine unavailable.");
  await expect(body.locator(".flip-block")).toHaveCount(0);
});

// Probe 01-F7 (live, isolated app with every history unavailable): the risk
// payload degrades to `{error: "insufficient data"}` with `coverage.risk =
// {ok:0,total:7}` and no GREEN is fabricated. The risk card must show its
// unavailable state, and — the stale-content trap — a fragility sub-card that
// rendered on the previous healthy run must not keep its old flag rows.
test("a later risk error clears the previous run's fragility sub-card", async ({ page }) => {
  // First load is healthy: basePayload() carries one fragility flag, so the
  // sub-card is visible with a real flag row.
  await mockApi(page);
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).toContainText("YELLOW");
  const fragility = page.locator('[data-card="fragility"]');
  await expect(fragility).toBeVisible();
  await expect(page.locator("#fragilityList .flag-row")).toHaveCount(1);

  // The next dashboard fetch reports the risk engine unavailable while the
  // rest of the payload stays healthy — the exact probe shape, including the
  // zero-coverage count (0 of 7).
  const errPayload = basePayload();
  errPayload.risk = { error: "insufficient data" };
  errPayload.coverage = { risk: { ok: 0, total: 7 } };
  await page.route("**/api/dashboard", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(errPayload) })
  );

  await page.locator("#refreshBtn").click();
  await expect(page.locator("#refreshBtn")).toHaveText("Refresh");

  // (a) The risk card renders the unavailable state — no stale verdict.
  await expect(page.locator("#riskBody")).toHaveText("Risk engine unavailable.");
  await expect(page.locator("#riskBody .big")).toHaveCount(0);
  await expect(page.locator("#riskBody")).not.toContainText("YELLOW");

  // (b) The fragility sub-card does NOT persist the previous run's flags.
  await expect(fragility).toBeHidden();
  await expect(page.locator("#fragilityList .flag-row")).toHaveCount(0);
  await expect(page.locator("#fragilityList")).toBeEmpty();

  // (c) The probe's coverage shape is the one rendered (0 of 7 available).
  await expect(page.locator('[data-card="risk"] .cov-badge')).toHaveText("0/7");
});
