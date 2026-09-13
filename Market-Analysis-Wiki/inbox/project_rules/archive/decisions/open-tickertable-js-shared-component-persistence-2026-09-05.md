# OPEN — tickerTable.js shared-component persistence (2026-09-05)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## OPEN — tickerTable.js shared-component persistence (2026-09-05) — CLOSED 2026-09-06

**Status:** confirmed + defensively fixed.

Investigation: per-section keys (`pfSort.{section}`, `pfVisible.{section}`,
`pfOrder.{section}`) are correctly namespaced in `static/js/tickerTable.js`.
The `column_order` / `column_visibility` backend storage in `app/api.py`'s
`columns_put` is also correctly keyed per-section (`state["column_order"][section]`).
The bug class warned about by AGENT-WORKFLOW-PROMPT.md §3b — "shared
component loses per-section namespacing" — did NOT occur; the refactor was
done correctly.

**Defensive fix:** `static/js/tickerTable.js` now exports a `VALID_SECTIONS`
allowlist (`["earnings", "portfolio"]`) and `_assertValidSection()` runs at
the top of every load/save helper plus `createTickerTable()`. An undefined
or unknown `section` prop throws immediately with a message pointing at
this rule, instead of silently templating `pfSort.undefined` /
`pfVisible.null` and dropping every preference change.

**Rule for future extractions:** "Shared UI components must take their
persistence key as a required prop, validated against an allowlist; never
let a shared component default or hardcode a storage key." Adding a new
section to `VALID_SECTIONS` requires a paired regression test in
`tests/frontend/section-position.spec.mjs` covering the new key.

Regression coverage: `tests/frontend/section-position.spec.mjs` (7 tests)
verifies Earnings/Portfolio isolation across all three persistence
channels (Sort / Visible / Order), reload round-trip, and that no bare
`pfOrder` / `pfVisible` / `pfSort` (no section suffix) keys exist.

