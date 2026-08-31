// Component test for the reusable tooltip (static/js/tooltip.js).
//
// Exercises the WCAG 2.1 AA contract: ARIA wiring (role="tooltip" +
// aria-describedby), keyboard focus show/hide, Escape dismiss, hover
// show/hide, viewport-edge placement flip, and deps pills.

import { test, expect } from "@playwright/test";

const FIXTURE = "/tests/frontend/fixtures/tooltip.html";

function tooltipFor(page, triggerId) {
  // The tooltip id is the trigger's aria-describedby value.
  return page.locator(`#${triggerId}`).evaluate((el) => {
    const id = el.getAttribute("aria-describedby");
    const surface = document.getElementById(id);
    return {
      id,
      role: surface ? surface.getAttribute("role") : null,
      text: surface ? surface.textContent : null,
      placement: surface ? surface.getAttribute("data-placement") : null,
      hidden: surface ? surface.hidden : null,
      deps: surface ? [...surface.querySelectorAll(".tt-dep")].map((p) => p.textContent) : [],
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