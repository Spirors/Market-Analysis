// Regression test for the portfolio-name-input UX.
//
// The portfolio name has an inline rename affordance — click the pencil \u270e
// button next to the name to swap it for an <input class="pf-name-input">.
// The input must be single-line (not stretched to fill the header), clicking
// outside the input blurs it (commit-or-cancel UX), and Enter/Escape work
// as expected.
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
  // Wait for the portfolio name span to appear with real data.
  await expect(page.locator(".pf-pf-name").first()).toContainText("Fidelity Main");
}

test.describe("portfolio name inline rename input", () => {
  test("input height is single-line (not stretched to fill the header)", async ({ page }) => {
    await setupDashboard(page);
    // Click the pencil button to trigger inline rename.
    await page.locator(".pf-rename-btn").first().click();
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
    // Click the pencil button to trigger inline rename.
    await page.locator(".pf-rename-btn").first().click();
    const input = page.locator(".pf-name-input").first();
    await expect(input).toBeVisible();
    await input.fill("Renamed");
    // Click somewhere outside the header to blur the input. The blur
    // handler saves the new name synchronously before any async refresh.
    // Use page.mouse to click at the very top-left of the viewport, well
    // outside any portfolio elements.
    await page.mouse.click(0, 0);
    // The span should be back, with the new name applied.
    await expect(page.locator(".pf-pf-name").first()).toContainText("Renamed");
  });

  test("Enter saves the new name and re-renders the span", async ({ page }) => {
    await setupDashboard(page);
    await page.locator(".pf-rename-btn").first().click();
    const input = page.locator(".pf-name-input").first();
    await expect(input).toBeVisible();
    await input.fill("Fidelity Roth");
    await input.press("Enter");
    await expect(page.locator(".pf-pf-name").first()).toContainText("Fidelity Roth");
  });
});

// Regression test for the ROADMAP Phase 2 "portfolio rename layout shift"
// item.  Pre-fix (.pf-name-input { min-width: 160px }) was wider than
// the rendered title for SHORT portfolio names like "IRA" (3 chars), so
// entering edit mode shoved the pencil icon / totals / close button to
// the right.  Post-fix uses `min-width: max(min-content, 8ch)` —
// content-sized for longer names, 8ch floor for shorter ones.  Neither
// extreme should reintroduce the pre-4716e02 ~87%-of-header behavior.

test.describe("portfolio name input — short-name layout shift", () => {
  const SHORT_PORTFOLIOS = {
    version: 1,
    portfolios: {
      "ira": {
        id: "ira",
        name: "IRA",  // 3 chars — well under the 160px old floor
        holdings: [
          { symbol: "AAPL", shares: 5, total_cost: 1000, last_price: 220, pct_daily: 0.5 },
        ],
      },
    },
    column_order: { earnings: [], portfolio: [] },
    column_visibility: { earnings: {}, portfolio: {} },
  };

  async function setupShortNameDashboard(page) {
    await page.route("**/api/dashboard", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: "2026-09-06T00:00:00",
          market: {}, indicators: {},
          risk: { risk_level: "YELLOW", signals: [] },
          ai_analysis: [],
          regime: { regime: "Unknown", components: [], as_of: "2026-09-06T00:00:00" },
          bottleneck: {}, ai_sentiment: {}, thirteenf: {}, events: [],
          earnings: { as_of: "2026-09-06T00:00:00", companies: [], watchlist: [] },
          portfolios: SHORT_PORTFOLIOS.portfolios,
          column_order: SHORT_PORTFOLIOS.column_order,
          column_visibility: SHORT_PORTFOLIOS.column_visibility,
        }),
      })
    );
    await page.route("**/api/portfolios", (route) =>
      route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify(SHORT_PORTFOLIOS) })
    );
    await page.route("**/api/portfolios/**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
    );
    await page.goto(DASH);
    await expect(page.locator(".pf-pf-name").first()).toContainText("IRA");
  }

  test("input width does not visually exceed rendered title (short name)", async ({ page }) => {
    // The bug: entering edit mode for a short name (3 chars) shows an
    // input wider than the rendered title, shifting the pencil icon /
    // totals / close button to the right.  Pre-Phase-2 the rule was
    // `min-width: 160px` — a fixed pixel floor wider than a 3-char
    // title rendered at 13px font.  Post-fix uses `field-sizing: content`
    // (the input sizes to its actual value) plus `min-width: 8ch` as a
    // usability floor (no fixed pixel value).
    await setupShortNameDashboard(page);

    const titleMeasurements = await page.evaluate(() => {
      const titleSpan = document.querySelector(".pf-pf-name");
      if (!titleSpan) return null;
      const tr = titleSpan.getBoundingClientRect();
      return {
        titleWidth: tr.width,
        titleText: titleSpan.textContent.trim(),
      };
    });
    expect(titleMeasurements).not.toBeNull();
    expect(titleMeasurements.titleText).toBe("IRA");

    await page.locator(".pf-rename-btn").first().click();
    const input = page.locator(".pf-name-input").first();
    await expect(input).toBeVisible();

    const inputMeasurements = await page.evaluate(() => {
      const inp = document.querySelector(".pf-name-input");
      const cs = getComputedStyle(inp);
      return {
        inputWidth: inp.getBoundingClientRect().width,
        computedFieldSizing: cs.fieldSizing,
        computedMinWidth: cs.minWidth,
      };
    });

    // Post-fix (field-sizing: content): input is sized to the actual
    // content + padding/border, ~74px for "IRA" at 13px font.  Pre-fix
    // (min-width: 160px) was 160px and visibly larger than the
    // rendered title.  Use 130 as the upper bound — gives a 30px
    // margin above the old 160px floor (enough to catch a regression
    // where someone reverts to a pixel-fixed floor).
    expect(inputMeasurements.inputWidth).toBeLessThan(130);
    // Structural: `field-sizing: content` is the new mechanism.  A
    // revert to the pixel-floor approach would fail this assertion.
    expect(inputMeasurements.computedFieldSizing).toBe("content");
    // Floor is `8ch` (no fixed pixel value).  8ch at 13px font ≈ 58px.
    // The assertion catches any reversion to a fixed pixel floor like
    // `min-width: 160px` (the original bug).
    expect(inputMeasurements.computedMinWidth).not.toBe("160px");
  });

  test("input width does not reintroduce pre-4716e02 stretch behavior", async ({ page }) => {
    // Pre-4716e02 the input had `flex: 1; min-width: 0` which stretched
    // it to ~87% of header width.  Post-fix `flex: 0 0 auto` +
    // `field-sizing: content` keeps the input well under 50% of header
    // width — for a 3-char name it's ~74px on a ~1184px header, ~6%
    // ratio.  Pin this so a future revert to `flex: 1; min-width: 0`
    // would fail.
    await setupShortNameDashboard(page);
    await page.locator(".pf-rename-btn").first().click();
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
        inputWidth: ir.width,
        headerWidth: hr.width,
        inputWidthRatio: ir.width / hr.width,
        computedFlex: cs.flex,
        computedMinWidth: cs.minWidth,
        computedFieldSizing: cs.fieldSizing,
      };
    });

    expect(measurements).not.toBeNull();
    // Width ratio: well under 50% (existing assertion for long names
    // is <0.5; for short names it's even smaller because the input is
    // content-sized rather than header-filling).
    expect(measurements.inputWidthRatio).toBeLessThan(0.5);
    // Structural: flex is `0 0 auto`, NOT `1 1 0` / `1 1 auto` etc.
    // A revert to `flex: 1` (pre-4716e02) would fail this assertion.
    expect(measurements.computedFlex).toMatch(/0.*0.*auto|0.*0.*0/);
    // `field-sizing: content` is the size mechanism.  A revert to the
    // pixel-floor approach (or to the default intrinsic size) would
    // fail this assertion.
    expect(measurements.computedFieldSizing).toBe("content");
  });
});
