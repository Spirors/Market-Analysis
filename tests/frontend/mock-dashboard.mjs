// Shared mock for the dashboard e2e test.
//
// The frontend is exercised WITHOUT the real backend: /api/dashboard and
// /api/meta are intercepted, and the Chart.js CDN is aborted (the renderers
// degrade to placeholder text when window.Chart is missing, which is fine).
//
// Each /api/dashboard call gets a fresh `as_of` (a counter is appended), so
// tests can assert that clicking global Refresh actually re-fetches and
// re-renders instead of silently no-op'ing.

let dashboardCalls = 0;

export function dashboardCallCount() {
  return dashboardCalls;
}

export function basePayload() {
  return {
    as_of: "2026-08-30T12:00:00Z",
    market: {
      indices: {
        "^GSPC": { price: 6120.5, pct_change: 0.42 },
        "^NDX": { price: 22410.0, pct_change: 0.61 },
        "^DJI": { price: 44120.0, pct_change: -0.12 },
        "^RUT": { price: 2390.0, pct_change: 0.88 },
      },
      rates: {
        "^TNX": { price: 4.32, pct_change: 0.03 },
        "^FVX": { price: 4.05, pct_change: -0.01 },
      },
      commodities: {
        "GC=F": { price: 2540.0, pct_change: 0.5 },
        "CL=F": { price: 78.2, pct_change: -1.1 },
      },
    },
    futures: {
      as_of: "2026-08-30T11:55:00Z",
      index_futures: [
        { symbol: "ES=F", last: 6130.0, chg_pct: 0.4 },
        { symbol: "NQ=F", last: 22490.0, chg_pct: 0.58 },
        { symbol: "YM=F", last: 44190.0, chg_pct: -0.1 },
        { symbol: "RTY=F", last: 2400.0, chg_pct: 0.9 },
      ],
      commodities: [
        { symbol: "GC=F", name: "Gold", last: 2541.0, chg_pct: 0.5 },
        { symbol: "CL=F", name: "WTI Crude", last: 78.1, chg_pct: -1.1 },
      ],
    },
    indicators: {
      breadth: {
        breadth_pct: 68,
        detail: {
          XLK: { close: 210, ma: 200, pct_from_ma: 5.0 },
          XLF: { close: 45, ma: 44, pct_from_ma: 2.3 },
        },
      },
      breadth_ai: { breadth_pct: 74, detail: {} },
      spy: {
        trend: { state: "Uptrend", sma_short: "above", sma_long: "above", drawdown_pct: -3.2 },
        realized_vol_annual_pct: 14.5,
      },
      vix: { level: 15.8, signal: "Low / complacent" },
    },
    risk: {
      risk_level: "YELLOW",
      verdict: "Signals divided; fragility building",
      color: "#B9860B",
      counts: { bullish: 4, bearish: 3, neutral: 2 },
      thesis: "Divided signals keep the read neutral, with optimism-side flags creeping in.",
      signals: [
        { name: "Breadth > 50DMA", tone: "bullish", value: "68%", note: "healthy" },
        { name: "VIX vs own MA", tone: "bearish", value: "1.02x", note: "calm" },
      ],
      fragility_flags: [
        { flag: "Consensus optimism in AI names", side: "optimism", flip: "Breadth < 50%" },
      ],
    },
    ai_sentiment: {
      score: 38,
      verdict: "Expansion",
      spread_pct: 8.2,
      news: { tone: "bullish" },
      valuation: { note: "Stretched vs history" },
      cohorts: [
        { name: "AI beneficiaries", roc_3m_pct: 12.4, breadth_pct: 80, tone: "bullish", note: "leading" },
      ],
      flip_conditions: ["AI news tone turns negative"],
    },
    ai_analysis: {
      stance: "Cautious",
      confidence: 62,
      headline: "Cautious: breadth healthy but valuation stretched",
      bullets: ["Breadth above 50DMA is healthy.", "AI sentiment is elevated."],
      divergences: ["Rates vs equity momentum"],
      watch: ["Credit spreads"],
    },
    regime: {
      regime: {
        regime_label: "Transitional",
        regime_description: "Signals are mixed and the market is between regimes.",
        confidence: "Medium",
        portfolio_posture: "Balanced",
      },
      composite: {
        composite_score: 52,
        zone: "Neutral",
        guidance: "Wait-and-watch with elevated chop risk.",
        component_scores: {
          a: { label: "Equity trend (SPX)", score: 60 },
          b: { label: "Credit (HYG/LQD)", score: 48 },
        },
      },
      transition_probability: { probability_range: "35–45%" },
    },
    bottleneck: {
      thesis: "Chokepoints cluster in compute and power.",
      categories: [
        {
          category: "Compute",
          proxy_40d_roc_pct: -6.2,
          streams: {
            upstream: { proxy_40d_roc_pct: -4.1, layers: [{ layer: "Advanced logic", why_scarce: "TSMC capacity", proxies: ["TSM"], proxy_40d_roc_pct: -4.1 }] },
            downstream: { proxy_40d_roc_pct: -2.0, layers: [] },
          },
        },
      ],
      strongest_signal: { layer: "Advanced logic", why_scarce: "TSMC capacity", proxy_40d_roc_pct: -4.1 },
    },
    earnings: {
      companies: [
        { symbol: "NVDA", next_earnings: "2026-08-27", price: 145.2, pct_daily: 2.1, pct_7d: 5.4, high_52w: 150.0, forward_pe: 32.5, forward_peg: 1.4, market_cap_fmt: "$3.6T", sector: "Semiconductors", rec_signal: "Buy", rec_color: "#3B6D11", rec_reason: "Strong momentum" },
      ],
    },
    thirteenf: {
      funds: [
        { name: "Test Fund", quarter: "Q2 2026", n_positions: 42, top: [{ ticker: "NVDA", weight_pct: 12.5 }, { ticker: "MSFT", weight_pct: 9.1 }], link: "https://www.sec.gov/Archives/edgar/data/0001067983/000156459016014950/0001564590-16-014950-index.htm", manager: "Jane Doe" },
      ],
      errors: [],
    },
    events: [
      {
        source: "Wikipedia",
        title: "Fed holds rates steady, signals patience",
        link: "seed://fed-hold",
        published: "2026-08-24T00:00:00",
        date_label: null,
        summary: "The Federal Reserve left rates unchanged.",
        category: "macro",
        actor: "government",
        direction: "neutral",
        region: "us",
        impact: "Critical",
        finance_relevance: 9.2,
        source_weight: 1.2,
        tags: ["macro", "government", "neutral", "us", "ai"],
      },
      {
        source: "Curated (gauge)",
        title: "China unveils stimulus package",
        link: "seed://china-stimulus",
        published: "2026-08-25T00:00:00",
        date_label: "Aug 2026",
        summary: "Beijing announced fresh fiscal stimulus.",
        category: "macro",
        actor: "government",
        direction: "bullish",
        region: "china",
        impact: "High",
        finance_relevance: 5.0,
        source_weight: 0.8,
        tags: ["macro", "government", "bullish", "china"],
      },
      {
        source: "MarketWatch",
        title: "Nvidia earnings beat, guidance raised",
        link: "https://example.com/nvda-earnings",
        published: "2026-08-26T00:00:00",
        date_label: null,
        summary: "Nvidia beat revenue estimates and raised guidance.",
        category: "micro",
        actor: "company",
        direction: "bullish",
        region: "global",
        impact: "High",
        finance_relevance: 7.5,
        source_weight: 1.0,
        tags: ["micro", "company", "bullish", "global", "ai"],
      },
      {
        source: "Korea Herald",
        title: "Korea shipbuilders rally on record orders",
        link: "https://example.com/korea-shipbuilders",
        published: "2026-08-27T00:00:00",
        date_label: null,
        summary: "South Korean shipbuilder shares surged.",
        category: "macro",
        actor: "company",
        direction: "bullish",
        region: "korea",
        impact: "High",
        finance_relevance: 3.0,
        source_weight: 0.7,
        tags: ["macro", "company", "bullish", "korea"],
      },
    ],
    coverage: {
      risk: { ok: 2, total: 3 },
    },
    vintage: {
      risk: "2026-08-30T11:58:00Z",
      events: "2026-08-30T11:59:00Z",
    },
  };
}

// Fresh payload per dashboard call: the counter stamps a new as_of so tests
// can observe that a refresh genuinely re-fetched and re-rendered.
export function dashboardPayload() {
  dashboardCalls += 1;
  const p = basePayload();
  p.as_of = `2026-08-30T12:0${dashboardCalls % 10}:00Z`;
  p.vintage.risk = `2026-08-30T11:5${dashboardCalls % 10}:00Z`;
  return p;
}

export async function mockApi(page) {
  dashboardCalls = 0;
  await page.route("**/api/dashboard", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(dashboardPayload()) })
  );
  await page.route("**/api/refresh?full=true", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
  );
  await page.route("**/api/meta", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ labels: {} }) })
  );
  await page.route("**/api/analysis/history*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
  // Chart.js CDN is intentionally unavailable in tests — renderers degrade.
  await page.route("**/cdn.jsdelivr.net/**", (route) => route.abort());
}