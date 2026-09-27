// Component test for the reusable tooltip (static/js/tooltip.js).
//
// Exercises the WCAG 2.1 AA contract: ARIA wiring (role="tooltip" +
// aria-describedby), keyboard focus show/hide, Escape dismiss, hover
// show/hide, viewport-edge placement flip, and deps pills.

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const FIXTURE = "/tests/frontend/fixtures/tooltip.html";

function tooltipFor(page, triggerId) {
  // The tooltip id is the trigger's aria-describedby value.
  return page.locator(`#${triggerId}`).evaluate((el) => {
    const id = el.getAttribute("aria-describedby");
    const surface = document.getElementById(id);
    const depsRow = surface ? surface.querySelector(".tt-deps") : null;
    return {
      id,
      role: surface ? surface.getAttribute("role") : null,
      text: surface ? surface.textContent : null,
      placement: surface ? surface.getAttribute("data-placement") : null,
      hidden: surface ? surface.hidden : null,
      deps: surface ? [...surface.querySelectorAll(".tt-dep")].map((p) => p.textContent) : [],
      // AT exposure of the deps/data-source row.
      depsAriaHidden: depsRow ? depsRow.getAttribute("aria-hidden") : null,
      depsRole: depsRow ? depsRow.getAttribute("role") : null,
      depsLabel: depsRow ? (depsRow.querySelector(".tt-dep-label")?.textContent ?? null) : null,
      depsPillRoles: depsRow
        ? [...depsRow.querySelectorAll(".tt-dep")].map((p) => p.getAttribute("role"))
        : [],
    };
  });
}

test.beforeEach(async ({ page }) => {
  await page.goto(FIXTURE);
});

test("ARIA wiring: role=tooltip, aria-describedby, aria-label", async ({ page }) => {
  const top = await tooltipFor(page, "trigTop");
  expect(top.role).toBe("tooltip");
  expect(top.id).toBeTruthy();

  const describedBy = await page.locator("#trigTop").getAttribute("aria-describedby");
  expect(describedBy).toBe(top.id);

  // Explicit ariaLabel lands on the trigger as its accessible name.
  await expect(page.locator("#trigMid")).toHaveAttribute("aria-label", "About the middle trigger");
});

test("hover shows, mouseleave hides", async ({ page }) => {
  await page.hover("#trigMid");
  await expect(page.locator("#tt-2")).toBeVisible();
  expect((await tooltipFor(page, "trigMid")).text).toContain("Middle tooltip body");

  await page.mouse.move(10, 10); // off the trigger and tooltip
  await expect(page.locator("#tt-2")).toBeHidden();
});

test("keyboard focus shows, blur hides", async ({ page }) => {
  await page.locator("#trigMid").focus();
  await expect(page.locator("#tt-2")).toBeVisible();

  await page.locator("#trigTop").focus();
  await expect(page.locator("#tt-2")).toBeHidden();
});

test("Escape dismisses while the trigger has focus", async ({ page }) => {
  await page.locator("#trigMid").focus();
  await expect(page.locator("#tt-2")).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.locator("#tt-2")).toBeHidden();
});

test("placement flips to bottom near the top edge, stays top mid-page", async ({ page }) => {
  // #trigTop sits near the top of the viewport: "top" must flip to "bottom".
  await page.hover("#trigTop");
  await expect(page.locator("#tt-1")).toBeVisible();
  expect((await tooltipFor(page, "trigTop")).placement).toBe("bottom");

  // #trigMid is mid-page: "top" stays on top.
  await page.hover("#trigMid");
  await expect(page.locator("#tt-2")).toBeVisible();
  expect((await tooltipFor(page, "trigMid")).placement).toBe("top");

  // Explicit "bottom" stays below.
  await page.hover("#trigBottom");
  await expect(page.locator("#tt-3")).toBeVisible();
  expect((await tooltipFor(page, "trigBottom")).placement).toBe("bottom");
});

test("deps render as pills inside the tooltip", async ({ page }) => {
  await page.hover("#trigTop");
  const deps = (await tooltipFor(page, "trigTop")).deps;
  expect(deps).toEqual(["breadth", "VIX"]);
});

test("deps/data-source row is exposed and labelled for assistive tech", async ({ page }) => {
  await page.hover("#trigTop");
  const tt = await tooltipFor(page, "trigTop");

  // The regression: the row used to be aria-hidden, hiding the data-source
  // point from AT for every card. It must no longer be hidden.
  expect(tt.depsAriaHidden).toBeNull();

  // It is a structured list of the dependency pills...
  expect(tt.depsRole).toBe("list");
  expect(tt.depsPillRoles).toEqual(["listitem", "listitem"]);

  // ...carrying its explicit "Depends on" label, in meaningful DOM order
  // (label first, then the pills), inside the surface's accessible text that
  // the trigger's aria-describedby resolves to.
  expect(tt.depsLabel).toBe("Depends on");
  expect(tt.text).toContain("Depends on");
  expect(tt.text).toContain("breadth");
  expect(tt.text).toContain("VIX");
});

test("only one tooltip is open at a time", async ({ page }) => {
  await page.hover("#trigTop");
  await expect(page.locator("#tt-1")).toBeVisible();
  await page.hover("#trigMid");
  await expect(page.locator("#tt-2")).toBeVisible();
  await expect(page.locator("#tt-1")).toBeHidden();
});

test("accessibility tree: tooltip role + described-by relationship", async ({ page }) => {
  await page.locator("#trigMid").focus();
  await expect(page.locator("#tt-2")).toBeVisible();

  // Exactly one role=tooltip node is exposed while the tooltip is open.
  const tooltipNodes = page.locator('[role="tooltip"]:visible');
  await expect(tooltipNodes).toHaveCount(1);

  // The focused trigger announces it via aria-describedby -> the tooltip id.
  const describedBy = await page.locator("#trigMid").getAttribute("aria-describedby");
  expect(describedBy).toBe("tt-2");
  await expect(page.locator(`#${describedBy}`)).toHaveAttribute("role", "tooltip");
  await expect(page.locator(`#${describedBy}`)).toContainText("Middle tooltip body");
});

test("fragility sub-card tooltip: info icon, ARIA wiring, keyboard focus", async ({ page }) => {
  await mockApi(page);
  await page.goto("/static/index.html");
  await expect(page.locator("#riskBody")).not.toHaveText("Loading…");

  // The fragility card is revealed by the mock's fragility_flags.
  await expect(page.locator('[data-card="fragility"]')).toBeVisible();

  // Info icon present with a real accessible name.
  const btn = page.locator('[data-card="fragility"] .card-info');
  await expect(btn).toHaveCount(1);
  await expect(btn).toHaveAttribute("aria-label", "About the Fragility flags card");

  // Keyboard focus opens the tooltip with the sub-card copy.
  await btn.focus();
  const describedBy = await btn.getAttribute("aria-describedby");
  expect(describedBy).toBeTruthy();
  const surface = page.locator(`#${describedBy}`);
  await expect(surface).toBeVisible();
  await expect(surface).toHaveAttribute("role", "tooltip");
  await expect(surface).toContainText("Sub-card of risk");
  await expect(surface).toContainText("optimism-side flags");
  await expect(surface.locator(".tt-dep")).toHaveCount(4);

  // Escape dismisses while focus stays on the trigger.
  await page.keyboard.press("Escape");
  await expect(surface).toBeHidden();
});

test("live text provider: Refresh tooltip computes freshness on keyboard focus", async ({ page }) => {
  await mockApi(page);
  await page.goto("/static/index.html");
  await expect(page.locator("#riskBody")).not.toHaveText("Loading…");

  // The old mouseenter-only native title hack is gone: no title attribute.
  const btn = page.locator("#refreshBtn");
  expect(await btn.getAttribute("title")).toBeNull();

  // Keyboard focus alone opens the unified tooltip and lands the live copy.
  await btn.focus();
  const describedBy = await btn.getAttribute("aria-describedby");
  expect(describedBy).toBeTruthy();
  const surface = page.locator(`#${describedBy}`);
  await expect(surface).toBeVisible();
  await expect(surface).toHaveAttribute("role", "tooltip");
  // The provider was re-run at open time, not frozen at attach time.
  await expect(surface).toContainText("Last refresh");
  await expect(surface).toContainText("Next refresh");
});