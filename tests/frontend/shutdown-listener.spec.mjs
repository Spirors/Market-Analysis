// Component test for the shutdown listener (static/js/shutdown-listener.js).
//
// Guards the regression where a visibilitychange-timeout beacon killed the
// server after 3 s of the tab being backgrounded — every tab switch tore
// down the process while the user was still using the app.

import { test, expect } from "@playwright/test";

const FIXTURE = "/tests/frontend/fixtures/shutdown-listener.html";

test.beforeEach(async ({ page }) => {
  // Stub the beacon so we can count sends without hitting the network.
  await page.addInitScript(() => {
    // @ts-ignore
    window.__shutdownSends = 0;
    const realBeacon = navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon = function (url) {
      if (typeof url === "string" && url.indexOf("/api/shutdown") !== -1) {
        // @ts-ignore
        window.__shutdownSends += 1;
        return true;
      }
      return realBeacon(url);
    };
  });
  await page.goto(FIXTURE);
});

test("visibility-hidden does NOT beacon /api/shutdown", async ({ page }) => {
  // Simulate the tab going to the background (visibilitychange -> hidden)
  // and wait past the old 3 s timeout. The listener must not fire.
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.waitForTimeout(3500);
  const sends = await page.evaluate(() => window.__shutdownSends);
  expect(sends).toBe(0);
});

test("pagehide beacons /api/shutdown (and only once)", async ({ page }) => {
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pagehide"));
  });
  const sends = await page.evaluate(() => window.__shutdownSends);
  expect(sends).toBe(1);

  // A second pagehide is a no-op (fired guard).
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pagehide"));
  });
  const sends2 = await page.evaluate(() => window.__shutdownSends);
  expect(sends2).toBe(1);
});

test("beforeunload beacons /api/shutdown", async ({ page }) => {
  await page.evaluate(() => {
    window.dispatchEvent(new Event("beforeunload"));
  });
  const sends = await page.evaluate(() => window.__shutdownSends);
  expect(sends).toBe(1);
});

test("visibility-hidden after a real pagehide still does not re-beacon", async ({ page }) => {
  // Real close -> beacon. Then the user reopens / the page revisits a
  // backgrounded state — no second beacon from the visibility listener.
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pagehide"));
  });
  expect(await page.evaluate(() => window.__shutdownSends)).toBe(1);

  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.waitForTimeout(3500);
  expect(await page.evaluate(() => window.__shutdownSends)).toBe(1);
});
