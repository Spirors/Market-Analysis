// Fetch orchestration: generation tokens + per-section error routing.
// Every fetch path captures a token before awaiting and bails instead of
// rendering when a newer request has started, so stale responses can never
// overwrite fresh ones. Global loads bump the global token AND every section
// token; single-section refreshes bump only their own.

import { $ } from "./format.js";

// Section id → body container, so fetch errors render into the card that
// actually failed (same plain-text pattern as the risk engine's error state)
// instead of always landing in #riskBody.
const SECTION_ERROR_TARGETS = {
  risk: "#riskBody",
  analysis: "#analysisBody",
  regime: "#regimeBody",
  indicators: "#indicatorBody",
  indices: "#indicesBody",
  rates: "#ratesBody",
  commodities: "#commoditiesBody",
  ai_sentiment: "#aiSentimentBody",
  bottleneck: "#bottleneckBody",
  earnings: "#earningsBody",
  thirteenf: "#thirteenfBody",
  events: "#newsBody",
};
const SECTION_IDS = [...Object.keys(SECTION_ERROR_TARGETS), "breadth", "breadth_ai"];

function renderSectionError(section, e) {
  let el = null;
  if (section === "breadth" || section === "breadth_ai") {
    // Chart cards have no text body — degrade into their .chart-empty slot,
    // mirroring how _renderBarChart shows placeholder content.
    const canvas = $(section === "breadth" ? "#breadthChart" : "#breadthAIChart");
    const box = canvas ? canvas.closest(".chart-box") : null;
    el = box ? box.querySelector(".chart-empty") : null;
    if (el && canvas) {
      canvas.classList.add("hidden");
      el.classList.remove("hidden");
    }
  } else {
    el = document.querySelector(SECTION_ERROR_TARGETS[section] || "");
  }
  if (el) el.textContent = `Failed to load ${section}: ${e.message}`;
}

const gen = { global: 0 };
const sectionGen = {};

let dashboardData = null;

// The dashboard renderers live in cards.js; registering them here (instead of
// importing cards.js) keeps the module graph acyclic — cards.js needs this
// module's fetch helpers too.
let renderSectionFn = null;
export function registerRenderer(fn) {
  renderSectionFn = fn;
}

async function fetchDashboard() {
  const res = await fetch("/api/dashboard");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function load() {
  const g = ++gen.global;
  // A full load also supersedes any in-flight single-section refresh.
  for (const s of SECTION_IDS) sectionGen[s] = (sectionGen[s] || 0) + 1;
  try {
    const data = await fetchDashboard();
    if (gen.global !== g) return; // a newer full load superseded this one
    dashboardData = data;
    $("#asof").textContent = "As of " + (dashboardData.as_of || "—").replace("T", " ").slice(0, 19);
    renderSectionFn("all", dashboardData);
  } catch (e) {
    if (gen.global !== g) return;
    $("#riskBody").textContent = "Failed to load dashboard: " + e.message;
  }
}

export async function refreshSection(section) {
  const btn = document.querySelector(`.section-refresh[data-section="${section}"]`);
  if (btn) { btn.disabled = true; btn.style.opacity = "0.4"; }
  const t = (sectionGen[section] || 0) + 1;
  sectionGen[section] = t;
  try {
    const data = await fetchDashboard();
    if (sectionGen[section] !== t) return; // superseded by a newer refresh
    dashboardData = data;
    // Header as_of is intentionally NOT touched here: a single-card refresh
    // must not desync the header timestamp from the rest of the dashboard.
    renderSectionFn(section, data);
  } catch (e) {
    if (sectionGen[section] === t) renderSectionError(section, e);
  }
  if (btn) { btn.disabled = false; btn.style.opacity = ""; }
}

// ---- Single-purpose API calls (all throw on non-2xx like the callers did) ----

export async function postFullRefresh() {
  const res = await fetch("/api/refresh?full=true", { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function fetchAnalysisHistory(limit = 20) {
  const res = await fetch(`/api/analysis/history?limit=${limit}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function validateEarningsSymbol(symbol) {
  const res = await fetch(`/api/earnings/validate?symbol=${encodeURIComponent(symbol)}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function addEarningsSymbol(symbol) {
  const res = await fetch(`/api/earnings/watchlist?symbol=${encodeURIComponent(symbol)}`, { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function removeEarningsSymbol(symbol) {
  const res = await fetch(`/api/earnings/watchlist?symbol=${encodeURIComponent(symbol)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteEvent(link) {
  const res = await fetch(`/api/events?link=${encodeURIComponent(link)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function suppressSource(source) {
  const res = await fetch(`/api/events/suppress?source=${encodeURIComponent(source)}`, { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
