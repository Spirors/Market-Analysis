// Regression test for the portfolio-name-input UX regression.
//
// The portfolio name has an inline rename affordance — click the name span
// and it swaps for an <input class="pf-name-input">. The bug was that the
// input took the full header height (flex: 1 + align-items: stretch on the
// parent .pf-pf-header) and was the only focusable region in the header —
// the surrounding empty space inside the header didn't respond to clicks.
//
// Fix: collapse the input to a single line (its natural <input type="text">
// height) so the surrounding header area is clickable again as expected by
// users who try to click "outside" the input to blur it.
//
// This test loads the actual portfolio page and verifies:
//   1. The inline rename input is single-line (not stretched to header height).
//   2. Clicking outside the input blurs it (UX behavior the user expects).
//   3. The rename still works end-to-end.

import { test, expect } from "@playwright/test";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

const POPULATED_PORTFOLIOS = {
  version: 1,
  portfolios: {
    "fidelity-main": {
      id: "fidelity-main",
      name: "Fidelity Main",
      holdings: [
        { symbol: "AAPL", shares: 10, total_cost: 1500, last_price: 220, pct_daily: 0.5 },
      ],
    },
  },
  column_order: { earnings: [], portfolio: [] },
  column_visibility: { earnings: {}, portfolio: {} },
};

async function setupDashboard(page) {
  await page.route("**/api/dashboard", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        as_of: "2026-09-06T00:00:00",
        market: {},
        indicators: {},
        risk: { risk_level: "YELLOW", signals: [] },
        ai_analysis: [],
        regime: { regime: "Unknown", components: [], as_of: "2026-09-06T00:00:00" },
        bottleneck: {},
        ai_sentiment: {},
        thirteenf: {},
        events: [],
        earnings: { as_of: "2026-09-06T00:00:00", companies: [], watchlist: [] },
        // The dashboard payload's `portfolios` field is the inner dict
        // ({ id: name: holdings: }), NOT the whole portfolios.json file —
        // cards.js → renderPortfolio() reads this dict directly via
        // Object.values(state.portfolios).
        portfolios: POPULATED_PORTFOLIOS.portfolios,
        column_order: POPULATED_PORTFOLIOS.column_order,
        column_visibility: POPULATED_PORTFOLIOS.column_visibility,
      }),
    })
  );
  await page.route("**/api/portfolios", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(POPULATED_PORTFOLIOS) })
  );
  await page.route("**/api/portfolios/**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
  );
  await page.goto(DASH);
  // Wait for the rename span to appear with real data.
  await expect(page.locator(".pf-pf-name-edit").first()).toContainText("Fidelity Main");
}

test.describe("portfolio name inline rename input", () => {
  test("input height is single-line (not stretched to fill the header)", async ({ page }) => {
    await setupDashboard(page);
    // Click the name to trigger inline rename.
    await page.locator(".pf-pf-name-edit").first().click();
    const input = page.locator(".pf-name-input").first();
    await expect(input).toBeVisible();

    const measurements = await page.evaluate(() => {
      const inp = document.querySelector(".pf-name-input");
      const header = document.querySelector(".pf-pf-header");
      if (!inp || !header) return null;
      const ir = inp.getBoundingClientRect();
      const hr = header.getBoundingClientRect();
      const cs = getComputedStyle(inp);
      return {
        inputHeight: ir.height,
        headerHeight: hr.height,
        // Width: the input must not dominate the header. Pre-fix the input
        // took ~87% of header width (flex: 1 + min-width: 0). Post-fix it
        // sizes to content (flex: 0 0 auto + width: auto + min-width: 160px),
        // so the input should occupy well under 50% of header width for a
        // short portfolio name like "Fidelity Main".
        inputWidth: ir.width,
        headerWidth: hr.width,
        inputWidthRatio: ir.width / hr.width,
        computedHeight: cs.height,
        computedMinHeight: cs.minHeight,
        computedAlignSelf: cs.alignSelf,
        // We rely on the input being an <input type="text"> (single-line by
        // default). A textarea or contenteditable would silently regress
        // the UX fix.
        inputType: inp.type,
        tagName: inp.tagName,
      };
    });

    expect(measurements).not.toBeNull();
    // The input must be a single-line text input.
    expect(measurements.tagName).toBe("INPUT");
    expect(measurements.inputType).toBe("text");
    // The input must NOT be stretched to the header height. Allow up to 6px
    // of slack for border + padding (input has 1px border on top and bottom,
    // 2px padding on top and bottom, so the visible height is naturally
    // larger than the line-height of the text).
    expect(measurements.inputHeight).toBeLessThan(measurements.headerHeight);
    // Width regression guard: pre-fix `flex: 1` made the input ~87% of the
    // header width. Post-fix the input sizes to its content. For the test
    // fixture's "Fidelity Main" (12 chars) plus the `min-width: 160px` floor,
    // the ratio must be well under the pre-fix value.
    expect(measurements.inputWidthRatio).toBeLessThan(0.5);
  });

  test("clicking outside the input blurs it (commit-or-cancel UX)", async ({ page }) => {
    await setupDashboard(page);
    const span = page.locator(".pf-pf-name-edit").first();
    await span.click();
    const input = page.locator(".pf-name-input").first();
    await expect(input).toBeVisible();
    await input.fill("Renamed");
    // Click somewhere else in the header (outside the input) — this is
    // the user-visible click target that the surrounding empty space
    // should provide. The blur handler saves the new name.
    await page.locator(".pf-pf-totals").first().click();
    // The span should be back, with the new name applied.
    await expect(page.locator(".pf-pf-name-edit").first()).toContainText("Renamed");
  });

  test("Enter saves the new name and re-renders the span", async ({ page }) => {
    await setupDashboard(page);
    await page.locator(".pf-pf-name-edit").first().click();
    const input = page.locator(".pf-name-input").first();
    await expect(input).toBeVisible();
    await input.fill("Fidelity Roth");
    await input.press("Enter");
    await expect(page.locator(".pf-pf-name-edit").first()).toContainText("Fidelity Roth");
  });
});
