// tests/frontend/breadth-labels.spec.mjs
//
// Breadth card labelling contract.
//
// The breadth charts plot each symbol's SIGNED distance from its own 50-day
// moving average (`pct_from_ma`), not the aggregate share of names above the
// 50DMA. The aggregate share lives on the Indicators card. This spec guards
// that every label on the breadth cards describes the distance metric, and
// that the no-Chart.js fallback labels the aggregate share as such instead of
// presenting it as the chart's own metric.
//
// Chart.js is intentionally blocked in tests (CDN abort), so the breadth
// renderer always takes the fallback branch here.

import { test, expect } from "@playwright/test";
import { installMockDashboard } from "./mock-dashboard.mjs";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

async function tooltipText(page, cardId) {
  const infoIcon = page.locator(`[data-card="${cardId}"] .card-info`).first();
  await expect(infoIcon).toBeVisible();
  const tooltipId = await infoIcon.getAttribute("aria-describedby");
  expect(tooltipId).toBeTruthy();
  return page.locator(`#${tooltipId} .tt-body`).textContent();
}

test("breadth card heading describes distance from the 50-day MA", async ({ page }) => {
  await installMockDashboard(page);
  await page.goto(DASH);
  await page.waitForSelector('[data-card="breadth"]');

  const heading = await page.locator('[data-card="breadth"] h2').first().textContent();
  expect(heading).toContain("Sectors & indices");
  expect(heading).toContain("distance from 50-day MA");
  // The old, wrong claim must be gone.
  expect(heading).not.toContain("% above 50-day MA");
});

test("breadth tooltip describes per-symbol distance and points at the aggregate share", async ({ page }) => {
  await installMockDashboard(page);
  await page.goto(DASH);
  await page.waitForSelector('[data-card="breadth"]');

  const lower = (await tooltipText(page, "breadth")).toLowerCase();
  expect(lower).toContain("distance");
  expect(lower).toContain("50-day moving average");
  // Sign convention is explicit.
  expect(lower).toContain("positive = above");
  expect(lower).toContain("negative = below");
  // Real universe: 4 indices + 12 sector ETFs.
  expect(lower).toContain("12 sector etf");
  expect(lower).toContain("4 indices");
  // The aggregate share is redirected to the Indicators card.
  expect(lower).toContain("indicators");
  // The old, wrong framing is gone.
  expect(lower).not.toContain("share of sector constituents trading above");
});

test("breadth-ai tooltip describes distance, keeps cooldown, points at the aggregate share", async ({ page }) => {
  await installMockDashboard(page);
  await page.goto(DASH);
  await page.waitForSelector('[data-card="breadth-ai"]');

  const lower = (await tooltipText(page, "breadth-ai")).toLowerCase();
  expect(lower).toContain("distance");
  expect(lower).toContain("positive = above");
  expect(lower).toContain("indicators");
  // The 30-minute refresh-cooldown sentence must survive the relabel.
  expect(lower).toContain("30-minute refresh cooldown");
  expect(lower).not.toContain("share of ai-cohort constituents trading above");
});

test("no-Chart.js fallback labels the number as the aggregate share", async ({ page }) => {
  await installMockDashboard(page);
  await page.goto(DASH);
  await page.waitForSelector('[data-card="breadth"]');

  const fallback = await page.locator('[data-card="breadth"] .chart-empty').textContent();
  expect(fallback).toContain("aggregate share");
  expect(fallback).toContain("Chart.js unavailable");
  // The aggregate share value itself still renders.
  expect(fallback).toContain("68%");
});
