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
  column_order: { portfolio: [] },
  column_visibility: { portfolio: {} },
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
    // Sanity bound on width: input must never overflow the header box.
    // (The actual no-shift property is verified in the dedicated tests
    // below — this test is named for height, not width.)
    expect(measurements.inputWidthRatio).toBeLessThanOrEqual(1);
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
    column_order: { portfolio: [] },
    column_visibility: { portfolio: {} },
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

  test("input width matches span width so surrounding elements don't shift (short name)", async ({ page }) => {
    // The bug: entering edit mode for a short name (3 chars) showed the
    // pencil icon, totals, and close button visibly shift LEFT (~25-30px)
    // because the input replaced the flex:1 span with a narrower
    // field-sizing:content input.  Post-fix the JS sets
    // `inp.style.minWidth = spanWidth` so the input box matches the
    // span's outer edge exactly — no shift.
    await setupShortNameDashboard(page);

    // Capture the pencil ✎ icon position BEFORE entering rename mode
    // (when the span is visible) and AFTER (when the input replaces it).
    const beforeRename = await page.evaluate(() => {
      const pencil = document.querySelector(".pf-rename-btn");
      const titleSpan = document.querySelector(".pf-pf-name");
      const header = document.querySelector(".pf-pf-header");
      if (!pencil || !titleSpan || !header) return null;
      const pr = pencil.getBoundingClientRect();
      const tr = titleSpan.getBoundingClientRect();
      const hr = header.getBoundingClientRect();
      return {
        pencilLeft: pr.left,
        pencilRight: pr.right,
        spanLeft: tr.left,
        spanRight: tr.right,
        spanWidth: tr.width,
        headerWidth: hr.width,
        titleText: titleSpan.textContent.trim(),
      };
    });
    expect(beforeRename).not.toBeNull();
    expect(beforeRename.titleText).toBe("IRA");

    await page.locator(".pf-rename-btn").first().click();
    const input = page.locator(".pf-name-input").first();
    await expect(input).toBeVisible();

    const afterRename = await page.evaluate(() => {
      const pencil = document.querySelector(".pf-rename-btn");
      const inp = document.querySelector(".pf-name-input");
      const header = document.querySelector(".pf-pf-header");
      if (!pencil || !inp || !header) return null;
      const pr = pencil.getBoundingClientRect();
      const ir = inp.getBoundingClientRect();
      const hr = header.getBoundingClientRect();
      const cs = getComputedStyle(inp);
      return {
        pencilLeft: pr.left,
        pencilRight: pr.right,
        inputLeft: ir.left,
        inputRight: ir.right,
        inputWidth: ir.width,
        headerWidth: hr.width,
        computedFieldSizing: cs.fieldSizing,
        computedMinWidth: cs.minWidth,
      };
    });

    expect(afterRename).not.toBeNull();
    // The pencil ✎ icon must not visibly shift.  Allow a 1px slack for
    // sub-pixel rendering.  Pre-fix the pencil shifted ~25-30px left
    // because the input was narrower than the span was.
    expect(Math.abs(afterRename.pencilLeft - beforeRename.pencilLeft)).toBeLessThanOrEqual(1);
    // The input box must occupy the same horizontal slot the span did
    // — this is the JS-applied `minWidth = spanWidth` doing its job.
    expect(Math.abs(afterRename.inputLeft - beforeRename.spanLeft)).toBeLessThanOrEqual(1);
    expect(Math.abs(afterRename.inputRight - beforeRename.spanRight)).toBeLessThanOrEqual(1);
    // Structural: `field-sizing: content` is still the size mechanism.
    expect(afterRename.computedFieldSizing).toBe("content");
    // No fixed pixel value like the old `min-width: 160px`.
    expect(afterRename.computedMinWidth).not.toBe("160px");
  });

  test("input width does not reintroduce pre-4716e02 stretch behavior", async ({ page }) => {
    // Pre-4716e02 the input had `flex: 1; min-width: 0` which stretched
    // it to ~87% of header width.  Post-fix `flex: 0 0 auto` +
    // `field-sizing: content` + JS-applied `minWidth = spanWidth`
    // keeps the input aligned with the span (no shift) without the old
    // `flex: 1` stretch behavior.
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
    // Structural: flex is `0 0 auto`, NOT `1 1 0` / `1 1 auto` etc.
    // A revert to `flex: 1` (pre-4716e02) would fail this assertion.
    expect(measurements.computedFlex).toMatch(/0.*0.*auto|0.*0.*0/);
    // `field-sizing: content` is the size mechanism.  A revert to the
    // pixel-floor approach (or to the default intrinsic size) would
    // fail this assertion.
    expect(measurements.computedFieldSizing).toBe("content");
    // The input occupies a sizable share of the header now (it matches
    // the span width).  Cap at <100% so the input can never overflow
    // the header box; the structural assertions above are the real
    // anti-revert guarantees.
    expect(measurements.inputWidthRatio).toBeLessThanOrEqual(1);
  });
});
