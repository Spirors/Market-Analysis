// tickerTable.js — shared column-controls + table renderer for the
// Earnings watchlist and the Portfolio section. Owned by this module:
// columns dropdown (checkbox + ↑/↓ reorder, debounced PUT), header
// rendering, row rendering, sort, add input + validation, per-row delete,
// watch stars (optional), edit-cell autosave (optional), empty state.
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
    if (Array.isArray(v) && v.length) return v;
  } catch (e) { /* ignore */ }
  return columns.map((c) => c.key);
}

function saveOrder(section, order) {
  try { localStorage.setItem(`${STORAGE_PREFIX}Order.${section}`, JSON.stringify(order)); } catch (e) { /* ignore */ }
}

export function createTickerTable(opts) {
  const { section, containerSel, controlsSel, columns, fetchData, addRow, removeRow, editCell, columnPrefsUrl, watchStars } = opts;

  let data = { rows: [] };
  let sort = loadSort(section);
  let visibleCols = loadVisibility(section, columns);
  let order = loadOrder(section, columns);
  let editDebounceTimers = new Map();
  let lastPrefPutAt = 0;
  let prefDebounceTimer = null;
  let expandedSet = new Set();

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
    return [...data.rows].sort((a, b) => {
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
  }

  function visibleColumnsOrdered() {
    return order
      .map((k) => columns.find((c) => c.key === k))
      .filter((c) => c && visibleCols.has(c.key));
  }

  function drawControls() {
    const el = $(controlsSel);
    if (!el) return;
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
    document.addEventListener("click", closeMenuOnOutside);
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
      const cls = `sortable${c.num ? " num" : ""}${sort.key === c.key ? (sort.dir > 0 ? " asc" : " desc") : ""}`;
      return `<th class="${cls}" data-key="${c.key}">${escapeHtml(c.label)}</th>`;
    }).join("");
    let html = `<table><thead><tr>${ths}<th></th></tr></thead><tbody>`;
    if (!rows.length) {
      html += `<tr><td colspan="${cols.length + 1}">No tickers yet. Add one above.</td></tr>`;
    } else {
      for (const r of rows) {
        const rowId = r.symbol || r.kind || "";
        html += `<tr data-symbol="${escapeHtml(rowId)}">` + cols.map((c) => {
          let content;
          if (c.editable && editCell) {
            const raw = r[c.key];
            const display = raw == null ? "" : String(raw);
            content = `<input class="tt-edit" data-symbol="${escapeHtml(rowId)}" data-key="${c.key}" value="${escapeHtml(display)}" />`;
          } else {
            content = c.fmt ? c.fmt(r) : (r[c.key] == null ? "—" : escapeHtml(String(r[c.key])));
          }
          return `<td${c.num ? ' class="num"' : ""}>${content}</td>`;
        }).join("") + `<td><button class="tt-del mini" data-symbol="${escapeHtml(rowId)}" title="Remove">✕</button></td></tr>`;
      }
    }
    html += `</tbody></table>`;
    el.innerHTML = html;

    el.querySelectorAll("th.sortable").forEach((h) => h.addEventListener("click", () => {
      const k = h.dataset.key;
      if (sort.key === k) sort.dir *= -1; else { sort.key = k; sort.dir = 1; }
      saveSort(section, sort);
      drawBody();
    }));
    el.querySelectorAll(".tt-del").forEach((b) => b.addEventListener("click", async () => {
      try { await removeRow(b.dataset.symbol); } catch (e) { setStatus(e.message, "bad"); }
    }));
    el.querySelectorAll(".tt-edit").forEach((inp) => {
      inp.addEventListener("input", () => {
        const k = `${inp.dataset.symbol}::${inp.dataset.key}`;
        clearTimeout(editDebounceTimers.get(k));
        const timer = setTimeout(async () => {
          try { await editCell(inp.dataset.symbol, inp.dataset.key, inp.value); } catch (e) { setStatus(e.message, "bad"); }
        }, 400);
        editDebounceTimers.set(k, timer);
      });
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); inp.blur(); }
      });
      inp.addEventListener("blur", async () => {
        const k = `${inp.dataset.symbol}::${inp.dataset.key}`;
        clearTimeout(editDebounceTimers.get(k));
        try { await editCell(inp.dataset.symbol, inp.dataset.key, inp.value); } catch (e) { setStatus(e.message, "bad"); }
      });
    });
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
  };
}
