// Shared formatting + escaping helpers and tiny DOM utilities used by every
// dashboard module.

export const $ = (sel) => document.querySelector(sel);

// All timestamps the dashboard stores are UTC ISO strings (the server-side
// "as of" is stamped in UTC, see app/service.py: `_now_iso`). The dashboard
// is read in US Eastern time, so every visible timestamp is rendered in
// `America/New_York` (which is EST in winter, EDT in summer — the standard
// ET convention used across US financial markets). Using a fixed UTC offset
// would be wrong in summer: a 4pm ET close would render as "5pm" if we hard
// pinned UTC-5, and as "3pm" if we hard pinned UTC-4.
const ET_TZ = "America/New_York";
const ET_FMT_LONG = new Intl.DateTimeFormat("en-US", {
  timeZone: ET_TZ,
  year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", second: "2-digit",
  hour12: false,
});
const ET_FMT_HM = new Intl.DateTimeFormat("en-US", {
  timeZone: ET_TZ,
  hour: "2-digit", minute: "2-digit", hour12: false,
});

function _parseTs(ts) {
  if (!ts || typeof ts !== "string") return null;
  const d = new Date(ts);
  return isNaN(d) ? null : d;
}

// Render a UTC ISO timestamp in ET, e.g. "2026-08-22 12:00" (minute precision).
// Returns "—" for missing or unparseable input.
export function fmtTimestampET(ts) {
  const d = _parseTs(ts);
  if (!d) return "—";
  const parts = ET_FMT_LONG.formatToParts(d);
  const get = (t) => parts.find((p) => p.type === t)?.value || "";
  return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")}`;
}

// Just the HH:MM portion in ET, e.g. "14:05" — for the per-card vintage
// stamps. Returns "" when the input is missing or unparseable so callers can
// fall through to "remove the stamp" instead of printing a bad time.
export function fmtHmET(ts) {
  const d = _parseTs(ts);
  if (!d) return "";
  return ET_FMT_HM.format(d);
}

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
// Renders the source timestamp in US Eastern time (handles EST/EDT).
export function asofNote(ts) {
  if (!ts || typeof ts !== "string") return "";
  return `<div class="asof-note">As of ${escapeHtml(fmtTimestampET(ts))} ET</div>`;
}
