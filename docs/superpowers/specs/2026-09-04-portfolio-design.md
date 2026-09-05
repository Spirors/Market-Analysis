# Portfolio Section — Design Spec

**Date:** 2026-09-04
**Status:** Approved (brainstorming complete; awaiting writing-plans skill)
**Author:** Brainstorming session with the user

---

## 1. Overview

Add a new `Portfolio` section to the dashboard, placed immediately above the
existing `Earnings watchlist` section. The Portfolio section supports multiple
user-created portfolios (e.g., "Fidelity Cash", "Fidelity Roth IRA"), each with
its own holdings table, an editable cash row, per-portfolio totals, and a
grand-total aggregate in the card header.

While building the section, extract a medium-scope shared `tickerTable.js`
framework so the existing Earnings watchlist and the new Portfolio section
both render through it (no copy-pasted table code). The Earnings watchlist
also gains a long-requested feature: column reorder via ↑/↓ buttons in the
Columns dropdown.

All portfolio data is persisted under `data/portfolios.json`, which is
gitignored by the existing `data/*` rule (only `events.json` and `.gitkeep`
are tracked). No data leaves the local machine.

---

## 2. Architecture

### 2.1 Backend (new)

- **`app/portfolio.py`** — data model + persistence + business logic.
  Mirrors the shape of `app/earnings.py`: load/save JSON via
  `store.save_json`, atomic temp+os.replace writes, default fallback when
  file is missing. Single source of truth for portfolio CRUD; live price
  enrichment happens at serve time via the existing
  `market._quote_snapshot([unique_symbols])` path.

- **`app/api.py`** — new routes under `/api/portfolios/*` (see Section 4).
  No new router file.

### 2.2 Frontend (new + refactor)

- **`static/js/tickerTable.js`** (new) — the medium-scope shared framework.
  Owns: Columns dropdown (checkbox + ↑/↓ reorder, debounced PUT),
  table header rendering, row rendering, sort, add input + validation,
  per-row delete button, watch stars (Earnings only), edit-cell autosave
  (Portfolio only), empty state.

- **`static/js/portfolio.js`** (new) — portfolio-specific glue:
  `PORTFOLIO_COLUMNS` metadata, cash-row renderer, totals footer row,
  serenity-style expand/collapse per portfolio, editable-cell value
  coercion (parse float, validate ≥ 0), grand total in card header.

- **`static/js/earnings.js`** (refactored) — ~300 LOC → ~80 LOC.
  Reduced to `EARN_COLUMNS` metadata + watch-stars persistence + a thin
  `renderEarnings(earn)` that calls `createTickerTable(...)` and `.render(earn)`.
  Same user-visible behavior, plus the new ↑/↓ reorder.

- **`static/js/api.js`** — new helpers under the existing apiFetch umbrella:
  `fetchPortfolios`, `createPortfolio`, `deletePortfolio`, `renamePortfolio`,
  `addPortfolioHolding`, `editPortfolioHolding`, `removePortfolioHolding`,
  `validatePortfolioSymbol`, `putPortfolioColumns`. Generation-token +
  error-routing logic is shared with the existing earnings path.

### 2.3 HTML / CSS

- **`static/index.html`** — new `<section class="card wide" data-card="portfolio">`
  inserted immediately before the existing
  `<section class="card wide" data-card="earnings">`. Same `reorder`
  controls (↑/↓) as other cards.

- **`static/style.css`** — new `.pf-*` rules for the serenity-style
  expand/collapse, the cash-row styling, totals footer row, and editable
  cell focus/hover/error states.

### 2.4 Files touched (summary)

**New:**
- `app/portfolio.py`
- `static/js/tickerTable.js`
- `static/js/portfolio.js`
- `tests/test_portfolio.py`
- `tests/frontend/portfolio.spec.mjs`
- `tests/frontend/earnings.spec.mjs`

**Modified:**
- `app/api.py` (new routes)
- `static/js/api.js` (new fetch helpers + column endpoint)
- `static/js/cards.js` (`case "portfolio": renderPortfolio`)
- `static/js/earnings.js` (refactored to use `tickerTable.js`)
- `static/index.html` (new card inserted before earnings)
- `static/style.css` (new `.pf-*` rules)
- `AGENTS.md` (new module entry + Recent activity row)

---

## 3. Data Model

### 3.1 `data/portfolios.json` (gitignored)

```json
{
  "version": 1,
  "portfolios": {
    "fidelity-cash": {
      "id": "fidelity-cash",
      "name": "Fidelity Cash",
      "created_at": "2026-09-04T14:30:00",
      "holdings": [
        {"symbol": "NVDA", "shares": 10.5, "total_cost": 5000.00},
        {"symbol": "AAPL", "shares": 25,   "total_cost": 4000.00},
        {"kind": "cash", "label": "Cash", "total_cost": 1500.00, "total_value": 1500.00}
      ]
    },
    "fidelity-roth": {
      "id": "fidelity-roth",
      "name": "Fidelity Roth IRA",
      "created_at": "2026-09-04T14:31:00",
      "holdings": [
        {"symbol": "VTI", "shares": 50, "total_cost": 11000.00}
      ]
    }
  }
}
```

> **Note (final-review fix wave):** The `column_order` and `column_visibility`
> keys shown in earlier revisions of this spec have been removed from the JSON
> schema.  Column prefs are managed entirely on the client via localStorage
> (`pfOrder.<section>`, `pfVisible.<section>`).  The
> `PUT /api/portfolios/columns/{section}` route still exists in `app/api.py`
> (used by the Earnings section's `columnPrefsUrl` callback), but the
> portfolio section ignores server-stored column prefs — they are write-only
> dead data.  This is a deliberate deviation from the original spec to avoid
> duplicating state across localStorage and the JSON file.

### 3.2 Key design points

- **Portfolio id** is a URL-safe slug derived from the user-supplied name
  at create time (`"Fidelity Cash"` → `"fidelity-cash"`); collisions append
  `-2`, `-3`, etc. Stable across renames.
- **Cash row discriminator**: `{"kind": "cash"}` distinguishes it from
  ticker holdings. Symbol-less. `total_cost` (= principal deposited) and
  `total_value` (= current balance) are both user-edited since no live
  price exists.
- **Ticker holdings** are an ordered list (not a map), preserving display
  order. Reordering is done via ↑/↓ buttons in the row (not columns).
- **Empty portfolio** is valid: `"holdings": []`. Shows an empty-state row.
- **No live price fields in JSON.** Prices are fetched live from yfinance
  via `market._quote_snapshot(holdings_symbols)` (same path as
  `app/earnings.py`). Enrichment happens at serve time, never persisted.
- **`version: 1`** allows future schema migrations.
- **Atomic writes** via existing `store.save_json` (temp + os.replace).
- **First-run default**: when `data/portfolios.json` doesn't exist, return
  `{"version": 1, "portfolios": {}}`.
  No migration code needed for v1.

### 3.3 Per-row derived fields (computed at serve, not stored)

| Field | Formula |
|---|---|
| `last_price` | yfinance live quote (`market._quote_snapshot`) |
| `pct_daily` | yfinance 1-day percent change |
| `total_value` | `shares * last_price` (ticker) or `total_value` (cash row, user-edited) |
| `gain_loss` | `total_value - total_cost` (cash row: same formula on its own fields) |
| `gain_loss_pct` | `gain_loss / total_cost * 100` when `total_cost > 0` |

### 3.4 Write validation

- **Symbol**: must pass `earnings.validate_symbol` (existing validator —
  single source of truth).
- **`shares`**: float, ≥ 0.
- **`total_cost`**: float, ≥ 0.
- **Cash row**: `total_cost` ≥ 0, `total_value` ≥ 0.
- Invalid rows rejected with HTTP 400 + `{error, field}`.

---

## 4. API Surface

All routes under `/api/portfolios/*`. JSON in/out. No auth (single-user
local tool, like the rest of the API).

| Method | Path | Body | Response | Purpose |
|---|---|---|---|---|
| `GET` | `/api/portfolios` | — | `{portfolios: {...}, column_order: {...}, column_visibility: {...}}` | All portfolios + column prefs. Enriched with live prices. |
| `POST` | `/api/portfolios` | `{name: "Fidelity Cash"}` | `{id: "fidelity-cash", portfolio: {...empty}}` | Create new empty portfolio. Slug id derived; collision suffix `-2`. |
| `PUT` | `/api/portfolios/{id}` | `{name?, holdings?}` | `{portfolio: {...}}` | Rename and/or replace holdings. Holdings fully replaced (not merged) to keep reorder/remove simple. |
| `DELETE` | `/api/portfolios/{id}` | — | `{deleted: id}` | Remove portfolio. |
| `POST` | `/api/portfolios/{id}/holdings` | `{symbol, shares, total_cost}` | `{holding: {...}}` | Add ticker holding. Symbol validated via `earnings.validate_symbol`. |
| `PUT` | `/api/portfolios/{id}/holdings/{symbol}` | `{shares?, total_cost?}` | `{holding: {...}}` | Edit one holding (used by autosave debounce). |
| `DELETE` | `/api/portfolios/{id}/holdings/{symbol}` | — | `{deleted: symbol}` | Remove a holding. |
| `POST` | `/api/portfolios/{id}/cash` | `{label?, total_cost, total_value}` | `{holding: {...kind: cash...}}` | Add the cash row. Rejected if cash row already exists. |
| `PUT` | `/api/portfolios/{id}/cash` | `{label?, total_cost?, total_value?}` | `{holding: {...kind: cash...}}` | Edit the cash row. |
| `GET` | `/api/portfolios/validate?symbol=` | — | `{valid, symbol, name, sector[, reason]}` | Ticker validation, reused from `earnings.validate_symbol`. |
| `PUT` | `/api/portfolios/columns/{section}` | `{order: [...keys], visibility: {...key: bool}}` | `{order, visibility}` | Save column order + visibility for `earnings` or `portfolio`. Both arrays replaced fully (not merged). |

### 4.1 Error contract

| Status | Body | When |
|---|---|---|
| `400` | `{error: str, field?: str}` | Validation failure (invalid symbol, negative shares, etc.) |
| `404` | `{error: str}` | Unknown portfolio id or symbol |
| `409` | `{error: str}` | Duplicate symbol in portfolio, second cash row, slug collision |

### 4.2 Why per-holding endpoints instead of `PUT /api/portfolios/{id}` only

The autosave debounce fires per-cell (400ms after last keystroke in a Shares
or Total cost cell). Hitting `PUT /api/portfolios/{id}` with the whole
holdings list on every cell change would rewrite all holdings and re-fetch
prices for every symbol on every keystroke. Per-holding endpoint keeps the
payload small and lets the server only re-enrich the changed row's live
price.

### 4.3 Live price enrichment

`GET /api/portfolios` and any endpoint that returns a holding's payload
runs `market._quote_snapshot([unique_symbols])` and merges `last_price`,
`pct_daily` into the response. Failures stay `null` (no exception —
yfinance rate limits are common).

### 4.4 File location

All routes added to `app/api.py` in a new section near the existing
`/api/earnings/*` routes. No new router file.

---

## 5. Frontend Framework — `static/js/tickerTable.js`

The medium-scope shared module both `earnings.js` and `portfolio.js` call.
Single responsibility: column-controls + table rendering. Portfolio- and
earnings-specific behavior stays in their respective files.

### 5.1 Public API

```js
// static/js/tickerTable.js
import { /* shared fetch helpers */ } from "./api.js";

export function createTickerTable({
  section,        // "earnings" | "portfolio"
  containerSel,   // CSS selector for the body element
  controlsSel,    // CSS selector for the controls row
  columns,        // [{key, label, default, num?, editable?, fmt(row, ctx)?}, ...]
  fetchData,      // async () => {rows: [...], rowMeta?: ...}
  addRow,         // async (input) => {rows: [...]}
  removeRow,      // async (rowId) => {rows: [...]}
  editCell,       // async (rowId, colKey, value) => {row}
  columnPrefsUrl, // "/api/portfolios/columns/<section>"
  watchStars,     // optional: {get, set, clear}
});
// Returns { render(data), refresh(), setEditingState(...) }
```

### 5.2 What `tickerTable.js` owns

1. **Columns dropdown UI** — checkbox per column + ↑/↓ buttons inline.
   State changes → `PUT <columnPrefsUrl>` (debounced 300ms).
2. **Header rendering** — `<th class="sortable num? asc/desc" data-key="...">`.
   Click-to-sort toggle.
3. **Row rendering** — applies each column's `fmt(row, ctx)` in order. If
   column has `editable: true`, wraps the cell in an editable `<input>` with
   autosave debounce.
4. **Sort state** — `{key, dir}` per section. Persisted to localStorage
   (`pfSort.<section>`).
5. **Add input** — text input + validate + Add button. Calls `addRow(input)`.
6. **Watch stars** — only if `watchStars` option provided (Earnings only).
7. **Delete button** — per row, calls `removeRow(rowId)`.
8. **Empty state** — "No tickers yet. Add one above." text when no rows.
9. **Re-render orchestration** — single `render(data)` entry point that
   redraws controls + body, preserving sort + column state + editing focus.

### 5.3 What stays in section-specific files

- **`earnings.js`** — exports `renderEarnings(earn)`. Mostly column metadata
  (`EARN_COLUMNS`), watch-stars load/save (`loadEarnWatchColors`,
  `saveEarnWatchColors`), and a thin `renderEarnings` that wraps
  `createTickerTable(...)` and calls `.render(earn)`.
- **`portfolio.js`** — exports `renderPortfolio(state)`. Column metadata
  (`PORTFOLIO_COLUMNS`), cash-row renderer, totals footer row, the
  serenity-style expand/collapse per portfolio, editable-cell value
  coercion (parse float, validate ≥ 0).

### 5.4 Shared fetch helpers in `api.js`

```js
// static/js/api.js
export async function fetchPortfolios() { ... }
export async function createPortfolio(name) { ... }
export async function deletePortfolio(id) { ... }
export async function renamePortfolio(id, name) { ... }
export async function addPortfolioHolding(id, h) { ... }
export async function editPortfolioHolding(id, sym, h) { ... }
export async function removePortfolioHolding(id, sym) { ... }
export async function validatePortfolioSymbol(sym) { ... }
export async function putPortfolioColumns(section, prefs) { ... }
```

Generation-token + error routing logic stays in `api.js`'s
`fetchSectionData` path, reused by both sections' top-level fetch.

### 5.5 Refactor impact on `earnings.js`

- Before: ~300 LOC, owns columns, controls UI, table render, sort, add,
  remove, watch stars.
- After: ~80 LOC: just `EARN_COLUMNS` metadata + watch-star persistence +
  a `renderEarnings(earn)` that calls `createTickerTable(...)`.
- Net: ~220 LOC removed from `earnings.js`, ~180 LOC added to
  `tickerTable.js`. Net reduction ~40 LOC plus higher reuse.

---

## 6. Portfolio-Specific Behavior

### 6.1 Card structure

```
┌─ Portfolio ────────── $XXX,XXX  [▼/▲ all] [⚙ Columns] [+ Create portfolio] ─┐
│                                                                             │
│  ▶ Fidelity Cash ·······  $12,500  (+$1,500 / +13.6%)  [✎ Rename] [✕]       │
│  ▼ Fidelity Roth IRA ····  $11,800  (+$800 / +7.3%)  [✎ Rename] [✕]          │
│     ┌─────────┬────────┬─────────┬─────────┬─────────┬─────────┬─────────┐   │
│     │ Ticker  │ Shares │Tot.cost │Last px  │Tot.value│Gain/loss│ Daily % │   │
│     ├─────────┼────────┼─────────┼─────────┼─────────┼─────────┼─────────┤   │
│     │ VTI     │ 50     │ $11,000 │ $234.56 │ $11,728 │ +$728🟢│ +1.2%🟢 │   │
│     │ Cash    │ —      │ $1,500  │   —     │ $1,500  │  $0     │   —     │   │
│     ├─────────┼────────┼─────────┼─────────┼─────────┼─────────┼─────────┤   │
│     │ Totals  │        │ $12,500 │         │ $13,228 │ +$728🟢│         │   │
│     └─────────┴────────┴─────────┴─────────┴─────────┴─────────┴─────────┘   │
│     [+ Add holding]  [+ Add cash row]                                        │
│                                                                             │
│  ▶ Hidden portfolio ······  $0  [✎ Rename] [✕]                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Card header (always visible)

- **Portfolio** name (h2)
- **Grand total** — sum of all portfolio totals (value, gain/loss $, gain/loss %)
- **▼/▲ all** toggle to expand or collapse all portfolios at once
- **⚙ Columns** dropdown (checkboxes + ↑/↓)
- **+ Create portfolio** button → inline prompt for name → creates empty
  portfolio, auto-expands the new section

### 6.3 Each portfolio = serenity-style expandable section

- **Header row**: caret ▶/▼ + name + totals (value, gain/loss $/%) +
  Rename (✎) + Delete (✕)
- **Expanded body**: holdings table + [+ Add holding] + [+ Add cash row]
- **Collapsed**: only header row
- **Default state**: most-recently-edited portfolio auto-expanded; others
  collapsed. State persisted in localStorage (`pfExpanded.<portfolio_id>`).

### 6.4 Holdings table columns (default visible)

1. **Ticker** — bold symbol (or "Cash" label for cash row). Not editable.
2. **Shares** — editable (float, ≥ 0). Input on focus, autosave on 400ms
   debounce. Cash row shows "—".
3. **Total cost** — editable ($ prefix, formatted). Cash row editable.
4. **Last price** — read-only, live yfinance price. Cash row "—".
5. **Total value** — read-only, computed `shares × last_price`. Cash row
   shows `total_value`.
6. **Gain/loss** — read-only, computed `total_value - total_cost`.
   Color-coded via the existing `pctClass()` helper from `cards.js`
   (green ≥ 0, red < 0) — same convention as Daily % / 7-day %. Cash row
   uses its own `total_value - total_cost`.
7. **Daily %** — read-only, from yfinance (`pct_daily`). Cash row "—".

### 6.5 Cash row

- Rendered **last** in every expanded portfolio's holdings table, fixed
  position (cannot be reordered via ↑/↓).
- Backend discriminator: `{"kind": "cash"}`. Frontend renders "Cash" in
  the Ticker column.
- `Shares` column shows "—" (no input).
- `Total cost` and `Total value` are editable (user manages their cash
  balance manually).
- `Last price`, `Daily %` show "—".
- `Gain/loss` = `total_value - total_cost` (positive if interest accrued).

### 6.6 Editable cell behavior

- Click cell → `<input>` replaces the displayed value, focused + selected.
- Type → debounce 400ms → `PUT /api/portfolios/{id}/holdings/{symbol}` (or
  `/cash`).
- On Enter or blur → immediate save (no debounce wait).
- Network error → revert input to server value + subtle inline error
  (red border, error tooltip).
- Optimistic UI: local state updates first; server response reconciles.

### 6.7 Totals footer row

- `<tr class="pf-totals">` after the last holding.
- Computed columns: Shares (sum), Total cost (sum), Last price ("—"),
  Total value (sum), Gain/loss (sum, color-coded), Daily % ("—").
- Cash row's `total_cost` and `total_value` are included in totals
  (totals row = entire portfolio value).

### 6.8 Grand total (card header)

- Sums across all portfolios' totals: total value across all, total cost
  across all, grand gain/loss $ and %.
- Updates reactively whenever any portfolio's data changes.

### 6.9 Empty state

When no portfolios exist: "No portfolios yet. Click **+ Create portfolio**
above to start." with a centered + Create button.

---

## 7. Earnings Watchlist Refactor (impact)

### 7.1 Same after refactor

- Column visibility toggles (checkboxes in Columns dropdown).
- Click-to-sort on column headers.
- Watch stars (left-click cycles amber → bull → bear → amber; right-click
  clears).
- Add ticker input with validation, Add button, error status text.
- Delete (✕) button per row.
- "No tickers yet" empty state.
- `localStorage` keys: `earnVisibleCols` → renamed to a section-keyed map
  (`pfVisibleCols.earnings`, `pfVisibleCols.portfolio`); `earnSort` →
  `pfSort.earnings` / `pfSort.portfolio`; `earnWatchColors` stays as-is
  (Earnings-only feature).
- No data-shape change in API: `/api/earnings`, `/api/earnings/validate`,
  `/api/earnings/watchlist` unchanged.

### 7.2 New after refactor

- ↑ / ↓ buttons inline next to each row in the Columns dropdown.
  Reordering a column moves it left/right in the table. Default order
  preserved if user never reorders.
- Column order persisted to `data/portfolios.json` under
  `column_order.earnings` (debounced PUT).

### 7.3 Net code change

`earnings.js` ~300 LOC → ~80 LOC. Watch-stars color-cycle/clear logic
stays in `earnings.js` (Portfolio doesn't use it). Everything else moves
to `tickerTable.js`.

---

## 8. Testing Strategy

### 8.1 Backend (`tests/test_portfolio.py`)

- `load_portfolios()` returns default when file missing.
- `save_portfolios()` atomic write (uses `store.save_json`).
- `create_portfolio(name)` derives slug id; collision suffix `-2`.
- `create_portfolio(name)` rejects empty / whitespace / duplicate slug.
- `rename_portfolio(id, name)` updates `name`; id stays stable; rejects
  empty / whitespace name.
- `add_holding()` validates symbol via `earnings.validate_symbol`; rejects
  invalid / duplicate.
- `add_holding()` rejects negative shares or `total_cost`.
- `add_cash_row()` rejects duplicate (one cash row per portfolio).
- `edit_holding()` rejects negative values; returns updated holding.
- `edit_cash_row()` works on the cash row specifically.
- `remove_holding()` removes; missing symbol returns 404.
- `delete_portfolio()` removes; missing id returns 404.
- `enrich_portfolios()` merges live prices (mocked
  `market._quote_snapshot`); null prices stay null.
- `save_column_prefs()` / `load_column_prefs()` round-trip both `earnings`
  and `portfolio` sections independently.
- `validate_symbol()` shared via `earnings.validate_symbol` (covered by
  existing earnings tests).

### 8.2 Frontend Playwright (`tests/frontend/portfolio.spec.mjs`)

- Empty state shows "+ Create portfolio" CTA.
- Create flow: click + → enter name → press Enter → new section appears
  expanded.
- Add holding: ticker validates, row appears with live price, totals
  update.
- Editable Shares cell: click → input → type → debounced save → server
  updated.
- Editable Total cost: same.
- Cash row: appears last; editable cost + value; gain/loss reflects user
  input.
- Rename portfolio: click ✎ → input → save → header updates.
- Delete portfolio: click ✕ → confirm → row disappears, grand total
  updates.
- Column dropdown: toggle visibility, reorder via ↑/↓, persists across
  reload.
- Expand/collapse: click caret → body toggles; state persists across
  reload.
- Grand total: sums across all portfolios correctly.

### 8.3 Frontend Playwright (`tests/frontend/earnings.spec.mjs`)

- Regression: all existing Earnings behaviors still work (sort, toggle,
  add, remove, watch stars).
- New: ↑ / ↓ buttons reorder columns; reload preserves new order.
- New: column visibility/order persists via
  `PUT /api/portfolios/columns/earnings`.

### 8.4 Manual verification (per AGENTS.md hard rules)

- Run `python run.py`, open `http://127.0.0.1:8000`.
- Create a test portfolio, add a holding, edit shares, refresh page →
  state persists.
- Verify `data/portfolio.json` is gitignored (no `git status` entries after
  editing).

---

## 9. Out of Scope (YAGNI)

- Multi-currency. Everything is USD.
- Historical cost-basis tracking (lot-level). `total_cost` is a single
  user-edited number per holding.
- Drag-and-drop column reorder. User chose ↑/↓ buttons.
- Per-portfolio column visibility (each portfolio uses the section-level
  prefs in `column_visibility.portfolio`).
- CSV / OFX / broker import. User edits holdings manually.
- Real-time price updates (websocket). Refresh button + 30-min auto
  refresh is sufficient.
- Multi-cash row (e.g., one per currency). One cash row per portfolio.

---

## 10. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| yfinance rate-limits during `enrich_portfolios()` | Reuse existing `market._quote_snapshot` retry/backoff pattern; null prices stay null (no exception). |
| User edits many holdings fast → debounce storms | Per-cell debounce; PUT is per-holding, not per-portfolio; price fetch is per-symbol. |
| Frontend framework regression in Earnings | Existing earnings behavior preserved exactly; covered by Playwright regression suite. |
| User accidentally deletes a portfolio | Confirm modal before `DELETE /api/portfolios/{id}`. |
| Column reorder makes table layout shift unexpectedly | Sort state survives re-render; ↑/↓ moves one slot at a time (no surprise jumps). |

---

## 11. Open Questions

None remaining. All brainstorming questions resolved before writing this
spec.
