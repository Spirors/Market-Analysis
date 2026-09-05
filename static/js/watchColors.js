// watchColors.js — shared watch/star state across Earnings + Portfolio.
//
// One module-level Map is the single source of truth for the session: both
// consumers import the same `watchColors` instance, so a star set in the
// Earnings watchlist is immediately visible in the Portfolio tables (and
// vice versa) without a page reload. Persistence is localStorage under
// `earnWatchColors` — the same key both sections used before this module
// existed, so existing stars carry over unchanged.
//
// Left-click cycles a star through amber -> bull -> bear -> amber; right-click
// clears it. The star icon + row tint + left border take the tier color
// (see the tr.earn-row-* rules in style.css).

import { escapeHtml } from "./format.js";

const STORAGE_KEY = "earnWatchColors";
const LEGACY_KEY = "earnWatched";
const COLORS = ["amber", "bull", "bear"];

export function loadWatchColors() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (saved && typeof saved === "object" && !Array.isArray(saved)) {
      const m = new Map();
      for (const [sym, color] of Object.entries(saved)) if (COLORS.includes(color)) m.set(sym, color);
      return m;
    }
    // Legacy pre-tiers format: a plain array of watched symbols -> amber.
    const legacy = JSON.parse(localStorage.getItem(LEGACY_KEY));
    if (Array.isArray(legacy) && legacy.length) {
      const m = new Map();
      for (const sym of legacy) if (sym) m.set(sym, "amber");
      return m;
    }
  } catch (e) { /* ignore */ }
  return new Map();
}

export function saveWatchColors(map) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(Object.fromEntries(map))); } catch (e) { /* ignore */ }
}

export function nextWatchColor(cur) {
  const i = COLORS.indexOf(cur);
  return COLORS[(i + 1) % COLORS.length];
}

export function renderStarBtn(sym, color) {
  const star = color ? "★" : "☆";
  const title = color
    ? `${sym} · ${color} (left-click cycles, right-click clears)`
    : `Watch ${sym}`;
  return `<button type="button" class="earn-star" data-sym="${escapeHtml(sym)}" data-color="${escapeHtml(color || "")}" aria-pressed="${color ? "true" : "false"}" title="${escapeHtml(title)}">${star}</button>`;
}

// Live session singleton — both sections mutate this one Map.
export const watchColors = loadWatchColors();