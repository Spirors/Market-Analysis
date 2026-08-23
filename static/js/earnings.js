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
  let html = `<table><thead><tr>${cols.map(th).join("")}<th></th></tr></thead><tbody>`;
  if (!rows.length) {
    html += `<tr><td colspan="${cols.length + 1}">No tickers yet. Add one above.</td></tr>`;
  } else {
    for (const r of sorted) {
      html += `<tr>${cols.map((c) => `<td${c.num ? " class=\"num\"" : ""}>${c.fmt(r)}</td>`).join("")}<td><button class="mini-del" data-sym="${escapeHtml(r.symbol)}" title="Remove">✕</button></td></tr>`;
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
  } catch (e) {
    setEarnStatus(`Failed to remove ${sym} (${e.message})`, "bad");
  }
}
