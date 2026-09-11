// tickerTable.js — shared column-controls + table renderer for the
// Earnings watchlist and the Portfolio section. Owned by this module:
// columns dropdown (checkbox + ↑/↓ reorder, debounced PUT), header
// rendering, row rendering, sort, add input + validation, per-row delete,
// watch stars (optional), edit-cell autosave (optional), empty state.
//
// Manual row order: in addition to column-header sorts (which are
// temporary view states), each row has ▲/▼ buttons that move it in a
// session-only manual order. ▲/▼ and the "↺ Default order" reset button
// are gated to the "portfolio" section only — Earnings uses the same
// shared factory but does NOT expose manual reordering. Reordering is
// session-only (no localStorage), so refreshing the page returns rows to
// their data order. Clicking ▲/▼ in a column-sorted view also resets
// the sort to "default" so the user sees the row move immediately.
//
// Section-specific behavior (which symbols, which validators, which
// edit-cell URL) is passed in via the factory function.
//
// **Per-section persistence is mandatory.** All three localStorage channels
// (Sort / Visible / Order) are namespaced by `section`:
//
//   pfSort.{section}, pfVisible.{section}, pfOrder.{section}
//
// Hard-coding or defaulting the section to a shared key (e.g. just
// "pfOrder") would silently merge state across every caller — the same
// class of bug the AGENT-WORKFLOW-PROMPT.md §3b hypothesis warns about.
// `VALID_SECTIONS` below is the single source of truth; passing anything
// else throws immediately so a future extraction can't reintroduce the bug.
//
// **Per-portfolio persistence.** Portfolio columns are configured
// independently per portfolio (the user wanted "more customization"):
// each tickerTable instance for a portfolio is created with
// `section: "portfolio.<pid>"` and the localStorage keys become
// `pfSort.portfolio.<pid>` / `pfVisible.portfolio.<pid>` /
// `pfOrder.portfolio.<pid>`. VALID_SECTIONS still lists just "portfolio"
// as the canonical default; "portfolio.<anything>" is accepted via the
// `portfolio.*` prefix check in _assertValidSection.

import { $, escapeHtml, fmtPrice, fmtPctHtml, fmtFloat, fmtPct } from "./format.js";

const STORAGE_PREFIX = "pf";

// Single source of truth for the canonical `section` values. Per-portfolio
// instances pass "portfolio.<pid>" — see _assertValidSection for the prefix
// check that admits those. Adding a brand-new section (e.g. a watchlist
// panel) means extending this list AND updating any frontend tests that
// assert the section whitelist.
export const VALID_SECTIONS = ["portfolio"];

function _assertValidSection(section) {
  if (!section || typeof section !== "string") {
    throw new Error(
      `tickerTable.js: 'section' is required and must be a string ` +
      `(got ${JSON.stringify(section)}). Per-section persistence keys are ` +
      `mandatory — a shared default key would silently merge state across ` +
      `every caller (see AGENT-WORKFLOW-PROMPT.md §3b).`
    );
  }
  if (!VALID_SECTIONS.includes(section) && !section.startsWith("portfolio.")) {
    throw new Error(
      `tickerTable.js: 'section' must be one of ${JSON.stringify(VALID_SECTIONS)} ` +
      `or match the "portfolio.*" prefix for per-portfolio persistence ` +
      `(got ${JSON.stringify(section)}).`
    );
  }
}

function loadSort(section) {
  _assertValidSection(section);
  try {
    const v = JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}Sort.${section}`));
    if (v && typeof v.key === "string") return v;
  } catch (e) { /* ignore */ }
  return { key: "default", dir: 1 };
}

function saveSort(section, sort) {
  _assertValidSection(section);
  try { localStorage.setItem(`${STORAGE_PREFIX}Sort.${section}`, JSON.stringify(sort)); } catch (e) { /* ignore */ }
}

function loadVisibility(section, columns) {
  _assertValidSection(section);
  try {
    const v = JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}Visible.${section}`));
    if (Array.isArray(v) && v.length) return new Set(v);
  } catch (e) { /* ignore */ }
  return new Set(columns.filter((c) => c.default !== false).map((c) => c.key));
}

function saveVisibility(section, visibleSet) {
  _assertValidSection(section);
  try { localStorage.setItem(`${STORAGE_PREFIX}Visible.${section}`, JSON.stringify([...visibleSet])); } catch (e) { /* ignore */ }
}

function loadOrder(section, columns) {
  _assertValidSection(section);
  try {
    const v = JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}Order.${section}`));
    if (Array.isArray(v) && v.length) {
      const missing = columns.map((c) => c.key).filter((k) => !v.includes(k));
      return missing.length ? [...v, ...missing] : v;
    }
  } catch (e) { /* ignore */ }
  return columns.map((c) => c.key);
}

function saveOrder(section, order) {
  _assertValidSection(section);
  try { localStorage.setItem(`${STORAGE_PREFIX}Order.${section}`, JSON.stringify(order)); } catch (e) { /* ignore */ }
}

// Position the Columns dropdown via position: fixed so it never clips
// against the portfolio boundary / viewport edge. Picks whichever side
// of the trigger button has more room (drops down by default; flips
// up if the bottom of the menu would extend past the viewport). The
// per-portfolio Columns button sits at the bottom of each expanded
// portfolio body, so on short portfolios + long menus the down path
// clips against the viewport bottom - the JS flip avoids that.
//
// Called on every menu open. Re-runs on viewport resize would be
// nice-to-have but isn't wired; the menu is short-lived and the
// resize case is rare.
function positionColumnsMenu(controlsEl) {
  const btn = controlsEl.querySelector(".tt-cols-btn");
  const menu = controlsEl.querySelector(".tt-cols-menu");
  if (!btn || !menu) return;
  const btnBox = btn.getBoundingClientRect();
  const menuBox = menu.getBoundingClientRect();
  const margin = 4;
  const vh = window.innerHeight || document.documentElement.clientHeight;
  // Default: drop down below the button. Flip up if no room below.
  const spaceBelow = vh - btnBox.bottom;
  const dropDown = spaceBelow >= menuBox.height + margin || spaceBelow > vh / 2;
  const top = dropDown
    ? btnBox.bottom + margin
    : btnBox.top - menuBox.height - margin;
  // Left-align with the button; if the menu is wider than the button,
  // let it extend right. If it would overflow the viewport, shift left.
  const menuWidth = menuBox.width || 220;
  let left = btnBox.left;
  if (left + menuWidth > window.innerWidth - 4) {
    left = Math.max(4, window.innerWidth - menuWidth - 4);
  }
  menu.style.top = `${Math.max(4, top)}px`;
  menu.style.left = `${left}px`;
}

export function createTickerTable(opts) {
  const { section, containerSel, controlsSel, columns, fetchData, addRow, removeRow, editCell, columnPrefsUrl, watchStars, rowClass, afterRender, afterEdit, initialSort, onReorder } = opts;
  // controlsMode defaults to "full" (Columns dropdown + ↺ reset + Add
  // input). Portfolio callers pass "columnsOnly" so the per-portfolio
  // controls render only the Columns dropdown + ↺ reset (Add holding /
  // Add cash are bespoke buttons in the portfolio body, not a free-text
  // input). Anything else (e.g. "columnsOnly" with an addRow callback
  // configured) just silently skips the add input — addRow still works
  // through any other UI surface the caller wires up.
  const controlsMode = opts.controlsMode || "full";
  // Fail loud, not silent: an undefined / unknown section would otherwise
  // template the localStorage keys as 'pfSort.undefined' / 'pfVisible.null'
  // and silently drop every preference change (the AGENT-WORKFLOW-PROMPT.md
  // §3b regression scenario).
  _assertValidSection(section);
  // Manual row reorder (▲/▼ + ↺ reset) is a Portfolio-only feature.
  // Per-portfolio tickerTable instances are constructed with
  // `section: "portfolio.<pid>"` (see portfolio.js:559), so the strict
  // equality `section === "portfolio"` would silently disable the feature
  // for every portfolio. Mirror `_assertValidSection` and admit both the
  // canonical "portfolio" key and any "portfolio.*" per-portfolio key.
  // See DECISIONS.md "tickerTable.js section gating must mirror
  // _assertValidSection, not collapse to a single string".
  const reorderEnabled = section === "portfolio" || section.startsWith("portfolio.");

  let data = { rows: [] };
  let sort = initialSort || loadSort(section);
  let visibleCols = loadVisibility(section, columns);
  let order = loadOrder(section, columns);
  let editDebounceTimers = new Map();
  let lastPrefPutAt = 0;
  let prefDebounceTimer = null;
  let expandedSet = new Set();
  let outsideClickHandler = null;

  function persistPrefsSoon() {
    clearTimeout(prefDebounceTimer);
    prefDebounceTimer = setTimeout(async () => {
      try {
        await columnPrefsUrl({ order, visibility: Object.fromEntries([...visibleCols].map((k) => [k, true])), hidden: columns.map((c) => c.key).filter((k) => !visibleCols.has(k)) });
      } catch (e) { /* swallow — best effort */ }
    }, 300);
  }

  function keyFn(r) {
    if (sort.key === "default") return 0;
    if (sort.key === "symbol") return r.symbol || "";
    const v = r[sort.key];
    if (v == null) return -Infinity;
    if (typeof v === "string") return v;
    return Number(v);
  }

  function sortedRows() {
    const rows = [...data.rows];
    if (sort.key === "default") {
      // "default" mode = data insertion order. Manual reordering (▲/▼) is
      // session-only and never persisted to localStorage.
      return rows;
    }
    rows.sort((a, b) => {
      const ka = keyFn(a), kb = keyFn(b);
      if (typeof ka === "string" && typeof kb === "string") {
        if (ka < kb) return -1 * sort.dir;
        if (ka > kb) return 1 * sort.dir;
        return 0;
      }
      if (ka < kb) return -1 * sort.dir;
      if (ka > kb) return 1 * sort.dir;
      return 0;
    });
    return rows;
  }

  function visibleColumnsOrdered() {
    return order
      .map((k) => columns.find((c) => c.key === k))
      .filter((c) => c && visibleCols.has(c.key));
  }

function drawControls() {
    const el = $(controlsSel);
    if (!el) return;
    const showReset = reorderEnabled;
    // controlsMode === "columnsOnly" omits the add input + button — callers
    // own their own add flow (e.g. Portfolio uses bespoke +Add holding /
    // +Add cash buttons). The Columns dropdown + ↺ reset still render.
    const addBlock = controlsMode === "columnsOnly" ? "" : `
      <div class="tt-add">
        <input class="tt-input" placeholder="Add ticker (e.g. NVDA)" autocomplete="off">
        <button class="tt-add-btn mini" disabled>Add</button>
      </div>
    `;
    el.innerHTML = `
      <div class="tt-actions">
        <div class="tt-cols">
          <button class="tt-cols-btn mini">Columns</button>
          <div class="tt-cols-menu hidden">
            ${columns.map((c) => `
              <div class="tt-cols-row">
                <button class="tt-col-up mini" data-key="${c.key}" title="Move left">◀</button>
                <button class="tt-col-down mini" data-key="${c.key}" title="Move right">▶</button>
                <label><input type="checkbox" data-col="${c.key}" ${visibleCols.has(c.key) ? "checked" : ""}> ${escapeHtml(c.label)}</label>
              </div>
            `).join("")}
          </div>
        </div>
        ${showReset ? '<button class="tt-reset-order mini" title="Reset to insertion order (clears any column-header sorts and any session-only ▲/▼ moves)">↺ Default order</button>' : ""}
        <span class="tt-status"></span>
      </div>
      ${addBlock}
    `;

    el.querySelector(".tt-cols-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      const menu = el.querySelector(".tt-cols-menu");
      const willShow = menu.classList.contains("hidden");
      menu.classList.toggle("hidden");
      if (willShow) positionColumnsMenu(el);
    });
    el.querySelectorAll(".tt-cols-menu input").forEach((cb) => {
      cb.addEventListener("change", () => {
        if (cb.checked) visibleCols.add(cb.dataset.col); else visibleCols.delete(cb.dataset.col);
        saveVisibility(section, visibleCols);
        persistPrefsSoon();
        drawBody();
      });
    });
    el.querySelectorAll(".tt-col-up").forEach((b) => {
      b.addEventListener("click", (e) => { e.preventDefault(); moveCol(b.dataset.key, -1); });
    });
    el.querySelectorAll(".tt-col-down").forEach((b) => {
      b.addEventListener("click", (e) => { e.preventDefault(); moveCol(b.dataset.key, +1); });
    });
    const resetBtn = el.querySelector(".tt-reset-order");
    if (resetBtn) resetBtn.addEventListener("click", resetSort);
    // Re-wire the add input + button on every controls rebuild. drawControls()
    // runs on every column reorder / sort / reset (because innerHTML replaces
    // the whole controls subtree), so the freshly-created .tt-input /
    // .tt-add-btn would otherwise lose their listeners — that was the bug
    // behind "Add button broken after first column reorder" regression.
    // Listeners are attached to the new DOM nodes, so old ones are GC'd
    // along with the discarded elements (no listener leak).
    wireAddInput();
    // Remove previous listener to avoid leaking one per render call.
    if (outsideClickHandler) {
      document.removeEventListener("click", outsideClickHandler);
    }
    outsideClickHandler = (e) => closeMenuOnOutside(e);
    document.addEventListener("click", outsideClickHandler);
  }

  function closeMenuOnOutside(e) {
    const el = $(controlsSel);
    if (!el) return;
    const menu = el.querySelector(".tt-cols-menu");
    if (!menu || menu.classList.contains("hidden")) return;
    if (!el.contains(e.target)) menu.classList.add("hidden");
  }

  function moveCol(key, delta) {
    const idx = order.indexOf(key);
    if (idx < 0) return;
    const newIdx = idx + delta;
    if (newIdx < 0 || newIdx >= order.length) return;
    [order[idx], order[newIdx]] = [order[newIdx], order[idx]];
    saveOrder(section, order);
    persistPrefsSoon();
    drawControls();
    drawBody();
  }

  function resetSort() {
    sort = { key: "default", dir: 1 };
    saveSort(section, sort);
    drawControls();
    drawBody();
  }

  function moveRow(symbol, delta) {
    if (!reorderEnabled) return; // portfolio-only feature
    if (sort.key !== "default") return; // grey-out guard: must be in default order
    const idx = data.rows.findIndex((r) => (r.symbol || r.kind || "") === symbol);
    if (idx < 0) return;
    const newIdx = idx + delta;
    if (newIdx < 0 || newIdx >= data.rows.length) return;
    // Optimistic swap: move the row in data.rows and re-render immediately.
    const originalRows = [...data.rows];
    [data.rows[idx], data.rows[newIdx]] = [data.rows[newIdx], data.rows[idx]];
    // Always surface the move by returning the view to manual order.
    if (sort.key !== "default") {
      sort = { key: "default", dir: 1 };
      saveSort(section, sort);
      drawControls();
    }
    drawBody();
    // Persist the new order via callback (fire-and-forget with rollback).
    if (typeof onReorder === "function") {
      const newOrder = data.rows.map((r) => r.symbol).filter(Boolean);
      onReorder(newOrder).catch((e) => {
        // Rollback: restore original rows and re-render.
        data.rows = originalRows;
        drawBody();
        setStatus(e.message, "bad");
      });
    }
  }

  function setStatus(text, cls) {
    const st = $(controlsSel + " .tt-status");
    if (!st) return;
    st.textContent = text;
    st.className = "tt-status " + (cls || "");
  }

  function drawBody() {
    const el = $(containerSel);
    if (!el) return;
    const cols = visibleColumnsOrdered();
    const rows = sortedRows();
    const ths = cols.map((c) => {
      if (c.sortable === false) {
        return `<th class="non-sortable${c.num ? " num" : ""}" data-key="${c.key}">${escapeHtml(c.label)}</th>`;
      }
      const cls = `sortable${c.num ? " num" : ""}${sort.key === c.key ? (sort.dir > 0 ? " asc" : " desc") : ""}`;
      return `<th class="${cls}" data-key="${c.key}">${escapeHtml(c.label)}</th>`;
    }).join("");
    let html = `<table><thead><tr>${ths}<th></th></tr></thead><tbody>`;
    if (!rows.length) {
      html += `<tr><td colspan="${cols.length + 1}">No tickers yet. Add one above.</td></tr>`;
    } else {
      for (let rowIdx = 0; rowIdx < rows.length; rowIdx++) {
        const r = rows[rowIdx];
        const rowId = r.symbol || r.kind || "";
        // Optional per-row CSS class (e.g. earnings star tint). Pure addition —
        // callers that don't pass `rowClass` get no class attribute.
        const extra = typeof rowClass === "function" ? (rowClass(r) || "").trim() : "";
        const cls = extra ? ` class="${escapeHtml(extra)}"` : "";
        // Boundary-disable the up/down chevrons (matches the same UX pattern
        // the portfolio cards, bottleneck categories, and dashboard layout
        // cards use). Without this, clicking ▲ on the first row or ▼ on the
        // last row silently no-ops inside moveRow — the user gets no
        // feedback that the move isn't possible. Disabling the button makes
        // the constraint visible.
        const isFirstRow = rowIdx === 0;
        const isLastRow = rowIdx === rows.length - 1;
        const reorderBlocked = sort.key !== "default";
        const reorderBtns = reorderEnabled
          ? `<button class="tt-up mini" data-symbol="${escapeHtml(rowId)}" title="${reorderBlocked ? "Reset to default order (\u21ba) before reordering rows" : "Move up"}" aria-label="Move up"${isFirstRow || reorderBlocked ? " disabled" : ""}>▲</button><button class="tt-down mini" data-symbol="${escapeHtml(rowId)}" title="${reorderBlocked ? "Reset to default order (\u21ba) before reordering rows" : "Move down"}" aria-label="Move down"${isLastRow || reorderBlocked ? " disabled" : ""}>▼</button>`
          : "";
        html += `<tr data-symbol="${escapeHtml(rowId)}"${cls}>` + cols.map((c) => {
          let content;
          if (c.editable && editCell) {
            const raw = r[c.key];
            const display = raw == null ? "" : String(raw);
            content = `<input class="tt-edit" data-symbol="${escapeHtml(rowId)}" data-key="${c.key}" value="${escapeHtml(display)}" />`;
          } else {
            content = c.fmt ? c.fmt(r) : (r[c.key] == null ? "—" : escapeHtml(String(r[c.key])));
          }
          return `<td${c.num ? ' class="num"' : ""}>${content}</td>`;
        }).join("") + `<td class="tt-row-actions">${reorderBtns}<button class="tt-del mini" data-symbol="${escapeHtml(rowId)}" title="Remove">✕</button></td></tr>`;
      }
    }
    html += `</tbody></table>`;
    el.innerHTML = html;

    el.querySelectorAll("th.sortable").forEach((h) => h.addEventListener("click", () => {
      const k = h.dataset.key;
      if (sort.key === k) sort.dir *= -1; else { sort.key = k; sort.dir = 1; }
      saveSort(section, sort);
      drawControls();
      drawBody();
    }));
    el.querySelectorAll(".tt-up").forEach((b) => b.addEventListener("click", (e) => { e.preventDefault(); moveRow(b.dataset.symbol, -1); }));
    el.querySelectorAll(".tt-down").forEach((b) => b.addEventListener("click", (e) => { e.preventDefault(); moveRow(b.dataset.symbol, +1); }));
    el.querySelectorAll(".tt-del").forEach((b) => b.addEventListener("click", async () => {
      try {
        // removeRow returns fresh rows (or undefined); re-render so the
        // deleted row actually leaves the DOM instead of lingering until the
        // next unrelated drawBody().
        const result = await removeRow(b.dataset.symbol);
        if (result && result.rows) refresh(result);
      } catch (e) { setStatus(e.message, "bad"); }
    }));
    el.querySelectorAll(".tt-edit").forEach((inp) => {
      inp.addEventListener("input", () => {
        const k = `${inp.dataset.symbol}::${inp.dataset.key}`;
        clearTimeout(editDebounceTimers.get(k));
        const timer = setTimeout(() => saveEdit(inp), 400);
        editDebounceTimers.set(k, timer);
      });
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); inp.blur(); }
      });
      inp.addEventListener("blur", () => saveEdit(inp));
    });

    // Optional hook after every drawBody() — used by Portfolio to append the
    // cash + totals rows that sit below the ticker holdings. Receives the
    // visible column defs so appended rows can match the header cell count
    // when columns are hidden.
    const tbody = el.querySelector("tbody");
    if (tbody && typeof afterRender === "function") afterRender(tbody, visibleColumnsOrdered());
  }

  // Persist an editable-cell change without re-rendering the whole table.
  // Re-rendering here would destroy the input the user is typing into (the
  // "decimal input bugging out" regression). Instead we update the cached row
  // and patch only the row's computed display cells (gain/loss, total_value)
  // in place, so the input keeps focus while the derived numbers stay live.
  async function saveEdit(inp) {
    const k = `${inp.dataset.symbol}::${inp.dataset.key}`;
    clearTimeout(editDebounceTimers.get(k));
    try {
      await editCell(inp.dataset.symbol, inp.dataset.key, inp.value);
      const tr = inp.closest("tr");
      const row = data.rows.find((r) => (r.symbol || r.kind || "") === inp.dataset.symbol);
      if (row) {
        row[inp.dataset.key] = parseFloat(inp.value) || 0;
        patchRowCells(tr, row);
        if (typeof afterEdit === "function") afterEdit(row, tr ? tr.closest("tbody") : null, visibleColumnsOrdered());
      }
    } catch (e) { setStatus(e.message, "bad"); }
  }

  // Re-render only the non-editable display cells of one row. Editable inputs
  // are left untouched so focus survives the update.
  function patchRowCells(tr, row) {
    if (!tr) return;
    const cols = visibleColumnsOrdered();
    const tds = tr.querySelectorAll("td");
    let i = 0;
    for (const c of cols) {
      const td = tds[i];
      if (!td) break;
      if (!(c.editable && editCell)) {
        td.innerHTML = c.fmt ? c.fmt(row) : (row[c.key] == null ? "—" : escapeHtml(String(row[c.key])));
      }
      i++;
    }
  }

  async function tryAdd(input) {
    const sym = (input.value || "").trim().toUpperCase();
    if (!sym) return;
    const btn = $(controlsSel + " .tt-add-btn");
    const origText = btn ? btn.textContent : "Add";
    if (btn) { btn.disabled = true; btn.textContent = "Adding\u2026"; }
    try {
      const result = await addRow(sym);
      input.value = "";
      setStatus("", "");
      await refresh(result);
    } catch (e) { setStatus(e.message, "bad"); }
    finally { if (btn) { btn.disabled = false; btn.textContent = origText; } }
  }

  function wireAddInput() {
    const input = $(controlsSel + " .tt-input");
    const btn = $(controlsSel + " .tt-add-btn");
    if (!input || !btn) return;
    input.addEventListener("input", () => {
      setStatus("", "");
      btn.disabled = !input.value.trim();
    });
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") tryAdd(input); });
    btn.addEventListener("click", () => tryAdd(input));
  }

  async function refresh(newData) {
    if (newData) { data = newData; drawBody(); return; }
    data = await fetchData();
    drawBody();
  }

  return {
    // drawControls() now re-wires the add-input listeners internally, so
    // the public render() entry point just rebuilds the controls + body.
    render(d) { data = d; drawControls(); drawBody(); },
    refresh,
    resetSort,
  };
}