# Portfolio holdings reorder persistence (2026-09-11)

## Problem

The Portfolio section's per-row ▲/▼ buttons (rendered by
`tickerTable.js:moveRow`) mutated the in-memory `data.rows` array only.
The mutation did NOT persist to the backend, so on page reload (or
after the Portfolio card re-rendered for any reason — column reorder,
sort, add/delete holding), the rows snapped back to the order in
`data/portfolios.json`. The "↺ Default order" button was exactly what
got the user back to insertion order after a column-header sort, but
the manual move itself was session-only — an inconsistency the user
flagged.

A second related issue: clicking ▲/▼ while a column-header sort was
active silently worked (the sort auto-reset to default in `moveRow`,
the move became visible). The user wanted the buttons to be greyed
out in that state instead, with a tooltip pointing the user to the
"↺ Default order" button as the recovery path.

## Decision

Three coordinated commits (one backend, two frontend):

1. **`9f6eac1` — `feat(portfolio): backend holdings reorder endpoint + tests`**
   New `app.portfolio.reorder_holdings(pid, order)` mirrors the
   existing `reorder_portfolios` pattern from commit `b45858e` era
   ("Portfolio mutations must patch the cached dashboard payload"):
   - Read state via `load_portfolios()`.
   - Validate `order` is a permutation of the current non-cash
     holdings' symbols (no additions, removals, duplicates) — raise
     `ValueError` if not.
   - Mutate the holdings list in place: non-cash rows in `order`'s
     sequence, cash row (identified by `kind == "cash"`) appended at
     the end.
   - `save_portfolios(state)` then `_patch_dashboard_cache(state)`.
   - Return the updated portfolio dict.

   New `POST /api/portfolios/{pid}/holdings/reorder` endpoint in
   `app/api.py` mirrors the existing `POST /api/portfolios/reorder`
   handler:
   - Body: `{"order": ["NVDA", "AAPL", "MSFT"]}` (symbols only;
     cash row is implicit).
   - `ValueError → HTTP 400`; `KeyError → HTTP 404`.
   - Returns `{"order": [...]}` on success.

2. **`4392797` — `feat(portfolio): frontend holdings reorder persistence`**
   - New `static/js.api.reorderHoldings(pid, order)` (mirror of
     `reorderPortfolios`).
   - `tickerTable.js:moveRow` now POSTs the new symbol order
     (cash rows filtered out) optimistically; on error, reverts and
     surfaces via `setStatus(msg, "bad")` — same status surface the
     add/delete paths already use.
   - `portfolio.js` wires the new `onReorder` callback when
     constructing the per-portfolio `createTickerTable` instance.

3. **`b0e9789` — `fix(portfolio): grey-out ▲/▼ when not in default order`**
   - `tickerTable.js:drawBody` computes `const reorderBlocked =
     sort.key !== "default"` for each row. When true, ▲/▼ render
     with the `disabled` attribute + a tooltip `"Reset to default
     order (↺) before reordering rows"`.
   - `moveRow` gains a defensive `sort.key !== "default"` guard
     (defense in depth — the button is already disabled in the UI).
   - Existing `moveRow` auto-reset-to-default behavior removed in
     favor of the disable; the user must click ↺ first.

## Rationale

- **Why backend persistence (not localStorage):** the existing
  portfolio list reorder (`reorder_portfolios`) and bottleneck
  category reorder (`bottleneck_prefs.reorder_categories`) both
  persist to disk. Holdings reorder joining that pattern keeps the
  three reorder surfaces consistent — and matches the
  "per-entity scope must use composite keys, not nested Maps"
  decision (commit `1fafbc1`) in that the persistence target is the
  canonical source of truth, not a per-browser ephemeral store.
- **Why dict-key insertion order, not a separate `order` field:**
  mirrors `reorder_portfolios` (decision: "Portfolio reorder: dict
  key order, not a separate `order` field"). Python's `json` preserves
  dict insertion order; JS's `JSON.parse` reads it back as an object
  whose iteration order matches. No field schema change.
- **Why filter cash rows out of the request body:** cash rows are
  unique per portfolio (`add_cash_row` rejects duplicates) and always
  rendered last. Sending them in `order` would create ambiguity (two
  rows vs one + the cash row) for zero UX benefit. Server-side
  filtering is one branch in `reorder_holdings`; the test
  `test_reorder_holdings_preserves_cash_row_at_end` enforces the
  invariant.
- **Why grey-out, not auto-reset:** the auto-reset-to-default behavior
  in `moveRow` was a UX surprise — clicking ▲/▼ while a sort was
  active silently changed the sort without telling the user why
  their view "jumped". Grey-out is honest: the row can't be moved
  in non-default order; click ↺ first.
- **Why defense-in-depth in `moveRow`:** the disabled attribute in
  the UI is one layer. `moveRow` is the action layer. Either alone
  is sufficient; both together catch future regressions where a
  caller wires `moveRow` directly (e.g. a programmatic reorder) and
  forgets the UI gate. Same pattern as the boundary-disable on
  ▲/▼ for first/last rows.

## Tests added

- `tests/test_portfolio.py` (+101 lines, 10 new tests):
  - `test_reorder_holdings_swaps_symbols_in_place`
  - `test_reorder_holdings_preserves_cash_row_at_end`
  - `test_reorder_holdings_rejects_missing_symbol`
  - `test_reorder_holdings_rejects_duplicate_symbol`
  - `test_reorder_holdings_unknown_portfolio_raises_KeyError`
  - `test_reorder_holdings_persists_across_reload`
  - +4 edge cases (empty order, single holding, single holding +
    cash, all-cash portfolio).
- `tests/test_api_contract.py` (+67 lines, 4 new tests):
  - `test_post_holdings_reorder_endpoint` (round-trip)
  - `test_post_holdings_reorder_returns_400_on_bad_permutation`
  - `test_post_holdings_reorder_returns_404_on_unknown_pid`
  - `test_post_holdings_reorder_preserves_cash_row`
- `tests/frontend/portfolio-holdings-reorder.spec.mjs` (+147 lines
  across two commits, 6 new tests):
  - `test("▲/▼ move POSTs to /api/portfolios/<pid>/holdings/reorder")`
  - `test("▲/▼ move reverts when the reorder POST fails")`
  - `test("▲/▼ move order omits the cash row")`
  - `test("▲/▼ buttons are disabled when a column header is sorted")`
  - `test("▲/▼ buttons re-enable after ↺ Default order")`
  - `test("▲/▼ click in non-default order is a no-op")`

## Verification

- `python -m pytest tests/test_service_cooldown.py tests/test_portfolio.py
  tests/test_api_contract.py` → **104 passed** in 6.0s.
- `npx playwright test --config=tests/frontend/playwright.config.mjs
  tests/frontend/portfolio-holdings-reorder.spec.mjs
  tests/frontend/refresh-cooldown.spec.mjs` → **17 passed** in 6.4s.

## Mistakes to avoid

- Do NOT extend `add_holding` / `edit_holding` to accept an `index`
  field — that's a different design (positional insert) and would
  conflict with the existing "holdings are a list, append-only" model.
  If the user later asks "add a holding between two existing ones",
  add an `insert_at_index` to `add_holding` as a separate change.
- Do NOT persist the in-memory `data.rows` swap to localStorage
  alongside the server write. The two stores would diverge on a
  failed POST (server says old order, localStorage says new order)
  and the next refresh would silently re-order. Server is the single
  source of truth.
- Do NOT add a `GET /api/portfolios/<pid>/holdings/order` endpoint —
  the order is implicit in the existing holdings list's iteration
  order, and `GET /api/portfolios` already returns it.
