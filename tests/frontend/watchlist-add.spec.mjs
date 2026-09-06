// Regression test for the "earnings watchlist add button broken" bug.
//
// Root cause: `drawControls()` in static/js/tickerTable.js rebuilds the
// entire controls subtree (including the add input + Add button) on every
// column reorder / sort / reset — but `wireAddInput()` was only called from
// the public `render()` entry point (once). After the first column reorder,
// the freshly-created add input + button had no event listeners and the
// Add button silently did nothing.
//
// Fix: `wireAddInput()` now runs at the end of `drawControls()`, so every
// rebuild re-attaches the listeners. Listeners attach to fresh DOM nodes
// so the discarded elements (and their listeners) are GC'd naturally —
// no leak.
//
// This test loads the actual tickerTable.js module in a Playwright page
// and exercises the add-input flow under a fresh render, a column reorder,
// and a sort-header click. The Add button must work in all three cases.

import { test, expect } from "@playwright/test";

const BASE_URL = "http://127.0.0.1:8123";
const DASH = BASE_URL + "/static/index.html";

// Sets up the page: injects container/controls hosts and loads tickerTable.js
// as a module (ES modules can be loaded via dynamic import in a Playwright page).
async function setupPage(page) {
  await page.goto(DASH);
  await page.evaluate(() => {
    document.body.innerHTML = '<div id="ttContainer"></div><div id="ttControls"></div>';
  });
  await page.evaluate(async () => {
    try {
      const mod = await import("http://127.0.0.1:8123/static/js/tickerTable.js?v=" + Date.now());
      window.__createTickerTable = mod.createTickerTable;
      window.__VALID_SECTIONS = mod.VALID_SECTIONS;
    } catch (e) {
      window.__tickerTableError = String(e) + " | " + (e && e.stack ? e.stack : "");
    }
  });
}

async function buildTable(page) {
  return await page.evaluate(() => {
    if (!window.__createTickerTable) {
      return { error: "tickerTable.js failed to load: " + (window.__tickerTableError || "no error captured") };
    }
    // Columns are defined IN-PAGE (Playwright can't serialize closures).
    const columns = [
      { key: "symbol", label: "Ticker", default: true,
        fmt: (r) => "<b>" + r.symbol + "</b>" },
      { key: "price",  label: "Price",  default: true, num: true,
        fmt: (r) => r.price == null ? "—" : String(r.price) },
    ];
    let initialRows = [{ symbol: "AAPL", price: 220 }];
    window.__addCalls = [];
    const table = window.__createTickerTable({
      section: "earnings",
      containerSel: "#ttContainer",
      controlsSel: "#ttControls",
      columns,
      fetchData: async () => ({ rows: initialRows }),
      addRow: async (sym) => {
        window.__addCalls.push(sym);
        initialRows = [...initialRows, { symbol: sym, price: 100 }];
        return { rows: initialRows };
      },
      removeRow: async (sym) => ({ rows: initialRows.filter((r) => r.symbol !== sym) }),
      editCell: null,
      columnPrefsUrl: async () => {},
    });
    table.render({ rows: initialRows });
    window.__table = table;
    return { ok: true };
  });
}

async function typeAndAdd(page, symbol) {
  await page.fill("#ttControls .tt-input", symbol);
  await page.click("#ttControls .tt-add-btn");
}

test.describe("earnings watchlist add button", () => {
  test.beforeEach(async ({ page }) => {
    await setupPage(page);
  });

  test("Add button works on initial render", async ({ page }) => {
    const r = await buildTable(page);
    expect(r.error, r.error).toBeUndefined();
    await typeAndAdd(page, "NVDA");
    const calls = await page.evaluate(() => window.__addCalls);
    expect(calls).toEqual(["NVDA"]);
  });

  test("Add button still works after a column reorder", async ({ page }) => {
    // This is the regression: previously, the first column reorder replaced
    // the controls HTML, dropping the add-input listeners. Re-triggering
    // would have silently done nothing.
    const r = await buildTable(page);
    expect(r.error, r.error).toBeUndefined();
    // The column reorder buttons live inside .tt-cols-menu which starts
    // hidden; open it first so the ◀ button is clickable.
    await page.click("#ttControls .tt-cols-btn");
    await page.click("#ttControls .tt-col-up[data-key='price']");
    // Verify the reorder actually fired (sanity check on the test).
    const headers = await page.locator("#ttContainer thead th").allInnerTexts();
    expect(headers[0].toLowerCase()).toBe("price");
    // Add must still work.
    await typeAndAdd(page, "TSLA");
    const calls = await page.evaluate(() => window.__addCalls);
    expect(calls).toEqual(["TSLA"]);
  });

  test("Add button still works after sorting by a column header", async ({ page }) => {
    const r = await buildTable(page);
    expect(r.error, r.error).toBeUndefined();
    await page.click("#ttContainer thead th.sortable[data-key='symbol']");
    await page.click("#ttContainer thead th.sortable[data-key='symbol']");
    await typeAndAdd(page, "GOOG");
    const calls = await page.evaluate(() => window.__addCalls);
    expect(calls).toEqual(["GOOG"]);
  });

  test("Add button still works after toggling a column's visibility", async ({ page }) => {
    const r = await buildTable(page);
    expect(r.error, r.error).toBeUndefined();
    await page.click("#ttControls .tt-cols-btn");
    await page.click("#ttControls input[data-col='price']");
    await page.click("#ttControls .tt-cols-btn"); // close menu
    await typeAndAdd(page, "AMZN");
    const calls = await page.evaluate(() => window.__addCalls);
    expect(calls).toEqual(["AMZN"]);
  });

  test("Add button still works after multiple back-to-back column reorders", async ({ page }) => {
    const r = await buildTable(page);
    expect(r.error, r.error).toBeUndefined();
    // Mix of reorder + sort + visibility toggles — every one of these
    // triggers drawControls() under the hood. The fix calls wireAddInput()
    // inside drawControls(), so the add-input must survive. The columns
    // menu starts hidden and re-renders hidden after every controls
    // rebuild, so we re-open it before each menu-scoped interaction.
    await page.click("#ttControls .tt-cols-btn");
    await page.click("#ttControls .tt-col-up[data-key='price']");
    await page.click("#ttContainer thead th.sortable[data-key='symbol']");
    await page.click("#ttControls .tt-cols-btn"); // re-open the menu
    await page.click("#ttControls input[data-col='price']");
    // Force-close the columns menu so the Add button is clickable. The
    // production app's outside-click listener only fires on document-level
    // clicks, and a programmatic .tt-cols-btn toggle here doesn't dispatch
    // a document click that the listener recognizes — toggle visibility
    // directly so the test is deterministic.
    await page.evaluate(() => {
      const menu = document.querySelector("#ttControls .tt-cols-menu");
      if (menu) menu.classList.add("hidden");
    });
    await typeAndAdd(page, "MSFT");
    const calls = await page.evaluate(() => window.__addCalls);
    expect(calls).toEqual(["MSFT"]);
  });

  test("Enter key in the add input triggers add (independent of the Add button click)", async ({ page }) => {
    const r = await buildTable(page);
    expect(r.error, r.error).toBeUndefined();
    await page.fill("#ttControls .tt-input", "INTC");
    await page.press("#ttControls .tt-input", "Enter");
    const calls = await page.evaluate(() => window.__addCalls);
    expect(calls).toEqual(["INTC"]);
  });

  test("Add button is enabled only when the input has non-whitespace content", async ({ page }) => {
    const r = await buildTable(page);
    expect(r.error, r.error).toBeUndefined();
    const initiallyDisabled = await page.locator("#ttControls .tt-add-btn").isDisabled();
    expect(initiallyDisabled).toBe(true);
    await page.fill("#ttControls .tt-input", "META");
    const afterType = await page.locator("#ttControls .tt-add-btn").isDisabled();
    expect(afterType).toBe(false);
    await page.fill("#ttControls .tt-input", "   ");
    const afterWhitespace = await page.locator("#ttControls .tt-add-btn").isDisabled();
    expect(afterWhitespace).toBe(true);
  });

  test("VALID_SECTIONS exposes the per-section allowlist", async ({ page }) => {
    // If a future extraction drops this constant, this test fails loud.
    const sections = await page.evaluate(() => window.__VALID_SECTIONS);
    expect(sections).toEqual(["earnings", "portfolio"]);
  });
});
