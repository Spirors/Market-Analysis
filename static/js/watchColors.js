// watchColors.js — Portfolio star state (per-portfolio, per-ticker).
//
// The Portfolio section has its own localStorage key and singleton Map.
// Left-click cycles a star through amber -> bull -> bear -> amber;
// the context menu clears it (right-click, or the keyboard route:
// Shift+F10 / the dedicated ContextMenu key). The star icon + row tint +
// left border take the tier color (see the tr.earn-row-* rules in style.css).
//
// Portfolio star scoping: starring NVDA in "Fidelity Main" must NOT also
// star NVDA in "Fidelity Roth IRA". The portfolio Map stores composite
// keys "<pid>::<sym>" so each (portfolio, ticker) pair has independent
// star state. Helper functions compose/decompose the key transparently.

import { escapeHtml } from "./format.js";

const SECTIONS = {
  portfolio: { key: "pfWatchColors", legacy: null },
};
const COLORS = ["amber", "bull", "bear"];

function loadSection(section) {
  const cfg = SECTIONS[section];
  const m = new Map();
  try {
    const saved = JSON.parse(localStorage.getItem(cfg.key));
    if (saved && typeof saved === "object" && !Array.isArray(saved)) {
      for (const [sym, color] of Object.entries(saved)) if (COLORS.includes(color)) m.set(sym, color);
    }
  } catch (e) { /* ignore */ }
  return m;
}

const _maps = {};
export function getWatchColors(section) {
  if (!SECTIONS[section]) return new Map();
  if (!_maps[section]) _maps[section] = loadSection(section);
  return _maps[section];
}

export function saveWatchColors(section, map) {
  const cfg = SECTIONS[section];
  if (!cfg) return;
  try { localStorage.setItem(cfg.key, JSON.stringify(Object.fromEntries(map))); } catch (e) { /* ignore */ }
}

// Live session singleton — only the Portfolio section remains after the
// Earnings watchlist section was removed.
export const portfolioWatchColors = getWatchColors("portfolio");

export function nextWatchColor(cur) {
  const i = COLORS.indexOf(cur);
  return COLORS[(i + 1) % COLORS.length];
}

// ---- Portfolio-scoped star helpers -----------------------------------------
// The portfolio Map uses composite keys "<pid>::<sym>" so starring NVDA in
// "Fidelity Main" does not also star NVDA in "Fidelity Roth IRA".

function _pfKey(pid, sym) {
  return `${pid}::${sym}`;
}

export function getPortfolioWatchColor(pid, sym) {
  return portfolioWatchColors.get(_pfKey(pid, sym)) || null;
}

export function setPortfolioWatchColor(pid, sym, color) {
  if (color) {
    portfolioWatchColors.set(_pfKey(pid, sym), color);
  } else {
    portfolioWatchColors.delete(_pfKey(pid, sym));
  }
  saveWatchColors("portfolio", portfolioWatchColors);
}

// ---- Render star button ----------------------------------------------------

export function renderStarBtn(sym, color) {
  const star = color ? "★" : "☆";
  const label = color
    ? `${sym} starred ${color}. Click, Enter or Space cycles the colour; to clear, open the context menu (right-click, Shift+F10 or the ContextMenu key).`
    : `${sym} not starred. Click, Enter or Space starts the colour cycle; to clear, open the context menu (right-click, Shift+F10 or the ContextMenu key).`;
  const title = label;
  return `<button type="button" class="earn-star" data-sym="${escapeHtml(sym)}" data-color="${escapeHtml(color || "")}" aria-pressed="${color ? "true" : "false"}" aria-label="${escapeHtml(label)}" title="${escapeHtml(title)}">${star}</button>`;
}
