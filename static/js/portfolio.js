// portfolio.js — Portfolio card renderer (serenity-style expand/collapse
// per portfolio, cash row, totals footer, grand total in card header).
//
// Holdings tables are rendered by the shared tickerTable.js framework, which
// owns column visibility/order (persisted to localStorage + PUT to the
// backend). The Columns dropdown lives in the card header controls and
// operates on the same shared `pfVisible.portfolio` / `pfOrder.portfolio`
// keys that every per-portfolio table reads, so toggling a column re-renders
// every expanded portfolio consistently — same UX as the Earnings watchlist.

import { $, escapeHtml, fmtPrice, fmtPctHtml } from "./format.js";
import { createTickerTable } from "./tickerTable.js?v=20260905h";
import { getPortfolioWatchColor, setPortfolioWatchColor, nextWatchColor, renderStarBtn } from "./watchColors.js?v=20260906a";
import * as API from "./api.js";

let portfolioData = { portfolios: {}, column_order: {}, column_visibility: {} };
let expanded = loadExpanded();
// Per-portfolio tickerTable handles. Used for cleanup on delete; each
// portfolio owns its own sort state (the per-portfolio "↺ Default order"
// button calls table.resetSort() on its own instance, never touching
// siblings).
const portfolioTables = new Map();

// Portfolio column set: star + portfolio holding columns + earnings-derived
// columns. The Columns dropdown (card header) and every per-portfolio table
// read this single source via pfVisible.portfolio / pfOrder.portfolio
// localStorage keys. Earnings fields (next_earnings, pct_7d, high_52w,
// forward_pe, forward_peg, market_cap_fmt, sector, rec_*) come from the
// portfolio response after enrich_portfolios_with_earnings runs in the
// service layer.
const PORTFOLIO_COLUMNS = [
  { key: "_star",        label: "Star",          default: true,  num: false, sortable: false,
    fmt: (r) => renderStarBtn(r.symbol, watchColors.get(r.symbol)) },
  { key: "symbol",       label: "Ticker",        default: true,  num: false,
    fmt: (r) => `<b>${escapeHtml(r.symbol || r.label || "—")}</b>` },
  { key: "shares",       label: "Shares",        default: true,  num: true,  editable: true,
    fmt: (r) => r.shares == null ? "—" : String(r.shares) },
  { key: "total_cost",   label: "Total cost",    default: true,  num: true,  editable: true,
    fmt: (r) => r.total_cost == null ? "—" : fmtPrice(r.total_cost) },
  { key: "last_price",   label: "Last price",    default: true,  num: true,
    fmt: (r) => r.last_price == null ? "—" : fmtPrice(r.last_price) },
  { key: "total_value",  label: "Total value",   default: true,  num: true,
    fmt: (r) => (r.shares != null && r.last_price != null) ? fmtPrice(r.shares * r.last_price) : "—" },
  { key: "gain_loss",    label: "Gain/loss",     default: true,  num: true,
    fmt: (r) => {
      const v = (r.shares != null && r.last_price != null) ? r.shares * r.last_price - r.total_cost : null;
      if (v == null) return "—";
      const sign = v >= 0 ? "+" : "−";
      return `<span class="${pctClassName(v)}">${sign}${fmtPrice(Math.abs(v))}</span>`;
    } },
  { key: "pct_daily",    label: "Daily %",       default: true,  num: true,
    fmt: (r) => fmtPctHtml(r.pct_daily) },
  // Earnings-derived columns (enriched server-side by enrich_portfolios_with_earnings).
  { key: "date",         label: "Next earnings", default: true,
    fmt: (r) => escapeHtml(r.next_earnings || r.last_earnings || "—") },
  { key: "pct_7d",       label: "7-day %",       default: true,  num: true,
    fmt: (r) => r.pct_7d == null ? "—" : `<span class="${r.pct_7d >= 0 ? "pos" : "neg"}">${r.pct_7d >= 0 ? "+" : ""}${escapeHtml(String(r.pct_7d))}%</span>` },
  { key: "high_52w",     label: "52W high",      default: true,  num: true,
    fmt: (r) => r.high_52w == null ? "—" : escapeHtml(String(r.high_52w)) },
  { key: "forward_pe",   label: "Forward PE",    default: true,  num: true,
    fmt: (r) => r.forward_pe == null ? "—" : escapeHtml(String(r.forward_pe)) },
  { key: "forward_peg",  label: "Forward PEG",   default: true,  num: true,
    fmt: (r) => r.forward_peg == null ? "—" : escapeHtml(String(r.forward_peg)) },
  { key: "market_cap_fmt", label: "Market cap",  default: true,  num: true,
    fmt: (r) => escapeHtml(r.market_cap_fmt || "—") },
  { key: "sector",       label: "Sector",        default: true,  num: true,
    fmt: (r) => escapeHtml(r.sector || "—") },
  { key: "rec",          label: "AI rec",        default: true,
    fmt: (r) => {
      const color = r.rec_color || "#888";
      return `<span class="earn-rec" style="background:${color}22;color:${color};border:1px solid ${color}" title="${escapeHtml(r.rec_reason || "")}">${escapeHtml(r.rec_signal || "—")}</span>`;
    } },
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

function startEditForPid(pid) {
  const s = document.querySelector(`.pf-pf-name[data-pid="${CSS.escape(pid)}"]`);
  if (!s) return;
  const cur = portfolioData.portfolios[pid]?.name || "";
  const inp = document.createElement("input");
  inp.className = "pf-name-input";
  inp.value = cur;
  inp.addEventListener("click", (e) => e.stopPropagation());
  inp.addEventListener("focus", (e) => e.stopPropagation());
  inp.addEventListener("keydown", async (e) => {
    e.stopPropagation();
    if (e.key === "Enter") { e.preventDefault(); inp.blur(); }
    if (e.key === "Escape") { inp.value = cur; inp.blur(); }
  });
  inp.addEventListener("blur", async () => {
    const next = inp.value.trim();
    s.textContent = next || cur;
    s.style.display = "";
    inp.replaceWith(s);
    if (next && next !== cur) {
      try { await API.renamePortfolio(pid, next); await refresh(); }
      catch (e) { alert(e.message); await refresh(); }
    }
  });
  s.style.display = "none";
  s.parentNode.insertBefore(inp, s.nextSibling);
  inp.focus();
  inp.select();
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
      <header class="pf-pf-header" data-pid="${escapeHtml(p.id)}" tabindex="0" role="button" aria-expanded="${isExpanded}" title="Click to expand/collapse">
        <button class="pf-caret" data-pid="${escapeHtml(p.id)}" aria-label="Toggle expand/collapse">${isExpanded ? "\u25bc" : "\u25b6"}</button>
        <span class="pf-pf-name" data-pid="${escapeHtml(p.id)}">${escapeHtml(p.name)}</span>
        <button class="pf-rename-btn mini" data-pid="${escapeHtml(p.id)}" aria-label="Rename portfolio" title="Rename">\u270e</button>
        <span class="pf-pf-totals"><span class="pf-pf-value">${fmtMoney(t.value)}</span> <span class="${pctClassName(t.gain)}">(${fmtSigned(t.gain)})</span></span>
        <button class="pf-del mini" data-pid="${escapeHtml(p.id)}" title="Delete portfolio" aria-label="Delete portfolio">\u2715</button>
      </header>
      <div class="pf-pf-body ${isExpanded ? "" : "hidden"}"></div>
    </section>`;
  }
  el.innerHTML = html;

  // Header click → toggle collapse/expand. Ignore clicks that bubbled from
  // the rename/delete/caret buttons (those handlers run first and stopPropagation).
  el.querySelectorAll(".pf-pf-header").forEach((h) => {
    h.addEventListener("click", (e) => {
      if (e.target.closest(".pf-rename-btn, .pf-del, .pf-caret, .pf-pf-totals, .pf-name-input")) return;
      const pid = h.dataset.pid;
      if (expanded.has(pid)) expanded.delete(pid); else expanded.add(pid);
      saveExpanded();
      renderBody();
    });
    h.addEventListener("keydown", (e) => {
      if (e.target !== h) return;  // don't double-fire on child button focus
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); h.click(); }
    });
  });

  // Existing caret handler — keep for keyboard, but stopPropagation so the
  // header doesn't double-fire.
  el.querySelectorAll(".pf-caret").forEach((b) => b.addEventListener("click", (e) => {
    e.stopPropagation();
    const pid = b.dataset.pid;
    if (expanded.has(pid)) expanded.delete(pid); else expanded.add(pid);
    saveExpanded();
    renderBody();
  }));

  // Pencil icon → existing rename logic.
  el.querySelectorAll(".pf-rename-btn").forEach((b) => b.addEventListener("click", (e) => {
    e.stopPropagation();
    startEditForPid(b.dataset.pid);
  }));

  // Delete button — keep existing handler, add stopPropagation so it doesn't
  // also collapse the (now-deleted) portfolio.
  el.querySelectorAll(".pf-del").forEach((b) => b.addEventListener("click", async (e) => {
    e.stopPropagation();
    const pid = b.dataset.pid;
    if (!confirm("Delete this portfolio? This cannot be undone.")) return;
    try { await API.deletePortfolio(pid); expanded.delete(pid); portfolioTables.delete(pid); saveExpanded(); await refresh(); } catch (e) { alert(e.message); }
  }));

  for (const p of portfolios) {
    if (!expanded.has(p.id)) continue;
    const slot = el.querySelector(`.pf-pf[data-pid="${CSS.escape(p.id)}"] .pf-pf-body`);
    if (!slot) continue;
    renderHoldingsTable(slot, p);
  }
  renderGrandHeader();
}

// Per-portfolio holdings table built on the shared createTickerTable factory.
// A fresh instance is created on every render so it re-reads the shared
// column visibility/order from localStorage (which the header Columns
// dropdown owns). `afterRender` appends the cash + totals rows below the
// ticker holdings; `afterEdit` refreshes the totals row when a holding's
// shares/cost change in place.
function renderHoldingsTable(slot, p) {
  slot.innerHTML = `
    <div class="pf-holdings-table" id="pf-table-${escapeHtml(p.id)}"></div>
    <div class="pf-add-row">
      <button class="pf-add-holding mini">+ Add holding</button>
      <button class="pf-add-cash mini">+ Add cash row</button>
      <button class="pf-reset-order mini" title="Reset this portfolio's row order to insertion order (clears any column sort and any session-only ▲/▼ moves)">↺ Default order</button>
    </div>
  `;

  // Override the star column with a pid-scoped version so starring NVDA in
  // "Fidelity Main" does NOT also star NVDA in "Fidelity Roth IRA".
  const pid = p.id;
  const columns = PORTFOLIO_COLUMNS.map((c) => {
    if (c.key !== "_star") return c;
    return {
      ...c,
      fmt: (r) => renderStarBtn(r.symbol, getPortfolioWatchColor(pid, r.symbol)),
    };
  });

  const table = createTickerTable({
    section: "portfolio",
    containerSel: `#pf-table-${CSS.escape(p.id)}`,
    // No controlsSel — the Columns dropdown + add flow live in the card
    // header and the bespoke .pf-add-row buttons respectively.
    columns,
    initialSort: { key: "default", dir: 1 },
    // Starred rows get the same amber/bull/bear row tint + left border
    // that earnings uses (state lives in the per-portfolio watchColors Map).
    rowClass: (r) => {
      const c = getPortfolioWatchColor(pid, r.symbol);
      return c ? `earn-row-${c}` : "";
    },
    fetchData: async () => ({ rows: p.holdings.filter((h) => h.kind !== "cash") }),
    addRow: async (sym) => {
      const v = await API.validatePortfolioSymbol(sym);
      if (!v.valid) throw new Error(v.reason || "invalid symbol");
      const h = await API.addPortfolioHolding(p.id, { symbol: v.symbol, shares: 0, total_cost: 0 });
      p.holdings.push(h);
      renderGrandHeader();  // Update card-level totals
      return { rows: p.holdings.filter((x) => x.kind !== "cash") };
    },
    removeRow: async (sym) => {
      await API.removePortfolioHolding(p.id, sym);
      p.holdings = p.holdings.filter((x) => !(x.kind !== "cash" && x.symbol === sym));
      renderGrandHeader();  // Update card-level totals
      return { rows: p.holdings.filter((x) => x.kind !== "cash") };
    },
    editCell: async (sym, key, value) => {
      const patch = {};
      patch[key] = parseFloat(value) || 0;
      const r = await API.editPortfolioHolding(p.id, sym, patch);
      renderGrandHeader();  // Update card-level totals
      return r; // don't blow away the input — handled by tickerTable edit-fix
    },
    columnPrefsUrl: async (prefs) => {
      const visibility = {};
      for (const c of PORTFOLIO_COLUMNS) visibility[c.key] = prefs.visibility[c.key] || false;
      await API.putPortfolioColumns("portfolio", { order: prefs.order, visibility });
    },
    afterRender: (tbody, cols) => {
      const cash = p.holdings.find((h) => h.kind === "cash");
      if (cash) tbody.appendChild(buildCashRow(cash, p, cols));
      tbody.appendChild(buildTotalsRow(p, cols));
    },
    afterEdit: (row, tbody, cols) => {
      // A holding's shares/cost changed in place — sync the closure's
      // p.holdings so the totals row rebuilds from fresh numbers, then swap
      // the totals row without a full re-render.
      const h = p.holdings.find((x) => x.kind !== "cash" && x.symbol === row.symbol);
      if (h) { h.shares = row.shares; h.total_cost = row.total_cost; }
      const totals = tbody ? tbody.querySelector(".pf-totals-row") : null;
      if (totals) totals.replaceWith(buildTotalsRow(p, cols));
    },
  });

  table.render({ rows: p.holdings.filter((h) => h.kind !== "cash") });
  portfolioTables.set(p.id, table);

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
  // Per-portfolio reset: only this portfolio's table goes back to
  // insertion order. Sibling portfolios are untouched (each tickerTable
  // instance owns its own in-memory sort — they don't share state).
  slot.querySelector(".pf-reset-order").addEventListener("click", () => {
    try { table.resetSort(); } catch (e) { /* ignore */ }
  });
}

// Cash row — single editable input (Total value, mirrored to cost), removable.
// Cells are generated per visible column so the row stays aligned with the
// header when columns are hidden.
function buildCashRow(cash, p, cols) {
  const tr = document.createElement("tr");
  tr.className = "pf-cash-row";
  const v = cash.total_value || 0;
  const cells = cols.map((c) => {
    const num = c.num ? ' class="num"' : "";
    switch (c.key) {
      case "symbol":
        return `<td><b>${escapeHtml(cash.label || "Cash")}</b></td>`;
      case "total_value":
        return `<td${num}><input class="pf-cash-edit" data-key="total_value" value="${escapeHtml(String(v))}" inputmode="decimal" /></td>`;
      case "gain_loss":
        return `<td class="num muted">\u2014</td>`;
      default:
        return `<td${num}>\u2014</td>`;
    }
  });
  tr.innerHTML = cells.join("") + `<td><button class="pf-cash-del mini" title="Remove cash row">\u2715</button></td>`;
  tr.querySelector(".pf-cash-edit").addEventListener("input", () => {
    clearTimeout(tr._timer);
    tr._timer = setTimeout(async () => {
      const num = parseFloat(tr.querySelector(".pf-cash-edit").value) || 0;
      try {
        await API.editPortfolioCash(p.id, { total_cost: num, total_value: num });
        await refresh();
      } catch (e) {
        tr.querySelector(".pf-cash-edit").classList.add("error");
        setTimeout(() => tr.querySelector(".pf-cash-edit").classList.remove("error"), 2000);
      }
    }, 600);
  });
  tr.querySelector(".pf-cash-del").addEventListener("click", async () => {
    if (!confirm("Remove cash row from this portfolio?")) return;
    try { await API.removePortfolioCash(p.id); await refresh(); }
    catch (e) { alert(e.message); }
  });
  return tr;
}

function buildTotalsRow(p, cols) {
  const t = portfolioTotals(p);
  const tr = document.createElement("tr");
  tr.className = "pf-totals-row";
  const cells = cols.map((c) => {
    const num = c.num ? ' class="num"' : "";
    switch (c.key) {
      case "symbol":
        return `<td><b>Totals</b></td>`;
      case "total_cost":
        return `<td${num}>${fmtMoney(t.cost)}</td>`;
      case "total_value":
        return `<td${num}>${fmtMoney(t.value)}</td>`;
      case "gain_loss":
        return `<td class="num ${pctClassName(t.gain)}">${fmtSigned(t.gain)}</td>`;
      default:
        return `<td${num}></td>`;
    }
  });
  tr.innerHTML = cells.join("") + "<td></td>";
  return tr;
}

// ---- Column visibility/order (shared with the per-portfolio tables) -------
// The header Columns dropdown is the single owner of the portfolio column
// state. It reads/writes the same localStorage keys tickerTable uses for
// section "portfolio" (pfVisible.portfolio / pfOrder.portfolio) and persists
// to the backend, then re-renders so every expanded table picks up the change.

function defaultVisibleKeys() {
  return new Set(PORTFOLIO_COLUMNS.filter((c) => c.default !== false).map((c) => c.key));
}

function loadColVisibility() {
  try {
    const v = JSON.parse(localStorage.getItem("pfVisible.portfolio"));
    if (Array.isArray(v) && v.length) return new Set(v);
  } catch (e) { /* ignore */ }
  return defaultVisibleKeys();
}

function saveColVisibility(set) {
  try { localStorage.setItem("pfVisible.portfolio", JSON.stringify([...set])); } catch (e) { /* ignore */ }
}

function loadColOrder() {
  try {
    const v = JSON.parse(localStorage.getItem("pfOrder.portfolio"));
    if (Array.isArray(v) && v.length) {
      const missing = PORTFOLIO_COLUMNS.map((c) => c.key).filter((k) => !v.includes(k));
      return missing.length ? [...v, ...missing] : v;
    }
  } catch (e) { /* ignore */ }
  return PORTFOLIO_COLUMNS.map((c) => c.key);
}

function saveColOrder(order) {
  try { localStorage.setItem("pfOrder.portfolio", JSON.stringify(order)); } catch (e) { /* ignore */ }
}

let prefDebounceTimer = null;
let colMenuOutsideHandler = null;

function persistColPrefsSoon() {
  clearTimeout(prefDebounceTimer);
  prefDebounceTimer = setTimeout(async () => {
    const order = loadColOrder();
    const visibility = {};
    const visible = loadColVisibility();
    for (const c of PORTFOLIO_COLUMNS) visibility[c.key] = visible.has(c.key);
    try { await API.putPortfolioColumns("portfolio", { order, visibility }); } catch (e) { /* best effort */ }
  }, 300);
}

function renderHeaderControls() {
  const el = $("#portfolioControls");
  if (!el) return;
  const visible = loadColVisibility();
  const order = loadColOrder();
  // The toggle-all icon reflects the action that the click will perform,
  // not the current state: "▼ all" = clicking will expand, "▲ all" =
  // clicking will collapse. The original literal "▼/▲ all" was visually
  // ambiguous (read as two icons, not a state hint) and gave no feedback
  // after the user expanded/collapsed everything.
  const portfolios = Object.values(portfolioData.portfolios || {});
  const allExpanded = portfolios.length > 0 && expanded.size === portfolios.length;
  el.innerHTML = `
    <div class="pf-header-actions">
      <div class="tt-cols">
        <button class="tt-cols-btn mini">Columns</button>
        <div class="tt-cols-menu hidden">
          ${PORTFOLIO_COLUMNS.map((c) => `
            <div class="tt-cols-row">
              <button class="tt-col-up mini" data-key="${c.key}" title="Move left">◀</button>
              <button class="tt-col-down mini" data-key="${c.key}" title="Move right">▶</button>
              <label><input type="checkbox" data-col="${c.key}" ${visible.has(c.key) ? "checked" : ""}> ${escapeHtml(c.label)}</label>
            </div>
          `).join("")}
        </div>
      </div>
      <button class="pf-toggle-all mini" title="${allExpanded ? "Collapse all portfolios" : "Expand all portfolios"}">${allExpanded ? "▲ all" : "▼ all"}</button>
      <button class="pf-create mini">+ Create portfolio</button>
    </div>
  `;

  el.querySelector(".tt-cols-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    el.querySelector(".tt-cols-menu").classList.toggle("hidden");
  });
  const closeMenu = (e) => {
    const menu = el.querySelector(".tt-cols-menu");
    if (!menu || menu.classList.contains("hidden")) return;
    if (!el.contains(e.target)) menu.classList.add("hidden");
  };
  // Remove the previous outside-click listener to avoid leaking one per
  // renderHeaderControls() call (same pattern as tickerTable.drawControls).
  if (colMenuOutsideHandler) document.removeEventListener("click", colMenuOutsideHandler);
  colMenuOutsideHandler = closeMenu;
  document.addEventListener("click", closeMenu);

  el.querySelectorAll(".tt-cols-menu input").forEach((cb) => {
    cb.addEventListener("change", () => {
      const vis = loadColVisibility();
      if (cb.checked) vis.add(cb.dataset.col); else vis.delete(cb.dataset.col);
      saveColVisibility(vis);
      persistColPrefsSoon();
      renderBody();
    });
  });
  el.querySelectorAll(".tt-col-up").forEach((b) => {
    b.addEventListener("click", (e) => { e.preventDefault(); movePortfolioCol(b.dataset.key, -1); });
  });
  el.querySelectorAll(".tt-col-down").forEach((b) => {
    b.addEventListener("click", (e) => { e.preventDefault(); movePortfolioCol(b.dataset.key, +1); });
  });

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

function movePortfolioCol(key, delta) {
  const order = loadColOrder();
  const idx = order.indexOf(key);
  if (idx < 0) return;
  const newIdx = idx + delta;
  if (newIdx < 0 || newIdx >= order.length) return;
  [order[idx], order[newIdx]] = [order[newIdx], order[idx]];
  saveColOrder(order);
  persistColPrefsSoon();
  renderHeaderControls();
  renderBody();
}

export function renderPortfolio(state) {
  portfolioData = state || { portfolios: {}, column_order: {}, column_visibility: {} };
  // Bind star click handlers ONCE on #portfolioBody. Re-renders only swap
  // innerHTML on this container (the element itself never moves), so event
  // delegation survives every refresh. Left-click cycles amber -> bull ->
  // bear -> amber; right-click clears. State lives in the per-portfolio
  // watchColors Map keyed by "<pid>::<sym>" so starring NVDA in one
  // portfolio does NOT affect other portfolios.
  const body = $("#portfolioBody");
  if (body && !body.dataset.starBound) {
    body.dataset.starBound = "1";
    body.addEventListener("click", (e) => {
      const star = e.target.closest(".earn-star");
      if (!star) return;
      e.preventDefault();
      const sym = star.dataset.sym;
      if (!sym) return;
      const pfSection = star.closest("[data-pid]");
      const pid = pfSection ? pfSection.dataset.pid : null;
      if (!pid) return;
      const cur = getPortfolioWatchColor(pid, sym);
      setPortfolioWatchColor(pid, sym, nextWatchColor(cur));
      renderBody();
    });
    body.addEventListener("contextmenu", (e) => {
      const star = e.target.closest(".earn-star");
      if (!star) return;
      e.preventDefault();
      const sym = star.dataset.sym;
      if (!sym) return;
      const pfSection = star.closest("[data-pid]");
      const pid = pfSection ? pfSection.dataset.pid : null;
      if (!pid) return;
      setPortfolioWatchColor(pid, sym, null);
      renderBody();
    });
  }
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
