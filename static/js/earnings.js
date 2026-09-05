// earnings.js — Earnings watchlist section. Thin wrapper over the shared
// tickerTable.js framework; only watch-stars (Earnings-only) and column
// metadata live here.

import { $, escapeHtml } from "./format.js";
import { createTickerTable } from "./tickerTable.js";
import * as API from "./api.js";

const EARN_COLUMNS = [
  { key: "_star", label: "", default: true, sortable: false,
    fmt: (r) => {
      const color = watchColors.get(r.symbol) || null;
      const star = color ? "★" : "☆";
      const title = color
        ? `${r.symbol} · ${color} (left-click cycles color, right-click clears)`
        : `Watch ${r.symbol} (left-click cycles color, right-click clears)`;
      return `<button type="button" class="earn-star" data-sym="${escapeHtml(r.symbol)}" data-color="${escapeHtml(color || "")}" aria-pressed="${color ? "true" : "false"}" title="${escapeHtml(title)}">${star}</button>`;
    }
  },
  { key: "symbol", label: "Ticker", default: true,
    fmt: (r) => `<b>${escapeHtml(r.symbol)}</b>` },
  { key: "date", label: "Next earnings", default: true,
    fmt: (r) => escapeHtml(r.next_earnings || r.last_earnings || "—") },
  { key: "price", label: "Last price", default: true, num: true,
    fmt: (r) => r.price == null ? "—" : escapeHtml(String(r.price)) },
  { key: "pct_daily", label: "Daily %", default: true, num: true,
    fmt: (r) => r.pct_daily == null ? "—" : `<span class="${r.pct_daily >= 0 ? "pos" : "neg"}">${r.pct_daily >= 0 ? "+" : ""}${escapeHtml(String(r.pct_daily))}%</span>` },
  { key: "pct_7d", label: "7-day %", default: true, num: true,
    fmt: (r) => r.pct_7d == null ? "—" : `<span class="${r.pct_7d >= 0 ? "pos" : "neg"}">${r.pct_7d >= 0 ? "+" : ""}${escapeHtml(String(r.pct_7d))}%</span>` },
  { key: "high_52w", label: "52W high", default: true, num: true,
    fmt: (r) => r.high_52w == null ? "—" : escapeHtml(String(r.high_52w)) },
  { key: "forward_pe", label: "Forward PE", default: true, num: true,
    fmt: (r) => r.forward_pe == null ? "—" : escapeHtml(String(r.forward_pe)) },
  { key: "forward_peg", label: "Forward PEG", default: false, num: true,
    fmt: (r) => r.forward_peg == null ? "—" : escapeHtml(String(r.forward_peg)) },
  { key: "market_cap_fmt", label: "Market cap", default: false, num: true,
    fmt: (r) => escapeHtml(r.market_cap_fmt || "—") },
  { key: "sector", label: "Sector", default: false, num: true,
    fmt: (r) => escapeHtml(r.sector || "—") },
  { key: "rec", label: "AI rec", default: true,
    fmt: (r) => `<span class="earn-rec" style="background:${r.rec_color}22;color:${r.rec_color};border:1px solid ${r.rec_color}" title="${escapeHtml(r.rec_reason || "")}">${escapeHtml(r.rec_signal || "—")}</span>` },
];

const WATCH_COLORS = ["amber", "bull", "bear"];

function loadWatchColors() {
  try {
    const saved = JSON.parse(localStorage.getItem("earnWatchColors"));
    if (saved && typeof saved === "object" && !Array.isArray(saved)) {
      const m = new Map();
      for (const [sym, color] of Object.entries(saved)) if (WATCH_COLORS.includes(color)) m.set(sym, color);
      return m;
    }
    const legacy = JSON.parse(localStorage.getItem("earnWatched"));
    if (Array.isArray(legacy) && legacy.length) {
      const m = new Map();
      for (const sym of legacy) if (sym) m.set(sym, "amber");
      return m;
    }
  } catch (e) { /* ignore */ }
  return new Map();
}

let watchColors = loadWatchColors();
let lastData = { companies: [] };

function saveWatchColors() {
  const live = new Set((lastData.companies || []).map((r) => r.symbol));
  const obj = {};
  for (const [sym, color] of watchColors.entries()) if (live.has(sym)) obj[sym] = color;
  try { localStorage.setItem("earnWatchColors", JSON.stringify(obj)); } catch (e) { /* ignore */ }
}

function nextWatchColor(current) {
  const idx = WATCH_COLORS.indexOf(current);
  if (idx < 0) return WATCH_COLORS[0];
  return WATCH_COLORS[(idx + 1) % WATCH_COLORS.length];
}

let table = null;

export function renderEarnings(earn) {
  lastData = earn || { companies: [] };
  if (!table) {
    table = createTickerTable({
      section: "earnings",
      containerSel: "#earningsBody",
      controlsSel: "#earnControls",
      columns: EARN_COLUMNS,
      fetchData: async () => ({ rows: lastData.companies || [] }),
      addRow: async (sym) => {
        const v = await API.validateEarningsSymbol ? API.validateEarningsSymbol(sym) : { valid: true, symbol: sym };
        if (!v.valid) throw new Error(v.reason || "invalid symbol");
        const data = await API.addEarningsSymbol(sym);
        return { rows: data.companies || [] };
      },
      removeRow: async (sym) => {
        const data = await API.removeEarningsSymbol(sym);
        watchColors.delete(sym);
        saveWatchColors();
        return { rows: data.companies || [] };
      },
      editCell: null,
      columnPrefsUrl: async (prefs) => {
        const visibility = {};
        for (const c of EARN_COLUMNS) visibility[c.key] = prefs.visibility[c.key] || false;
        await API.putPortfolioColumns("earnings", { order: prefs.order, visibility });
      },
    });
  }
  table.render({ rows: lastData.companies || [] });
  // Event delegation: bind once on the body element so listeners survive
  // table.refresh() DOM rebuilds. The body element itself is never replaced.
  const body = $("#earningsBody");
  if (body && !body.dataset.starBound) {
    body.dataset.starBound = "1";
    body.addEventListener("click", (e) => {
      const star = e.target.closest(".earn-star");
      if (!star) return;
      e.preventDefault();
      const sym = star.dataset.sym;
      watchColors.set(sym, nextWatchColor(watchColors.get(sym)));
      saveWatchColors();
      table.refresh();
    });
    body.addEventListener("contextmenu", (e) => {
      const star = e.target.closest(".earn-star");
      if (!star) return;
      e.preventDefault();
      const sym = star.dataset.sym;
      watchColors.delete(sym);
      saveWatchColors();
      table.refresh();
    });
  }
}
