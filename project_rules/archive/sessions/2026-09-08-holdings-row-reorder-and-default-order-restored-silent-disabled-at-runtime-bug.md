# 2026-09-08 — Holdings row reorder + "↺ Default order" restored (silent-disabled-at-runtime bug)

Full text of the entry from `project_rules/SESSION_LOG.md`
(retrofit pattern: this file is the single source of truth for the
verbose detail; the live file holds only the pointer).

---

## 2026-09-08 — Holdings row reorder + "↺ Default order" restored

**Trigger.** User reported that two features were missing from the
Portfolio section:

1. "Move tickers up and down inside portfolio"
2. "Have a default ordering button. The default ordering is
   determined by above (so I change back to default after sorting by
   other columns)"

Investigation surfaced that **both features already exist in code**
but were silently disabled at runtime.

**Root cause.** `static/js/tickerTable.js:166` (pre-fix):

```js
const reorderEnabled = section === "portfolio";
```

But every per-portfolio tickerTable instance is constructed in
`static/js/portfolio.js:559` with `section: "portfolio.${pid}"`
(e.g. `"portfolio.alpha-1"`). The strict equality was always FALSE,
so:

- the ▲/▼ row reorder buttons (`reorderBtns`, line 375) rendered as
  empty string for every portfolio,
- the "↺ Default order" reset button (`showReset = reorderEnabled`,
  line 226) never rendered for any portfolio,
- `moveRow` and `resetSort` still existed and were wired, but the UI
  to invoke them was gone.

**Why it wasn't caught earlier.** Two compounding failures:

1. **Stale string check after the per-portfolio scoping refactor**
   (commit `1fafbc1`). The `section === "portfolio"` check predates
   the per-portfolio scoping. When the Earnings watchlist section was
   removed (`0c745b6`), every caller switched to `portfolio.<pid>`
   keys, but the gate was never widened. The canonical "portfolio"
   key now has zero callers — the gate matches nothing in production.

2. **Zero test coverage for the affected buttons.** `portfolio-move.spec.mjs`
   covers the **portfolio card** reorder (`.pf-move-up /
   .pf-move-down`), not the **holdings row** reorder. No test asserted
   that `.tt-up` / `.tt-down` / `.tt-reset-order` exist on the
   holdings rows of an expanded portfolio, so the silent removal
   went undetected.

**Files changed.**

1. **`static/js/tickerTable.js`**:
   - Line 166: `const reorderEnabled = section === "portfolio" || section.startsWith("portfolio.");`
     — mirrors `_assertValidSection` and admits the per-portfolio
     `portfolio.*` prefix.
   - Lines 369-385: render the ▲/▼ buttons with explicit
     boundary-disable (`isFirstRow` / `isLastRow` locals + the existing
     `${... ? " disabled" : ""}` template). Pre-fix `moveRow`
     silently no-op'd at boundaries; with the buttons now visible,
     users needed visual feedback that the move isn't possible.
2. **`static/style.css`** — give the action column (`<th></th>` +
   `.tt-row-actions` cell) an explicit `width: 90px`. The holdings
   table uses `table-layout: fixed`, so without an explicit width
   the column shrinks to its content-min and the row delete button
   is partially covered by the next column's overflow. This was the
   reason `portfolio.spec.mjs:492 "holding can be removed with the
   row delete button"` failed once the new buttons were rendered.
3. **`tests/frontend/portfolio-holdings-reorder.spec.mjs`** (new, 7
   tests): ▲/▼ buttons render per row with boundary-disable; ▲ swaps
   a row up; ▼ swaps a row down; "↺ Default order" button renders;
   "↺ Default order" resets a column-header sort; "↺ Default order"
   resets a column-header sort back to the manual order (after a
   manual ▲/▼ move, the manual order is the "default"); sort state
   is per-portfolio (sorting Portfolio A doesn't affect Portfolio B).
4. **`project_rules/DECISIONS.md`** — new pointer entry
   (cross-reference 2026-09-05 shared-component persistence decision
   for the same anti-pattern class).
5. **`project_rules/archive/decisions/tickertable-js-section-gating-must-mirror-assertvalidsection-not-collapse-to-single-string-2026-09-08.md`**
   (new, full text).
6. **`project_rules/HANDOFF.md`** — updated "Latest" line.
7. **`project_rules/SESSION_LOG.md`** — this entry.
8. **`data/logs/summary-YYYY-MM-DD.md`** — `app.changelog.log_change` called.

**Verification.**

- New spec: **7 passed in 3.2s** — red-green verified against the
  pre-fix code (all 7 tests failed with `ERR_CONNECTION_REFUSED` /
  `Locator not found` on the buggy build).
- Full Playwright suite: **87 passed, 22 failed**. Pre-change baseline:
  **80 passed, 29 failed**. Same 22 failures (environmental issues in
  `tooltip.spec.mjs`, `bottleneck-move.spec.mjs`,
  `shutdown-listener.spec.mjs`, `dash-layout-survives-reload.spec.mjs`,
  `portfolio-star-scope.spec.mjs`). Net delta vs. baseline: **+7
  passing, -7 failing**.
- Python suite: **424 passed, 0 failed** (77 portfolio-related + 347
  others; `test_thirteenf.py` and `test_service_coverage.py`
  excluded as the runbook documents).

**Lessons for future agent workflows (rules to apply when adding a
feature gate that depends on a section key):**

- **Mirror the validation function.** When `_assertValidSection`
  accepts both `"portfolio"` and `"portfolio.*"`, every other
  per-section feature flag must accept both too. Treat the validation
  function as the single source of truth.
- **Test every button you render.** Buttons added to the DOM but
  unused at runtime still need a test. A button that's "wired but
  never rendered" is one regression away from being "wired but
  broken" — and the user won't see the bug until they look for it.
- **The help text is part of the contract.** `cards.js:793`
  advertised the feature; the renderer hid it. Stale docs + live
  code = silent regression.
- **`table-layout: fixed` + per-row action buttons = explicit column
  width required.** Three small buttons can still overflow an
  unconstrained fixed-layout column, especially when one column's
  `<th>` is empty (action column header).
- **Stale equality checks after refactors.** When a code path
  refactors from "single key" to "key + prefix", every
  `key === "foo"` in the same file is a candidate bug. Search for
  them in the same commit as the refactor, not later.

**Cross-references.**

- DECISIONS.md "tickerTable.js section gating must mirror
  _assertValidSection, not collapse to a single string" (2026-09-08,
  this entry).
- DECISIONS.md "OPEN — tickerTable.js shared-component persistence"
  (2026-09-05) — same anti-pattern class (silent collapse of
  per-entity state into a single hardcoded key).
- DECISIONS.md "Per-portfolio scope must use composite keys, not
  nested Maps" (2026-09-06) — the per-portfolio scoping refactor
  that introduced the `portfolio.<pid>` section keys.
- DECISIONS.md "Portfolio reorder: dict key order, not a separate
  `order` field" (2026-09-07) — the portfolio **card** reorder that
  inspired the holdings row reorder.
