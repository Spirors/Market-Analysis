// Market events timeline: week grouping/selection, tag filter chips,
// event rendering, and the manual review mutations (tag add/remove,
// delete, hide source).

import { $, escapeHtml, safeUrl } from "./format.js";
import { deleteEvent, suppressSource, updateEventTags } from "./api.js";

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

// Fixed tag dimensions (set by the ingest heuristics) plus the auto-AI tag.
// These never get a "× remove" button in the UI; only user-added tags do.
const FIXED_DIMENSIONS = ["macro", "micro", "government", "company", "bullish", "bearish", "neutral", "us", "japan", "china", "middle-east", "europe", "korea", "russia-ukraine", "global"];
const AUTO_TAG = "ai";

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
  // Fixed dimensions + user tags + auto "ai", all shown as pills. Anything
  // outside the FIXED_DIMENSIONS list (so both "ai" and user-added tags)
  // opens the rename/remove popover on click. The fixed dimensions stay
  // inert because they're set by the ingest heuristics, not by the user.
  const pills = (n.tags || []).map((t) => {
    const clickable = !FIXED_DIMENSIONS.includes(t);
    const cls = `pill ${tagClass(t)}${t === AUTO_TAG ? " pill-ai" : ""}${clickable ? " pill-clickable" : ""}`;
    const dataAttrs = clickable
      ? ` data-act="tag-edit" data-link="${escapeHtml(n.link)}" data-tag="${escapeHtml(t)}"`
      : "";
    return `<span class="${cls}"${dataAttrs}>${escapeHtml(t)}</span>`;
  }).join(" ");
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
  // Inline tag-add form: a tiny "+ tag" button that reveals a text input.
  // Submitting it (Enter or button click) POSTs to /api/events/tags with
  // the new label and the event's link.
  const tagAdd = `<span class="pill-add" data-link="${escapeHtml(n.link)}">
      <button type="button" class="tag-add-btn" data-act="tag-add-open" title="Add a custom tag">+ tag</button>
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
      <div class="tl-tags">${impactPill}${pills}${tagAdd}</div>
      <div class="meta">${escapeHtml(n.source)}
        <button class="mini-del ev-del" data-link="${escapeHtml(n.link)}" title="Remove this event from the timeline">✕ Remove</button>
        <button class="mini-del ev-hide" data-src="${escapeHtml(n.source)}" title="Hide all events from this source">hide source</button>
      </div>
      ${summary}
    </div>
  </div>`;
}

// ---- Confirm modal -----------------------------------------------------------
// The native confirm() dialog is too narrow for a deletion warning that names
// the event title and spells out the side effect on the AI gauge. This small
// modal reuses the existing card chrome (same border / radius / shadow) so
// the warning sits in a familiar shape and doesn't read as a separate UI.

let _modalConfirm = null;

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
  overlay.hidden = false;
  // Focus the cancel button by default — destructive actions must require a
  // deliberate click on the dangerous option.
  setTimeout(() => cancel.focus(), 0);
  return new Promise((resolve) => { _modalConfirm = resolve; });
}

function closeConfirmModal(result) {
  const overlay = $("#confirmOverlay");
  if (overlay) overlay.hidden = true;
  const cb = _modalConfirm;
  _modalConfirm = null;
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
    if (e.key === "Enter") closeConfirmModal(true);
  });
  _confirmBound = true;
}

// ---- Tag-edit popover -------------------------------------------------------
// Anchored to a clicked user tag. Two actions: rename (add new + remove old
// is one round-trip; the server collapses both into one update) and remove.
// Click anywhere outside the popover closes it.

const _popState = { link: null, tag: null, sourcePill: null };
let _popBound = false;

function closeTagPopover() {
  const pop = $("#tagPopover");
  if (!pop) return;
  pop.hidden = true;
  _popState.link = null;
  _popState.tag = null;
  _popState.sourcePill = null;
}

function openTagPopover(link, tag, pillEl) {
  const pop = $("#tagPopover");
  const nameEl = $("#tagPopName");
  const input = $("#tagPopRenameInput");
  const renameBtn = $("#tagPopRename");
  const removeBtn = $("#tagPopRemove");
  if (!pop || !nameEl || !input || !renameBtn || !removeBtn) return;
  _popState.link = link;
  _popState.tag = tag;
  _popState.sourcePill = pillEl;
  nameEl.textContent = tag;
  input.value = tag;
  renameBtn.disabled = true;
  pop.hidden = false;
  // Position below the clicked pill, with the arrow centered on it.
  positionTagPopover(pillEl, pop);
  setTimeout(() => input.focus(), 0);
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
  const renameBtn = $("#tagPopRename");
  const removeBtn = $("#tagPopRemove");
  if (!pop || !input || !renameBtn || !removeBtn) return;
  // Disable the rename button until the text actually differs from the
  // original tag. Pressing Enter in the input submits the rename.
  const refreshDisabled = () => {
    const next = (input.value || "").trim().toLowerCase();
    renameBtn.disabled = !(next && next !== _popState.tag);
  };
  input.addEventListener("input", refreshDisabled);
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
    const next = (input.value || "").trim().toLowerCase();
    if (!next || next === _popState.tag) return;
    const link = _popState.link;
    const oldTag = _popState.tag;
    closeTagPopover();
    try {
      renderNews((await updateEventTags(link, [next], [oldTag])).events);
    } catch (err) {
      showEventError(_popState.sourcePill, `Rename failed (${err.message})`);
    }
  });
  removeBtn.addEventListener("click", async () => {
    const link = _popState.link;
    const tag = _popState.tag;
    closeTagPopover();
    try {
      renderNews((await updateEventTags(link, [], [tag])).events);
    } catch (err) {
      showEventError(_popState.sourcePill, `Remove failed (${err.message})`);
    }
  });
  // Close on outside click / Escape. Bound on document so any click on
  // empty area (or another pill, or scroll) dismisses the popover.
  document.addEventListener("click", (e) => {
    if (pop.hidden) return;
    if (e.target === pop || pop.contains(e.target)) return;
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
  initWeekSelection();
  bindConfirmModalOnce();
  bindTagPopoverOnce();

  $("#weekSelect").addEventListener("change", (e) => {
    activeWeekKey = e.target.value || null;
    saveSelectedWeek(activeWeekKey);
    renderTagFilters();
    applyEventFilter();
  });

  $("#newsBody").addEventListener("click", async (e) => {
    const del = e.target.closest(".ev-del");
    const hide = e.target.closest(".ev-hide");
    const tagEdit = e.target.closest('[data-act="tag-edit"]');
    const tagAddOpen = e.target.closest('[data-act="tag-add-open"]');
    const tagAddSubmit = e.target.closest('[data-act="tag-add-submit"]');
    const tagAddCancel = e.target.closest('[data-act="tag-add-cancel"]');

    // Brief inline failure notice next to the clicked control. Reuses the
    // earnings status styling (the only existing inline status classes).
    const showEventError = (btn, msg) => {
      const meta = btn.closest(".meta") || btn.closest(".tl-tags") || btn.closest(".tl-body");
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
      openTagPopover(tagEdit.dataset.link, tagEdit.dataset.tag, tagEdit);
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
        renderNews((await updateEventTags(link, [newTag], [])).events);
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
    if (!(target instanceof HTMLInputElement)) return;
    if (target.classList.contains("tag-add-input") && e.key === "Enter") {
      e.preventDefault();
      const wrap = target.closest(".pill-add");
      const submit = wrap ? wrap.querySelector('[data-act="tag-add-submit"]') : null;
      if (submit) submit.click();
    }
  });
}
