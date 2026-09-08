# tickerTable.js section gating must mirror _assertValidSection, not collapse to a single string (2026-09-08)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit pattern: this file is the single source of truth for the
verbose detail; the live file holds only the pointer).

---

## tickerTable.js section gating must mirror _assertValidSection, not collapse to a single string (2026-09-08)

**Status:** confirmed + fixed.

**Bug.** `static/js/tickerTable.js:166` (pre-fix):

```js
const reorderEnabled = section === "portfolio";
```

But every per-portfolio tickerTable instance is constructed in
`static/js/portfolio.js:559` with `section: "portfolio.${pid}"` (e.g.
`"portfolio.alpha-1"`). The strict equality was always FALSE, so:

- the ▲/▼ row reorder buttons (`reorderBtns`, line 375) rendered as
  empty string for every portfolio,
- the "↺ Default order" reset button (`showReset = reorderEnabled`,
  line 226) never rendered for any portfolio,
- `moveRow` and `resetSort` still existed and were wired, but the UI
  to invoke them was gone.

**Why it wasn't caught.** Two layers of failure compounded:

1. **Stale string check after the per-portfolio scoping refactor.**
   The `section === "portfolio"` check predates the per-portfolio
   scoping commit (`1fafbc1`). When the Earnings watchlist section was
   removed (`0c745b6`), every caller of the factory switched to
   `portfolio.<pid>` keys, but the gate was never widened. The
   canonical "portfolio" key now has zero callers — the gate matches
   nothing in production.
2. **Zero test coverage for the affected buttons.** `portfolio-move.spec.mjs`
   covers the **portfolio card** reorder (`.pf-move-up / .pf-move-down`),
   not the **holdings row** reorder. There was no test asserting that
   `.tt-up` / `.tt-down` / `.tt-reset-order` exist on the holdings
   rows of an expanded portfolio, so the silent removal went
   undetected.

**User-facing symptom.** The user reported: *"Was it just removed by
accident. I don't see it in the front-end."* Both the per-row ▲/▼
reorder and the "↺ Default order" button were absent from every
portfolio. The help text in `cards.js:793` still advertised them
("▲/▼ reorder rows in the current view only; ↺ Default order resets
after a column header sort.") — a stale-docs / live-code mismatch.

**Root cause classification.** This is the same anti-pattern class as
the `tickerTable.js` shared-component persistence decision
(2026-09-05): **silent collapse of a per-entity state channel into a
single hardcoded key**. The persistence layer was already fixed for
columns (`pfOrder.portfolio.<pid>`) but the *feature gate* layer was
not — both layers needed to learn the `"portfolio.*"` prefix, and
only one did.

**Fix.**

1. **`static/js/tickerTable.js:166`** — widen `reorderEnabled` to
   match `_assertValidSection`:
   ```js
   const reorderEnabled = section === "portfolio" || section.startsWith("portfolio.");
   ```
2. **`static/js/tickerTable.js:369-371`** — render the ▲/▼ buttons
   with explicit boundary-disable (matches the existing pattern used
   by portfolio cards, bottleneck categories, and dashboard layout
   cards). Pre-fix `moveRow` silently no-op'd at boundaries; with the
   buttons now visible, users needed visual feedback that the move
   isn't possible.
3. **`static/style.css`** — give the action column (`<th></th>` +
   `.tt-row-actions` cell) an explicit width of 90px. The holdings
   table uses `table-layout: fixed`, so without an explicit width the
   column shrunk to its content-min and the row delete button was
   partially covered by the next column's overflow. This was the
   reason a previously-passing portfolio test (`portfolio.spec.mjs:492
   "holding can be removed with the row delete button"`) failed once
   the new buttons were rendered.
4. **`tests/frontend/portfolio-holdings-reorder.spec.mjs`** — new
   spec, 7 tests:
   - ▲/▼ buttons render on every holding row in an expanded portfolio
     (with boundary-disable)
   - ▲ on a middle row swaps it with the row above
   - ▼ on a middle row swaps it with the row below
   - "↺ Default order" button renders inside each portfolio's controls
   - "↺ Default order" resets a column-header sort
   - "↺ Default order" resets a column-header sort back to the manual
     order (after a manual ▲/▼ move, the manual order is the "default")
   - sort state is per-portfolio: sorting Portfolio A doesn't affect
     Portfolio B

**Verification.**

- New spec: **7 passed in 3.2s** — red-green verified against the
  pre-fix code (all 7 tests failed with `ERR_CONNECTION_REFUSED` /
  `Locator not found` on the buggy build).
- Full Playwright suite: **87 passed, 22 failed** — same 22 failures
  as the pre-change baseline (environmental issues in
  `tooltip.spec.mjs`, `bottleneck-move.spec.mjs`, `shutdown-listener.spec.mjs`,
  `dash-layout-survives-reload.spec.mjs`, `portfolio-star-scope.spec.mjs`
  — none caused by this change). Net delta vs. baseline: **+7
  passing, -7 failing**.
- Python suite: **424 passed, 0 failed** (77 portfolio-related + 347
  others; `test_thirteenf.py` and `test_service_coverage.py`
  excluded as the runbook documents).

**Lessons for future agent workflows — rules to apply when adding a
feature gate that depends on a section key:**

- **Mirror the validation function.** When `_assertValidSection`
  accepts both `"portfolio"` and `"portfolio.*"`, every other
  per-section feature flag must accept both too. Treat the validation
  function as the single source of truth and either (a) reuse it,
  or (b) mirror its conditions exactly.
- **Test every button you render.** Buttons added to the DOM but
  unused at runtime still need a test. A button that's "wired but
  never rendered" is one regression away from being "wired but
  broken" — and the user won't see the bug until they look for it.
  This is the broader version of the shared-component persistence
  rule (2026-09-05): per-entity state channels must be tested
  end-to-end through every consumer.
- **The help text is part of the contract.** `cards.js:793` advertised
  the feature; the renderer hid it. Stale docs + live code = a
  silent regression. When a help text string lists a feature, that
  feature should be tested directly so the test fails before the docs
  do.
- **`table-layout: fixed` + per-row action buttons = explicit column
  width required.** Three small buttons can still overflow an
  unconstrained fixed-layout column, especially when one column's
  `<th>` is empty (action column header). Adding a width is cheaper
  than chasing the next regression.
- **Stale equality checks after refactors.** When a code path
  refactors from "single key" to "key + prefix", every `key === "foo"`
  in the same file is a candidate bug. Search for them in the same
  commit as the refactor, not later.
