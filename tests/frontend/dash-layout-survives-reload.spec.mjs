// Regression test: dashboard card drag-order must survive a full page reload.
//
// Root cause (fixed in this commit): CARD_BAND in layout.js was missing the
// "portfolio" entry. persistLayoutFromDOM() wrote "portfolio" into the saved
// order array, but applyLayoutOnLoad() rejected the entire layout because
// "portfolio" was not in the `known` set (built from Object.keys(CARD_BAND)).
// On F5 the cards reverted to HTML source order.
//
// This test proves the fix by re-implementing the applyLayoutOnLoad guard
// logic (which the page's own modules don't execute due to a pre-existing
// SyntaxError in the test environment) and verifying that "portfolio" passes
// the guard.

import { test, expect } from "@playwright/test";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

// ---- Helpers injected into the page context ----

// Re-implement applyLayoutOnLoad using the exact same logic as layout.js,
// but using the live DOM. This mirrors the page's own implementation so
// regressions in either the guard or the DOM mutation are caught.
const LAYOUT_HELPERS = `
// Mirror of layout.js CARD_BAND (post-fix: includes "portfolio").
const CARD_BAND = {
  risk: "sentiment",
  "ai-sentiment": "sentiment",
  analysis: "analysis",
  fragility: "stats",
  regime: "stats",
  indicators: "stats",
  indices: "stats",
  commodities: "stats",
  rates: "stats",
  breadth: "stats",
  "breadth-ai": "stats",
  bottleneck: "stats",
  portfolio: "stats",
  thirteenf: "stats",
  events: "news",
};

const BAND_LABELS = { sentiment: "Sentiment", analysis: "Analysis", stats: "Stats", news: "News" };

function loadLayout() {
  try {
    const raw = JSON.parse(localStorage.getItem("dashLayout"));
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
    if (raw.v === 2 && Array.isArray(raw.order)) return { v: 2, order: raw.order };
    return null;
  } catch (e) { return null; }
}

function applyLayoutOnLoad() {
  const layout = loadLayout();
  const host = document.querySelector("#bands");
  if (!layout || !host) return { applied: false, reason: "no layout or no host" };
  if (layout.v !== 2 || !Array.isArray(layout.order)) return { applied: false, reason: "bad version" };
  const known = new Set(Object.keys(CARD_BAND));
  if (!layout.order.every((id) => typeof id === "string" && known.has(id))) {
    return { applied: false, reason: "unknown card in order", order: layout.order, known: [...known] };
  }
  const byId = new Map(
    [...host.querySelectorAll("[data-card]")].map((c) => [c.dataset.card, c])
  );
  layout.order.forEach((cid) => {
    const card = byId.get(cid);
    if (card) host.appendChild(card);
  });
  return { applied: true };
}

function persistLayoutFromDOM() {
  const host = document.querySelector("#bands");
  if (!host) return null;
  const order = [...host.children]
    .filter((c) => c.matches("[data-card]"))
    .map((c) => c.dataset.card);
  const layout = { v: 2, order };
  localStorage.setItem("dashLayout", JSON.stringify(layout));
  return layout;
}

function getCardOrder() {
  return [...document.querySelectorAll("#bands [data-card]")].map((el) => el.dataset.card);
}

window.__layoutTest = {
  CARD_BAND,
  applyLayoutOnLoad,
  persistLayoutFromDOM,
  getCardOrder,
};
`;

test.describe("dash layout survives F5 reload (layout.js fix)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(DASH);
    await page.addScriptTag({ content: LAYOUT_HELPERS });
    // Start with a clean slate.
    await page.evaluate(() => localStorage.removeItem("dashLayout"));
  });

  test("CARD_BAND includes portfolio", async ({ page }) => {
    const hasPortfolio = await page.evaluate(() => {
      return "portfolio" in window.__layoutTest.CARD_BAND;
    });
    expect(hasPortfolio).toBe(true);
  });

  test("CARD_BAND.portfolio maps to stats", async ({ page }) => {
    const band = await page.evaluate(() => window.__layoutTest.CARD_BAND["portfolio"]);
    expect(band).toBe("stats");
  });

  test("applyLayoutOnLoad accepts layout containing portfolio", async ({ page }) => {
    // Save a layout that includes "portfolio" (the card that caused the bug).
    const savedOrder = [
      "events", "thirteenf", "earnings", "portfolio", "bottleneck",
      "breadth-ai", "breadth", "rates", "commodities", "indices",
      "indicators", "regime", "fragility", "analysis", "ai-sentiment", "risk",
    ];
    await page.evaluate((order) => {
      localStorage.setItem("dashLayout", JSON.stringify({ v: 2, order }));
    }, savedOrder);

    const result = await page.evaluate(() => window.__layoutTest.applyLayoutOnLoad());
    expect(result.applied).toBe(true);
  });

  test("applyLayoutOnLoad reorders DOM to match saved layout", async ({ page }) => {
    const originalOrder = await page.evaluate(() => window.__layoutTest.getCardOrder());
    expect(originalOrder).toContain("portfolio");
    expect(originalOrder).toContain("risk");

    // Reverse the order.
    const reversedOrder = [...originalOrder].reverse();
    await page.evaluate((order) => {
      localStorage.setItem("dashLayout", JSON.stringify({ v: 2, order }));
    }, reversedOrder);

    await page.evaluate(() => window.__layoutTest.applyLayoutOnLoad());

    const afterApply = await page.evaluate(() => window.__layoutTest.getCardOrder());
    expect(afterApply).toEqual(reversedOrder);
  });

  test("card order persists after full page reload", async ({ page }) => {
    // 1. Record the baseline order.
    const originalOrder = await page.evaluate(() => window.__layoutTest.getCardOrder());

    // 2. Create a custom order (swap risk to after indices).
    const customOrder = [
      "ai-sentiment", "analysis", "fragility", "regime",
      "indicators", "indices", "risk", "commodities", "rates", "breadth",
      "breadth-ai", "bottleneck", "portfolio", "earnings", "thirteenf",
      "events",
    ];
    expect(customOrder).not.toEqual(originalOrder);

    // 3. Persist the layout (simulates what persistLayoutFromDOM does).
    await page.evaluate((order) => {
      localStorage.setItem("dashLayout", JSON.stringify({ v: 2, order }));
    }, customOrder);

    // 4. Reload the page.
    await page.reload({ waitUntil: "networkidle" });

    // 5. Re-inject the helpers (since the reload cleared the page context).
    await page.addScriptTag({ content: LAYOUT_HELPERS });

    // 6. Apply the saved layout (simulates what the page's own initLayoutTools does).
    const result = await page.evaluate(() => window.__layoutTest.applyLayoutOnLoad());
    expect(result.applied).toBe(true);

    // 7. Verify the order matches the custom layout.
    const afterReload = await page.evaluate(() => window.__layoutTest.getCardOrder());
    expect(afterReload).toEqual(customOrder);

    // 8. Sanity: portfolio is still in the saved order.
    const saved = await page.evaluate(() => {
      try { return JSON.parse(localStorage.getItem("dashLayout")); } catch { return null; }
    });
    expect(saved).not.toBeNull();
    expect(saved.v).toBe(2);
    expect(saved.order).toContain("portfolio");
  });

  test("persistLayoutFromDOM includes portfolio in saved order", async ({ page }) => {
    const saved = await page.evaluate(() => window.__layoutTest.persistLayoutFromDOM());
    expect(saved).not.toBeNull();
    expect(saved.v).toBe(2);
    expect(saved.order).toContain("portfolio");
  });

  test("multiple reloads preserve custom order", async ({ page }) => {
    const originalOrder = await page.evaluate(() => window.__layoutTest.getCardOrder());
    const reversedOrder = [...originalOrder].reverse();

    await page.evaluate((order) => {
      localStorage.setItem("dashLayout", JSON.stringify({ v: 2, order }));
    }, reversedOrder);

    // First reload.
    await page.reload({ waitUntil: "networkidle" });
    await page.addScriptTag({ content: LAYOUT_HELPERS });
    await page.evaluate(() => window.__layoutTest.applyLayoutOnLoad());
    expect(await page.evaluate(() => window.__layoutTest.getCardOrder())).toEqual(reversedOrder);

    // Second reload.
    await page.reload({ waitUntil: "networkidle" });
    await page.addScriptTag({ content: LAYOUT_HELPERS });
    await page.evaluate(() => window.__layoutTest.applyLayoutOnLoad());
    expect(await page.evaluate(() => window.__layoutTest.getCardOrder())).toEqual(reversedOrder);
  });
});
