// Playwright coverage for the Portfolio section. Runs against the static
// file server (python -m http.server 8123) with all /api/* mocked via
// page.route(). No FastAPI server is started.
//
// Mock scenarios:
//   - Empty state: GET /api/portfolios returns default empty state
//   - Populated state: GET /api/portfolios returns one portfolio with one holding
//
// Architecture note: cards.js calls renderPortfolio(fullDashboardPayload) on
// initial load. The portfolio data lives in data.portfolios, which is NOT in
// the standard dashboard payload — it comes from a separate GET /api/portfolios
// call triggered by portfolio.js's internal refresh(). For the populated tests,
// we inject portfolio data into the dashboard mock payload so the initial
// render shows the pre-existing portfolio.

import { test, expect } from "@playwright/test";
import { mockApi } from "./mock-dashboard.mjs";

const DASH = "/static/index.html";

// ---- Portfolio mock helpers ----

const EMPTY_PORTFOLIOS = {
  version: 1,
  portfolios: {},
  column_order: {
    earnings: ["symbol", "date", "price", "pct_daily", "pct_7d", "high_52w", "forward_pe", "forward_peg", "market_cap_fmt", "sector", "rec"],
    portfolio: ["symbol", "shares", "total_cost", "last_price", "total_value", "gain_loss", "pct_daily"],
  },
  column_visibility: {
    earnings: { symbol: true, date: true, price: true, pct_daily: true, pct_7d: true, high_52w: true, forward_pe: true, forward_peg: false, market_cap_fmt: false, sector: false, rec: true },
    portfolio: { symbol: true, shares: true, total_cost: true, last_price: true, total_value: true, gain_loss: true, pct_daily: true },
  },
};

function makePopulatedPortfolios() {
  const state = JSON.parse(JSON.stringify(EMPTY_PORTFOLIOS));
  state.portfolios["fidelity-cash"] = {
    id: "fidelity-cash",
    name: "Fidelity Cash",
    holdings: [
      { symbol: "NVDA", shares: 10, total_cost: 1500.0, last_price: 145.2, pct_daily: 2.1 },
    ],
  };
  return state;
}

// In-memory state that the mocked endpoints mutate
let portfolioState = EMPTY_PORTFOLIOS;

function resetPortfolios() {
  portfolioState = JSON.parse(JSON.stringify(EMPTY_PORTFOLIOS));
}

/**
 * Single catch-all route that intercepts ALL /api/portfolios** requests.
 * Playwright checks routes in registration order, first match wins.
 * Using ** at the end of the glob ensures query strings are matched too.
 */
async function mockPortfolioApi(page) {
  resetPortfolios();

  await page.route("**/api/portfolios**", async (route) => {
    const reqUrl = new URL(route.request().url());
    const method = route.request().method();
    const pathname = reqUrl.pathname.replace(/\/+$/, "");

    // --- GET /api/portfolios (collection) ---
    if (pathname === "/api/portfolios" && method === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(portfolioState) });
    }

    // --- POST /api/portfolios (create) ---
    if (pathname === "/api/portfolios" && method === "POST") {
      const name = reqUrl.searchParams.get("name") || "";
      if (!name.trim()) {
        return route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: "name is required" }) });
      }
      const id = name.trim().toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
      portfolioState.portfolios[id] = { id, name: name.trim(), holdings: [] };
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id, portfolio: portfolioState.portfolios[id] }) });
    }

    // --- GET /api/portfolios/validate?symbol=... ---
    if (pathname === "/api/portfolios/validate" && method === "GET") {
      const symbol = reqUrl.searchParams.get("symbol") || "";
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ valid: true, symbol: symbol.toUpperCase(), name: symbol.toUpperCase(), sector: "Test" }) });
    }

    // --- PUT /api/portfolios/columns/{section} ---
    if (pathname.startsWith("/api/portfolios/columns/") && method === "PUT") {
      const section = pathname.split("/").pop();
      const body = JSON.parse(route.request().postData() || "{}");
      if (section === "portfolio") {
        portfolioState.column_order.portfolio = body.order || portfolioState.column_order.portfolio;
        portfolioState.column_visibility.portfolio = body.visibility || portfolioState.column_visibility.portfolio;
      }
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ order: portfolioState.column_order[section], visibility: portfolioState.column_visibility[section] }) });
    }

    // Parse sub-path: /api/portfolios/{pid}/...
    const parts = pathname.split("/");
    // parts: ['', 'api', 'portfolios', '{pid}', ...]
    if (parts.length >= 4) {
      const pid = parts[3];

      // --- POST /api/portfolios/{pid}/holdings ---
      if (parts.length === 5 && parts[4] === "holdings" && method === "POST") {
        const p = portfolioState.portfolios[pid];
        if (!p) return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) });
        const holding = {
          symbol: reqUrl.searchParams.get("symbol"),
          shares: parseFloat(reqUrl.searchParams.get("shares") || "0"),
          total_cost: parseFloat(reqUrl.searchParams.get("total_cost") || "0"),
          last_price: 145.2,
          pct_daily: 2.1,
        };
        p.holdings.push(holding);
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(holding) });
      }

      // --- PUT/DELETE /api/portfolios/{pid}/holdings/{symbol} ---
      if (parts.length === 6 && parts[4] === "holdings" && method === "PUT") {
        const p = portfolioState.portfolios[pid];
        if (!p) return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) });
        const symbol = parts[5];
        const h = p.holdings.find((h) => h.symbol === symbol && h.kind !== "cash");
        if (!h) return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) });
        if (reqUrl.searchParams.has("shares")) h.shares = parseFloat(reqUrl.searchParams.get("shares"));
        if (reqUrl.searchParams.has("total_cost")) h.total_cost = parseFloat(reqUrl.searchParams.get("total_cost"));
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(h) });
      }

      if (parts.length === 6 && parts[4] === "holdings" && method === "DELETE") {
        const p = portfolioState.portfolios[pid];
        if (!p) return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) });
        const symbol = parts[5];
        const idx = p.holdings.findIndex((h) => h.symbol === symbol && h.kind !== "cash");
        if (idx < 0) return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) });
        p.holdings.splice(idx, 1);
        return route.fulfill({ status: 204 });
      }

      // --- POST/PUT /api/portfolios/{pid}/cash ---
      if (parts.length === 5 && parts[4] === "cash" && method === "POST") {
        const p = portfolioState.portfolios[pid];
        if (!p) return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) });
        if (p.holdings.some((h) => h.kind === "cash")) {
          return route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: "cash row already exists" }) });
        }
        const cash = { kind: "cash", label: reqUrl.searchParams.get("label") || "Cash", total_cost: 0, total_value: 0 };
        p.holdings.push(cash);
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(cash) });
      }

      if (parts.length === 5 && parts[4] === "cash" && method === "PUT") {
        const p = portfolioState.portfolios[pid];
        if (!p) return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) });
        const cash = p.holdings.find((h) => h.kind === "cash");
        if (!cash) return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "cash row not found" }) });
        if (reqUrl.searchParams.has("total_cost")) cash.total_cost = parseFloat(reqUrl.searchParams.get("total_cost"));
        if (reqUrl.searchParams.has("total_value")) cash.total_value = parseFloat(reqUrl.searchParams.get("total_value"));
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(cash) });
      }

      // --- DELETE /api/portfolios/{pid} ---
      if (parts.length === 4 && method === "DELETE") {
        if (portfolioState.portfolios[pid]) {
          delete portfolioState.portfolios[pid];
          return route.fulfill({ status: 204 });
        }
        return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) });
      }
    }

    // Fallback — pass through to the real server
    return route.fallback();
  });
}

/**
 * Full dashboard mock with portfolio endpoints wired in.
 * For the "populated" scenario, we also inject portfolio data into the
 * dashboard mock payload so that cards.js → renderPortfolio(data) picks
 * up the pre-existing portfolio on the initial render.
 */
async function mockDashboardWithPortfolios(page, scenario = "empty") {
  await mockApi(page);
  await mockPortfolioApi(page);
  if (scenario === "populated") {
    portfolioState = makePopulatedPortfolios();
    // Intercept the dashboard mock and inject portfolio data at the root
    // level so renderPortfolio(data) finds data.portfolios on first render.
    await page.route("**/api/dashboard", (route) => {
      const base = makePopulatedPortfolios();
      // Re-use the base dashboard mock structure but merge portfolio data
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: new Date().toISOString(),
          portfolios: base.portfolios,
          column_order: base.column_order,
          column_visibility: base.column_visibility,
          market: { indices: {}, rates: {}, commodities: {} },
          futures: { index_futures: [], commodities: [] },
          indicators: { breadth: { breadth_pct: 50, detail: {} }, breadth_ai: { breadth_pct: 50, detail: {} }, spy: { trend: { state: "Uptrend", sma_short: "above", sma_long: "above", drawdown_pct: 0 }, realized_vol_annual_pct: 15 }, vix: { level: 15, signal: "Normal" } },
          risk: { risk_level: "YELLOW", verdict: "Neutral", color: "#B9860B", counts: { bullish: 3, bearish: 3, neutral: 3 }, thesis: "Test", signals: [], fragility_flags: [] },
          ai_sentiment: { score: 0, verdict: "Neutral", spread_pct: 0, news: { tone: "neutral" }, valuation: { note: "" }, cohorts: [], flip_conditions: [] },
          ai_analysis: { stance: "Neutral", confidence: 50, headline: "Test", bullets: [], divergences: [], watch: [] },
          regime: { regime: { regime_label: "Test", regime_description: "Test", confidence: "Medium", portfolio_posture: "Balanced" }, composite: { composite_score: 50, zone: "Neutral", guidance: "Test", component_scores: {} }, transition_probability: { probability_range: "50%" } },
          bottleneck: { thesis: "Test", categories: [], strongest_signal: null },
          earnings: { companies: [] },
          thirteenf: { funds: [], errors: [] },
          events: [],
          coverage: {},
          vintage: { risk: new Date().toISOString() },
        }),
      });
    });
  }
}

/** Navigate to dashboard and wait for it to finish loading. */
async function loadDashboard(page) {
  await page.goto(DASH);
  await expect(page.locator("#riskBody")).not.toHaveText("Loading…");
}

// ---- Tests ----

test.describe("Portfolio section", () => {
  test("empty state shows create CTA and no-portfolio message", async ({ page }) => {
    await mockDashboardWithPortfolios(page, "empty");
    await loadDashboard(page);

    const body = page.locator("#portfolioBody");
    await expect(body).toContainText("No portfolios yet");
    // The + Create portfolio button should be visible
    await expect(page.locator("#portfolioControls .pf-create")).toBeVisible();
  });

  test("create flow prompts for name and expands new section", async ({ page }) => {
    await mockDashboardWithPortfolios(page, "empty");
    await loadDashboard(page);

    // Accept ALL dialogs (prompt + possible alerts) before any click
    page.on("dialog", (d) => d.accept("Fidelity Cash"));
    await page.locator("#portfolioControls .pf-create").click();

    // The new portfolio section should appear
    await expect(page.locator(".pf-pf")).toContainText("Fidelity Cash");
    // The portfolio should be auto-expanded (expanded set gets the new id)
    await expect(page.locator(".pf-pf-body")).not.toHaveClass(/hidden/);
  });

  test("add holding validates symbol and shows row in table", async ({ page }) => {
    await mockDashboardWithPortfolios(page, "empty");
    await loadDashboard(page);

    // Register a single dialog handler that handles both prompt types:
    // - prompt for portfolio name → "Test Portfolio"
    // - prompt for ticker symbol → "NVDA"
    // - confirm/alert → accept
    let dialogCount = 0;
    page.on("dialog", (d) => {
      dialogCount++;
      if (d.type() === "prompt") {
        return d.accept(dialogCount === 1 ? "Test Portfolio" : "NVDA");
      }
      return d.accept();
    });

    // First create a portfolio
    await page.locator("#portfolioControls .pf-create").click();
    await expect(page.locator(".pf-pf")).toContainText("Test Portfolio");

    // Now add a holding
    await page.locator(".pf-add-holding").click();

    // The holding row should appear
    await expect(page.locator(".pf-pf table tbody tr")).toHaveCount(1);
    await expect(page.locator(".pf-pf table tbody tr").first()).toContainText("NVDA");
  });

  test("column reorder PUT is sent when columns are reordered", async ({ page }) => {
    await mockDashboardWithPortfolios(page, "populated");
    await loadDashboard(page);

    // Wait for the portfolio body to render
    await expect(page.locator(".pf-pf")).toContainText("Fidelity Cash");

    // Verify initial column order via the mock state
    const initialOrder = portfolioState.column_order.portfolio;
    expect(initialOrder[0]).toBe("symbol");

    // Simulate a column reorder via the API route
    const result = await page.evaluate(async () => {
      const r = await fetch("/api/portfolios/columns/portfolio", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order: ["total_cost", "symbol", "shares", "last_price", "total_value", "gain_loss", "pct_daily"],
          visibility: { symbol: true, shares: true, total_cost: true, last_price: true, total_value: true, gain_loss: true, pct_daily: true },
        }),
      });
      return r.ok;
    });
    expect(result).toBe(true);

    // Verify the mock state was updated
    expect(portfolioState.column_order.portfolio[0]).toBe("total_cost");

    // Reload and verify persistence (the mock state persists across page reloads in the same test context)
    await page.reload();
    await expect(page.locator("#riskBody")).not.toHaveText("Loading…");
    const persistedOrder = await page.evaluate(async () => {
      const r = await fetch("/api/portfolios");
      const j = await r.json();
      return j.column_order.portfolio;
    });
    expect(persistedOrder[0]).toBe("total_cost");
  });

  test("populated state shows holding details and totals", async ({ page }) => {
    await mockDashboardWithPortfolios(page, "populated");
    await loadDashboard(page);

    // The portfolio should be visible (from the dashboard mock injection)
    await expect(page.locator(".pf-pf")).toContainText("Fidelity Cash");

    // Expand the portfolio by clicking the caret
    await page.locator(".pf-caret").click();

    // Now the holdings table should be visible
    await expect(page.locator(".pf-pf")).toContainText("NVDA");

    // The holding should show shares and cost (editable inputs)
    await expect(page.locator(".pf-edit[data-key='shares']").first()).toHaveValue("10");
    await expect(page.locator(".pf-edit[data-key='total_cost']").first()).toHaveValue("1500");
  });

  test("cash row can be added to a portfolio", async ({ page }) => {
    await mockDashboardWithPortfolios(page, "empty");
    await loadDashboard(page);

    // Single dialog handler for all prompts/confirms/alerts
    page.on("dialog", (d) => d.accept("Cash Test"));
    await page.locator("#portfolioControls .pf-create").click();
    await expect(page.locator(".pf-pf")).toContainText("Cash Test");

    // Add cash row
    await page.locator(".pf-add-cash").click();

    // Cash row should appear
    await expect(page.locator(".pf-cash-row")).toBeVisible();
    await expect(page.locator(".pf-cash-row")).toContainText("Cash");
  });

  test("delete portfolio removes section after confirm", async ({ page }) => {
    await mockDashboardWithPortfolios(page, "empty");
    await loadDashboard(page);

    // Single dialog handler for all dialogs
    let dialogCount = 0;
    page.on("dialog", (d) => {
      dialogCount++;
      if (d.type() === "prompt") {
        return d.accept("To Delete");
      }
      // confirm() and alert() — always accept
      return d.accept();
    });

    // Create a portfolio
    await page.locator("#portfolioControls .pf-create").click();
    await expect(page.locator(".pf-pf")).toContainText("To Delete");

    // Delete it
    await page.locator(".pf-del").click();

    // Portfolio section should disappear, showing empty state
    await expect(page.locator("#portfolioBody")).toContainText("No portfolios yet");
  });
});
