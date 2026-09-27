// Regression: the confirm-modal focus trap shipped in FIX-00-E (commit 6b1ae3b)
// with no spec. The modal backs the destructive timeline actions (delete event,
// hide source) — `openConfirmModal` in static/js/events.js records the invoking
// control, focuses Cancel, and `closeConfirmModal` restores focus. A keydown
// listener traps Tab / Shift+Tab inside `.confirm-modal`.
//
// The dashboard is served from static/index.html with /api/* mocked (see
// mock-dashboard.mjs), so this is deterministic and needs no backend.
//
// NOTE on structure: the dialog role lives on the inner `.confirm-modal`
// element, NOT on `#confirmOverlay` itself. `#confirmOverlay` is the
// (inert-when-closed) backdrop that *contains* the dialog, so the assertions
// below resolve the dialog via `#confirmOverlay [role="dialog"]`.

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

// The destructive action wired to openConfirmModal: the per-event "✕ Remove"
// button (`#newsBody .ev-del`, rendered by events.js rowTemplate). The dialog
// title it opens is fixed by the delete branch of the click handler.
const DELETE_BUTTON = "#newsBody .ev-del";
const DIALOG_TITLE = "Delete event from timeline?";
const OVERLAY = "#confirmOverlay";
const CANCEL = "#confirmCancel";
const CONFIRM = "#confirmOk";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

// Open the delete-event dialog through the real click handler, after focusing
// the invoking button so `document.activeElement` at open time is that button
// (real browsers focus a clicked <button>; the explicit focus removes any
// ambiguity and lets us assert focus restoration deterministically).
async function openDeleteModal(page) {
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading…");
  const del = page.locator(DELETE_BUTTON).first();
  await expect(del).toBeVisible();
  await del.focus();
  await del.click();

  await expect(page.locator(OVERLAY)).toBeVisible();
  // The implementation focuses Cancel (the safe option) on open.
  await expect(page.locator(CANCEL)).toBeFocused();
  return del;
}

async function focusedId(page) {
  return page.evaluate(() => (document.activeElement && document.activeElement.id) || null);
}

async function focusIsInsideDialog(page) {
  return page.evaluate(() => {
    const a = document.activeElement;
    return !!(a && a.closest && a.closest("#confirmOverlay"));
  });
}

test.describe("Confirm modal focus trap", () => {
  test("opening a destructive action moves focus into the dialog (Cancel)", async ({ page }) => {
    await openDeleteModal(page);

    // Focus landed on Cancel and, critically, inside the overlay — not on the
    // page behind it.
    await expect(page.locator(CANCEL)).toBeFocused();
    expect(await focusIsInsideDialog(page)).toBe(true);
    expect(await focusedId(page)).toBe("confirmCancel");

    // The dialog is honest about what it is warning about.
    await expect(page.locator("#confirmTitle")).toHaveText(DIALOG_TITLE);
  });

  test("Tab and Shift+Tab cycle within the dialog and never reach the page behind", async ({ page }) => {
    await openDeleteModal(page);

    // There IS focusable content behind the overlay; the trap must keep us off
    // it. `#refreshBtn` is the global header control.
    await expect(page.locator("#refreshBtn")).toBeVisible();

    const seen = new Set();

    // Several forward Tabs: every landing spot must stay inside the dialog.
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press("Tab");
      expect(await focusIsInsideDialog(page)).toBe(true);
      const id = await focusedId(page);
      expect([ "confirmCancel", "confirmOk" ]).toContain(id);
      seen.add(id);
      await expect(page.locator("#refreshBtn")).not.toBeFocused();
    }
    // Cycling must actually visit both controls, not sit on one.
    expect(seen.has("confirmCancel")).toBe(true);
    expect(seen.has("confirmOk")).toBe(true);

    // And backwards, too.
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press("Shift+Tab");
      expect(await focusIsInsideDialog(page)).toBe(true);
      const id = await focusedId(page);
      expect([ "confirmCancel", "confirmOk" ]).toContain(id);
      await expect(page.locator("#refreshBtn")).not.toBeFocused();
    }
  });

  test("Cancel restores focus to the invoking control", async ({ page }) => {
    const del = await openDeleteModal(page);

    await page.locator(CANCEL).click();

    await expect(page.locator(OVERLAY)).toBeHidden();
    await expect(del).toBeFocused();
  });

  test("Escape restores focus to the invoking control", async ({ page }) => {
    const del = await openDeleteModal(page);

    await page.keyboard.press("Escape");

    await expect(page.locator(OVERLAY)).toBeHidden();
    await expect(del).toBeFocused();
  });

  test("the overlay exposes a labelled, modal dialog", async ({ page }) => {
    await openDeleteModal(page);

    // The overlay contains the dialog (role lives on the inner `.confirm-modal`).
    const dialog = page.locator(`${OVERLAY} [role="dialog"]`);
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute("aria-modal", "true");
    await expect(dialog).toHaveAttribute("aria-labelledby", "confirmTitle");

    // Honest accessible name: the dialog's name is the actual warning title,
    // not an empty string or the generic word "dialog".
    await expect(page.getByRole("dialog")).toHaveAccessibleName(DIALOG_TITLE);
    const name = await page.getByRole("dialog").evaluate((el) => el.textContent || "");
    expect(name).toContain(DIALOG_TITLE);
  });
});
