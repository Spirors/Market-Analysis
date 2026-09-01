// Component test for the shutdown listener (static/js/shutdown-listener.js).
//
// Guards the regression where a visibilitychange-timeout beacon killed the
// server after 3 s of the tab being backgrounded — every tab switch tore
// down the process while the user was still using the app. Also guards
// the F5-reload contract: a page reload must NOT kill the server; the
// next page's pageshow must send /api/cancel-shutdown to abort the
// pending exit.

import { test, expect } from "@playwright/test";

const FIXTURE = "/tests/frontend/fixtures/shutdown-listener.html";

test.beforeEach(async ({ page }) => {
  // Stub the beacon so we can count sends without hitting the network.
  await page.addInitScript(() => {
    // @ts-ignore
    window.__shutdownSends = 0;
    // @ts-ignore
    window.__cancelSends = 0;
    const realBeacon = navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon = function (url) {
      if (typeof url !== "string") return realBeacon(url);
      if (url.indexOf("/api/shutdown") !== -1) {
        // @ts-ignore
        window.__shutdownSends += 1;
        return true;
      }
      if (url.indexOf("/api/cancel-shutdown") !== -1) {
        // @ts-ignore
        window.__cancelSends += 1;
        return true;
      }
      return realBeacon(url);
    };
  });
  await page.goto(FIXTURE);
  // Snapshot the baseline counts after goto() settles — the browser
  // already fired one pageshow at load time (the listener registered a
  // cancel beacon for it). All test assertions are deltas from this point.
  await page.evaluate(() => {
    // @ts-ignore
    window.__shutdownBaseline = window.__shutdownSends;
    // @ts-ignore
    window.__cancelBaseline = window.__cancelSends;
  });
});

async function counts(page) {
  return await page.evaluate(() => ({
    // @ts-ignore
    shutdown: window.__shutdownSends - window.__shutdownBaseline,
    // @ts-ignore
    cancel: window.__cancelSends - window.__cancelBaseline,
  }));
}

test("visibility-hidden does NOT beacon /api/shutdown", async ({ page }) => {
  // Simulate the tab going to the background (visibilitychange -> hidden)
  // and wait past the old 3 s timeout. The listener must not fire.
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.waitForTimeout(3500);
  expect((await counts(page)).shutdown).toBe(0);
});

test("pagehide beacons /api/shutdown (and only once)", async ({ page }) => {
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pagehide"));
  });
  expect((await counts(page)).shutdown).toBe(1);

  // A second pagehide is a no-op (fired guard).
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pagehide"));
  });
  expect((await counts(page)).shutdown).toBe(1);
});

test("beforeunload beacons /api/shutdown", async ({ page }) => {
  await page.evaluate(() => {
    window.dispatchEvent(new Event("beforeunload"));
  });
  expect((await counts(page)).shutdown).toBe(1);
});

test("visibility-hidden after a real pagehide still does not re-beacon", async ({ page }) => {
  // Real close -> beacon. Then the user reopens / the page revisits a
  // backgrounded state — no second beacon from the visibility listener.
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pagehide"));
  });
  expect((await counts(page)).shutdown).toBe(1);

  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.waitForTimeout(3500);
  expect((await counts(page)).shutdown).toBe(1);
});

test("dispatched pageshow beacons /api/cancel-shutdown", async ({ page }) => {
  // Fire pageshow manually — expect a cancel beacon and no shutdown.
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pageshow"));
  });
  const c = await counts(page);
  expect(c.cancel).toBe(1);
  expect(c.shutdown).toBe(0);
});

test("F5 sequence: pagehide then pageshow sends shutdown AND cancel", async ({ page }) => {
  // pagehide on the outgoing page -> /api/shutdown. The new page that
  // replaces it fires pageshow -> /api/cancel-shutdown. Together they tell
  // the server "the tab is reloading, don't exit".
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pagehide"));
    window.dispatchEvent(new PageTransitionEvent("pageshow"));
  });
  const c = await counts(page);
  expect(c.shutdown).toBe(1);
  expect(c.cancel).toBe(1);
});

test("pageshow also re-arms (allows another pagehide to fire)", async ({ page }) => {
  // pageshow resets the `fired` guard, so a subsequent pagehide fires
  // /api/shutdown again — the next reload starts a fresh countdown, not
  // a stale one.
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pagehide"));
  });
  expect((await counts(page)).shutdown).toBe(1);

  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pageshow"));
  });

  // Second reload cycle:
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pagehide"));
  });
  const c = await counts(page);
  expect(c.shutdown).toBe(2);
  expect(c.cancel).toBe(1);
});

test("bfcache restore (pageshow.persisted=true) still cancels", async ({ page }) => {
  // Real close first (pagehide, not persisted):
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pagehide", { persisted: false }));
  });
  expect((await counts(page)).shutdown).toBe(1);

  // Bfcache restore (persisted=true) fires pageshow; cancel should still
  // be sent so a stranded timer from the previous lifecycle cannot kill
  // the server after the user navigates back.
  await page.evaluate(() => {
    window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true }));
  });
  expect((await counts(page)).cancel).toBe(1);
});
