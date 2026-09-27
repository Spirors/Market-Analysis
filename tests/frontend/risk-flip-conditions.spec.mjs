// tests/frontend/risk-flip-conditions.spec.mjs
//
// Risk card "What would flip it" block. compute_risk() returns a top-level
// `flip_conditions` list ("what would change the call"); the risk card must
// render it with the same .flip-block markup the AI gauge uses, and must NOT
// render a block (or an empty heading) on the unavailable/error branch.

import { test, expect } from "@playwright/test";
import { installMockDashboard } from "./mock-dashboard.mjs";

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
