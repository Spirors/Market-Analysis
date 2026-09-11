// portfolio.js — Portfolio card renderer (serenity-style expand/collapse
// per portfolio, cash row, totals footer, grand total in card header).
//
// Holdings tables are rendered by the shared tickerTable.js framework, which
// owns column visibility/order (persisted to localStorage + PUT to the
// backend). Each portfolio gets its own tickerTable instance with
// `section: "portfolio.<pid>"` so column state is independent per portfolio —
// showing 7-day % in Portfolio A doesn't affect Portfolio B. The Columns
// dropdown lives INSIDE each expanded portfolio's controls (not in the
// card header anymore, so the columns button sees exactly the columns for
// the portfolio the user is configuring).

import { $, escapeHtml, fmtPrice, fmtPctHtml, fmtFloat } from "./format.js";
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

// Format a percent value like fmtPctHtml but tolerates null + sign. Used by
// pct_7d / pct_30d where the server returns a 3dp float (e.g. "-3.42") and
// we want "+/-X.XX%" with the green/red row tint. null -> "—".
function fmtSignedPct(v) {
  if (v == null) return "—";
  const sign = v >= 0 ? "+" : "−";
  return `<span class="${pctClassName(v)}">${sign}${escapeHtml(fmtFloat(Math.abs(v)))}%</span>`;
}

// Format a market-cap value as "1.23T" / "456.78B" / "12.34M". null -> "—".
// Mirrors the old _fmt_billions helper from the removed app/earnings.py.
function fmtMarketCap(v) {
  if (v == null) return "—";
  const n = Number(v);
  if (!isFinite(n)) return "—";
  if (n >= 1e12) return escapeHtml((n / 1e12).toFixed(2) + "T");
  if (n >= 1e9) return escapeHtml((n / 1e9).toFixed(2) + "B");
  if (n >= 1e6) return escapeHtml((n / 1e6).toFixed(2) + "M");
  return escapeHtml(n.toFixed(0));
}

// Portfolio column set: star + 7 base portfolio columns + 8 restored
// earnings-derived columns (7-day %, 30-day %, Earnings date, Marketcap,
// Forward PE, Forward PEG, 52W high, Sector). The Columns dropdown
// inside each portfolio reads this single source via the per-portfolio
// pfVisible.portfolio.<pid> / pfOrder.portfolio.<pid> localStorage keys
// (tickerTable.js namespaces persistence by section, and each portfolio
// passes section="portfolio.<pid>").
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
  // Restored earnings-derived columns (enriched server-side by
  // app.portfolio.enrich_portfolios -> market.get_histories_bulk + per-
  // symbol Ticker.info / calendar). All default visible per the user's
  // "all-on" choice during clarification.
  { key: "pct_7d",       label: "7-day %",       default: true,  num: true,
    fmt: (r) => fmtSignedPct(r.pct_7d) },
  { key: "pct_30d",      label: "30-day %",      default: true,  num: true,
    fmt: (r) => fmtSignedPct(r.pct_30d) },
  { key: "next_earnings",label: "Earnings date", default: true,  num: false,
    fmt: (r) => escapeHtml(r.next_earnings || "—") },
  { key: "marketcap",    label: "Marketcap",     default: true,  num: true,
    fmt: (r) => fmtMarketCap(r.marketcap) },
  { key: "forward_pe",   label: "Forward PE",    default: true,  num: true,
    fmt: (r) => r.forward_pe == null ? "—" : escapeHtml(fmtFloat(r.forward_pe)) },
  { key: "forward_peg",  label: "Forward PEG",   default: true,  num: true,
    fmt: (r) => r.forward_peg == null ? "—" : escapeHtml(fmtFloat(r.forward_peg)) },
  { key: "high_52w",     label: "52W high",      default: true,  num: true,
    fmt: (r) => r.high_52w == null ? "—" : escapeHtml(fmtPrice(r.high_52w)) },
  { key: "sector",       label: "Sector",        default: true,  num: false,
    fmt: (r) => escapeHtml(r.sector || "—") },
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
  // Match the span's box width so the pencil ✎ / totals / ✕ button don't
  // visibly shift left when the input replaces the flex:1 span.  The span
  // has `flex: 1` (grows to fill available space in the header) while the
  // input has `field-sizing: content` (sizes to its actual value).  Without
  // this match the input is narrower than the span was and the surrounding
  // elements visibly shift ~25-30px leftward — see the "portfolio rename
  // layout shift" regression captured in the Phase 2 audit.  Setting
  // `min-width` to the span's measured box width aligns the input's right
  // edge with where the span's right edge was.
  const spanWidth = s.getBoundingClientRect().width;
  inp.style.minWidth = `${Math.max(spanWidth, 0)}px`;
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
      try {
        await API.renamePortfolio(pid, next);
        // Optimistic: update local state and re-render without a full refresh.
        portfolioData.portfolios[pid].name = next;
        renderPortfolioRename(pid, next);
        renderGrandHeader();
      } catch (e) { alert(e.message); await refresh(); }
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
    // Wiping the body below destroys any expanded portfolio's .pf-pf-body
    // slot. Drop the corresponding tickerTable handles so renderHoldingsTable
    // recreates them (Patch C's early-return reuses an existing handle only
    // when its DOM container is still alive — after innerHTML = "", it isn't).
    portfolioTables.clear();
    el.innerHTML = `<div class="pf-empty">No portfolios yet. Click <b>+ Create portfolio</b> above to start.</div>`;
    renderGrandHeader();
    return;
  }
  let html = "";
  for (let i = 0; i < portfolios.length; i++) {
    const p = portfolios[i];
    html += buildPortfolioHTML(p, {
      isFirst: i === 0,
      isLast: i === portfolios.length - 1,
      index: i,
      total: portfolios.length,
    });
  }
  // Same reason as above — the old .pf-pf-body slots are about to be gone.
  portfolioTables.clear();
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
    try {
      await API.deletePortfolio(pid);
      delete portfolioData.portfolios[pid];
      renderPortfolioRemove(pid);
      renderGrandHeader();
    } catch (e) { alert(e.message); }
  }));

  // Move-up / move-down chevrons — reorder the portfolios list. Compute the
  // new order locally (just a swap), POST to /api/portfolios/reorder, and
  // re-render on success. The button is rendered `disabled` at the
  // boundaries (first row → up disabled, last row → down disabled) so the
  // click handler should never see a no-op swap; if it does (e.g. a
  // concurrent delete between render and click), the defensive check
  // below avoids a wasted round-trip and a confusing alert.
  el.querySelectorAll(".pf-move-up").forEach((b) => b.addEventListener("click", async (e) => {
    e.stopPropagation();
    await _movePortfolioBy(b.dataset.pid, -1);
  }));
  el.querySelectorAll(".pf-move-down").forEach((b) => b.addEventListener("click", async (e) => {
    e.stopPropagation();
    await _movePortfolioBy(b.dataset.pid, +1);
  }));

  for (const p of portfolios) {
    if (!expanded.has(p.id)) continue;
    const slot = el.querySelector(`.pf-pf[data-pid="${CSS.escape(p.id)}"] .pf-pf-body`);
    if (!slot) continue;
    renderHoldingsTable(slot, p);
  }
  renderGrandHeader();
}

// ---- Build HTML for a single portfolio section --------------------------------
// Extracted from renderBody() so both the full-rebuild path (renderBody) and
// the targeted-insert path (renderPortfolioInsert) produce identical HTML
// without duplication.
function buildPortfolioHTML(p, position = {}) {
  const t = portfolioTotals(p);
  const isExpanded = expanded.has(p.id);
  // position: { isFirst, isLast, index, total } — supplied by the caller
  // (renderBody for the full rebuild, renderPortfolioInsert for targeted
  // inserts). Missing values default to "no boundary disable" so old
  // callers (e.g. tests) keep working — the chevrons just always show
  // enabled when position isn't supplied. With position supplied the
  // first row's ▲ and last row's ▼ render disabled.
  const { isFirst = false, isLast = false } = position;
  return `<section class="pf-pf" data-pid="${escapeHtml(p.id)}">
    <header class="pf-pf-header" data-pid="${escapeHtml(p.id)}" tabindex="0" role="button" aria-expanded="${isExpanded}" title="Click to expand/collapse">
      <button class="pf-caret" data-pid="${escapeHtml(p.id)}" aria-label="Toggle expand/collapse">${isExpanded ? "\u25bc" : "\u25b6"}</button>
      <span class="pf-pf-name" data-pid="${escapeHtml(p.id)}">${escapeHtml(p.name)}</span>
      <button class="pf-rename-btn mini" data-pid="${escapeHtml(p.id)}" aria-label="Rename portfolio" title="Rename">\u270e</button>
      <button class="pf-move-up mini" data-pid="${escapeHtml(p.id)}" aria-label="Move portfolio up" title="Move up"${isFirst ? " disabled" : ""}>\u2191</button>
      <button class="pf-move-down mini" data-pid="${escapeHtml(p.id)}" aria-label="Move portfolio down" title="Move down"${isLast ? " disabled" : ""}>\u2193</button>
      <span class="pf-pf-totals"><span class="pf-pf-value">${fmtMoney(t.value)}</span> <span class="${pctClassName(t.gain)}">(${fmtSigned(t.gain)})</span></span>
      <button class="pf-del mini" data-pid="${escapeHtml(p.id)}" title="Delete portfolio" aria-label="Delete portfolio">\u2715</button>
    </header>
    <div class="pf-pf-body ${isExpanded ? "" : "hidden"}"></div>
  </section>`;
}

// ---- Attach header listeners to a single portfolio div -----------------------
// Mirrors the listener-attachment logic from renderBody() lines 242-288 but
// scoped to ONE portfolio element (used by renderPortfolioInsert).
function _wirePortfolioHeader(section) {
  const h = section.querySelector(".pf-pf-header");
  if (!h) return;
  h.addEventListener("click", (e) => {
    if (e.target.closest(".pf-rename-btn, .pf-del, .pf-caret, .pf-pf-totals, .pf-name-input")) return;
    const pid = h.dataset.pid;
    if (expanded.has(pid)) expanded.delete(pid); else expanded.add(pid);
    saveExpanded();
    renderBody();
  });
  h.addEventListener("keydown", (e) => {
    if (e.target !== h) return;
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); h.click(); }
  });
  const caret = section.querySelector(".pf-caret");
  if (caret) caret.addEventListener("click", (e) => {
    e.stopPropagation();
    const pid = caret.dataset.pid;
    if (expanded.has(pid)) expanded.delete(pid); else expanded.add(pid);
    saveExpanded();
    renderBody();
  });
  const renameBtn = section.querySelector(".pf-rename-btn");
  if (renameBtn) renameBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    startEditForPid(renameBtn.dataset.pid);
  });
  const delBtn = section.querySelector(".pf-del");
  if (delBtn) delBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    const pid = delBtn.dataset.pid;
    if (!confirm("Delete this portfolio? This cannot be undone.")) return;
    try {
      await API.deletePortfolio(pid);
      expanded.delete(pid);
      portfolioTables.delete(pid);
      saveExpanded();
      delete portfolioData.portfolios[pid];
      renderPortfolioRemove(pid);
      renderGrandHeader();
    } catch (e) { alert(e.message); }
  });

  // Move-up / move-down chevrons — same logic as the renderBody path; see
  // _movePortfolioBy for the full explanation.
  const moveUpBtn = section.querySelector(".pf-move-up");
  if (moveUpBtn) moveUpBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    await _movePortfolioBy(moveUpBtn.dataset.pid, -1);
  });
  const moveDownBtn = section.querySelector(".pf-move-down");
  if (moveDownBtn) moveDownBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    await _movePortfolioBy(moveDownBtn.dataset.pid, +1);
  });
}

// ---- Targeted insert / remove / rename ---------------------------------------
// These avoid the nuclear renderBody() rebuild on add/remove/rename by touching
// only the single affected portfolio div + the grand header totals.

function renderPortfolioInsert(p, opts = {}) {
  const el = $("#portfolioBody");
  if (!el) return null;
  // Build the portfolio section HTML. A new portfolio is always appended
  // at the end, so its up-chevron should render enabled (it's only
  // disabled when first) and its down-chevron disabled (only disabled
  // when last — and right now it IS the last). Re-render afterwards
  // (caller may do so) so the previous-now-second-to-last row's
  // down-chevron becomes enabled.
  const portfolios = Object.values(portfolioData.portfolios || {});
  const isLastNew = portfolios[portfolios.length - 1] && portfolios[portfolios.length - 1].id === p.id;
  const sectionHtml = buildPortfolioHTML(p, {
    isFirst: portfolios.length === 1,  // only portfolio in the list
    isLast: isLastNew,
    index: portfolios.length - 1,
    total: portfolios.length,
  });
  // Insert before the empty-state div or at the end of #portfolioBody
  const emptyDiv = el.querySelector(".pf-empty");
  if (emptyDiv) {
    // Replace the empty-state placeholder with the new portfolio
    emptyDiv.outerHTML = sectionHtml;
  } else {
    // Append the new section — the +Create controls live in #portfolioControls,
    // not inside #portfolioBody, so we just append to portfolioBody.
    el.insertAdjacentHTML("beforeend", sectionHtml);
  }
  const newSection = el.querySelector(`.pf-pf[data-pid="${CSS.escape(p.id)}"]`);
  if (!newSection) return null;
  // Wire header listeners for the new div
  _wirePortfolioHeader(newSection);
  // If auto-expand, render the holdings table into the body slot
  if (opts.autoExpand && expanded.has(p.id)) {
    const slot = newSection.querySelector(".pf-pf-body");
    if (slot) renderHoldingsTable(slot, p);
  }
  return newSection;
}

function renderPortfolioRemove(pid) {
  const section = document.querySelector(`.pf-pf[data-pid="${CSS.escape(pid)}"]`);
  if (!section) return;
  // Dispose the tickerTable instance if present (clear listeners; the DOM is
  // about to be removed).
  if (portfolioTables.has(pid)) {
    portfolioTables.delete(pid);
  }
  // Remove the DOM element
  section.remove();
  // Cleanup: remove from expanded Set if present
  expanded.delete(pid);
  saveExpanded();
  // If no portfolios left, show the empty-state placeholder
  const el = $("#portfolioBody");
  if (el && !el.querySelector(".pf-pf")) {
    el.innerHTML = `<div class="pf-empty">No portfolios yet. Click <b>+ Create portfolio</b> above to start.</div>`;
  }
}

function renderPortfolioRename(pid, newName) {
  const nameSpan = document.querySelector(`.pf-pf-name[data-pid="${CSS.escape(pid)}"]`);
  if (!nameSpan) return;
  nameSpan.textContent = newName;
  // Update aria-label on the header
  const header = document.querySelector(`.pf-pf-header[data-pid="${CSS.escape(pid)}"]`);
  if (header) header.setAttribute("title", `Click to expand/collapse — ${newName}`);
}

// ---- Reorder helper ---------------------------------------------------------
// Called by the per-row up/down chevrons in both renderBody and
// _wirePortfolioHeader. Computes the new order locally (cheap swap) and
// POSTs it to /api/portfolios/reorder. On success, the full body is
// re-rendered so the new disabled-state of the boundary chevrons (first
// row's ▲, last row's ▼) takes effect — that re-render also keeps the
// per-portfolio tickerTable instances alive (the same Map/clear dance
// renderBody already does for the add/remove flow).
//
// Defensive checks:
//   - pid not in state → bail silently (stale click after a delete)
//   - direction would walk off the end → bail silently (stale click
//     after another tab reordered, or the button was somehow not
//     disabled at click time)
//   - server returns 400 → alert (the user gave an invalid order from
//     the UI, which shouldn't happen but surface it if it does)
async function _movePortfolioBy(pid, direction) {
  const portfolios = Object.values(portfolioData.portfolios || {});
  const idx = portfolios.findIndex((p) => p.id === pid);
  if (idx === -1) return;
  const target = idx + direction;
  if (target < 0 || target >= portfolios.length) return;
  // Build the new order as a swap, then POST it.
  const newOrder = portfolios.map((p) => p.id);
  [newOrder[idx], newOrder[target]] = [newOrder[target], newOrder[idx]];
  try {
    await API.reorderPortfolios(newOrder);
  } catch (e) {
    alert(e.message);
    return;
  }
  // Server is the source of truth for the persisted order; mirror it
  // locally so the next renderBody sees the new order without a
  // refetch. The server response is just {order: [...]}; build the
  // new portfolios dict from the existing one in that order.
  const byId = portfolioData.portfolios;
  portfolioData.portfolios = Object.fromEntries(newOrder.map((id) => [id, byId[id]]));
  renderBody();
}

// Per-portfolio holdings table built on the shared createTickerTable factory.
// A fresh instance is created on every render so it re-reads the per-
// portfolio column visibility/order from localStorage (which the in-body
// Columns dropdown owns). `afterRender` appends the cash + totals rows
// below the ticker holdings; `afterEdit` refreshes the totals row when a
// holding's shares/cost change in place.
function renderHoldingsTable(slot, p) {
  // Per-portfolio container IDs: each portfolio owns its own section key
  // ("portfolio.<pid>") so localStorage persistence + tickerTable sort
  // state stay isolated between portfolios. If a tickerTable already exists
  // for this portfolio, reuse it — just update its data. This avoids
  // destroying and recreating the table (and losing sort state) on every
  // add/remove/holding mutation.
  const existing = portfolioTables.get(p.id);
  if (existing) {
    const rows = p.holdings.filter((h) => h.kind !== "cash");
    existing.refresh({ rows });
    return existing;
  }

  // First-time render: build the slot skeleton + create a new tickerTable.
  slot.innerHTML = `
    <div class="pf-holdings-table" id="pf-table-${escapeHtml(p.id)}"></div>
    <div class="pf-controls" id="pf-controls-${escapeHtml(p.id)}"></div>
    <div class="pf-add-row">
      <button class="pf-add-holding mini">+ Add holding</button>
      <button class="pf-add-cash mini">+ Add cash row</button>
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
    // Per-portfolio section — tickerTable namespaces pfSort/pfVisible/
    // pfOrder under this key, and _assertValidSection accepts the
    // "portfolio.*" prefix in addition to the canonical "portfolio"
    // default. Two portfolios never see each other's column prefs.
    section: `portfolio.${pid}`,
    containerSel: `#pf-table-${CSS.escape(p.id)}`,
    // Columns dropdown + ↺ reset render inside the portfolio body via
    // controlsSel (tickerTable owns the DOM and the persistence wiring).
    // controlsMode="columnsOnly" skips the add-input — Portfolio uses
    // bespoke +Add holding / +Add cash buttons in the body instead.
    controlsSel: `#pf-controls-${CSS.escape(p.id)}`,
    controlsMode: "columnsOnly",
    columns,
    initialSort: { key: "default", dir: 1 },
    // Starred rows get the amber/bull/bear row tint + left border (state
    // lives in the per-portfolio watchColors Map).
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
      await API.putPortfolioColumns(`portfolio.${pid}`, { order: prefs.order, visibility });
    },
    onReorder: async (order) => {
      await API.reorderHoldings(pid, order);
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
      const h = await API.addPortfolioHolding(p.id, { symbol: v.symbol, shares: 0, total_cost: 0 });
      // Optimistic: push the returned holding and re-render without a full refresh.
      p.holdings.push(h);
      const pfSlot = document.querySelector(`.pf-pf[data-pid="${CSS.escape(p.id)}"] .pf-pf-body`);
      if (pfSlot && expanded.has(p.id)) renderHoldingsTable(pfSlot, p);
      renderGrandHeader();
    } catch (e) { alert(e.message); }
  });
  slot.querySelector(".pf-add-cash").addEventListener("click", async () => {
    try {
      const h = await API.addPortfolioCash(p.id, { label: "Cash", total_cost: 0, total_value: 0 });
      // Optimistic: push the returned cash row and re-render without a full refresh.
      p.holdings.push(h);
      const pfSlot = document.querySelector(`.pf-pf[data-pid="${CSS.escape(p.id)}"] .pf-pf-body`);
      if (pfSlot && expanded.has(p.id)) renderHoldingsTable(pfSlot, p);
      renderGrandHeader();
    } catch (e) { alert(e.message); }
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
        // Optimistic: update the cash row in local state and re-render the
        // holdings table + card totals without a full refresh.
        const cashH = p.holdings.find((h) => h.kind === "cash");
        if (cashH) { cashH.total_cost = num; cashH.total_value = num; }
        const pfSlot = document.querySelector(`.pf-pf[data-pid="${CSS.escape(p.id)}"] .pf-pf-body`);
        if (pfSlot && expanded.has(p.id)) renderHoldingsTable(pfSlot, p);
        renderGrandHeader();
      } catch (e) {
        tr.querySelector(".pf-cash-edit").classList.add("error");
        setTimeout(() => tr.querySelector(".pf-cash-edit").classList.remove("error"), 2000);
      }
    }, 600);
  });
  tr.querySelector(".pf-cash-del").addEventListener("click", async () => {
    if (!confirm("Remove cash row from this portfolio?")) return;
    try {
      await API.removePortfolioCash(p.id);
      // Optimistic: filter out the cash row from local state and re-render
      // the holdings table + card totals without a full refresh.
      p.holdings = p.holdings.filter((h) => h.kind !== "cash");
      const pfSlot = document.querySelector(`.pf-pf[data-pid="${CSS.escape(p.id)}"] .pf-pf-body`);
      if (pfSlot && expanded.has(p.id)) renderHoldingsTable(pfSlot, p);
      renderGrandHeader();
    } catch (e) { alert(e.message); }
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

// ---- Card header controls (no Columns dropdown — it moved inside each portfolio) ----
//
// The card header now only owns the "+ Create portfolio" button. The
// earlier "▼ all / ▲ all" mass toggle was removed per user request —
// each portfolio's expand/collapse state lives in localStorage
// (`pfExpanded`, see loadExpanded / saveExpanded above) and is set
// per-portfolio by clicking the header or the caret. Column visibility
// + reorder for each portfolio lives inside the portfolio's own
// tickerTable controls (rendered via controlsSel="#pf-controls-<pid>");
// per-portfolio state means the header can no longer host one shared
// Columns dropdown — there's no single "active" portfolio. tickerTable
// owns the localStorage + PUT persistence wiring for each portfolio;
// portfolio.js has no remaining column-state code.

function renderHeaderControls() {
  const el = $("#portfolioControls");
  if (!el) return;
  el.innerHTML = `
    <div class="pf-header-actions">
      <button class="pf-create mini">+ Create portfolio</button>
    </div>
  `;

  el.querySelector(".pf-create").addEventListener("click", async () => {
    const name = prompt("Portfolio name (e.g. Fidelity Cash):");
    if (!name || !name.trim()) return;
    try {
      const result = await API.createPortfolio(name.trim());
      // result is { id, portfolio } — update local state optimistically
      const id = result.id;
      portfolioData.portfolios[id] = result.portfolio;
      expanded.add(id);
      saveExpanded();
      renderPortfolioInsert(result.portfolio, { autoExpand: true });
      renderGrandHeader();
    } catch (e) { alert(e.message); }
  });
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
