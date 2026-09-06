// watchColors.js — per-section watch/star state for Earnings + Portfolio.
//
// Each section has its own localStorage key and singleton Map, so starring
// a ticker in the Portfolio tables does NOT affect the Earnings watchlist
// (and vice versa). Left-click cycles a star through amber -> bull -> bear
// -> amber; right-click clears it. The star icon + row tint + left border
// take the tier color (see the tr.earn-row-* rules in style.css).
//
// Migration: the Earnings section keeps the legacy "earnWatched" pre-tiers
// migration so users who only ever used Earnings keep their existing
// watch list. Portfolio starts with an empty Map (no legacy to migrate).

import { escapeHtml } from "./format.js";

const SECTIONS = {
  earnings: { key: "earnWatchColors", legacy: "earnWatched" },
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
    // Legacy pre-tiers migration only applies to the original Earnings section.
    if (cfg.legacy) {
      const legacy = JSON.parse(localStorage.getItem(cfg.legacy));
      if (Array.isArray(legacy) && legacy.length) {
        for (const sym of legacy) if (sym) m.set(sym, "amber");
      }
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

// Live session singletons — each section mutates its own Map.
export const earningsWatchColors = getWatchColors("earnings");
export const portfolioWatchColors = getWatchColors("portfolio");

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