// portfolio.js — Portfolio card renderer (serenity-style expand/collapse
// per portfolio, cash row, totals footer, grand total in card header).
//
// Holdings come from the same backend as the rest of the app; the card
// shows all portfolios stacked, with each one expanded/collapsed
// independently (state persisted in localStorage).

import { $, escapeHtml, fmtPrice, fmtPctHtml } from "./format.js";
import * as API from "./api.js";

let portfolioData = { portfolios: {}, column_order: {}, column_visibility: {} };
let expanded = loadExpanded();

const PORTFOLIO_COLUMNS = [
  { key: "symbol",     label: "Ticker",      default: true,  num: true,  fmt: (r) => `<b>${escapeHtml(r.symbol || r.label || "\u2014")}</b>` },
  { key: "shares",     label: "Shares",      default: true,  num: true,  editable: true,
    fmt: (r) => r.kind === "cash" ? "\u2014" : (r.shares == null ? "\u2014" : String(r.shares)) },
  { key: "total_cost", label: "Total cost",  default: true,  num: true,  editable: true,
    fmt: (r) => r.total_cost == null ? "\u2014" : fmtPrice(r.total_cost) },
  { key: "last_price", label: "Last price",  default: true,  num: true,
    fmt: (r) => r.kind === "cash" ? "\u2014" : fmtPrice(r.last_price) },
  { key: "total_value",label: "Total value", default: true,  num: true,  editable: r => r.kind === "cash",
    fmt: (r) => r.kind === "cash" ? fmtPrice(r.total_value) : fmtPrice(r.shares != null && r.last_price != null ? r.shares * r.last_price : null) },
  { key: "gain_loss",  label: "Gain/loss",   default: true,  num: true,
    fmt: (r) => {
      const v = r.kind === "cash" ? (r.total_value - r.total_cost) : ((r.shares != null && r.last_price != null) ? r.shares * r.last_price - r.total_cost : null);
      if (v == null) return "\u2014";
      const sign = v >= 0 ? "+" : "";
      return `<span class="${pctClassName(v)}">${sign}${fmtPrice(Math.abs(v))}</span>`;
    } },
  { key: "pct_daily",  label: "Daily %",     default: true,  num: true,
    fmt: (r) => r.kind === "cash" ? "\u2014" : fmtPctHtml(r.pct_daily) },
];

// Ruling 2: clean 3-arm pctClassName (not the convoluted version from the plan).
function pctClassName(v) {
  if (v == null) return "muted";
  if (v > 0) return "pos";
  if (v < 0) return "neg";
  return "muted";
}

function loadExpanded() {
  try {
    const v = JSON.parse(localStorage.getItem("pfExpanded"));
    if (v && typeof v === "object") return new Set(Object.keys(v).filter((k) => v[k]));
  } catch (e) { /* ignore */ }
  return new Set();
}

function saveExpanded() {
  const obj = {};
  for (const id of expanded) obj[id] = true;
  try { localStorage.setItem("pfExpanded", JSON.stringify(obj)); } catch (e) { /* ignore */ }
}

function fmtMoney(v) {
  if (v == null) return "\u2014";
  return fmtPrice(v);
}

function fmtSigned(v) {
  if (v == null) return "\u2014";
  const sign = v >= 0 ? "+" : "\u2212";
  return `${sign}${fmtPrice(Math.abs(v))}`;
}

function portfolioTotals(p) {
  let value = 0, cost = 0;
  for (const h of p.holdings || []) {
    if (h.kind === "cash") { value += h.total_value || 0; cost += h.total_cost || 0; }
    else {
      const v = (h.shares != null && h.last_price != null) ? h.shares * h.last_price : null;
      value += v == null ? 0 : v;
      cost += h.total_cost || 0;
    }
  }
  return { value, cost, gain: value - cost };
}

function grandTotals(state) {
  let value = 0, cost = 0;
  for (const p of Object.values(state.portfolios || {})) {
    const t = portfolioTotals(p);
    value += t.value; cost += t.cost;
  }
  return { value, cost, gain: value - cost };
}

function renderGrandHeader() {
  const card = document.querySelector('[data-card="portfolio"]');
  if (!card) return;
  const h2 = card.querySelector("h2");
  if (!h2) return;
  let totalEl = h2.querySelector(".pf-grand-total");
  if (!totalEl) {
    totalEl = document.createElement("span");
    totalEl.className = "pf-grand-total";
    h2.appendChild(totalEl);
  }
  const t = grandTotals(portfolioData);
  totalEl.innerHTML = `<span class="pf-grand-value">${fmtMoney(t.value)}</span> <span class="${pctClassName(t.gain)}">(${fmtSigned(t.gain)})</span>`;
}

function renderBody() {
  const el = $("#portfolioBody");
  if (!el) return;
  const portfolios = Object.values(portfolioData.portfolios || {});
  if (!portfolios.length) {
    el.innerHTML = `<div class="pf-empty">No portfolios yet. Click <b>+ Create portfolio</b> above to start.</div>`;
    renderGrandHeader();
    return;
  }
  let html = "";
  for (const p of portfolios) {
    const t = portfolioTotals(p);
    const isExpanded = expanded.has(p.id);
    html += `<section class="pf-pf" data-pid="${escapeHtml(p.id)}">
      <header class="pf-pf-header">
        <button class="pf-caret" data-pid="${escapeHtml(p.id)}">${isExpanded ? "\u25bc" : "\u25b6"}</button>
        <span class="pf-pf-name">${escapeHtml(p.name)}</span>
        <span class="pf-pf-totals"><span class="pf-pf-value">${fmtMoney(t.value)}</span> <span class="${pctClassName(t.gain)}">(${fmtSigned(t.gain)})</span></span>
        <button class="pf-rename mini" data-pid="${escapeHtml(p.id)}" title="Rename">\u270e</button>
        <button class="pf-del mini" data-pid="${escapeHtml(p.id)}" title="Delete portfolio">\u2715</button>
      </header>
      <div class="pf-pf-body ${isExpanded ? "" : "hidden"}"></div>
    </section>`;
  }
  el.innerHTML = html;

  el.querySelectorAll(".pf-caret").forEach((b) => b.addEventListener("click", () => {
    const pid = b.dataset.pid;
    if (expanded.has(pid)) expanded.delete(pid); else expanded.add(pid);
    saveExpanded();
    renderBody();
  }));
  el.querySelectorAll(".pf-rename").forEach((b) => b.addEventListener("click", async () => {
    const pid = b.dataset.pid;
    const p = portfolioData.portfolios[pid];
    const next = prompt("Rename portfolio", p ? p.name : "");
    if (!next || !next.trim()) return;
    try { await API.renamePortfolio(pid, next.trim()); await refresh(); } catch (e) { alert(e.message); }
  }));
  el.querySelectorAll(".pf-del").forEach((b) => b.addEventListener("click", async () => {
    const pid = b.dataset.pid;
    if (!confirm("Delete this portfolio? This cannot be undone.")) return;
    try { await API.deletePortfolio(pid); expanded.delete(pid); saveExpanded(); await refresh(); } catch (e) { alert(e.message); }
  }));

  for (const p of portfolios) {
    if (!expanded.has(p.id)) continue;
    const slot = el.querySelector(`.pf-pf[data-pid="${CSS.escape(p.id)}"] .pf-pf-body`);
    if (!slot) continue;
    renderHoldingsTable(slot, p);
  }
  renderGrandHeader();
}

// Ruling 3: Use ONLY buildPortfolioTableHtml (bespoke renderer). Do NOT
// call createTickerTable for the per-portfolio holdings table.
function renderHoldingsTable(slot, p) {
  slot.innerHTML = `<div class="pf-holdings-table"></div><div class="pf-add-row">
    <button class="pf-add-holding mini">+ Add holding</button>
    <button class="pf-add-cash mini">+ Add cash row</button>
  </div>`;
  const tableEl = slot.querySelector(".pf-holdings-table");

  // Build the table using the bespoke renderer
  const table = document.createElement("table");
  table.innerHTML = buildPortfolioTableHtml(p);
  tableEl.appendChild(table);
  wirePortfolioRowEvents(table, p);

  // After ticker holdings, append the cash row + totals row into the table
  const tbody = table.querySelector("tbody");
  const cash = p.holdings.find((h) => h.kind === "cash");
  if (cash) tbody.appendChild(buildCashRow(cash, p));
  tbody.appendChild(buildTotalsRow(p));

  slot.querySelector(".pf-add-holding").addEventListener("click", async () => {
    const sym = prompt("Add ticker symbol (e.g. NVDA):");
    if (!sym) return;
    try {
      const v = await API.validatePortfolioSymbol(sym.trim().toUpperCase());
      if (!v.valid) { alert(v.reason || "Invalid symbol"); return; }
      await API.addPortfolioHolding(p.id, { symbol: v.symbol, shares: 0, total_cost: 0 });
      await refresh();
    } catch (e) { alert(e.message); }
  });
  slot.querySelector(".pf-add-cash").addEventListener("click", async () => {
    try { await API.addPortfolioCash(p.id, { label: "Cash", total_cost: 0, total_value: 0 }); await refresh(); }
    catch (e) { alert(e.message); }
  });
}

function buildPortfolioTableHtml(p) {
  const cols = PORTFOLIO_COLUMNS;
  const rows = p.holdings.filter((h) => h.kind !== "cash");
  let html = "<thead><tr>";
  for (const c of cols) html += `<th${c.num ? ' class="num"' : ""}>${escapeHtml(c.label)}</th>`;
  html += "<th></th></tr></thead><tbody>";
  for (const r of rows) {
    html += "<tr>";
    for (const c of cols) {
      let content;
      if (c.key === "shares" || c.key === "total_cost") {
        const display = r[c.key] == null ? "" : String(r[c.key]);
        content = `<input class="pf-edit" data-symbol="${escapeHtml(r.symbol)}" data-key="${c.key}" value="${escapeHtml(display)}" />`;
      } else {
        content = c.fmt(r);
      }
      html += `<td${c.num ? ' class="num"' : ""}>${content}</td>`;
    }
    html += `<td><button class="pf-row-del mini" data-symbol="${escapeHtml(r.symbol)}" title="Remove">\u2715</button></td>`;
    html += "</tr>";
  }
  html += "</tbody>";
  return html;
}

function wirePortfolioRowEvents(tableEl, p) {
  tableEl.querySelectorAll(".pf-edit").forEach((inp) => {
    let timer;
    const save = async () => {
      const patch = {};
      if (inp.dataset.key === "shares") patch.shares = parseFloat(inp.value) || 0;
      else patch.total_cost = parseFloat(inp.value) || 0;
      try { await API.editPortfolioHolding(p.id, inp.dataset.symbol, patch); await refresh(); }
      catch (e) { inp.classList.add("error"); inp.title = e.message; setTimeout(() => inp.classList.remove("error"), 2000); }
    };
    inp.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(save, 400); });
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); inp.blur(); } });
    inp.addEventListener("blur", () => { clearTimeout(timer); save(); });
  });
  tableEl.querySelectorAll(".pf-row-del").forEach((b) => b.addEventListener("click", async () => {
    try { await API.removePortfolioHolding(p.id, b.dataset.symbol); await refresh(); } catch (e) { alert(e.message); }
  }));
}

function buildCashRow(cash, p) {
  const tr = document.createElement("tr");
  tr.className = "pf-cash-row";
  tr.innerHTML = `
    <td><b>${escapeHtml(cash.label || "Cash")}</b></td>
    <td>\u2014</td>
    <td><input class="pf-cash-edit pf-cash-cost" data-key="total_cost" value="${escapeHtml(String(cash.total_cost ?? 0))}" /></td>
    <td>\u2014</td>
    <td><input class="pf-cash-edit pf-cash-value" data-key="total_value" value="${escapeHtml(String(cash.total_value ?? 0))}" /></td>
    <td class="num ${pctClassName((cash.total_value ?? 0) - (cash.total_cost ?? 0))}">${fmtSigned((cash.total_value ?? 0) - (cash.total_cost ?? 0))}</td>
    <td class="num">\u2014</td>
    <td><button class="pf-cash-del mini" title="Remove cash row">\u2715</button></td>
  `;
  tr.querySelectorAll(".pf-cash-edit").forEach((inp) => {
    const save = async () => {
      const body = { [inp.dataset.key]: parseFloat(inp.value) || 0 };
      try { await API.editPortfolioCash(p.id, body); await refresh(); }
      catch (e) { inp.classList.add("error"); setTimeout(() => inp.classList.remove("error"), 2000); }
    };
    let timer;
    inp.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(save, 400); });
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); inp.blur(); } });
    inp.addEventListener("blur", () => { clearTimeout(timer); save(); });
  });
  tr.querySelector(".pf-cash-del").addEventListener("click", () => {
    alert("Cash row cannot be removed once added. Edit values to zero to neutralize.");
  });
  return tr;
}

function buildTotalsRow(p) {
  const t = portfolioTotals(p);
  const tr = document.createElement("tr");
  tr.className = "pf-totals-row";
  tr.innerHTML = `
    <td><b>Totals</b></td>
    <td></td>
    <td class="num">${fmtMoney(t.cost)}</td>
    <td></td>
    <td class="num">${fmtMoney(t.value)}</td>
    <td class="num ${pctClassName(t.gain)}">${fmtSigned(t.gain)}</td>
    <td></td>
    <td></td>
  `;
  return tr;
}

function renderHeaderControls() {
  const el = $("#portfolioControls");
  if (!el) return;
  el.innerHTML = `
    <div class="pf-header-actions">
      <button class="pf-toggle-all mini">\u25bc/\u25b2 all</button>
      <button class="pf-create mini">+ Create portfolio</button>
    </div>
  `;
  el.querySelector(".pf-toggle-all").addEventListener("click", () => {
    const portfolios = Object.values(portfolioData.portfolios || {});
    if (expanded.size === portfolios.length) expanded.clear();
    else for (const p of portfolios) expanded.add(p.id);
    saveExpanded();
    renderBody();
  });
  el.querySelector(".pf-create").addEventListener("click", async () => {
    const name = prompt("Portfolio name (e.g. Fidelity Cash):");
    if (!name || !name.trim()) return;
    try {
      const { id } = await API.createPortfolio(name.trim());
      expanded.add(id);
      saveExpanded();
      await refresh();
    } catch (e) { alert(e.message); }
  });
}

export function renderPortfolio(state) {
  portfolioData = state || { portfolios: {}, column_order: {}, column_visibility: {} };
  renderHeaderControls();
  renderBody();
  // If the dashboard payload omitted the portfolios key entirely, fetch
  // the real data now.  An empty object (no portfolios yet) is correct
  // and should NOT trigger a fetch — only a missing key means the
  // payload didn't include the portfolio data at all.
  if (state && !state.portfolios) {
    refresh();
  }
}

async function refresh() {
  try {
    const data = await API.fetchPortfolios();
    renderPortfolio(data);
  } catch (e) { console.error("portfolio refresh failed", e); }
}
