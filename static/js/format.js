// Shared formatting + escaping helpers and tiny DOM utilities used by every
// dashboard module.

export const $ = (sel) => document.querySelector(sel);

export function fmtPrice(v) {
  if (v == null) return "—";
  return Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 });
}
export function fmtPct(v) {
  if (v == null) return "";
  const n = Number(v);
  return (n >= 0 ? "+" : "") + n.toFixed(2) + "%";
}
export function pctClass(v) {
  if (v == null) return "";
  return v >= 0 ? "pos" : "neg";
}
export function toneCellClass(tone) {
  if (tone === "bullish") return "tone-cell tone-bull";
  if (tone === "bearish") return "tone-cell tone-bear";
  return "tone-cell tone-sub";
}
export function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// Allowlist for hrefs built from external data (RSS links, EDGAR links).
// escapeHtml alone can't stop `javascript:` URIs inside an href attribute,
// so only http/https pass; anything else returns null and callers must
// render a non-anchor fallback instead of an <a>.
export function safeUrl(u) {
  const s = String(u ?? "").trim();
  return /^https?:\/\//i.test(s) ? s : null;
}

export function fmtFloat(v) {
  if (v == null) return "—";
  return Number(v).toFixed(2);
}
export function fmtPctHtml(v) {
  if (v == null) return "—";
  return `<span class="${pctClass(v)}">${fmtPct(v)}</span>`;
}

// Tiny "as of" stamp for cards that blend two sources (spot + futures).
export function asofNote(ts) {
  if (!ts || typeof ts !== "string") return "";
  return `<div class="asof-note">As of ${escapeHtml(ts.replace("T", " ").slice(0, 16))}</div>`;
}
