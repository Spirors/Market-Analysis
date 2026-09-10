// Playwright coverage for the news timeline's Week/Month grouping toggle and
// the AI gauge auto-re-render after a manual "ai" tag add/remove.
//
// Feature 1: the timeline groups by week or month (tlGroupingMode), persists
// each mode's selected period separately (tlSelectedWeek / tlSelectedMonth),
// and restores the previous selection when switching back.
// Feature 2: POST /api/events/tags now returns a recomputed ai_sentiment
// payload; when the tag change touched "ai", the gauge card re-renders
// without a full dashboard refresh.

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

  test("tagging an event with 'ai' re-renders the AI gauge", async ({ page }) => {
    await mockNewsDashboard(page);
    // Stub the tags endpoint with a recomputed gauge payload (the parallel
    // backend lane now returns ai_sentiment alongside events).
    await page.route("**/api/events/tags", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          updated: 1,
          events: NEWS_EVENTS,
          ai_sentiment: {
            score: 42,
            verdict: "Expansion",
            spread_pct: 9.0,
            news: { tone: "bullish" },
            valuation: { note: "Stretched vs history" },
            cohorts: [{ name: "AI beneficiaries", roc_3m_pct: 14.0, breadth_pct: 82, tone: "bullish", note: "leading" }],
            flip_conditions: ["AI news tone turns negative"],
          },
        }),
      });
    });
    await loadDashboard(page);

    // Initial gauge score from the dashboard payload (basePayload uses 38).
    await expect(page.locator("#aiSentimentBody")).toContainText("Score 38");

    // Add the "ai" tag to the first event via the inline + tag form.
    await page.locator(".tag-add-btn").first().click();
    const input = page.locator(".tag-add-input").first();
    await expect(input).toBeVisible();
    await input.fill("ai");
    await input.press("Enter");

    // The gauge re-renders with the recomputed score — no full refresh.
    await expect(page.locator("#aiSentimentBody")).toContainText("Score 42");
    await expect(page.locator("#aiSentimentBody")).not.toContainText("Score 38");
  });
});