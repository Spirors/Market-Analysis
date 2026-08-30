// Fetch orchestration: generation tokens + per-section error routing.
// Every fetch path captures a token before awaiting and bails instead of
// rendering when a newer request has started, so stale responses can never
// overwrite fresh ones. Global loads bump the global token AND every section
// token; single-section refreshes bump only their own.

import { $, fmtTimestampET } from "./format.js";

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

// A full load supersedes every in-flight single-section refresh, so it also
// owns their buttons: park all ↻ controls back in the idle state (a superseded
// refresh deliberately never touches the UI — the newer owner does).
function _resetSectionButtons() {
  document.querySelectorAll(".section-refresh").forEach((btn) => {
    btn.disabled = false;
    _setFeedback(btn, "idle");
  });
}

export async function load() {
  const g = ++gen.global;
  // A full load also supersedes any in-flight single-section refresh.
  for (const s of SECTION_IDS) sectionGen[s] = (sectionGen[s] || 0) + 1;
  _resetSectionButtons();
  try {
    const data = await fetchDashboard();
    if (gen.global !== g) return; // a newer full load superseded this one
    dashboardData = data;
    $("#asof").textContent = "As of " + fmtTimestampET(dashboardData.as_of) + " ET";
    renderSectionFn("all", dashboardData);
  } catch (e) {
    if (gen.global !== g) return;
    $("#riskBody").textContent = "Failed to load dashboard: " + e.message;
  }
}

// ---- Per-section refresh feedback -----------------------------------------
// The ↻ button is the feedback surface: it spins while in flight, then shows
// ✓ (green) or ✗ (red) for a beat before reverting. When the server answered
// from cache (payload as_of unchanged) the confirmation renders muted with a
// tiny "cached" tag instead of implying fresh data. The refreshed card also
// answers with one quiet blue ring so the eye finds WHICH card updated.

const FEEDBACK_HOLD_MS = { ok: 1500, "ok-cached": 2400, error: 2400 };

function _setFeedback(btn, state) {
  // state: "idle" | "refreshing" | "ok" | "ok-cached" | "error"
  clearTimeout(btn._fbTimer);
  btn.classList.remove("is-refreshing", "is-ok", "is-error", "is-cached");
  if (btn._hintEl) btn._hintEl.hidden = true;
  switch (state) {
    case "refreshing":
      btn.classList.add("is-refreshing");
      btn.textContent = "↻";
      break;
    case "ok":
    case "ok-cached":
      btn.classList.add("is-ok");
      if (state === "ok-cached") {
        btn.classList.add("is-cached");
        if (!btn._hintEl) {
          const hint = document.createElement("span");
          hint.className = "refresh-hint";
          hint.textContent = "cached";
          btn.after(hint);
          btn._hintEl = hint;
        }
        btn._hintEl.hidden = false;
      }
      btn.textContent = "✓";
      break;
    case "error":
      btn.classList.add("is-error");
      btn.textContent = "✗";
      break;
    default:
      btn.textContent = "↻";
      return; // idle is terminal — no auto-revert
  }
  btn._fbTimer = setTimeout(() => _setFeedback(btn, "idle"), FEEDBACK_HOLD_MS[state]);
}

// One soft ring pulse on the card shell — deliberately a neutral accent so it
// never fights the risk card's semantic GREEN/YELLOW/RED border.
function _pulseCard(card) {
  if (!card) return;
  card.classList.remove("refresh-pulse");
  void card.offsetWidth; // restart the animation on back-to-back refreshes
  card.classList.add("refresh-pulse");
}

export async function refreshSection(section) {
  const btn = document.querySelector(`.section-refresh[data-section="${section}"]`);
  if (btn) {
    if (btn.disabled) return; // one flight per button
    btn.disabled = true;
    _setFeedback(btn, "refreshing");
  }
  const t = (sectionGen[section] || 0) + 1;
  sectionGen[section] = t;
  const prevAsOf = dashboardData ? dashboardData.as_of : null;
  let outcome = "error";
  try {
    const data = await fetchDashboard();
    if (sectionGen[section] !== t) return; // superseded — the newer owner drives the UI
    dashboardData = data;
    // Header as_of is intentionally NOT touched here: a single-card refresh
    // must not desync the header timestamp from the rest of the dashboard.
    renderSectionFn(section, data);
    const asOf = data ? data.as_of : null;
    outcome = prevAsOf && asOf && prevAsOf === asOf ? "ok-cached" : "ok";
  } catch (e) {
    if (sectionGen[section] !== t) return;
    renderSectionError(section, e);
    outcome = "error";
  }
  if (btn) {
    btn.disabled = false;
    _setFeedback(btn, outcome);
    _pulseCard(btn.closest("[data-card]"));
  }
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

export async function updateEventTags(link, add = [], remove = []) {
  const res = await fetch("/api/events/tags", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ link, add, remove }),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body && body.detail) detail = body.detail;
    } catch (e) { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

export async function suppressSource(source) {
  const res = await fetch(`/api/events/suppress?source=${encodeURIComponent(source)}`, { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
