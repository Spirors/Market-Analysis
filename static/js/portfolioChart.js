// portfolioChart.js — "Portfolio Performance" panel: a gain-over-time line
// chart for the Portfolio card, rendered inside the card above the holdings
// tables.
//
// It lives in the card but OUTSIDE #portfolioBody, because portfolio.js's
// renderBody() rebuilds that container wholesale (innerHTML = "") on every
// collapse/expand and section render; the panel's container (#portfolioHistory)
// and its single <canvas> are static chrome in index.html, so the chart never
// gets wiped. On every redraw the previous Chart.js instance is destroyed
// before the new one is built — the same window[instanceKey] retention pattern
// cards.js uses (see _renderBarChart) — so no duplicate canvas or leaked
// instance can accumulate across re-renders.
//
// Data comes from GET /api/portfolios/history (frozen contract): per-portfolio
// desc-order-free ascending snapshot series (actual) plus a `retrospective`
// series (current holdings applied backwards). A null gain is a GAP (spanGaps
// off), never a zero. A portfolio's line colour is assigned from the full
// portfolio list (hash start + linear probe), so it stays stable as siblings are
// toggled on and off (never selection order) and no two portfolios collide
// within the 8-colour palette.

import { $, escapeHtml, fmtPrice } from "./format.js";
import * as API from "./api.js";

// Per-portfolio selection, following the portfolio.* localStorage family
// (pfExpanded / pfSort.* / pfVisible.* / pfOrder.*). Stores a JSON array of
// selected ids; a missing key means "no explicit choice yet" -> default all.
const SELECTION_KEY = "pfHistorySelected";
const INSTANCE_KEY = "portfolioHistoryInstance";

// Deterministic colour per portfolio id (hash -> palette slot), so toggling
// one portfolio never recolours another. Mirrors cards.js's palette family.
const PALETTE = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948", "#B07AA1", "#FF9DA7"];

const EMPTY_HISTORY = "History starts with your first snapshot \u2014 it builds after the next scheduled refresh.";
const EMPTY_SELECTION = "Select at least one portfolio to plot.";
const RETRO_NOTE = "Dashed = retrospective: current holdings applied backwards (not actual history)";

let historyData = null; // last /api/portfolios/history payload
let loading = null;     // in-flight fetch guard (avoids parallel requests)
let colorMap = new Map(); // id -> colour, rebuilt per draw from the full list

// Base palette slot for an id (hash -> slot 0..7). Collisions are resolved by
// colorMapForPortfolios, never by hashing alone.
function hashSlot(id) {
  const s = String(id == null ? "" : id);
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h % PALETTE.length;
}

// Deterministic, collision-free id -> colour for the FULL portfolio list (server
// order, never the selection). Each portfolio starts at its hash slot and
// linear-probes forward (wrapping) to the first slot no EARLIER portfolio in the
// list has taken. So the map depends only on the list, stays stable as the
// selection toggles, is distinct for up to PALETTE.length portfolios, and is
// reproducible across reloads. One shared map feeds both the selector swatches
// and the dataset colours.
function colorMapForPortfolios(portfolios) {
  const used = new Set();
  const map = new Map();
  for (const p of portfolios) {
    const id = String(p.id);
    let slot = hashSlot(id);
    for (let probe = 0; probe < PALETTE.length && used.has(slot); probe++) {
      slot = (slot + 1) % PALETTE.length;
    }
    used.add(slot);
    map.set(id, PALETTE[slot]);
  }
  return map;
}

function loadSelection() {
  try {
    const v = JSON.parse(localStorage.getItem(SELECTION_KEY));
    if (Array.isArray(v)) return new Set(v.filter((x) => typeof x === "string"));
  } catch (e) { /* ignore */ }
  return null; // null = no stored choice -> default to all
}

function saveSelection(set) {
  try { localStorage.setItem(SELECTION_KEY, JSON.stringify([...set])); } catch (e) { /* ignore */ }
}

// The selection to render: every id when nothing is stored, else the stored
// ids intersected with the portfolios that still exist (stale ids dropped). An
// explicitly empty stored array is meaningful — it means "user deselected all".
function computeSelection(portfolios) {
  const ids = portfolios.map((p) => p.id);
  const stored = loadSelection();
  if (stored === null) return new Set(ids);
  return new Set(ids.filter((id) => stored.has(id)));
}

function readSelectionFromDOM() {
  const set = new Set();
  const boxes = document.querySelectorAll("#portfolioHistorySelect input[type=checkbox]");
  boxes.forEach((c) => { if (c.checked) set.add(c.dataset.pid); });
  return set;
}

// date -> gain (null preserved as a gap). Returns an object so `d in map`
// distinguishes "no point for this date" from "point with a null gain".
function indexByDate(points, field) {
  const map = {};
  for (const pt of points || []) {
    if (!pt || !pt.date) continue;
    map[pt.date] = pt[field] == null ? null : pt[field];
  }
  return map;
}

function latestSnapshotDate(snapshots) {
  let latest = null;
  for (const arr of Object.values(snapshots || {})) {
    for (const pt of arr || []) {
      if (pt && pt.date && (!latest || pt.date > latest)) latest = pt.date;
    }
  }
  return latest;
}

function destroyInstance() {
  if (window[INSTANCE_KEY]) {
    window[INSTANCE_KEY].destroy();
    window[INSTANCE_KEY] = null;
  }
}

function showEmpty(msg) {
  const canvas = $("#portfolioHistoryChart");
  const emptyEl = $("#portfolioHistoryEmpty");
  if (canvas) canvas.classList.add("hidden");
  if (emptyEl) { emptyEl.textContent = msg; emptyEl.classList.remove("hidden"); }
}

function showCanvas() {
  const canvas = $("#portfolioHistoryChart");
  const emptyEl = $("#portfolioHistoryEmpty");
  if (canvas) canvas.classList.remove("hidden");
  if (emptyEl) { emptyEl.classList.add("hidden"); emptyEl.textContent = ""; }
}

// Selector legend: one checkbox + colour swatch per portfolio, default checked
// from the persisted choice. Re-wired on each rebuild; a toggle redraws the
// chart only (the selector DOM is left alone so focus is not lost).
function renderSelector(portfolios, selected) {
  const el = $("#portfolioHistorySelect");
  if (!el) return;
  el.innerHTML = portfolios.map((p) => {
    const checked = selected.has(p.id) ? " checked" : "";
    return `<label class="pf-hist-choice">`
      + `<input type="checkbox" data-pid="${escapeHtml(p.id)}"${checked}>`
      + `<span class="pf-hist-swatch" style="background:${colorMap.get(String(p.id))}"></span>`
      + `<span class="pf-hist-name">${escapeHtml(p.name || p.id)}</span>`
      + `</label>`;
  }).join("");
  el.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    cb.addEventListener("change", () => {
      const known = portfolios.map((p) => p.id);
      const chosen = readSelectionFromDOM();
      saveSelection(new Set(known.filter((id) => chosen.has(id))));
      renderChart(portfolios);
    });
  });
}

// Build datasets + draw, or render the right empty state. Reads the live
// checkbox state so a toggle can call this on its own.
function renderChart(portfolios) {
  const metaEl = $("#portfolioHistoryMeta");
  const noteEl = $("#portfolioHistoryNote");
  const selected = readSelectionFromDOM();
  const payload = historyData || {};
  const snapshots = payload.snapshots || {};
  const retro = payload.retrospective || {};

  if (!selected.size) {
    destroyInstance();
    showEmpty(EMPTY_SELECTION);
    if (metaEl) metaEl.textContent = "";
    if (noteEl) noteEl.textContent = "";
    return;
  }

  // Union of every date across the SELECTED portfolios (actual + retrospective),
  // ascending. ISO date strings sort correctly lexicographically.
  const dateSet = new Set();
  for (const p of portfolios) {
    if (!selected.has(p.id)) continue;
    for (const pt of snapshots[p.id] || []) if (pt && pt.date) dateSet.add(pt.date);
    for (const pt of retro[p.id] || []) if (pt && pt.date) dateSet.add(pt.date);
  }
  const labels = [...dateSet].sort();

  const datasets = [];
  let anyRetro = false;
  for (const p of portfolios) {
    if (!selected.has(p.id)) continue;
    const color = colorMap.get(String(p.id));
    const name = p.name || p.id;
    const solid = indexByDate(snapshots[p.id] || [], "gain");
    const retroPts = indexByDate(retro[p.id] || [], "gain");
    const solidData = labels.map((d) => (d in solid ? solid[d] : null));
    const retroData = labels.map((d) => (d in retroPts ? retroPts[d] : null));

    if (solidData.some((v) => v != null)) {
      datasets.push({
        label: name,
        data: solidData,
        borderColor: color,
        backgroundColor: color,
        fill: false,
        spanGaps: false,
        tension: 0.15,
        pointRadius: 2,
        borderWidth: 2,
      });
    }
    if (retroData.some((v) => v != null)) {
      anyRetro = true;
      datasets.push({
        label: `${name} (retrospective)`,
        data: retroData,
        borderColor: color,
        backgroundColor: color,
        fill: false,
        spanGaps: false,
        tension: 0.15,
        pointRadius: 0,
        borderWidth: 1.5,
        borderDash: [5, 4], // visually subordinate to the solid actual line
      });
    }
  }

  if (!datasets.length) {
    destroyInstance();
    showEmpty(EMPTY_HISTORY);
    if (metaEl) metaEl.textContent = "";
    if (noteEl) noteEl.textContent = "";
    return;
  }

  const latest = latestSnapshotDate(snapshots);
  if (metaEl) metaEl.textContent = latest ? `Gain over time \u00b7 as of close ${latest}` : "Gain over time";
  if (noteEl) noteEl.textContent = anyRetro ? RETRO_NOTE : "";

  if (!window.Chart) {
    // Chart.js unavailable (CDN blocked): keep an honest note rather than a
    // blank box — the numbers are not fabricated.
    destroyInstance();
    showEmpty("Chart unavailable \u2014 Chart.js could not load.");
    return;
  }

  showCanvas();
  destroyInstance();
  const canvas = $("#portfolioHistoryChart");
  window[INSTANCE_KEY] = new Chart(canvas, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      plugins: {
        legend: { display: datasets.length > 1, position: "top" },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y == null ? "\u2014" : fmtPrice(ctx.parsed.y)}`,
          },
        },
      },
      scales: {
        x: { title: { display: true, text: "Date" } },
        y: { title: { display: true, text: "Gain ($)" }, ticks: { callback: (v) => fmtPrice(v) } },
      },
    },
  });
}

function draw() {
  const host = $("#portfolioHistory");
  if (!host) return;
  const payload = historyData;
  const portfolios = (payload && payload.portfolios) || [];
  // No portfolios yet: the card already shows its own empty state — hide the
  // whole panel rather than duplicate it.
  if (!portfolios.length) {
    host.classList.add("hidden");
    destroyInstance();
    return;
  }
  host.classList.remove("hidden");
  colorMap = colorMapForPortfolios(portfolios);
  renderSelector(portfolios, computeSelection(portfolios));
  renderChart(portfolios);
}

// Entry point called from portfolio.js's renderPortfolio — i.e. on every
// section refresh (dashboard load + the card's own fallback refresh). Not on
// collapse/expand or holdings edits, which only call renderBody().
export function renderPortfolioHistory() {
  const host = $("#portfolioHistory");
  if (!host) return;
  if (!loading) {
    loading = API.fetchPortfoliosHistory()
      .then((data) => { historyData = data; })
      .catch((e) => { console.error("portfolio history fetch failed", e); })
      .finally(() => { loading = null; draw(); });
  }
  draw(); // paint immediately from whatever is already loaded
}
