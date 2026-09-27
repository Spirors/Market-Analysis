// Fetch orchestration: generation tokens + app-level error routing.
// A fetch path captures a token before awaiting and bails instead of
// rendering when a newer request has started, so stale responses can never
// overwrite fresh ones. A refresh/load failure is reported in the header
// status region (never written into a card body).

import { $, fmtTimestampET } from "./format.js";

// Server-side per-section refresh cooldowns, in seconds. Single source of
// truth shared by the Refresh tooltip's "up to" estimate (main.js) and the
// per-card "cached Xm" badge (cards.js) so the two can never drift.
export const COOLDOWN_SECONDS = {
  portfolio: 900,   // 15 min
  breadth_ai: 1800, // 30 min
};

// ---- App-level status region (header) --------------------------------------
// One header region owns every refresh/load failure message, so a transient
// blip can never blank a card body (notably the risk verdict and its vintage
// stamp). "soft" = a refresh failed but the last good payload is still on
// screen; "hard" = nothing has loaded yet. Copy is plain, never alarming, and
// never claims the data is current.
const STATUS_TEXT = {
  soft: "Refresh failed — still showing the last successful data.",
  hard: "Couldn't load data. Try Refresh again.",
};

export function showAppStatus(kind) {
  const el = $("#appStatus");
  if (!el) return;
  const isHard = kind === "hard";
  // Set the role before the text so assistive tech treats a hard failure as a
  // new alert and a soft one as a polite status update.
  el.setAttribute("role", isHard ? "alert" : "status");
  el.setAttribute("aria-live", isHard ? "assertive" : "polite");
  el.dataset.kind = isHard ? "hard" : "soft";
  el.textContent = STATUS_TEXT[isHard ? "hard" : "soft"];
}

export function clearAppStatus() {
  const el = $("#appStatus");
  if (!el) return;
  el.textContent = "";
  delete el.dataset.kind;
  el.setAttribute("role", "status");
  el.setAttribute("aria-live", "polite");
}

const gen = { global: 0 };

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
  try {
    const data = await fetchDashboard();
    if (gen.global !== g) return; // a newer full load superseded this one
    dashboardData = data;
    const asofEl = $("#asof");
    asofEl.textContent = "As of " + fmtTimestampET(dashboardData.as_of) + " ET";
    asofEl.dataset.iso = dashboardData.as_of;
    renderSectionFn("all", dashboardData);
    clearAppStatus();
  } catch (e) {
    if (gen.global !== g) return;
    // Never write into a card body: a prior payload (if any) stays rendered.
    // Only report "hard" when there is no previous payload to fall back on.
    console.error("Dashboard load failed:", e);
    showAppStatus(dashboardData ? "soft" : "hard");
  }
}

// ---- Single-purpose API calls (all throw on non-2xx like the callers did) ----

export async function postFullRefresh() {
  const res = await fetch("/api/refresh?full=true", { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
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

export async function updateEventDimensions(link, dimensions) {
  // dimensions is a dict like {category: "micro", direction: "bearish"} —
  // only the named keys are updated; null/empty clears that dimension.
  // Mirrors the backend's POST /api/events/dimensions endpoint.
  const res = await fetch("/api/events/dimensions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ link, ...dimensions }),
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

// ---- Portfolio section ----

export async function fetchPortfolios() {
  const r = await fetch("/api/portfolios");
  if (!r.ok) throw new Error(`fetchPortfolios failed: ${r.status}`);
  return r.json();
}

export async function createPortfolio(name) {
  const r = await fetch("/api/portfolios?" + new URLSearchParams({ name }), { method: "POST" });
  if (!r.ok) throw new Error((await r.json()).detail || `createPortfolio failed: ${r.status}`);
  return r.json();
}

export async function deletePortfolio(pid) {
  const r = await fetch(`/api/portfolios/${pid}`, { method: "DELETE" });
  if (!r.ok && r.status !== 204) throw new Error(`deletePortfolio failed: ${r.status}`);
}

export async function reorderHoldings(pid, order) {
  const r = await fetch(`/api/portfolios/${pid}/holdings/reorder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order }),
  });
  if (!r.ok) {
    let detail = `reorderHoldings failed: ${r.status}`;
    try {
      const body = await r.json();
      if (body && body.detail) detail = body.detail;
    } catch (e) { /* ignore */ }
    throw new Error(detail);
  }
  return r.json();
}

export async function reorderPortfolios(order) {
  const r = await fetch("/api/portfolios/reorder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order }),
  });
  if (!r.ok) {
    let detail = `reorderPortfolios failed: ${r.status}`;
    try {
      const body = await r.json();
      if (body && body.detail) detail = body.detail;
    } catch (e) { /* ignore */ }
    throw new Error(detail);
  }
  return r.json();
}

export async function renamePortfolio(pid, name) {
  const r = await fetch(`/api/portfolios/${pid}?` + new URLSearchParams({ name }), { method: "PUT" });
  if (!r.ok) throw new Error((await r.json()).detail || `renamePortfolio failed: ${r.status}`);
  return r.json();
}

export async function addPortfolioHolding(pid, holding) {
  const params = new URLSearchParams(holding);
  const r = await fetch(`/api/portfolios/${pid}/holdings?${params}`, { method: "POST" });
  if (!r.ok) throw new Error((await r.json()).detail || `addPortfolioHolding failed: ${r.status}`);
  return r.json();
}

export async function editPortfolioHolding(pid, symbol, patch) {
  const params = new URLSearchParams();
  if (patch.shares != null) params.set("shares", String(patch.shares));
  if (patch.total_cost != null) params.set("total_cost", String(patch.total_cost));
  const r = await fetch(`/api/portfolios/${pid}/holdings/${symbol}?${params}`, { method: "PUT" });
  if (!r.ok) throw new Error((await r.json()).detail || `editPortfolioHolding failed: ${r.status}`);
  return r.json();
}

export async function removePortfolioHolding(pid, symbol) {
  const r = await fetch(`/api/portfolios/${pid}/holdings/${symbol}`, { method: "DELETE" });
  if (!r.ok && r.status !== 204) throw new Error(`removePortfolioHolding failed: ${r.status}`);
}

export async function addPortfolioCash(pid, body) {
  const params = new URLSearchParams(body);
  const r = await fetch(`/api/portfolios/${pid}/cash?${params}`, { method: "POST" });
  if (!r.ok) throw new Error((await r.json()).detail || `addPortfolioCash failed: ${r.status}`);
  return r.json();
}

export async function editPortfolioCash(pid, body) {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(body)) {
    if (v != null) params.set(k, String(v));
  }
  const r = await fetch(`/api/portfolios/${pid}/cash?${params}`, { method: "PUT" });
  if (!r.ok) throw new Error((await r.json()).detail || `editPortfolioCash failed: ${r.status}`);
  return r.json();
}

export async function removePortfolioCash(pid) {
  const r = await fetch(`/api/portfolios/${pid}/cash`, { method: "DELETE" });
  if (!r.ok) throw new Error((await r.json()).detail || `removePortfolioCash failed: ${r.status}`);
  return r.json();
}

export async function validatePortfolioSymbol(sym) {
  const r = await fetch("/api/portfolios/validate?" + new URLSearchParams({ symbol: sym }));
  if (!r.ok) throw new Error(`validatePortfolioSymbol failed: ${r.status}`);
  return r.json();
}

// ---- Bottleneck section (topics + drafting jobs + skill) ----
// The server's error `detail` is the exact user-facing message (missing key,
// missing skill with the install command, a run already in progress, or the
// validator's own messages). It is passed through verbatim — never replaced
// with a generic status string.

// FastAPI returns `detail` as a string or (for validation) a list of
// strings/objects. Normalise both to one readable line so callers can show
// the server's own wording.
async function _detailFrom(res, fallback) {
  try {
    const body = await res.json();
    const detail = body && body.detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (typeof d === "string" ? d : (d && d.msg) || JSON.stringify(d)))
        .join("; ");
    }
    if (detail != null) return String(detail);
  } catch (e) { /* non-JSON body */ }
  return fallback;
}

// One call renders the whole section: raw stored topics (edit forms), the
// computed payload (topic blocks with tiers + momentum), and whether the
// drafting agent is available.
export async function fetchBottleneckTopics() {
  const r = await fetch("/api/bottleneck/topics");
  if (!r.ok) throw new Error(`fetchBottleneckTopics failed: ${r.status}`);
  return r.json();
}

export async function createBottleneckTopic(name) {
  const r = await fetch("/api/bottleneck/topics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!r.ok) throw new Error(await _detailFrom(r, `createBottleneckTopic failed: ${r.status}`));
  return r.json();
}

export async function updateBottleneckTopic(id, patch) {
  const r = await fetch(`/api/bottleneck/topics/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(await _detailFrom(r, `updateBottleneckTopic failed: ${r.status}`));
  return r.json();
}

export async function deleteBottleneckTopic(id) {
  const r = await fetch(`/api/bottleneck/topics/${encodeURIComponent(id)}`, { method: "DELETE" });
  // DELETE answers 204 with no body; only a real failure throws.
  if (!r.ok && r.status !== 204) {
    throw new Error(await _detailFrom(r, `deleteBottleneckTopic failed: ${r.status}`));
  }
}

export async function exportBottleneckTopics() {
  const r = await fetch("/api/bottleneck/topics/export");
  if (!r.ok) throw new Error(`exportBottleneckTopics failed: ${r.status}`);
  return r.json();
}

export async function importBottleneckTopics(doc) {
  const r = await fetch("/api/bottleneck/topics/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(doc),
  });
  if (!r.ok) throw new Error(await _detailFrom(r, `importBottleneckTopics failed: ${r.status}`));
  return r.json();
}

// 409 means a precondition failed; `detail` is the exact message to surface.
export async function generateBottleneckTopic(body) {
  const r = await fetch("/api/bottleneck/topics/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await _detailFrom(r, `generateBottleneckTopic failed: ${r.status}`));
  return r.json();
}

// The list endpoint returns a bare array in the current server; tolerate a
// `{jobs: [...]}` envelope too so the front-end is robust to either shape.
export async function fetchBottleneckJobs() {
  const r = await fetch("/api/bottleneck/jobs");
  if (!r.ok) throw new Error(`fetchBottleneckJobs failed: ${r.status}`);
  const body = await r.json();
  return Array.isArray(body) ? body : (body && body.jobs) || [];
}

export async function fetchBottleneckJob(id) {
  const r = await fetch(`/api/bottleneck/jobs/${encodeURIComponent(id)}`);
  if (!r.ok) throw new Error(await _detailFrom(r, `fetchBottleneckJob failed: ${r.status}`));
  return r.json();
}

export async function cancelBottleneckJob(id) {
  const r = await fetch(`/api/bottleneck/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" });
  if (!r.ok) throw new Error(await _detailFrom(r, `cancelBottleneckJob failed: ${r.status}`));
  return r.json();
}

export async function applyBottleneckJob(id, body) {
  const r = await fetch(`/api/bottleneck/jobs/${encodeURIComponent(id)}/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await _detailFrom(r, `applyBottleneckJob failed: ${r.status}`));
  return r.json();
}

export async function fetchBottleneckSkillStatus() {
  const r = await fetch("/api/bottleneck/skill/status");
  if (!r.ok) throw new Error(`fetchBottleneckSkillStatus failed: ${r.status}`);
  return r.json();
}

// Spawns the installer CLI. A non-zero exit is a 200 with `ok: false` — an
// outcome to report, not an exception.
export async function refreshBottleneckSkill() {
  const r = await fetch("/api/bottleneck/skill/refresh", { method: "POST" });
  if (!r.ok) throw new Error(await _detailFrom(r, `refreshBottleneckSkill failed: ${r.status}`));
  return r.json();
}
