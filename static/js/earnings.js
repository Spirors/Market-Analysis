// earnings.js — Earnings watchlist section. Thin wrapper over the shared
// tickerTable.js framework; only watch-stars (Earnings-only) and column
// metadata live here.

import { $, escapeHtml } from "./format.js";
import { createTickerTable } from "./tickerTable.js?v=20260905h";
import { earningsWatchColors as watchColors, saveWatchColors, nextWatchColor, renderStarBtn } from "./watchColors.js?v=20260905e";
import * as API from "./api.js";

const EARN_COLUMNS = [
  { key: "_star", label: "Star", default: true, sortable: false,
    fmt: (r) => renderStarBtn(r.symbol, watchColors.get(r.symbol)) },
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

let lastData = { companies: [] };
let table = null;

export function renderEarnings(earn) {
  lastData = earn || { companies: [] };
  if (!table) {
    table = createTickerTable({
      section: "earnings",
      containerSel: "#earningsBody",
      controlsSel: "#earnControls",
      // Earnings never uses the "default" sort mode — it always renders
      // sorted by a real column. Symbol asc is a neutral starting point
      // that's clearly indicated by the ▲ in the header (no longer looks
      // like an unannounced "default by date" ordering).
      initialSort: { key: "symbol", dir: 1 },
      columns: EARN_COLUMNS,
      fetchData: async () => ({ rows: lastData.companies || [] }),
      addRow: async (sym) => {
        const v = await API.validateEarningsSymbol ? API.validateEarningsSymbol(sym) : { valid: true, symbol: sym };
        if (!v.valid) throw new Error(v.reason || "invalid symbol");
        const data = await API.addEarningsSymbol(sym);
        lastData = { companies: data.companies || [] };
        return { rows: lastData.companies };
      },
      removeRow: async (sym) => {
        const data = await API.removeEarningsSymbol(sym);
        watchColors.delete(sym);
        saveWatchColors("earnings", watchColors);
        lastData = { companies: data.companies || [] };
        return { rows: lastData.companies };
      },
      editCell: null,
      columnPrefsUrl: async (prefs) => {
        const visibility = {};
        for (const c of EARN_COLUMNS) visibility[c.key] = prefs.visibility[c.key] || false;
        await API.putPortfolioColumns("earnings", { order: prefs.order, visibility });
      },
      // Restore the star-row tint: apply the matching earn-row-{amber,bull,bear}
      // class to each row so the existing CSS rules in style.css take effect.
      rowClass: (r) => {
        const c = watchColors.get(r.symbol);
        return c ? `earn-row-${c}` : "";
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
      saveWatchColors("earnings", watchColors);
      table.refresh();
    });
    body.addEventListener("contextmenu", (e) => {
      const star = e.target.closest(".earn-star");
      if (!star) return;
      e.preventDefault();
      const sym = star.dataset.sym;
      watchColors.delete(sym);
      saveWatchColors("earnings", watchColors);
      table.refresh();
    });
  }
}
