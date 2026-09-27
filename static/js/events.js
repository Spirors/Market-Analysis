// Market events timeline: week grouping/selection, tag filter chips,
// event rendering, and the manual review mutations (tag add/remove,
// dimension override, delete, hide source).

import { $, escapeHtml, safeUrl } from "./format.js";
import { deleteEvent, suppressSource, updateEventDimensions, updateEventTags } from "./api.js";
import { attachTooltip } from "./tooltip.js";

let eventsCache = [];
let activeTags = new Set();
const WEEK_KEY = "tlSelectedWeek";
const MONTH_KEY = "tlSelectedMonth";
const GROUP_MODE_KEY = "tlGroupingMode";
let groupingMode = "week"; // "week" | "month" — persisted per browser
let activePeriodKey = null;

function initGrouping() {
  try {
    const m = localStorage.getItem(GROUP_MODE_KEY);
    if (m === "month") groupingMode = "month";
  } catch (e) { /* ignore */ }
  try {
    activePeriodKey = localStorage.getItem(groupingMode === "month" ? MONTH_KEY : WEEK_KEY);
  } catch (e) { activePeriodKey = null; }
}

// Each mode keeps its own selected period in localStorage, so switching modes
// never clobbers the other mode's selection.
function saveSelectedPeriod(key) {
  try {
    localStorage.setItem(groupingMode === "month" ? MONTH_KEY : WEEK_KEY, key);
  } catch (e) { /* ignore */ }
}

// Fixed tag dimensions (set by the ingest heuristics). All of these are now
// editable through the popover — when the heuristic is wrong the user picks a
// different valid value (or clears the dimension entirely) and the change
// persists across RSS refreshes via the user_edited lock.
const FIXED_DIMENSIONS = ["macro", "micro", "government", "company", "bullish", "bearish", "neutral", "us", "japan", "china", "middle-east", "europe", "korea", "russia-ukraine", "global", "asia"];
const AUTO_TAG = "ai";

// Reverse lookup: fixed-dimension value → which column it controls. Used by
// the popover to know which dimension a clicked pill belongs to (and which
// allowed-value set to populate the <select> with). Mirrors the
// _DIMENSION_VALUES table in app/store.py so the front-end can never offer
// a value the backend would reject.
const TAG_TO_FIELD = {
  macro: "category", micro: "category",
  government: "actor", company: "actor",
  bullish: "direction", bearish: "direction", neutral: "direction",
  us: "region", global: "region", asia: "region", europe: "region",
  "middle-east": "region", "russia-ukraine": "region", korea: "region",
  japan: "region", china: "region",
};
const FIELD_VALUES = {
  category: ["macro", "micro"],
  actor: ["government", "company"],
  direction: ["bullish", "bearish", "neutral"],
  region: ["us", "global", "asia", "europe", "middle-east", "russia-ukraine", "korea", "japan", "china"],
};

const TAG_ORDER = [...FIXED_DIMENSIONS, AUTO_TAG];

function tagClass(t) {
  if (t === "macro" || t === "micro") return t;
  if (t === "government") return "gov";
  if (t === "company") return "co";
  if (t === "bullish") return "bull";
  if (t === "bearish") return "bear";
  if (t === "neutral") return "neutral";
  if (t === AUTO_TAG) return "ai";
  return "region";
}

// Tags that came from the user (and are mutable) versus the fixed dimensions
// the ingest heuristics set on insert. The merged `tags` array returned by
// the API is the union of both; subtracting the fixed ones plus the auto
// tag leaves only the user's contributions.
function userTagsForEvent(n) {
  const all = n.tags || [];
  return all.filter((t) => !FIXED_DIMENSIONS.includes(t) && t !== AUTO_TAG);
}

// ---- News filter chips (region / source weight / topic) --------------------
// Three chip rows sit above the legacy tag chips. Region is multi-select,
// source weight single-select, topic multi-select. All compose with the tag
// chips and the seed-only toggle, and the whole state persists per-browser.

const NEWS_FILTER_KEY = "tlNewsFilters";

const REGION_ORDER = ["us", "global", "asia", "europe", "middle-east", "russia-ukraine", "korea", "japan", "china", "other"];
const REGION_LABELS = {
  us: "US", global: "Global", asia: "Asia", europe: "Europe",
  "middle-east": "Middle East", "russia-ukraine": "Russia/Ukraine",
  korea: "Korea", japan: "Japan", china: "China", other: "Other",
};
const WEIGHT_ORDER = ["high", "med", "low"];
const WEIGHT_LABELS = { high: "High", med: "Med", low: "Low" };
const TOPIC_ORDER = ["rates", "equity", "macro", "micro"];
const TOPIC_LABELS = { rates: "Rates", equity: "Equity", macro: "Macro", micro: "Micro" };

// Seed events = the hand-curated timeline (Wikipedia + gauge extracts) that
// seeded data/events.json. Live RSS items are everything else. The seed-only
// toggle preserves this legacy Wikipedia view.
const SEED_SOURCES = new Set(["wikipedia", "curated (gauge)"]);

let regionSel = new Set();
let weightSel = null; // "high" | "med" | "low" | null (single-select)
let topicSel = new Set();
let seedOnly = false;

function loadNewsFilters() {
  try {
    const f = JSON.parse(localStorage.getItem(NEWS_FILTER_KEY));
    if (f && typeof f === "object") {
      if (Array.isArray(f.regions)) regionSel = new Set(f.regions.filter((r) => REGION_ORDER.includes(r)));
      if (WEIGHT_ORDER.includes(f.weight)) weightSel = f.weight;
      if (Array.isArray(f.topics)) topicSel = new Set(f.topics.filter((t) => TOPIC_ORDER.includes(t)));
      if (typeof f.seedOnly === "boolean") seedOnly = f.seedOnly;
    }
  } catch (e) { /* ignore */ }
}

function saveNewsFilters() {
  try {
    localStorage.setItem(NEWS_FILTER_KEY, JSON.stringify({
      regions: [...regionSel],
      weight: weightSel,
      topics: [...topicSel],
      seedOnly,
    }));
  } catch (e) { /* ignore */ }
}

// Backend emits a region per event; anything outside the taxonomy (or missing)
// buckets into "other" so the chip set always covers every row.
function eventRegion(e) {
  const r = String(e.region || "").toLowerCase();
  return REGION_ORDER.includes(r) ? r : "other";
}

// Source-weight bands: high ≥ 1.1, med 0.9..1.1, low < 0.9. Missing values
// are unclassified (no badge, matched by no chip) — never fabricated.
function weightBand(w) {
  if (w == null || isNaN(w)) return null;
  return w >= 1.1 ? "high" : w >= 0.9 ? "med" : "low";
}

// Topic membership is derived from the event's category tag plus headline/
// summary keywords. An event can carry several topics (e.g. macro + rates).
const RATES_TERMS = ["rate", "rates", "yield", "yields", "bond", "bonds", "treasury", "fed", "fomc", "cpi", "inflation", "ecb", "boj", "debt", "auction", "mortgage"];
const EQUITY_TERMS = ["stock", "stocks", "equit", "s&p", "nasdaq", "dow", "rally", "selloff", "sell-off", "earnings", "shares", "record high", "bear market", "bull market", "index"];

function eventTopics(e) {
  const topics = new Set();
  const cat = String(e.category || "").toLowerCase();
  if (cat === "macro") topics.add("macro");
  if (cat === "micro") topics.add("micro");
  const text = `${e.title || ""} ${e.summary || ""}`.toLowerCase();
  if (RATES_TERMS.some((t) => text.includes(t))) topics.add("rates");
  if (EQUITY_TERMS.some((t) => text.includes(t))) topics.add("equity");
  return topics;
}

function isSeedEvent(e) {
  return SEED_SOURCES.has(String(e.source || "").trim().toLowerCase());
}

// Finance-relevance chip: 0..10 score, color-graded by band.
function relBand(v) {
  if (v >= 9) return "crit";
  if (v >= 7) return "high";
  if (v >= 4) return "med";
  return "low";
}

function relFmt(v) {
  const n = Number(v);
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

// Parse a stored ISO timestamp on an explicit UTC basis. Records written
// before the explicit-UTC fix are naive; a missing designator is treated as
// UTC (never as the browser's local time) so legacy and new rows bucket,
// sort, and display identically. Returns null for empty/unparseable input.
export function parseUtc(s) {
  let t = String(s || "").trim();
  if (!t) return null;
  if (!/[zZ]$|[+-]\d{2}:?\d{2}$/.test(t)) {
    t += /^\d{4}-\d{2}-\d{2}$/.test(t) ? "T00:00:00Z" : "Z";
  }
  const d = new Date(t);
  return isNaN(d.getTime()) ? null : d;
}

// Monday-start week bucket, computed on the UTC calendar so the bucket key
// agrees with the stored UTC date (and with the row's .tl-date).
export function weekStart(s) {
  const d = parseUtc(s);
  if (!d) return null;
  const day = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - day);
  d.setUTCHours(0, 0, 0, 0);
  return d;
}

function fmtWeek(d) {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

function fmtWeekRange(ws) {
  const end = new Date(ws);
  end.setUTCDate(end.getUTCDate() + 6);
  const a = fmtWeek(ws);
  const b = fmtWeek(end);
  const [monthA, dayA] = a.split(" ");
  const [monthB, dayB] = b.split(" ");
  return monthA === monthB ? `${monthA} ${dayA}–${dayB}` : `${a} – ${b}`;
}

export function renderNews(items) {
  eventsCache = items || [];
  activeTags = new Set();
  renderTagFilters();
  applyEventFilter();
}

function renderTagFilters() {
  // Resolve the period scope the same way applyEventFilter does, so the tag
  // chips are correct even on the very first render (before the period selector
  // has run). Without this, a fresh browser shows an empty tag chip row.
  const groups = buildGroups(eventsCache, groupingMode);
  if (!activePeriodKey || !groups.some((g) => g.key === activePeriodKey)) {
    activePeriodKey = groups.length ? groups[0].key : null;
  }
  const group = groups.find((g) => g.key === activePeriodKey);
  const scope = group ? group.items : [];
  const counts = {};
  scope.forEach((e) => (e.tags || []).forEach((t) => { counts[t] = (counts[t] || 0) + 1; }));
  const tags = [...new Set([
    ...TAG_ORDER.filter((t) => counts[t]),
    ...Object.keys(counts).filter((t) => !TAG_ORDER.includes(t)),
  ])];
  const el = $("#tlFilters");
  if (!el) return;
  el.innerHTML = tags.map((t) => {
    const active = activeTags.has(t) ? " active" : "";
    return `<button class="chip${active}" data-tag="${escapeHtml(t)}">${escapeHtml(t)}<span class="cnt">${counts[t]}</span></button>`;
  }).join("");
  el.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => {
    const t = b.dataset.tag;
    if (activeTags.has(t)) activeTags.delete(t); else activeTags.add(t);
    renderTagFilters();
    applyEventFilter();
  }));
}

// Region / source-weight / topic chip rows. Counts reflect the selected period
// (same scope as the tag chips). Region + topic are multi-select; source
// weight is single-select (clicking the active chip clears it).
function renderChipFilters() {
  const group = buildGroups(eventsCache, groupingMode).find((g) => g.key === activePeriodKey);
  const scope = group ? group.items : [];
  const regionCounts = {};
  const weightCounts = {};
  const topicCounts = {};
  scope.forEach((e) => {
    const r = eventRegion(e);
    regionCounts[r] = (regionCounts[r] || 0) + 1;
    const wb = weightBand(e.source_weight);
    if (wb) weightCounts[wb] = (weightCounts[wb] || 0) + 1;
    eventTopics(e).forEach((t) => { topicCounts[t] = (topicCounts[t] || 0) + 1; });
  });

  const buildRow = (containerId, order, labels, counts, isActive, onToggle) => {
    const el = $(containerId);
    if (!el) return;
    el.innerHTML = order.map((key) => {
      const active = isActive(key);
      return `<button class="chip${active ? " active" : ""}" data-key="${key}" aria-pressed="${active}">${escapeHtml(labels[key] || key)}<span class="cnt">${counts[key] || 0}</span></button>`;
    }).join("");
    el.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => onToggle(b.dataset.key)));
  };

  buildRow("#tlRegionChips", REGION_ORDER, REGION_LABELS, regionCounts,
    (k) => regionSel.has(k),
    (k) => {
      if (regionSel.has(k)) regionSel.delete(k); else regionSel.add(k);
      saveNewsFilters(); renderChipFilters(); applyEventFilter();
    });

  buildRow("#tlWeightChips", WEIGHT_ORDER, WEIGHT_LABELS, weightCounts,
    (k) => weightSel === k,
    (k) => {
      weightSel = weightSel === k ? null : k;
      saveNewsFilters(); renderChipFilters(); applyEventFilter();
    });

  buildRow("#tlTopicChips", TOPIC_ORDER, TOPIC_LABELS, topicCounts,
    (k) => topicSel.has(k),
    (k) => {
      if (topicSel.has(k)) topicSel.delete(k); else topicSel.add(k);
      saveNewsFilters(); renderChipFilters(); applyEventFilter();
    });
}

const UNDATED_KEY = "—";

// Month bucket = the event's UTC YYYY-MM. Anything unparseable (missing or
// malformed published) lands in the undated bucket like the week path does.
function monthKeyOf(n) {
  const d = parseUtc(n.published);
  return d ? d.toISOString().slice(0, 7) : UNDATED_KEY;
}

function monthLabel(key) {
  const [y, m] = key.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

// Generic timeline grouping: "week" keeps the legacy Monday-start buckets,
// "month" buckets by year-month (YYYY-MM). Both sort newest first with the
// undated bucket pinned last.
function buildGroups(items, mode) {
  const groups = [];
  items.forEach((n) => {
    let key, label;
    if (mode === "month") {
      key = monthKeyOf(n);
      label = key === UNDATED_KEY ? "Undated" : monthLabel(key);
    } else {
      const ws = weekStart(n.published);
      key = ws ? ws.toISOString().slice(0, 10) : UNDATED_KEY;
      label = ws ? "Week of " + fmtWeekRange(ws) : "Undated";
    }
    let g = groups.find((x) => x.key === key);
    if (!g) { g = { key, label, items: [] }; groups.push(g); }
    g.items.push(n);
  });
  // Newest first within each period, on the parsed UTC instant (so a legacy
  // naive timestamp and a new Z-suffixed one for the same instant tie rather
  // than the Z string sorting "newer"). Tie-break on `link` (descending) to
  // match the backend's stable secondary sort (`store._sort_state`) so equal
  // timestamps don't reshuffle between renders.
  groups.forEach((g) => g.items.sort((a, b) => {
    const da = parseUtc(a.published);
    const db = parseUtc(b.published);
    const ta = da ? da.getTime() : -Infinity;
    const tb = db ? db.getTime() : -Infinity;
    if (ta !== tb) return tb - ta;
    const la = a.link || "";
    const lb = b.link || "";
    if (la === lb) return 0;
    return la < lb ? 1 : -1;
  }));
  // Newest periods first; undated always last.
  groups.sort((a, b) => {
    if (a.key === UNDATED_KEY) return 1;
    if (b.key === UNDATED_KEY) return -1;
    return a.key < b.key ? 1 : -1;
  });
  return groups;
}

function renderPeriodSelector(groups) {
  const sel = $("#weekSelect");
  const badge = $("#weekBadge");
  if (!sel) return;
  if (!groups.length) {
    activePeriodKey = null;
    sel.innerHTML = `<option value="">No ${groupingMode === "month" ? "months" : "weeks"}</option>`;
    if (badge) { badge.hidden = true; badge.textContent = ""; }
    return;
  }
  // Keep a still-valid selection; otherwise fall back to the newest period
  // that actually contains events.
  if (!activePeriodKey || !groups.some((g) => g.key === activePeriodKey)) {
    activePeriodKey = groups[0].key;
    saveSelectedPeriod(activePeriodKey);
  }
  sel.innerHTML = groups.map((g) =>
    `<option value="${escapeHtml(g.key)}"${g.key === activePeriodKey ? " selected" : ""}>${escapeHtml(g.label)} · ${g.items.length} event${g.items.length === 1 ? "" : "s"}</option>`
  ).join("");
  // Glanceable count for the selected period, next to the dropdown.
  const current = groups.find((g) => g.key === activePeriodKey);
  if (badge && current) {
    badge.textContent = `${current.items.length} event${current.items.length === 1 ? "" : "s"}`;
    badge.hidden = false;
  }
}

function applyEventFilter() {
  const el = $("#newsBody");
  const groups = buildGroups(eventsCache, groupingMode);
  renderPeriodSelector(groups);
  renderChipFilters();

  // Only the selected period renders; tag chips filter within it. The news
  // chipsets (region / weight / topic) and the seed-only toggle stack on top,
  // all ANDed.
  const group = groups.find((g) => g.key === activePeriodKey) || null;
  let items = group ? group.items : [];
  if (activeTags.size) items = items.filter((e) => (e.tags || []).some((t) => activeTags.has(t)));
  if (regionSel.size) items = items.filter((e) => regionSel.has(eventRegion(e)));
  if (weightSel) items = items.filter((e) => weightBand(e.source_weight) === weightSel);
  if (topicSel.size) items = items.filter((e) => [...eventTopics(e)].some((t) => topicSel.has(t)));
  if (seedOnly) items = items.filter(isSeedEvent);
  // Announce the filter/period outcome to screen readers. The visually hidden
  // status region updates on every applyEventFilter() call (period, chip,
  // seed-only, or mode change), so the silently re-rendered #newsBody is not
  // the only feedback.
  const status = $("#tlStatus");
  if (status) {
    const total = group ? group.items.length : 0;
    status.textContent = items.length
      ? `${items.length} of ${total} event${total === 1 ? "" : "s"} shown`
      : "No events match the selected filters.";
  }
  // #newsBody is replaced wholesale below, which orphans any tooltip surfaces
  // attached to the old row chips — tear them down before both exits.
  if (!items.length) {
    disposeEventTooltips();
    el.innerHTML = "<p>No events match the selected filters.</p>";
    return;
  }

  disposeEventTooltips();
  el.innerHTML = `<div class="timeline">` +
    `<div class="subhead accent">${escapeHtml(group.label)}</div>` +
    items.map(renderEventItem).join("") +
    `</div>`;
  wireEventTooltips();
}

// ---- Row tooltips ------------------------------------------------------------
// The audit dropped the native `title` attributes: they were mouse-only and sat
// on non-focusable elements. The two row chips whose visible text hides real
// information — the source-weight badge (shows only High/Med/Low, not the
// numeric weight) and the finance-relevance chip (shows a number, not the 0–10
// scale or the band cuts) — now use the app's shared tooltip affordance: a
// focusable trigger carrying aria-describedby to a role="tooltip" surface,
// shown on hover AND focus. The three action buttons (`+ tag`, `✕ Remove`,
// `hide source`) carried titles that only restated their labels (and, for
// hide-source, the scope the confirm modal already spells out), so their native
// titles were removed outright. #newsBody is replaced wholesale on every
// filter/render, so the previous surfaces are torn down before each re-wire so
// nothing leaks across renders.

let tooltipHandles = [];

function disposeEventTooltips() {
  for (const h of tooltipHandles) {
    try { h.hide(); } catch (e) { /* ignore */ }
    if (h.surface && h.surface.parentNode) h.surface.parentNode.removeChild(h.surface);
  }
  tooltipHandles = [];
}

function wireEventTooltips() {
  disposeEventTooltips();
  const body = $("#newsBody");
  if (!body) return;
  for (const el of body.querySelectorAll("[data-ev-tip]")) {
    const text = el.getAttribute("data-ev-tip");
    if (text) tooltipHandles.push(attachTooltip(el, { text }));
  }
}

// Source weight is a per-source confidence multiplier, never a verdict on the
// story. The bands mirror weightBand() (High ≥ 1.1, Med 0.9–1.1, Low < 0.9) and
// the two example factors mirror the events card tooltip (MarketWatch 1.2×,
// BBC 1.0×) — no new figures are invented here.
function weightTip(w, wb) {
  return `Source weight ${w} (${WEIGHT_LABELS[wb]}) — a per-source confidence `
    + `multiplier applied when ranking this row, not a verdict on the story. A `
    + `higher weight lifts the composite score; bands: High \u2265 1.1, `
    + `Med 0.9\u20131.1, Low < 0.9. Fixed per source at ingest `
    + `(e.g. MarketWatch 1.2\u00d7, BBC 1.0\u00d7) — no as-of date, it is a `
    + `static source setting, not a market reading.`;
}

// Relevance is a 0–10 market-movement score, colour-graded by the same cuts as
// relBand() (Critical ≥ 9, High 7–8.9, Medium 4–6.9, Low < 4).
function relevanceTip(v) {
  return `Finance relevance ${relFmt(v)}/10 — how market-moving the story is for `
    + `financial markets (0 = not financial, 10 = highly market-moving). Bands: `
    + `Critical \u2265 9, High 7\u20138.9, Medium 4\u20136.9, Low < 4. Scored `
    + `from the headline and summary at ingest; it lifts this row's ranking but `
    + `is not a price or a dated reading.`;
}

function renderEventItem(n) {
  // All pills are clickable now — every dimension (category / actor /
  // direction / region), the auto "ai" tag, and any user-added tag. The
  // popover branches on tag type: fixed-dimension pills show a <select>
  // of valid values for that dimension + Remove; user tags keep the
  // existing free-text rename + Remove.
  const pills = (n.tags || []).map((t) => {
    const field = TAG_TO_FIELD[t] || "";
    const cls = `pill ${tagClass(t)}${t === AUTO_TAG ? " pill-ai" : ""} pill-clickable`;
    const fieldAttr = field ? ` data-field="${field}"` : "";
    // role=button + tabindex=0 put the pill in the tab order and expose it as
    // an interactive control; the keydown delegate below maps Enter/Space to
    // the same branch as a click. Focusable also lets closeTagPopover() return
    // focus here when the popover closes (see closeTagPopover).
    return `<span class="${cls}" role="button" data-act="tag-edit" data-link="${escapeHtml(n.link)}" data-tag="${escapeHtml(t)}"${fieldAttr} tabindex="0">${escapeHtml(t)}</span>`;
  }).join(" ");
  // Impact tiers: Critical = loud (red edge + glow + BREAKING badge);
  // High = quiet amber accent. Everything else stays plain so ordinary rows
  // never read like an error state.
  const isCritical = n.impact === "Critical";
  const isHigh = n.impact === "High";
  const impactCls = isCritical ? " tl-critical" : isHigh ? " tl-high" : "";
  const breaking = isCritical ? `<span class="breaking-badge">Breaking</span>` : "";
  // Date is derived from the parsed UTC instant (not a raw string slice), so
  // a stored offset timestamp normalises to its UTC day and agrees with the
  // UTC week/month bucket it sits in.
  const d = parseUtc(n.published);
  const date = d ? d.toISOString().slice(0, 10) : "";
  const dateShown = n.date_label ? `${escapeHtml(n.date_label)} · ${date}` : (date || "—");
  // Only http(s) links become anchors (scheme allowlist); seed:// entries and
  // anything with an unexpected scheme render as plain text, never an <a>.
  const linkHref = safeUrl(n.link);
  const titleEl = linkHref
    ? `<a href="${escapeHtml(linkHref)}" target="_blank" rel="noopener">${escapeHtml(n.title)}</a>`
    : `<span class="tl-plain">${escapeHtml(n.title)}</span>`;
  const summary = n.summary ? `<div class="tl-summary">${escapeHtml(n.summary)}</div>` : "";

  // Row metadata strip: source-weight badge + finance-relevance chip only.
  // Region is no longer in the strip — it's now a regular editable pill in
  // the row's tag line so the user can fix a wrong region classification
  // the same way they fix category / actor / direction.
  const wb = weightBand(n.source_weight);
  const weightBadge = wb
    ? `<span class="sw-badge sw-${wb}" tabindex="0" data-ev-tip="${escapeHtml(weightTip(n.source_weight, wb))}">${WEIGHT_LABELS[wb]}</span>`
    : "";
  const rel = n.finance_relevance;
  const relChip = (rel != null && !isNaN(rel))
    ? `<span class="rel-chip rel-${relBand(rel)}" tabindex="0" data-ev-tip="${escapeHtml(relevanceTip(rel))}">${relFmt(rel)}</span>`
    : "";
  const metaStrip = `<div class="tl-meta">${weightBadge}${relChip}</div>`;

  // Inline tag-add form: a tiny "+ tag" button that reveals a text input.
  // Submitting it (Enter or button click) POSTs to /api/events/tags with
  // the new label and the event's link.
  const tagAdd = `<span class="pill-add" data-link="${escapeHtml(n.link)}">
      <button type="button" class="tag-add-btn" data-act="tag-add-open">+ tag</button>
      <span class="tag-add-form" hidden>
        <input type="text" class="tag-add-input" placeholder="new-tag" maxlength="32" />
        <button type="button" class="tag-add-submit" data-act="tag-add-submit" data-link="${escapeHtml(n.link)}">add</button>
        <button type="button" class="tag-add-cancel" data-act="tag-add-cancel">cancel</button>
      </span>
    </span>`;
  return `<div class="tl-item${impactCls}">
    <div class="tl-date">${dateShown}</div>
    <div class="tl-body">
      ${breaking}${titleEl}
      ${metaStrip}
      <div class="tl-tags">${pills}${tagAdd}</div>
      <div class="meta">${escapeHtml(n.source)}
        <button class="mini-del ev-del" data-link="${escapeHtml(n.link)}">✕ Remove</button>
        <button class="mini-del ev-hide" data-src="${escapeHtml(n.source)}">hide source</button>
      </div>
      ${summary}
    </div>
  </div>`;
}

// ---- Tag update + AI gauge ---------------------------------------------------
// A successful tag update may carry a recomputed AI gauge payload (the backend
// ---- Tag update + dimension update -------------------------------------------
// Both endpoints return the same {updated, events} shape; both just need to
// re-render the timeline. The AI capex-cycle gauge does NOT recompute on a
// tag edit — the user clicks the global Refresh button to pick up the
// change. This keeps the gauge stable while the user is curating tags.
async function applyTagUpdate(link, add, remove) {
  const resp = await updateEventTags(link, add, remove);
  renderNews(resp.events);
  return resp;
}

async function applyDimensionUpdate(link, field, value) {
  const resp = await updateEventDimensions(link, { [field]: value });
  renderNews(resp.events);
  return resp;
}

// Brief inline failure notice next to the clicked control. Reuses the
// earnings status styling (the only existing inline status classes). Defined at
// module scope so the popover save/remove handlers can report a failed
// mutation instead of throwing a ReferenceError.
function showEventError(btn, msg) {
  const meta = btn && (btn.closest(".meta") || btn.closest(".tl-tags") || btn.closest(".tl-body"));
  if (!meta) return;
  let st = meta.querySelector(".earn-status");
  if (!st) {
    st = document.createElement("span");
    meta.appendChild(st);
  }
  st.textContent = msg;
  st.className = "earn-status bad";
}

// ---- Confirm modal -----------------------------------------------------------
// The native confirm() dialog is too narrow for a deletion warning that names
// the event title and spells out the side effect on the AI gauge. This small
// modal reuses the existing card chrome (same border / radius / shadow) so
// the warning sits in a familiar shape and doesn't read as a separate UI.

let _modalConfirm = null;
let _modalReturnFocus = null;

function openConfirmModal({ title, body, confirmLabel, cancelLabel }) {
  const overlay = $("#confirmOverlay");
  const tEl = $("#confirmTitle");
  const bEl = $("#confirmBody");
  const ok = $("#confirmOk");
  const cancel = $("#confirmCancel");
  if (!overlay || !tEl || !bEl || !ok || !cancel) {
    // Fallback to native if the modal markup isn't on the page (shouldn't
    // happen — the modal lives in index.html — but stay defensive).
    return Promise.resolve(window.confirm(`${title}\n\n${body}`));
  }
  tEl.textContent = title;
  bEl.textContent = body;
  ok.textContent = confirmLabel || "Confirm";
  cancel.textContent = cancelLabel || "Cancel";
  // Remember the invoking control so focus can be restored when the modal
  // closes (keyboard/AT users must not be dropped back to <body>).
  _modalReturnFocus = document.activeElement;
  overlay.hidden = false;
  // Focus the cancel button by default — destructive actions must require a
  // deliberate click on the dangerous option.
  setTimeout(() => cancel.focus(), 0);
  return new Promise((resolve) => { _modalConfirm = resolve; });
}

function closeConfirmModal(result) {
  const overlay = $("#confirmOverlay");
  if (overlay) overlay.hidden = true;
  const returnTo = _modalReturnFocus;
  _modalReturnFocus = null;
  const cb = _modalConfirm;
  _modalConfirm = null;
  // Restore focus to the control that opened the modal, if it is still in the
  // DOM (re-renders between open and close can remove it).
  if (returnTo && typeof returnTo.focus === "function" && document.contains(returnTo)) {
    returnTo.focus();
  }
  if (cb) cb(result);
}

let _confirmBound = false;
function bindConfirmModalOnce() {
  if (_confirmBound) return;
  const overlay = $("#confirmOverlay");
  const ok = $("#confirmOk");
  const cancel = $("#confirmCancel");
  if (!overlay || !ok || !cancel) return;
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeConfirmModal(false);
  });
  ok.addEventListener("click", () => closeConfirmModal(true));
  cancel.addEventListener("click", () => closeConfirmModal(false));
  document.addEventListener("keydown", (e) => {
    if (overlay.hidden) return;
    if (e.key === "Escape") closeConfirmModal(false);
    // No global Enter shortcut: Enter (keydown) and Space (keyup) both
    // activate whichever <button> has focus natively, so the focused control
    // decides the outcome. A document-level "Enter = confirm" override would
    // fire before the focused button's activation and turn Enter on the
    // focused Cancel button into the destructive confirm — Space and Enter
    // would then disagree. Escape stays global because it has no activation
    // target to defer to.
    // Trap Tab within the modal so keyboard users cannot reach the page behind
    // it while aria-modal="true" claims the rest is inert.
    if (e.key === "Tab") {
      const modal = overlay.querySelector(".confirm-modal") || overlay;
      const focusables = Array.from(modal.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")).filter((el) => !el.disabled);
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey) {
        if (active === first || !modal.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else if (active === last || !modal.contains(active)) {
        e.preventDefault();
        first.focus();
      }
    }
  });
  _confirmBound = true;
}

// ---- Tag-edit popover -------------------------------------------------------
// Anchored to a clicked user tag. Two actions: rename (add new + remove old
// is one round-trip; the server collapses both into one update) and remove.
// Click anywhere outside the popover closes it.

const _popState = { link: null, tag: null, sourcePill: null, field: "" };
let _popBound = false;

function closeTagPopover() {
  const pop = $("#tagPopover");
  if (!pop) return;
  const pill = _popState.sourcePill;
  // Return focus to the source pill only when focus is currently inside the
  // popover (Escape / Save / Remove). A click on the page outside the popover
  // has already moved focus there, so we must not yank it back.
  const restoreFocus = pop.contains(document.activeElement);
  pop.hidden = true;
  _popState.link = null;
  _popState.tag = null;
  _popState.sourcePill = null;
  _popState.field = "";
  if (restoreFocus && pill && document.contains(pill)) pill.focus();
}

// Popover has two modes — see the index.html markup:
//   * User tag (no field): the rename row shows a free-text input.
//   * Heuristic fixed dimension (field = category/actor/direction/region):
//     the dimension row shows a <select> of valid values for that field.
function openTagPopover(link, tag, field, pillEl) {
  const pop = $("#tagPopover");
  const nameEl = $("#tagPopName");
  const input = $("#tagPopRenameInput");
  const renameRow = $("#tagPopRenameRow");
  const dimRow = $("#tagPopDimensionRow");
  const dimSelect = $("#tagPopDimensionSelect");
  const renameBtn = $("#tagPopRename");
  const removeBtn = $("#tagPopRemove");
  if (!pop || !nameEl || !input || !renameRow || !dimRow || !dimSelect || !renameBtn || !removeBtn) return;
  _popState.link = link;
  _popState.tag = tag;
  _popState.field = field || "";
  _popState.sourcePill = pillEl;
  nameEl.textContent = tag;

  if (_popState.field) {
    // Dimension mode: hide rename row, populate the select.
    renameRow.hidden = true;
    dimRow.hidden = false;
    const allowed = FIELD_VALUES[_popState.field] || [];
    dimSelect.innerHTML = allowed.map((v) =>
      `<option value="${escapeHtml(v)}"${v === tag ? " selected" : ""}>${escapeHtml(v)}</option>`
    ).join("");
    // Allow "Clear" (set dimension to null). Only meaningful when there's
    // currently a value to clear — otherwise the row is redundant.
    if (tag) {
      const clearOpt = document.createElement("option");
      clearOpt.value = "";
      clearOpt.textContent = "(clear)";
      dimSelect.appendChild(clearOpt);
    }
  } else {
    // User-tag mode: hide dimension row, prep the rename input.
    renameRow.hidden = false;
    dimRow.hidden = true;
    input.value = tag;
  }
  refreshPopoverSaveEnabled();
  pop.hidden = false;
  // Position below the clicked pill, with the arrow centered on it.
  positionTagPopover(pillEl, pop);
  const focusEl = _popState.field ? dimSelect : input;
  setTimeout(() => focusEl.focus(), 0);
}

function refreshPopoverSaveEnabled() {
  const renameBtn = $("#tagPopRename");
  if (!renameBtn) return;
  if (_popState.field) {
    const select = $("#tagPopDimensionSelect");
    const next = select ? select.value : "";
    renameBtn.disabled = !(next !== _popState.tag);
  } else {
    const input = $("#tagPopRenameInput");
    const next = (input && input.value || "").trim().toLowerCase();
    renameBtn.disabled = !(next && next !== _popState.tag);
  }
}

function positionTagPopover(pillEl, pop) {
  // Use getBoundingClientRect on the pill, then translate into the popover's
  // positioned ancestor. The popover lives at <body> root, so viewport
  // coordinates equal page coordinates and we can write directly to .style.
  const r = pillEl.getBoundingClientRect();
  const popWidth = pop.offsetWidth || 260;
  // Default: center the popover horizontally on the pill; clamp to the viewport.
  let left = r.left + r.width / 2 - popWidth / 2 + window.scrollX;
  const margin = 8;
  left = Math.max(margin, Math.min(left, window.scrollX + window.innerWidth - popWidth - margin));
  const top = r.bottom + window.scrollY + 8; // 8px gap below the pill
  pop.style.left = `${left}px`;
  pop.style.top = `${top}px`;
  // Arrow centered on the pill within the popover box.
  const arrowX = r.left + r.width / 2 - left;
  pop.style.setProperty("--arrow-x", `${Math.max(14, Math.min(arrowX, popWidth - 14))}px`);
}

function bindTagPopoverOnce() {
  if (_popBound) return;
  const pop = $("#tagPopover");
  const input = $("#tagPopRenameInput");
  const dimSelect = $("#tagPopDimensionSelect");
  const renameBtn = $("#tagPopRename");
  const removeBtn = $("#tagPopRemove");
  if (!pop || !input || !dimSelect || !renameBtn || !removeBtn) return;
  // Disable the rename button until the visible input/select actually
  // differs from the original tag. Pressing Enter in the input submits.
  input.addEventListener("input", refreshPopoverSaveEnabled);
  dimSelect.addEventListener("change", refreshPopoverSaveEnabled);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (!renameBtn.disabled) renameBtn.click();
    }
    if (e.key === "Escape") {
      e.preventDefault();
      closeTagPopover();
    }
  });
  renameBtn.addEventListener("click", async () => {
    const link = _popState.link;
    const tag = _popState.tag;
    const field = _popState.field;
    closeTagPopover();
    try {
      if (field) {
        const next = $("#tagPopDimensionSelect").value;  // "" means clear
        if (next === tag) return;
        await applyDimensionUpdate(link, field, next || null);
      } else {
        const next = (input.value || "").trim().toLowerCase();
        if (!next || next === tag) return;
        await applyTagUpdate(link, [next], [tag]);
      }
    } catch (err) {
      showEventError(_popState.sourcePill, `${field ? "Override" : "Rename"} failed (${err.message})`);
    }
  });
  removeBtn.addEventListener("click", async () => {
    const link = _popState.link;
    const tag = _popState.tag;
    const field = _popState.field;
    closeTagPopover();
    try {
      if (field) {
        // Clear the dimension (set to null) instead of removing the
        // dimension concept entirely. The pill just disappears from the row.
        await applyDimensionUpdate(link, field, null);
      } else {
        await applyTagUpdate(link, [], [tag]);
      }
    } catch (err) {
      showEventError(_popState.sourcePill, `Remove failed (${err.message})`);
    }
  });
  // Close on outside click / Escape. Bound on document so any click on
  // empty area (or another pill, or scroll) dismisses the popover.
  document.addEventListener("click", (e) => {
    if (pop.hidden) return;
    if (e.target === pop || pop.contains(e.target)) return;
    // Ignore the click that just opened this popover (the source pill) and
    // any re-clicks of the same pill: otherwise the document bubble closes
    // the popover synchronously with openTagPopover() and it never appears.
    if (_popState.sourcePill && _popState.sourcePill.contains(e.target)) return;
    closeTagPopover();
  });
  document.addEventListener("keydown", (e) => {
    if (pop.hidden) return;
    if (e.key === "Escape") closeTagPopover();
  });
  window.addEventListener("scroll", () => {
    if (!pop.hidden && _popState.sourcePill) positionTagPopover(_popState.sourcePill, pop);
  }, true);
  window.addEventListener("resize", () => {
    if (!pop.hidden && _popState.sourcePill) positionTagPopover(_popState.sourcePill, pop);
  });
  _popBound = true;
}

// Binds the timeline's static controls. Called once from main.js at boot.
export function initEvents() {
  initGrouping();
  loadNewsFilters();
  bindConfirmModalOnce();
  bindTagPopoverOnce();

  // Week/Month segmented toggle. Each mode has its own persisted selection
  // so switching modes doesn't clobber the other mode's choice.
  document.querySelectorAll(".tl-mode-btn").forEach((btn) => {
    // Reflect the persisted mode into aria-pressed on boot.
    btn.setAttribute("aria-pressed", String(btn.dataset.mode === groupingMode));
    btn.addEventListener("click", () => {
      const next = btn.dataset.mode;
      if (!next || next === groupingMode) return;
      groupingMode = next;
      try { localStorage.setItem(GROUP_MODE_KEY, next); } catch (e) { /* ignore */ }
      // Restore the period selection saved under the new mode, if any.
      try {
        activePeriodKey = localStorage.getItem(next === "month" ? MONTH_KEY : WEEK_KEY);
      } catch (e) { activePeriodKey = null; }
      document.querySelectorAll(".tl-mode-btn").forEach((b) => {
        b.setAttribute("aria-pressed", String(b.dataset.mode === groupingMode));
      });
      const labelEl = $("#tlPeriodLabel");
      if (labelEl) labelEl.textContent = groupingMode === "month" ? "Timeline month" : "Timeline week";
      renderTagFilters();
      applyEventFilter();
    });
  });
  // Initialise the period-label text from the persisted mode so the toolbar
  // matches the active toggle on first paint.
  const labelEl0 = $("#tlPeriodLabel");
  if (labelEl0) labelEl0.textContent = groupingMode === "month" ? "Timeline month" : "Timeline week";

  $("#weekSelect").addEventListener("change", (e) => {
    activePeriodKey = e.target.value || null;
    saveSelectedPeriod(activePeriodKey);
    renderTagFilters();
    applyEventFilter();
  });

  // Seed-only toggle preserves the legacy Wikipedia view. It stacks on top of
  // every other filter and persists per-browser.
  const seedToggle = $("#tlSeedOnly");
  if (seedToggle) {
    seedToggle.checked = seedOnly;
    seedToggle.addEventListener("change", () => {
      seedOnly = seedToggle.checked;
      saveNewsFilters();
      applyEventFilter();
    });
  }

  $("#newsBody").addEventListener("click", async (e) => {
    const del = e.target.closest(".ev-del");
    const hide = e.target.closest(".ev-hide");
    const tagEdit = e.target.closest('[data-act="tag-edit"]');
    const tagAddOpen = e.target.closest('[data-act="tag-add-open"]');
    const tagAddSubmit = e.target.closest('[data-act="tag-add-submit"]');
    const tagAddCancel = e.target.closest('[data-act="tag-add-cancel"]');

    if (del) {
      const link = del.dataset.link;
      const ev = eventsCache.find((x) => x.link === link);
      const titleShort = (ev && ev.title ? ev.title : "this event").slice(0, 80);
      const ok = await openConfirmModal({
        title: "Delete event from timeline?",
        body: `"${titleShort}" will be removed permanently from your local news.json. The next RSS refresh will not re-add it (it's already deduped by link). If it's tagged "ai", the AI capex-cycle gauge will lose this signal. To undo, re-run: python run.py --backfill.`,
        confirmLabel: "Delete",
        cancelLabel: "Keep",
      });
      if (!ok) return;
      try {
        renderNews(await deleteEvent(link));
      } catch (err) {
        showEventError(del, `Remove failed (${err.message})`);
      }
    } else if (hide) {
      const src = hide.dataset.src;
      const ok = await openConfirmModal({
        title: `Hide source "${src}"?`,
        body: `All current events from this source will be removed and the source will be added to your local suppress list. The next refresh will skip it.`,
        confirmLabel: "Hide source",
        cancelLabel: "Keep",
      });
      if (!ok) return;
      try {
        renderNews(await suppressSource(src));
      } catch (err) {
        showEventError(hide, `Hide failed (${err.message})`);
      }
    } else if (tagEdit) {
      // Click on a user-added tag pill: open the rename/remove popover
      // anchored to the pill. Fixed dimensions and the auto "ai" tag never
      // carry this data-act, so they fall through to the next branch.
      e.preventDefault();
      openTagPopover(tagEdit.dataset.link, tagEdit.dataset.tag, tagEdit.dataset.field || "", tagEdit);
    } else if (tagAddOpen) {
      // "+ tag" button: reveal the inline input next to it. The form is
      // hidden by default in HTML so this is the only way it appears.
      e.preventDefault();
      const wrap = tagAddOpen.closest(".pill-add");
      if (!wrap) return;
      const form = wrap.querySelector(".tag-add-form");
      const btn = wrap.querySelector(".tag-add-btn");
      if (form) form.hidden = false;
      if (btn) btn.hidden = true;
      const input = wrap.querySelector(".tag-add-input");
      if (input) {
        input.value = "";
        setTimeout(() => input.focus(), 0);
      }
    } else if (tagAddSubmit) {
      e.preventDefault();
      const link = tagAddSubmit.dataset.link;
      const wrap = tagAddSubmit.closest(".pill-add");
      const input = wrap ? wrap.querySelector(".tag-add-input") : null;
      const newTag = (input && input.value || "").trim();
      if (!newTag) return;
      try {
        await applyTagUpdate(link, [newTag], []);
      } catch (err) {
        if (wrap) {
          showEventError(wrap, `Add tag failed (${err.message})`);
        }
      }
    } else if (tagAddCancel) {
      e.preventDefault();
      const wrap = tagAddCancel.closest(".pill-add");
      if (!wrap) return;
      const form = wrap.querySelector(".tag-add-form");
      const btn = wrap.querySelector(".tag-add-btn");
      if (form) form.hidden = true;
      if (btn) btn.hidden = false;
    }
  });

  // Submit-on-Enter inside the inline tag-add input.
  $("#newsBody").addEventListener("keydown", (e) => {
    const target = e.target;
    if (target instanceof HTMLInputElement) {
      if (target.classList.contains("tag-add-input") && e.key === "Enter") {
        e.preventDefault();
        const wrap = target.closest(".pill-add");
        const submit = wrap ? wrap.querySelector('[data-act="tag-add-submit"]') : null;
        if (submit) submit.click();
      }
      return;
    }
    // Keyboard activation for the tag-edit pills (role="button"). A <span>
    // never synthesises a click on Enter/Space, so forwarding to .click()
    // runs the click-delegation branch exactly once — no double-fire.
    if (e.key === "Enter" || e.key === " ") {
      const pill = target.closest && target.closest('[data-act="tag-edit"]');
      if (!pill) return;
      e.preventDefault();
      pill.click();
    }
  });
}
