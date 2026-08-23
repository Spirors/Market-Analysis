// Market events timeline: week grouping/selection, tag filter chips,
// event rendering, and the delete / hide-source mutations.

import { $, escapeHtml, safeUrl } from "./format.js";
import { deleteEvent, suppressSource } from "./api.js";

let eventsCache = [];
let activeTags = new Set();
const WEEK_KEY = "tlSelectedWeek";
let activeWeekKey = null;

function initWeekSelection() {
  try { activeWeekKey = localStorage.getItem(WEEK_KEY); } catch (e) { activeWeekKey = null; }
}

function saveSelectedWeek(key) {
  try { localStorage.setItem(WEEK_KEY, key); } catch (e) { /* ignore */ }
}

const TAG_ORDER = ["macro", "micro", "government", "company", "bullish", "bearish", "neutral", "us", "japan", "china", "middle-east", "europe", "korea", "russia-ukraine", "global"];

function tagClass(t) {
  if (t === "macro" || t === "micro") return t;
  if (t === "government") return "gov";
  if (t === "company") return "co";
  if (t === "bullish") return "bull";
  if (t === "bearish") return "bear";
  if (t === "neutral") return "neutral";
  return "region";
}

function weekStart(s) {
  const d = new Date(s);
  if (isNaN(d)) return null;
  const day = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - day);
  d.setHours(0, 0, 0, 0);
  return d;
}

function fmtWeek(d) {
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function fmtWeekRange(ws) {
  const end = new Date(ws);
  end.setDate(end.getDate() + 6);
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
  // Counts reflect the selected week — that's the scope the chips filter.
  const group = buildWeekGroups(eventsCache).find((g) => g.key === activeWeekKey);
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

const UNDATED_KEY = "—";

function buildWeekGroups(items) {
  const groups = [];
  items.forEach((n) => {
    const ws = weekStart(n.published);
    const key = ws ? ws.toISOString().slice(0, 10) : UNDATED_KEY;
    const label = ws ? "Week of " + fmtWeekRange(ws) : "Undated";
    let g = groups.find((x) => x.key === key);
    if (!g) { g = { key, label, items: [] }; groups.push(g); }
    g.items.push(n);
  });
  // Newest first within each week.
  groups.forEach((g) => g.items.sort((a, b) => ((a.published || "") < (b.published || "") ? 1 : -1)));
  // Newest weeks first; undated always last.
  groups.sort((a, b) => {
    if (a.key === UNDATED_KEY) return 1;
    if (b.key === UNDATED_KEY) return -1;
    return a.key < b.key ? 1 : -1;
  });
  return groups;
}

function renderWeekSelector(groups) {
  const sel = $("#weekSelect");
  const badge = $("#weekBadge");
  if (!sel) return;
  if (!groups.length) {
    activeWeekKey = null;
    sel.innerHTML = `<option value="">No weeks</option>`;
    if (badge) { badge.hidden = true; badge.textContent = ""; }
    return;
  }
  // Keep a still-valid selection; otherwise fall back to the newest week
  // that actually contains events.
  if (!activeWeekKey || !groups.some((g) => g.key === activeWeekKey)) {
    activeWeekKey = groups[0].key;
    saveSelectedWeek(activeWeekKey);
  }
  sel.innerHTML = groups.map((g) =>
    `<option value="${escapeHtml(g.key)}"${g.key === activeWeekKey ? " selected" : ""}>${escapeHtml(g.label)} · ${g.items.length} event${g.items.length === 1 ? "" : "s"}</option>`
  ).join("");
  // Glanceable count for the selected week, next to the dropdown.
  const current = groups.find((g) => g.key === activeWeekKey);
  if (badge && current) {
    badge.textContent = `${current.items.length} event${current.items.length === 1 ? "" : "s"}`;
    badge.hidden = false;
  }
}

function applyEventFilter() {
  const el = $("#newsBody");
  const groups = buildWeekGroups(eventsCache);
  renderWeekSelector(groups);

  // Only the selected week renders; tag chips filter within it.
  const group = groups.find((g) => g.key === activeWeekKey) || null;
  let items = group ? group.items : [];
  if (activeTags.size) items = items.filter((e) => (e.tags || []).some((t) => activeTags.has(t)));
  if (!items.length) { el.innerHTML = "<p>No events match the selected filters.</p>"; return; }

  el.innerHTML = `<div class="timeline">` +
    `<div class="subhead accent">${escapeHtml(group.label)}</div>` +
    items.map(renderEventItem).join("") +
    `</div>`;
}

function renderEventItem(n) {
  const pills = (n.tags || []).map((t) => `<span class="pill ${tagClass(t)}">${escapeHtml(t)}</span>`).join(" ");
  // Impact tiers: Critical = loud (red edge + glow + BREAKING badge);
  // High = quiet amber accent. Everything else stays plain so ordinary rows
  // never read like an error state.
  const isCritical = n.impact === "Critical";
  const isHigh = n.impact === "High";
  const impactCls = isCritical ? " tl-critical" : isHigh ? " tl-high" : "";
  const breaking = isCritical ? `<span class="breaking-badge">Breaking</span>` : "";
  const impactPill = isHigh ? `<span class="pill high">High</span> ` : "";
  const date = (n.published || "").slice(0, 10);
  const dateShown = n.date_label ? `${escapeHtml(n.date_label)} · ${date}` : (date || "—");
  // Only http(s) links become anchors (scheme allowlist); seed:// entries and
  // anything with an unexpected scheme render as plain text, never an <a>.
  const linkHref = safeUrl(n.link);
  const titleEl = linkHref
    ? `<a href="${escapeHtml(linkHref)}" target="_blank" rel="noopener">${escapeHtml(n.title)}</a>`
    : `<span class="tl-plain">${escapeHtml(n.title)}</span>`;
  const summary = n.summary ? `<div class="tl-summary">${escapeHtml(n.summary)}</div>` : "";
  return `<div class="tl-item${impactCls}">
    <div class="tl-date">${dateShown}</div>
    <div class="tl-body">
      ${breaking}${titleEl}
      <div class="tl-tags">${impactPill}${pills}</div>
      <div class="meta">${escapeHtml(n.source)}
        <button class="mini-del ev-del" data-link="${escapeHtml(n.link)}" title="Remove this event from the timeline">✕ Remove</button>
        <button class="mini-del ev-hide" data-src="${escapeHtml(n.source)}" title="Hide all events from this source">hide source</button>
      </div>
      ${summary}
    </div>
  </div>`;
}

// Binds the timeline's static controls. Called once from main.js at boot.
export function initEvents() {
  initWeekSelection();

  $("#weekSelect").addEventListener("change", (e) => {
    activeWeekKey = e.target.value || null;
    saveSelectedWeek(activeWeekKey);
    renderTagFilters();
    applyEventFilter();
  });

  $("#newsBody").addEventListener("click", async (e) => {
    const del = e.target.closest(".ev-del");
    const hide = e.target.closest(".ev-hide");

    // Brief inline failure notice next to the clicked control. Reuses the
    // earnings status styling (the only existing inline status classes).
    const showEventError = (btn, msg) => {
      const meta = btn.closest(".meta");
      if (!meta) return;
      let st = meta.querySelector(".earn-status");
      if (!st) {
        st = document.createElement("span");
        meta.appendChild(st);
      }
      st.textContent = msg;
      st.className = "earn-status bad";
    };

    if (del) {
      if (!confirm("Remove this event from the timeline?")) return;
      try {
        renderNews(await deleteEvent(del.dataset.link));
      } catch (err) {
        showEventError(del, `Remove failed (${err.message})`);
      }
    } else if (hide) {
      const src = hide.dataset.src;
      if (confirm(`Hide all events from "${src}" and stop fetching it?`)) {
        try {
          renderNews(await suppressSource(src));
        } catch (err) {
          showEventError(hide, `Hide failed (${err.message})`);
        }
      }
    }
  });
}
