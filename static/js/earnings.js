// Earnings watchlist: column toggles, add/validate/remove tickers, sorting.
// All HTTP goes through api.js; this module owns state + rendering.

import { $, escapeHtml, fmtPrice, fmtPctHtml, fmtFloat } from "./format.js";
import { validateEarningsSymbol, addEarningsSymbol, removeEarningsSymbol } from "./api.js";

let earningsData = { companies: [] };
let earnSort = { key: "date", dir: 1 };
let earnValidateTimer = null;
let earnValidated = null;

const EARN_COLUMNS = [
  { key: "symbol", label: "Ticker", default: true, fmt: (r) => `<b>${escapeHtml(r.symbol)}</b>` },
  { key: "date", label: "Next earnings", default: true, fmt: (r) => escapeHtml(r.next_earnings || r.last_earnings || "—") },
  { key: "price", label: "Last price", default: true, num: true, fmt: (r) => fmtPrice(r.price) },
  { key: "pct_daily", label: "Daily %", default: true, num: true, fmt: (r) => fmtPctHtml(r.pct_daily) },
  { key: "pct_7d", label: "7-day %", default: true, num: true, fmt: (r) => fmtPctHtml(r.pct_7d) },
  { key: "high_52w", label: "52W high", default: true, num: true, fmt: (r) => fmtPrice(r.high_52w) },
  { key: "forward_pe", label: "Forward PE", default: true, num: true, fmt: (r) => fmtFloat(r.forward_pe) },
  { key: "forward_peg", label: "Forward PEG", default: false, num: true, fmt: (r) => fmtFloat(r.forward_peg) },
  { key: "market_cap_fmt", label: "Market cap", default: false, num: true, fmt: (r) => escapeHtml(r.market_cap_fmt ?? "—") },
  { key: "sector", label: "Sector", default: false, num: true, fmt: (r) => escapeHtml(r.sector || "—") },
  { key: "rec", label: "AI rec", default: true, fmt: (r) => `<span class="earn-rec" style="background:${r.rec_color}22;color:${r.rec_color};border:1px solid ${r.rec_color}" title="${escapeHtml(r.rec_reason || "")}">${escapeHtml(r.rec_signal || "—")}</span>` },
];

function loadVisibleEarnCols() {
  try {
    const saved = JSON.parse(localStorage.getItem("earnVisibleCols"));
    if (Array.isArray(saved) && saved.length) return new Set(saved);
  } catch (e) { /* ignore */ }
  return new Set(EARN_COLUMNS.filter((c) => c.default).map((c) => c.key));
}

function saveVisibleEarnCols() {
  try {
    localStorage.setItem("earnVisibleCols", JSON.stringify([...visibleEarnCols]));
  } catch (e) { /* ignore */ }
}

let visibleEarnCols = loadVisibleEarnCols();

// Personal watch flags (the star column). Each symbol carries a color so the
// watchlist can be triaged visually with three colors. Left-click on the star
// cycles amber -> bull -> bear -> amber; right-click clears the watch
// entirely. The colors are pure visual markers — no sentiment is implied.
// Persisted under "earnWatchColors" as { "SYMBOL": "amber"|"bull"|"bear" }.
// The legacy "earnWatched" array (pre-tier, plain symbols) is migrated on
// first load — every starred symbol becomes amber.
// saveEarnWatchColors() prunes symbols that are no longer in the current list
// so a removed ticker's flag dies with it instead of lingering as an orphan
// in localStorage.
const WATCH_COLORS = ["amber", "bull", "bear"];

function loadEarnWatchColors() {
  try {
    const saved = JSON.parse(localStorage.getItem("earnWatchColors"));
    if (saved && typeof saved === "object" && !Array.isArray(saved)) {
      const out = new Map();
      for (const [sym, color] of Object.entries(saved)) {
        if (WATCH_COLORS.includes(color)) out.set(sym, color);
      }
      return out;
    }
  } catch (e) { /* ignore */ }
  // Migrate legacy earnWatched (plain array of symbols) -> all amber.
  try {
    const legacy = JSON.parse(localStorage.getItem("earnWatched"));
    if (Array.isArray(legacy) && legacy.length) {
      const out = new Map();
      for (const sym of legacy) if (sym) out.set(sym, "amber");
      return out;
    }
  } catch (e) { /* ignore */ }
  return new Map();
}

function saveEarnWatchColors() {
  const live = new Set((earningsData.companies || []).map((r) => r.symbol));
  const obj = {};
  for (const [sym, color] of watchColors.entries()) {
    if (live.has(sym)) obj[sym] = color;
  }
  try {
    localStorage.setItem("earnWatchColors", JSON.stringify(obj));
  } catch (e) { /* ignore */ }
}

function nextWatchColor(current) {
  const idx = WATCH_COLORS.indexOf(current);
  // Unwatched (idx === -1) starts at amber; any tiered color advances one
  // slot, wrapping bear -> amber.
  if (idx < 0) return WATCH_COLORS[0];
  return WATCH_COLORS[(idx + 1) % WATCH_COLORS.length];
}

let watchColors = loadEarnWatchColors();

export function renderEarnings(earn) {
  earningsData = earn || { companies: [] };
  drawEarningsControls();
  drawEarnings();
}

function earnKey(r) {
  if (earnSort.key === "symbol") return r.symbol || "";
  if (earnSort.key === "date") return r.next_earnings || r.last_earnings || "";
  const v = r[earnSort.key];
  if (v == null) return -Infinity;
  return Number(v);
}

function drawEarningsControls() {
  const el = $("#earnControls");
  if (!el) return;
  el.innerHTML = `
    <div class="earn-actions">
      <div class="earn-cols">
        <button id="earnColsBtn" class="mini">Columns</button>
        <div id="earnColsMenu" class="earn-cols-menu hidden">
          ${EARN_COLUMNS.map((c) => `
            <label><input type="checkbox" data-col="${c.key}" ${visibleEarnCols.has(c.key) ? "checked" : ""}> ${escapeHtml(c.label)}</label>
          `).join("")}
        </div>
      </div>
    </div>
    <div class="earn-add">
      <input id="earnInput" placeholder="Add ticker (e.g. NVDA)" autocomplete="off">
      <button id="earnAddBtn" disabled>Add</button>
      <span id="earnInputStatus" class="earn-status"></span>
    </div>
  `;

  $("#earnColsBtn").addEventListener("click", (e) => {
    e.stopPropagation();
    $("#earnColsMenu").classList.toggle("hidden");
  });
  $("#earnColsMenu").querySelectorAll("input").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) visibleEarnCols.add(cb.dataset.col); else visibleEarnCols.delete(cb.dataset.col);
      saveVisibleEarnCols();
      drawEarnings();
    });
  });
  // Note: the outside-click close for #earnColsMenu is bound ONCE in
  // initLayoutTools() — binding it here leaked a document listener per render.

  const input = $("#earnInput");
  input.addEventListener("input", () => {
    earnValidated = null;
    setEarnStatus("", "");
    $("#earnAddBtn").disabled = true;
    clearTimeout(earnValidateTimer);
    const sym = input.value.trim().toUpperCase();
    if (!sym) return;
    earnValidateTimer = setTimeout(() => validateEarningsTicker(sym), 400);
  });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") tryAddEarningsTicker(); });

  $("#earnAddBtn").addEventListener("click", tryAddEarningsTicker);
}

function setEarnStatus(text, cls) {
  const st = $("#earnInputStatus");
  if (!st) return;
  st.textContent = text;
  st.className = "earn-status " + (cls || "");
}

async function validateEarningsTicker(sym) {
  if (!sym) return;
  setEarnStatus("checking…", "muted");
  try {
    const data = await validateEarningsSymbol(sym);
    if (data.valid) {
      earnValidated = data.symbol;
      setEarnStatus(`${data.name}${data.sector ? " · " + data.sector : ""}`, "ok");
      $("#earnAddBtn").disabled = false;
    } else {
      earnValidated = null;
      setEarnStatus("Ticker not found", "bad");
      $("#earnAddBtn").disabled = true;
    }
  } catch (e) {
    earnValidated = null;
    setEarnStatus("Validation failed", "bad");
    $("#earnAddBtn").disabled = true;
  }
}

async function tryAddEarningsTicker() {
  const input = $("#earnInput");
  const sym = (input.value || "").trim().toUpperCase();
  if (!sym) return;
  if (earnValidated !== sym) {
    await validateEarningsTicker(sym);
    if (earnValidated !== sym) return;
  }
  await addEarningsTicker(sym);
}

function drawEarnings() {
  const el = $("#earningsBody");
  const rows = earningsData.companies || [];
  const sorted = [...rows].sort((a, b) => {
    const ka = earnKey(a), kb = earnKey(b);
    if (typeof ka === "string" && typeof kb === "string") {
      if (ka < kb) return -1 * earnSort.dir;
      if (ka > kb) return 1 * earnSort.dir;
      return 0;
    }
    if (ka < kb) return -1 * earnSort.dir;
    if (ka > kb) return 1 * earnSort.dir;
    return 0;
  });

  const cols = EARN_COLUMNS.filter((c) => visibleEarnCols.has(c.key));
  const th = (c) => `<th class="sortable${c.num ? " num" : ""}${earnSort.key === c.key ? (earnSort.dir > 0 ? " asc" : " desc") : ""}" data-key="${c.key}">${escapeHtml(c.label)}</th>`;
  // Watching star column: a personal action column, deliberately OUTSIDE the
  // EARN_COLUMNS toggle menu (it's not data). Empty header keeps it quiet;
  // the row stars carry the meaning.
  const watchTh = `<th class="earn-watch-th" title="Watching"></th>`;
  let html = `<table><thead><tr>${watchTh}${cols.map(th).join("")}<th></th></tr></thead><tbody>`;
  if (!rows.length) {
    html += `<tr><td colspan="${cols.length + 2}">No tickers yet. Add one above.</td></tr>`;
  } else {
    for (const r of sorted) {
      const watchColor = watchColors.get(r.symbol) || null;
      const rowCls = watchColor ? ` class="earn-row-${watchColor}"` : "";
      const starTitle = watchColor
        ? `${r.symbol} · ${watchColor} (left-click cycles color, right-click clears)`
        : `Watch ${r.symbol} (left-click cycles color, right-click clears)`;
      html += `<tr${rowCls}>` +
        `<td class="earn-watch-cell"><button type="button" class="earn-star" data-sym="${escapeHtml(r.symbol)}" data-color="${watchColor || ""}" aria-pressed="${watchColor ? "true" : "false"}" title="${escapeHtml(starTitle)}">${watchColor ? "★" : "☆"}</button></td>` +
        cols.map((c) => `<td${c.num ? " class=\"num\"" : ""}>${c.fmt(r)}</td>`).join("") +
        `<td><button class="mini-del" data-sym="${escapeHtml(r.symbol)}" title="Remove">✕</button></td></tr>`;
    }
  }
  html += `</tbody></table>`;
  el.innerHTML = html;

  el.querySelectorAll("th.sortable").forEach((h) => h.addEventListener("click", () => {
    const k = h.dataset.key;
    if (earnSort.key === k) earnSort.dir *= -1; else { earnSort.key = k; earnSort.dir = 1; }
    drawEarnings();
  }));

  el.querySelectorAll(".mini-del").forEach((b) => b.addEventListener("click", () => removeEarningsTicker(b.dataset.sym)));
  el.querySelectorAll(".earn-star").forEach((b) => {
    b.addEventListener("click", (e) => {
      e.preventDefault();
      cycleEarnWatch(b.dataset.sym);
    });
    b.addEventListener("contextmenu", (e) => {
      // Right-click clears the watch entirely; suppress the browser menu so
      // the star stays the only affordance users need to remember.
      e.preventDefault();
      clearEarnWatch(b.dataset.sym);
    });
  });
}

function cycleEarnWatch(sym) {
  watchColors.set(sym, nextWatchColor(watchColors.get(sym)));
  saveEarnWatchColors();
  drawEarnings();
}

function clearEarnWatch(sym) {
  watchColors.delete(sym);
  saveEarnWatchColors();
  drawEarnings();
}

async function addEarningsTicker(sym) {
  try {
    const data = await addEarningsSymbol(sym);
    earnValidated = null;
    const input = $("#earnInput");
    if (input) input.value = "";
    setEarnStatus("", "");
    renderEarnings(data);
  } catch (e) {
    setEarnStatus(`Failed to add ${sym} (${e.message})`, "bad");
  }
}

async function removeEarningsTicker(sym) {
  try {
    renderEarnings(await removeEarningsSymbol(sym));
    // Drop the star flag with the ticker: saveEarnWatchColors() prunes
    // symbols that are no longer in the list, so no orphan entries accumulate.
    watchColors.delete(sym);
    saveEarnWatchColors();
  } catch (e) {
    setEarnStatus(`Failed to remove ${sym} (${e.message})`, "bad");
  }
}
