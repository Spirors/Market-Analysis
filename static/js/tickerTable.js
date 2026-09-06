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

import { $, escapeHtml, fmtPrice, fmtPctHtml, fmtFloat, fmtPct } from "./format.js";

const STORAGE_PREFIX = "pf";

function loadSort(section) {
  try {
    const v = JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}Sort.${section}`));
    if (v && typeof v.key === "string") return v;
  } catch (e) { /* ignore */ }
  return { key: "default", dir: 1 };
}

function saveSort(section, sort) {
  try { localStorage.setItem(`${STORAGE_PREFIX}Sort.${section}`, JSON.stringify(sort)); } catch (e) { /* ignore */ }
}

function loadVisibility(section, columns) {
  try {
    const v = JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}Visible.${section}`));
    if (Array.isArray(v) && v.length) return new Set(v);
  } catch (e) { /* ignore */ }
  return new Set(columns.filter((c) => c.default !== false).map((c) => c.key));
}

function saveVisibility(section, visibleSet) {
  try { localStorage.setItem(`${STORAGE_PREFIX}Visible.${section}`, JSON.stringify([...visibleSet])); } catch (e) { /* ignore */ }
}

function loadOrder(section, columns) {
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
  try { localStorage.setItem(`${STORAGE_PREFIX}Order.${section}`, JSON.stringify(order)); } catch (e) { /* ignore */ }
}

export function createTickerTable(opts) {
  const { section, containerSel, controlsSel, columns, fetchData, addRow, removeRow, editCell, columnPrefsUrl, watchStars, rowClass, afterRender, afterEdit, initialSort } = opts;
  // Manual row reorder (▲/▼ + ↺ reset) is a Portfolio-only feature.
  // Earnings uses this factory too but never exposes it.
  const reorderEnabled = section === "portfolio";

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
    // "Next earnings" / "Next earnings" column uses key "date" in both
    // Earnings and Portfolio column defs, but the actual data property is
    // next_earnings (with last_earnings as fallback). Map it explicitly so
    // sort-by-date works.
    if (sort.key === "date") return r.next_earnings || r.last_earnings || "";
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
        ${showReset ? '<button class="tt-reset-order mini" title="Reset to insertion order (clears any column-header sort and any session-only ▲/▼ moves)">↺ Default order</button>' : ""}
      </div>
      <div class="tt-add">
        <input class="tt-input" placeholder="Add ticker (e.g. NVDA)" autocomplete="off">
        <button class="tt-add-btn mini" disabled>Add</button>
        <span class="tt-status"></span>
      </div>
    `;

    el.querySelector(".tt-cols-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      el.querySelector(".tt-cols-menu").classList.toggle("hidden");
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
    const idx = data.rows.findIndex((r) => (r.symbol || r.kind || "") === symbol);
    if (idx < 0) return;
    const newIdx = idx + delta;
    if (newIdx < 0 || newIdx >= data.rows.length) return;
    [data.rows[idx], data.rows[newIdx]] = [data.rows[newIdx], data.rows[idx]];
    // Always surface the move by returning the view to manual order. If the
    // user was column-sorted, the underlying data changed but the visible
    // order didn't — resetting makes the move immediately visible.
    if (sort.key !== "default") {
      sort = { key: "default", dir: 1 };
      saveSort(section, sort);
      drawControls();
    }
    drawBody();
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
      for (const r of rows) {
        const rowId = r.symbol || r.kind || "";
        // Optional per-row CSS class (e.g. earnings star tint). Pure addition —
        // callers that don't pass `rowClass` get no class attribute.
        const extra = typeof rowClass === "function" ? (rowClass(r) || "").trim() : "";
        const cls = extra ? ` class="${escapeHtml(extra)}"` : "";
        const reorderBtns = reorderEnabled
          ? `<button class="tt-up mini" data-symbol="${escapeHtml(rowId)}" title="Move up" aria-label="Move up">▲</button><button class="tt-down mini" data-symbol="${escapeHtml(rowId)}" title="Move down" aria-label="Move down">▼</button>`
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
    try {
      const result = await addRow(sym);
      input.value = "";
      setStatus("", "");
      await refresh(result);
    } catch (e) { setStatus(e.message, "bad"); }
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
    render(d) { data = d; drawControls(); wireAddInput(); drawBody(); },
    refresh,
    resetSort,
  };
}