// FIX-00-B: a failed global refresh must NOT blank a card body. Failures are
// reported in one header-level status region (#appStatus), which clears on the
// next successful refresh. The dashboard is served from static/index.html with
// /api/* mocked, so the test is deterministic and needs no backend.

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";
const STATUS = "#appStatus";

const SOFT = "Refresh failed — still showing the last successful data.";
const HARD = "Couldn't load data. Try Refresh again.";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("a failed refresh shows the header status and keeps the rendered risk card", async ({ page }) => {
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).toContainText("YELLOW");
  const before = await page.locator("#riskBody").innerText();
  const cardTopBefore = (await page.locator('[data-card="risk"]').boundingBox()).y;

  // The refresh POST now fails (network blip / non-2xx).
  await page.route("**/api/refresh?full=true", (route) =>
    route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) })
  );

  await page.locator("#refreshBtn").click();
  await expect(page.locator("#refreshBtn")).toHaveText("Refresh"); // done spinning

  // (a) The header status region reports the soft failure.
  await expect(page.locator(STATUS)).toHaveText(SOFT);
  await expect(page.locator(STATUS)).toHaveAttribute("role", "status");
  await expect(page.locator(STATUS)).toHaveAttribute("data-kind", "soft");

  // (b) #riskBody keeps exactly its previous render (verdict + vintage stamp).
  expect(await page.locator("#riskBody").innerText()).toBe(before);
  await expect(page.locator('[data-card="risk"] .vintage-note')).toBeVisible();

  // The reserved status row means the message never shifts the page.
  const cardTopAfter = (await page.locator('[data-card="risk"]').boundingBox()).y;
  expect(Math.round(cardTopAfter)).toBe(Math.round(cardTopBefore));
});

test("a subsequent successful refresh clears the header status", async ({ page }) => {
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).toContainText("YELLOW");

  // Fail once.
  await page.route("**/api/refresh?full=true", (route) => route.fulfill({ status: 500 }));
  await page.locator("#refreshBtn").click();
  await expect(page.locator(STATUS)).toHaveText(SOFT);

  // Restore success and refresh again.
  await page.route("**/api/refresh?full=true", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
  );
  await page.locator("#refreshBtn").click();
  await expect(page.locator("#refreshBtn")).toHaveText("Refresh");

  // (c) Status is cleared on success.
  await expect(page.locator(STATUS)).toBeEmpty();
  expect(await page.locator(STATUS).getAttribute("data-kind")).toBeNull();
  await expect(page.locator("#riskBody")).toContainText("YELLOW");
});

test("a dashboard fetch failure after a good load keeps cards and shows the soft status", async ({ page }) => {
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).toContainText("YELLOW");
  const before = await page.locator("#riskBody").innerText();

  // POST succeeds but the dashboard GET fails -> load()'s catch path.
  await page.route("**/api/dashboard", (route) => route.fulfill({ status: 500 }));
  await page.locator("#refreshBtn").click();
  await expect(page.locator("#refreshBtn")).toHaveText("Refresh");

  await expect(page.locator(STATUS)).toHaveText(SOFT);
  expect(await page.locator("#riskBody").innerText()).toBe(before);
});

test("an initial load failure shows the hard status, not a card body", async ({ page }) => {
  // No prior payload exists yet: this is the hard case.
  await page.route("**/api/dashboard", (route) => route.fulfill({ status: 500 }));
  await page.goto(DASH);

  await expect(page.locator(STATUS)).toHaveText(HARD);
  await expect(page.locator(STATUS)).toHaveAttribute("role", "alert");
  await expect(page.locator(STATUS)).toHaveAttribute("data-kind", "hard");

  // The error string never leaks into the risk card.
  await expect(page.locator("#riskBody")).not.toContainText("Couldn't load data");
  await expect(page.locator("#riskBody")).not.toContainText("Failed to load");
});
