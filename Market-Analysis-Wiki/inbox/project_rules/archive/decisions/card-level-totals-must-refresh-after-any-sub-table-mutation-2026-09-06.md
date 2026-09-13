# Card-level totals must refresh after any sub-table mutation (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Card-level totals must refresh after any sub-table mutation (2026-09-06)

**Status:** confirmed + fixed (commit `8f3a82e`).

Pre-fix `static/js/portfolio.js:289-305` tickerTable callbacks for
per-holding add/remove/edit mutated the local `p.holdings` closure
and returned rows for the per-table totals row to update — but
`renderGrandHeader()` (which paints the card-level "$X (+Y)" total)
was never called. Only the per-table totals row updated; the card
header stayed stale until the user triggered a full reload. Same
bug class as the earlier Phase 0 "dashboard cache stale after
mutation" (commit `b45858e`) but on a different layer: the
table-internal render fired, the card-internal render did not.

**Fix:** Added `renderGrandHeader()` calls after every addRow,
removeRow, editCell mutation so the card header totals refresh
synchronously with the per-table updates.

**Rule for any per-table mutation callback in a card with a
card-level aggregate (header total, footer count, etc.):** The
callback MUST also re-render the card-level aggregate after the
mutation. Don't rely on a top-level `refresh()` to cascade —
top-level refreshes only fire on explicit user action (Refresh
button, F5), and per-table mutations should be self-contained.

**Generalization:** This same pattern likely applies to other
sections (Bottleneck, Indicators, Breadth cards) that have a
header-level aggregate computed from a table body. Audit each
section's render functions for "table body updates but header
total doesn't" before shipping the Phase 2 codebase health audit.

---

