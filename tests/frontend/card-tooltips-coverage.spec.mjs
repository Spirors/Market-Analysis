// tests/frontend/card-tooltips-coverage.spec.mjs
//
// 00-TEST: the card-header info-tooltip contract, pinned for every entry that
// initCardTooltips() (static/js/cards.js) wires from CARD_TOOLTIPS. Each card's
// h2 gets one .card-info trigger whose aria-describedby points at a
// role="tooltip" surface built by the shared attachTooltip component.
//
// Two universal points are asserted here for every card:
//   1. the body copy is non-empty, and
//   2. it states a freshness / as-of pointer, so the reader knows how old the
//      reading is.
// The other contract points (purpose, controls, dependencies) are card-specific
// and live beside each card in its own spec.
//
// Triggering follows tooltip.spec.mjs: focus the trigger, resolve the surface
// through aria-describedby, and read .tt-body.

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

// Every key in CARD_TOOLTIPS, each a [data-card] section in static/index.html.
// fragility ships hidden but the mock's risk.fragility_flags reveal it.
const CARD_IDS = [
  "risk",
  "ai-sentiment",
  "regime",
  "indicators",
  "indices",
  "commodities",
  "rates",
  "breadth",
  "breadth-ai",
  "bottleneck",
  "portfolio",
  "events",
  "fragility",
];

// The freshness / as-of pointer wording the CARD_TOOLTIPS copy uses. Every one
// of the 13 entries states its freshness (or the card's own stamp).
const FRESHNESS = /as of|freshness|stamp|cached|per-topic/i;

for (const cardId of CARD_IDS) {
  test(`card tooltip [${cardId}]: non-empty body with a freshness/as-of pointer`, async ({ page }) => {
    await mockApi(page);
    await page.goto(DASH);
    await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");

    const btn = page.locator(`[data-card="${cardId}"] .card-info`);
    await expect(btn).toHaveCount(1);

    await btn.focus();
    const describedBy = await btn.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    const surface = page.locator(`#${describedBy}`);
    await expect(surface).toBeVisible();
    await expect(surface).toHaveAttribute("role", "tooltip");

    const body = ((await surface.locator(".tt-body").textContent()) || "").trim();
    expect(body.length).toBeGreaterThan(0);
    expect(body).toMatch(FRESHNESS);
  });
}
