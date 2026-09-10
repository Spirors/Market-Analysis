// Playwright coverage for the news timeline's Week/Month grouping toggle,
// the dimension-edit popover (manual fix for mis-classified events), and
// the AI capex-cycle gauge NOT auto-refreshing on tag edits.
//
// Feature 1: the timeline groups by week or month (tlGroupingMode), persists
// each mode's selected period separately (tlSelectedWeek / tlSelectedMonth),
// and restores the previous selection when switching back.
// Feature 2: every pill on a row is editable. Fixed-dimension pills
// (category / actor / direction / region) open a <select>-based popover
// that overrides the column. User-added / "ai" tags use the existing
// free-text rename popover. The user_edited lock prevents the override
// from being silently undone by a future RSS refresh.
// Feature 3: the AI capex-cycle gauge does NOT auto-refresh on tag edits —
// the user must click the global Refresh button to pick up the change.
// This keeps the gauge stable while the user is curating tags.

import { test, expect } from "@playwright/test";
import { mockApi, basePayload } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

// Six events spanning three months plus one undated, so both grouping modes
// have multiple buckets and the fallback/persistence logic is observable.
const NEWS_EVENTS = [
  { source: "MarketWatch", title: "Fed signals patience on rates", link: "https://example.com/fed-patience", published: "2026-09-18T00:00:00", date_label: null, summary: "", category: "macro", actor: "government", direction: "neutral", region: "us", impact: "High", finance_relevance: 8.0, source_weight: 1.2, tags: ["macro", "government", "neutral", "us"] },
  { source: "MarketWatch", title: "AI capex surge continues", link: "https://example.com/ai-capex", published: "2026-09-05T00:00:00", date_label: null, summary: "", category: "micro", actor: "company", direction: "bullish", region: "global", impact: "High", finance_relevance: 7.0, source_weight: 1.0, tags: ["micro", "company", "bullish", "global"] },
  { source: "BBC Business", title: "ECB holds rates", link: "https://example.com/ecb-hold", published: "2026-08-25T00:00:00", date_label: null, summary: "", category: "macro", actor: "government", direction: "neutral", region: "europe", impact: "High", finance_relevance: 6.0, source_weight: 1.0, tags: ["macro", "government", "neutral", "europe"] },
  { source: "BBC Business", title: "China stimulus", link: "https://example.com/china-stimulus", published: "2026-08-02T00:00:00", date_label: null, summary: "", category: "macro", actor: "government", direction: "bullish", region: "china", impact: "High", finance_relevance: 5.0, source_weight: 1.0, tags: ["macro", "government", "bullish", "china"] },
  { source: "Wikipedia", title: "Historic market event", link: "seed://historic", published: "2026-07-15T00:00:00", date_label: null, summary: "", category: "macro", actor: "government", direction: "bearish", region: "global", impact: "Critical", finance_relevance: 9.0, source_weight: 1.0, tags: ["macro", "government", "bearish", "global"] },
  { source: "Wikipedia", title: "Undated event", link: "seed://undated", published: "", date_label: null, summary: "", category: "macro", actor: "government", direction: "neutral", region: "global", impact: "High", finance_relevance: 4.0, source_weight: 1.0, tags: ["macro", "government", "neutral", "global"] },
];

function makeNewsPayload(events) {
  const p = basePayload();
  p.events = events;
  return p;
}

async function mockNewsDashboard(page, events = NEWS_EVENTS) {
  await mockApi(page);
  // Registered after mockApi so this route wins for /api/dashboard.
  await page.route("**/api/dashboard", (route) => {
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(makeNewsPayload(events)) });
  });
}

async function loadDashboard(page) {
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading…");
}

test.describe("News timeline Week/Month grouping", () => {
  test("toggle defaults to week", async ({ page }) => {
    await mockNewsDashboard(page);
    await loadDashboard(page);

    await expect(page.locator('.tl-mode-btn[data-mode="week"]')).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator('.tl-mode-btn[data-mode="month"]')).toHaveAttribute("aria-pressed", "false");
    // Week-mode dropdown options.
    await expect(page.locator("#weekSelect option").first()).toHaveText(/Week of /);
  });

  test("clicking Month shows month groups in the dropdown", async ({ page }) => {
    await mockNewsDashboard(page);
    await loadDashboard(page);

    await page.locator('.tl-mode-btn[data-mode="month"]').click();

    const options = page.locator("#weekSelect option");
    await expect(options).toHaveCount(4);
    await expect(options.nth(0)).toHaveText("September 2026 \u00b7 2 events");
    await expect(options.nth(1)).toHaveText("August 2026 \u00b7 2 events");
    await expect(options.nth(2)).toHaveText("July 2026 \u00b7 1 event");
    await expect(options.nth(3)).toHaveText("Undated \u00b7 1 event");
  });

  test("selecting a month filters events to that month only", async ({ page }) => {
    await mockNewsDashboard(page);
    await loadDashboard(page);

    await page.locator('.tl-mode-btn[data-mode="month"]').click();
    await page.locator("#weekSelect").selectOption({ label: "August 2026 \u00b7 2 events" });

    await expect(page.locator("#newsBody .tl-item")).toHaveCount(2);
    const dates = await page.locator("#newsBody .tl-date").allTextContents();
    for (const d of dates) expect(d).toContain("2026-08");
  });

  test("switching back to Week restores the previously selected week", async ({ page }) => {
    await mockNewsDashboard(page);
    await loadDashboard(page);

    // Pick a specific week (not the default first option).
    await page.locator("#weekSelect").selectOption({ index: 1 });
    const savedWeek = await page.locator("#weekSelect").inputValue();

    // Switch to Month and pick a month.
    await page.locator('.tl-mode-btn[data-mode="month"]').click();
    await page.locator("#weekSelect").selectOption({ label: "July 2026 \u00b7 1 event" });

    // Back to Week: the previously selected week should be restored.
    await page.locator('.tl-mode-btn[data-mode="week"]').click();
    await expect(page.locator("#weekSelect")).toHaveValue(savedWeek);
  });

  test("month selection persists across reload", async ({ page }) => {
    await mockNewsDashboard(page);
    await loadDashboard(page);

    await page.locator('.tl-mode-btn[data-mode="month"]').click();
    await page.locator("#weekSelect").selectOption({ label: "July 2026 \u00b7 1 event" });

    await page.reload();
    await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");

    await expect(page.locator('.tl-mode-btn[data-mode="month"]')).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("#weekSelect")).toHaveValue("2026-07");
    await expect(page.locator("#newsBody .tl-item")).toHaveCount(1);
  });

  test("mode (week/month) persists across reload", async ({ page }) => {
    await mockNewsDashboard(page);
    await loadDashboard(page);

    await page.locator('.tl-mode-btn[data-mode="month"]').click();
    await expect(page.locator('.tl-mode-btn[data-mode="month"]')).toHaveAttribute("aria-pressed", "true");

    await page.reload();
    await expect(page.locator("#riskBody")).not.toHaveText("Loading\u2026");

    await expect(page.locator('.tl-mode-btn[data-mode="month"]')).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator('.tl-mode-btn[data-mode="week"]')).toHaveAttribute("aria-pressed", "false");
    // Dropdown still shows month groups after reload.
    await expect(page.locator("#weekSelect option").first()).toHaveText("September 2026 \u00b7 2 events");
  });
});

test.describe("Editable news tags (manual fix for mis-classified events)", () => {
  // Captures POST /api/events/dimensions calls so we can assert the payload.
  const dimensionCalls = { byLink: {} };

  async function stubDimensions(page, events) {
    dimensionCalls.byLink = {};
    await page.route("**/api/events/dimensions", async (route) => {
      const body = JSON.parse(route.request().postData() || "{}");
      const link = body.link;
      (dimensionCalls.byLink[link] = dimensionCalls.byLink[link] || []).push(body);
      // Build the response: mutate the matching event's column in place.
      const updated_events = events.map((ev) => {
        if (ev.link !== link) return ev;
        const next = { ...ev };
        for (const [field, value] of Object.entries(body)) {
          if (field === "link") continue;
          next[field] = value;
        }
        // Rebuild tags from the (possibly changed) dimensions + remaining user tags.
        const userTags = (ev.tags || []).filter((t) =>
          !["macro", "micro", "government", "company", "bullish", "bearish", "neutral",
             "us", "global", "asia", "europe", "middle-east", "russia-ukraine",
             "korea", "japan", "china"].includes(t)
        );
        const fixed = [next.category, next.actor, next.direction, next.region].filter(Boolean);
        next.tags = Array.from(new Set([...fixed, ...userTags]));
        return next;
      });
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ updated: updated_events.find((e) => e.link === link), events: updated_events }) });
    });
  }

  test("every pill on a row is clickable (fixed dimensions + auto ai + user tags)", async ({ page }) => {
    await mockNewsDashboard(page);
    await loadDashboard(page);

    // Every pill in a row should carry the data-act="tag-edit" marker — no
    // inert fixed dimensions any more.
    const pills = page.locator('#newsBody .tl-tags [data-act="tag-edit"]');
    const count = await pills.count();
    // First event has 4 tags (macro, government, neutral, us) + optionally ai.
    expect(count).toBeGreaterThanOrEqual(4);
  });

  test("clicking a fixed-dimension pill opens a <select>-based popover", async ({ page }) => {
    await stubDimensions(page, NEWS_EVENTS);
    await mockNewsDashboard(page);
    await loadDashboard(page);

    // First event's "macro" pill is a category dimension. Click it.
    const macroPill = page.locator('#newsBody .tl-tags [data-tag="macro"]').first();
    await expect(macroPill).toBeVisible();
    await macroPill.click();

    // Popover: rename row hidden, dimension row visible with <select>.
    await expect(page.locator("#tagPopRenameRow")).toBeHidden();
    await expect(page.locator("#tagPopDimensionRow")).toBeVisible();
    const select = page.locator("#tagPopDimensionSelect");
    await expect(select).toBeVisible();
    // Allowed values for category = macro + micro, plus a "(clear)" option
    // because the row currently has category=macro set.
    const opts = await select.locator("option").allTextContents();
    expect(opts).toEqual(["macro", "micro", "(clear)"]);

    // Picking "micro" + Save -> POST /api/events/dimensions with
    // {link, category: "micro"} and the pill flips to "micro".
    await select.selectOption("micro");
    await page.locator("#tagPopRename").click();
    await expect(page.locator('#newsBody .tl-tags [data-tag="micro"]').first()).toBeVisible();
    expect(dimensionCalls.byLink["https://example.com/fed-patience"]).toBeDefined();
    expect(dimensionCalls.byLink["https://example.com/fed-patience"][0]).toEqual({
      link: "https://example.com/fed-patience", category: "micro",
    });
  });

  test("the popover also offers 'clear' to null out a dimension", async ({ page }) => {
    await stubDimensions(page, NEWS_EVENTS);
    await mockNewsDashboard(page);
    await loadDashboard(page);

    const macroPill = page.locator('#newsBody .tl-tags [data-tag="macro"]').first();
    await macroPill.click();
    const select = page.locator("#tagPopDimensionSelect");
    // 'macro' has a value, so a "(clear)" option should appear.
    const opts = await select.locator("option").allTextContents();
    expect(opts.some((o) => o.includes("clear"))).toBe(true);

    await select.selectOption("");
    await page.locator("#tagPopRename").click();
    // The dimension call should send category: null.
    const calls = dimensionCalls.byLink["https://example.com/fed-patience"];
    expect(calls[0]).toEqual({ link: "https://example.com/fed-patience", category: null });
  });

  test("dimension edit arms user_edited lock (refresh cannot undo it)", async ({ page }) => {
    // Stub the dimensions endpoint to mirror the backend: set user_edited
    // on the response AND rebuild the merged `tags` array from the new
    // dimensions + remaining user tags (the frontend reads tags to render
    // the pill line).
    const fixedSet = new Set([
      "macro", "micro", "government", "company", "bullish", "bearish", "neutral",
      "us", "global", "asia", "europe", "middle-east", "russia-ukraine",
      "korea", "japan", "china",
    ]);
    let lastResponseEvents = NEWS_EVENTS;
    await page.route("**/api/events/dimensions", async (route) => {
      const body = JSON.parse(route.request().postData() || "{}");
      const link = body.link;
      lastResponseEvents = lastResponseEvents.map((ev) => {
        if (ev.link !== link) return ev;
        const next = { ...ev, user_edited: true };
        for (const [field, value] of Object.entries(body)) {
          if (field === "link") continue;
          next[field] = value;
        }
        const userTags = (ev.tags || []).filter((t) => !fixedSet.has(t));
        const fixed = [next.category, next.actor, next.direction, next.region].filter(Boolean);
        next.tags = Array.from(new Set([...fixed, ...userTags]));
        return next;
      });
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ updated: lastResponseEvents.find((e) => e.link === link), events: lastResponseEvents }) });
    });
    await mockNewsDashboard(page);
    await loadDashboard(page);

    // Override category from macro to micro on the first event.
    await page.locator('#newsBody .tl-tags [data-tag="macro"]').first().click();
    await page.locator("#tagPopDimensionSelect").selectOption("micro");
    await page.locator("#tagPopRename").click();
    // The pill now reads "micro".
    await expect(page.locator('#newsBody .tl-tags [data-tag="micro"]').first()).toBeVisible();
    // The "macro" pill is gone (replaced by "micro" in the merged tags).
    await expect(page.locator('#newsBody .tl-tags [data-tag="macro"]')).toHaveCount(0);
  });

  test("clicking a user-added (or auto 'ai') tag opens the free-text popover", async ({ page }) => {
    // Add the "ai" tag first so it appears as a user/auto pill.
    await page.route("**/api/events/tags", (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          updated: NEWS_EVENTS[0],
          events: NEWS_EVENTS.map((ev, i) => i === 0 ? { ...ev, tags: [...ev.tags, "ai"] } : ev),
        }),
      });
    });
    await mockNewsDashboard(page);
    await loadDashboard(page);

    // Open the + tag form and submit "ai" on the first event.
    await page.locator(".tag-add-btn").first().click();
    await page.locator(".tag-add-input").first().fill("ai");
    await page.locator(".tag-add-input").first().press("Enter");

    // Click the new "ai" pill — should open the free-text popover (no field attr).
    const aiPill = page.locator('#newsBody .tl-tags [data-tag="ai"]').first();
    await expect(aiPill).toBeVisible();
    await aiPill.click();

    // Popover: rename row visible, dimension row hidden.
    await expect(page.locator("#tagPopRenameRow")).toBeVisible();
    await expect(page.locator("#tagPopDimensionRow")).toBeHidden();
    await expect(page.locator("#tagPopRenameInput")).toHaveValue("ai");
  });
});

test.describe("AI gauge does NOT auto-refresh on tag edits", () => {
  test("tagging 'ai' leaves the gauge showing its pre-tag score until Refresh", async ({ page }) => {
    await mockNewsDashboard(page);
    // The tags endpoint intentionally returns NO ai_sentiment key now — the
    // gauge only refreshes via /api/dashboard on the user's Refresh button.
    await page.route("**/api/events/tags", (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          updated: NEWS_EVENTS[0],
          events: NEWS_EVENTS.map((ev, i) => i === 0 ? { ...ev, tags: [...ev.tags, "ai"] } : ev),
        }),
      });
    });
    await loadDashboard(page);

    // Initial gauge score from the dashboard payload (basePayload uses 38).
    const gauge = page.locator("#aiSentimentBody");
    await expect(gauge).toContainText("Score 38");

    // Add the "ai" tag.
    await page.locator(".tag-add-btn").first().click();
    await page.locator(".tag-add-input").first().fill("ai");
    await page.locator(".tag-add-input").first().press("Enter");

    // The timeline re-renders, the gauge does NOT.
    await expect(page.locator('#newsBody .tl-tags [data-tag="ai"]').first()).toBeVisible();
    await expect(gauge).toContainText("Score 38");
  });
});