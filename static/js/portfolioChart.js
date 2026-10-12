// portfolioChart.js — "Portfolio Performance" panel: ONE aggregate
// gain-over-time line for the selected set of portfolios, rendered inside the
// Portfolio card above the holdings tables.
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
// ascending snapshot series (actual, recorded settled closes) plus a
// `retrospective` series (current holdings applied backwards). A null gain is a
// GAP (spanGaps off), never a zero.
//
// The plotted series is the SUM across the selected portfolios, per date:
//   total(d) = Σ portfolio value for d, where a portfolio contributes its
//              snapshot gain for d if it has one, else its retrospective gain.
// If ANY selected portfolio has no point or a null gain for d, the total for d
// is null — never a partial sum (the project's "a missing close nulls the
// total" honesty rule, extended across portfolios).
//
// One line, two stretches: the retrospective-only dates (before the first
// recorded snapshot) draw DASHED, everything from the first snapshot date on
// draws SOLID — done inside the single dataset via a scriptable
// `segment.borderDash`, so there is no legend and no second dataset. The
// per-portfolio checkbox row stays: it selects which portfolios feed the total
// (each swatch keeps its own stable colour); the line itself is one fixed
// colour, deliberately outside that per-portfolio palette.

import { $, escapeHtml, fmtPrice } from "./format.js";
import * as API from "./api.js";

// Per-portfolio selection, following the portfolio.* localStorage family
// (pfExpanded / pfSort.* / pfVisible.* / pfOrder.*). Stores a JSON array of
// selected ids; a missing key means "no explicit choice yet" -> default all.
const SELECTION_KEY = "pfHistorySelected";
// Time-range choice for the x window: one of RANGES[].key. Missing/invalid ->
// the default (ALL).
const RANGE_KEY = "pfHistoryRange";
const INSTANCE_KEY = "portfolioHistoryInstance";

// Deterministic colour per portfolio id (hash -> palette slot), so toggling
// one portfolio never recolours another. Mirrors cards.js's palette family.
// Used ONLY for the selector swatches now — the aggregate line is one colour.
const PALETTE = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948", "#B07AA1", "#FF9DA7"];

// The aggregate line's single fixed colour: the app's --blue (#185FA5), kept
// OFF the per-portfolio PALETTE so the total is never mistaken for one
// portfolio's swatch.
const LINE_COLOR = "#185FA5";

const EMPTY_HISTORY = "History starts with your first snapshot \u2014 it builds after the next scheduled refresh.";
const EMPTY_SELECTION = "Select at least one portfolio to plot.";
const CDN_MISSING = "Chart unavailable \u2014 Chart.js could not load.";

// Time-range presets. Window = the last N days of the plotted series (dates
// >= maxDataDate - N days); ALL keeps everything. `fmt` shapes the x-axis so a
// dense daily series never crams rotated labels: short windows show MM-DD with
// a capped sampled tick count (`maxTicks`), while long windows show YYYY-MM
// with EXACTLY one tick per calendar month (the first label of each month) —
// see the afterBuildTicks filter in renderChart.
const RANGES = [
  { key: "1W", days: 7, maxTicks: 8, fmt: "md" },
  { key: "1M", days: 30, maxTicks: 8, fmt: "md" },
  { key: "3M", days: 90, maxTicks: 9, fmt: "md" },
  { key: "6M", days: 180, maxTicks: 10, fmt: "ym" },
  { key: "1Y", days: 365, maxTicks: 12, fmt: "ym" },
  { key: "ALL", days: null, maxTicks: 12, fmt: "ym" },
];
const DEFAULT_RANGE = "ALL";

let historyData = null; // last /api/portfolios/history payload
let loading = null;     // in-flight fetch guard (avoids parallel requests)
let colorMap = new Map(); // id -> swatch colour, rebuilt per draw from the full list

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
// reproducible across reloads. Feeds the selector swatches.
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

function loadRange() {
  try {
    const v = localStorage.getItem(RANGE_KEY);
    if (v && RANGES.some((r) => r.key === v)) return v;
  } catch (e) { /* ignore */ }
  return DEFAULT_RANGE;
}

function saveRange(key) {
  try { localStorage.setItem(RANGE_KEY, key); } catch (e) { /* ignore */ }
}

function rangeSpec(key) {
  return RANGES.find((r) => r.key === key) || RANGES[RANGES.length - 1];
}

// The active range: the pressed button's key, else the stored/default one
// (covers the pre-DOM-render case).
function currentRange() {
  const btn = document.querySelector('#portfolioHistoryRange .pf-range-btn[aria-pressed="true"]');
  return btn ? btn.dataset.range : loadRange();
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

// Earliest recorded snapshot date across the SELECTED portfolios (the date the
// solid stretch begins) — null when nothing selected has a snapshot yet.
function firstSnapshotDate(portfolios, selected, snapshots) {
  let first = null;
  for (const p of portfolios) {
    if (!selected.has(p.id)) continue;
    for (const pt of snapshots[p.id] || []) {
      if (pt && pt.date && (!first || pt.date < first)) first = pt.date;
    }
  }
  return first;
}

// Shift an ISO (YYYY-MM-DD) date by whole days, staying in UTC.
function shiftDays(iso, days) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d) - days * 86400000);
  const yy = dt.getUTCFullYear();
  const mm = String(dt.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(dt.getUTCDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

// x tick label from an ISO date: MM-DD for short windows, YYYY-MM for long.
function fmtTick(iso, fmt) {
  return fmt === "ym" ? iso.slice(0, 7) : iso.slice(5);
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

// The aggregate series over the union of the SELECTED portfolios' dates.
// Returns { labels, data, fromRetro }; data[i] is null when any selected
// portfolio is missing/null for labels[i]; fromRetro[i] is true when any
// portfolio's contribution came from the retrospective series.
function aggregate(portfolios, selected, snapshots, retro) {
  const chosen = portfolios.filter((p) => selected.has(p.id));
  const snaps = chosen.map((p) => indexByDate(snapshots[p.id] || [], "gain"));
  const retros = chosen.map((p) => indexByDate(retro[p.id] || [], "gain"));

  const dateSet = new Set();
  for (let i = 0; i < chosen.length; i++) {
    for (const d of Object.keys(snaps[i])) dateSet.add(d);
    for (const d of Object.keys(retros[i])) dateSet.add(d);
  }
  const labels = [...dateSet].sort();

  const data = [];
  const fromRetro = [];
  for (const d of labels) {
    let total = 0;
    let gap = false;
    let usedRetro = false;
    for (let i = 0; i < chosen.length; i++) {
      let v;
      if (d in snaps[i]) {
        v = snaps[i][d]; // snapshot wins over retrospective on the same date
      } else if (d in retros[i]) {
        v = retros[i][d];
        usedRetro = true;
      } else {
        gap = true; // no point at all for this date -> total is a gap
        break;
      }
      if (v == null) { gap = true; break; } // null gain -> gap, never a partial sum
      total += v;
    }
    data.push(gap ? null : total);
    fromRetro.push(gap ? false : usedRetro);
  }
  return { labels, data, fromRetro };
}

// Note copy explaining the current chart's semantics, grounded in the actual
// data: the solid stretch (recorded snapshots, and when they begin), the dashed
// stretch (retrospective estimate) when the plotted window contains one, and
// the gap meaning. With no recorded snapshot at all, the whole line is a
// retrospective estimate and the note says so.
function noteFor(firstSnap, hasDashed) {
  if (!firstSnap) {
    return "Retrospective estimate from current holdings \u2014 no recorded settled-close snapshots yet. Gaps are missing closes.";
  }
  const head = hasDashed
    ? "Solid = recorded settled-close snapshots; dashed = retrospective estimate from current holdings."
    : "Recorded settled-close snapshots.";
  return `${head} Snapshots begin ${firstSnap}. Gaps are missing closes.`;
}

// Range control: buttons in static chrome, populated once per draw. A click
// updates aria-pressed, persists, and re-renders the chart ONLY — the control
// DOM is left alone so focus is not lost.
function renderRange() {
  const el = $("#portfolioHistoryRange");
  if (!el) return;
  const active = loadRange();
  el.innerHTML = RANGES.map((r) =>
    `<button type="button" class="pf-range-btn" data-range="${escapeHtml(r.key)}" `
    + `aria-pressed="${r.key === active}">${escapeHtml(r.key)}</button>`
  ).join("");
  el.querySelectorAll(".pf-range-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      saveRange(btn.dataset.range);
      el.querySelectorAll(".pf-range-btn").forEach((b) =>
        b.setAttribute("aria-pressed", String(b === btn))
      );
      renderChart((historyData && historyData.portfolios) || []);
    });
  });
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

// Build the aggregate dataset + draw, or render the right empty state. Reads
// the live checkbox/range state so a toggle can call this on its own.
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

  const agg = aggregate(portfolios, selected, snapshots, retro);
  const firstSnap = firstSnapshotDate(portfolios, selected, snapshots);
  const spec = rangeSpec(currentRange());

  // Apply the time window: keep dates >= (maxDate - N days); ALL keeps all.
  let labels = agg.labels;
  let data = agg.data;
  let fromRetro = agg.fromRetro;
  if (spec.days != null && labels.length) {
    const cutoff = shiftDays(labels[labels.length - 1], spec.days);
    const start = labels.findIndex((d) => d >= cutoff);
    if (start > 0) {
      labels = labels.slice(start);
      data = data.slice(start);
      fromRetro = fromRetro.slice(start);
    }
  }

  // Nothing to plot for this selection/window (or every point is a gap).
  if (!labels.length || !data.some((v) => v != null)) {
    destroyInstance();
    showEmpty(EMPTY_HISTORY);
    if (metaEl) metaEl.textContent = "";
    if (noteEl) noteEl.textContent = "";
    return;
  }

  const latest = latestSnapshotDate(snapshots);
  if (metaEl) metaEl.textContent = latest ? `Gain over time \u00b7 as of close ${latest}` : "Gain over time";

  // Index at which the recorded snapshots begin in the PLOTTED window: dates
  // left of it are retrospective-only (dashed), from it on they are solid. No
  // snapshots at all -> the whole line is retrospective.
  const firstSlot = firstSnap ? Math.max(0, labels.findIndex((d) => d >= firstSnap)) : labels.length;
  if (noteEl) noteEl.textContent = noteFor(firstSnap, firstSlot > 0);

  // X-axis ticks. Long windows (fmt "ym") get exactly one tick per calendar
  // month: the month-start indices are filtered in afterBuildTicks, so
  // autoSkip sampling can never show a duplicated month or skip one (the
  // window's first label always counts). Short windows (fmt "md") keep the
  // sampled autoSkip ticks.
  const monthStartIdx = new Set();
  if (spec.fmt === "ym") {
    for (let i = 1; i < labels.length; i++) {
      if (labels[i].slice(0, 7) !== labels[i - 1].slice(0, 7)) monthStartIdx.add(i);
    }
    // The window's first label also anchors its month — but only when it does
    // not crowd the next month tick (a lone Sep 30 one slot before an Oct 1
    // tick would overlap its neighbour). Keep it when it sits near its month's
    // start (day <= 7), when the next boundary is >= 12 labels away, or when
    // the window contains no month boundary at all.
    if (labels.length) {
      let next = -1;
      for (let j = 1; j < labels.length; j++) {
        if (monthStartIdx.has(j)) { next = j; break; }
      }
      const day = Number(labels[0].slice(8, 10));
      if (next === -1 || next >= 12 || day <= 7) monthStartIdx.add(0);
    }
  }
  const xScale = {
    title: { display: true, text: "Date" },
    ticks: spec.fmt === "ym"
      ? {
          autoSkip: false,
          maxRotation: 0,
          callback: (value) => {
            const i = Number(value);
            return fmtTick(labels[i] != null ? labels[i] : String(value), "ym");
          },
        }
      : {
          autoSkip: true,
          maxTicksLimit: spec.maxTicks,
          maxRotation: 0,
          autoSkipPadding: 12,
          callback: (value, index) => fmtTick(
            labels[index] != null ? labels[index] : String(value), spec.fmt
          ),
        },
  };
  if (spec.fmt === "ym") {
    xScale.afterBuildTicks = (axis) => {
      axis.ticks = axis.ticks.filter((t) => monthStartIdx.has(t.value));
    };
  }

  if (!window.Chart) {
    // Chart.js unavailable (CDN blocked): keep an honest note rather than a
    // blank box — the numbers are not fabricated.
    destroyInstance();
    showEmpty(CDN_MISSING);
    return;
  }

  showCanvas();
  destroyInstance();
  const canvas = $("#portfolioHistoryChart");
  const dense = labels.length > 20; // dots help on short windows, clutter dense ones
  window[INSTANCE_KEY] = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Total gain",
        data,
        borderColor: LINE_COLOR,
        backgroundColor: LINE_COLOR,
        fill: false,
        spanGaps: false,
        tension: 0.15,
        borderWidth: 2,
        pointRadius: dense ? 0 : 3,
        pointHoverRadius: 5,
        // Dashed for the retrospective-only stretch, solid from the first
        // recorded snapshot on — one dataset, no legend.
        segment: { borderDash: (ctx) => (ctx.p0DataIndex < firstSlot ? [5, 4] : []) },
      }],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const y = ctx.parsed.y;
              const tag = (y != null && fromRetro[ctx.dataIndex]) ? " (retrospective)" : "";
              return `${ctx.dataset.label}: ${y == null ? "\u2014" : fmtPrice(y)}${tag}`;
            },
          },
        },
      },
      scales: {
        x: xScale,
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
  renderRange();
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
