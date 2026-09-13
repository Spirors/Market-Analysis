# Shared component rebuilds controls subtree — listeners must be re-wired (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Shared component rebuilds controls subtree — listeners must be re-wired (2026-09-06)

**Status:** confirmed + fixed.

In `static/js/tickerTable.js`, `drawControls()` rebuilds the entire
`controlsSel` subtree via `el.innerHTML = ...` on every column reorder,
header sort, and reset-sort. The pre-fix `render()` entry point called
`drawControls(); wireAddInput(); drawBody()` — `wireAddInput()` was wired
ONCE. After the first column reorder, the freshly-created
`.tt-input` / `.tt-add-btn` had no event listeners, and the Add button
silently did nothing.

**Fix:** `wireAddInput()` now runs at the end of `drawControls()`. Every
controls rebuild re-attaches the input/button listeners. Listeners
attach to fresh DOM nodes; the discarded elements (and their listeners)
are GC'd naturally — no leak.

**Rule for future shared components:** "Any shared component that
rebuilds a subtree containing interactive elements (inputs, buttons)
must re-wire those elements' listeners inside the rebuild path — not
rely on a one-shot setup call. Event delegation on a stable container
is the safer alternative if the rebuild happens often."

Regression coverage: `tests/frontend/watchlist-add.spec.mjs` (8 tests)
covers the add flow under: initial render, column reorder, header sort,
visibility toggle, multiple back-to-back reorders, Enter-key, and
input-validation (disabled when empty / whitespace-only).

