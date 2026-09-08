# 2026-09-06 — Phase 0 #2 / #3 / #4 closed in autonomous loop (commits pending)

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

## 2026-09-06 - Phase 0 #2 / #3 / #4 closed in autonomous loop (commits pending)

User stepped away and asked for the remaining Phase 0 items to be
worked through in a loop. Closed three bugs in one session with per-
section regression tests for each.

### Phase 0 #2 ΓÇö section position (column order) per-section persistence

Investigation: per-section keys (pfSort.{section}, pfVisible.{section},
pfOrder.{section}) are correctly namespaced in static/js/tickerTable.js,
and the columns_put backend endpoint correctly keys
state["column_order"][section] per section. The bug class warned about
in AGENT-WORKFLOW-PROMPT.md ┬º3b did NOT occur ΓÇö the refactor was clean.

Defensive fix: static/js/tickerTable.js exports a VALID_SECTIONS
allowlist (["earnings", "portfolio"]) and _assertValidSection()
guards every load/save helper plus createTickerTable(). An undefined or
unknown section prop throws immediately instead of silently templating
pfSort.undefined / pfVisible.null and dropping every preference
change.

Regression coverage: tests/frontend/section-position.spec.mjs (7 tests)
verifies per-section isolation across Sort / Visible / Order, reload
round-trip, and the absence of bare pfOrder / pfVisible / pfSort
keys without a section suffix.

### Phase 0 #3 ΓÇö earnings watchlist Add button broken after first column reorder

Root cause: in static/js/tickerTable.js, drawControls() rebuilds the
entire controlsSel subtree via el.innerHTML = ... on every column
reorder, header sort, and reset-sort. The pre-fix 
ender() entry point
called drawControls(); wireAddInput(); drawBody() ΓÇö wireAddInput() was
wired ONCE. After the first column reorder, the freshly-created
.tt-input / .tt-add-btn had no event listeners and the Add button
silently did nothing.

Fix: wireAddInput() now runs at the end of drawControls(). Every
controls rebuild re-attaches the input/button listeners. Listeners
attach to fresh DOM nodes; the discarded elements (and their listeners)
are GC'd naturally ΓÇö no leak.

Regression coverage: tests/frontend/watchlist-add.spec.mjs (8 tests)
covers the add flow under: initial render, column reorder, header sort,
visibility toggle, multiple back-to-back reorders, Enter-key, and
input-validation (disabled when empty / whitespace-only). Red-green
verified: with the fix reverted, 4 tests fail (3 wireAddInput regressions
+ 1 VALID_SECTIONS export check).

### Phase 0 #4 ΓÇö portfolio name input UX

Pre-fix .pf-name-input had flex: 1; min-width: 0; which stretched
the inline rename input to ~87% of .pf-pf-header width (measured
1027 / 1184 px on a typical desktop). The surrounding empty space
inside the header was too narrow to hit.

Fix: static/style.css switches .pf-name-input to
flex: 0 0 auto; width: auto; min-width: 160px; max-width: 100%. The
input now sizes to its content while staying usable on narrow headers.

Regression coverage: tests/frontend/portfolio-name-input.spec.mjs (3
tests) asserts the input width ratio stays under 50% of header width,
plus the single-line + click-outside-to-blur + Enter-saves UX behaviors.
Red-green verified: without the fix, the width ratio is 0.857; with the
fix, it's < 0.5.

### Aggregate session state

- All four Phase 0 items closed.
- Phase 1 (docs split) + Phase 0 are both fully done.
- Test counts: 400 Python tests pass (excluding test_thirteenf.py network-
  heavy + test_service_coverage.py long-running); 15 Playwright frontend
  tests pass across the three new spec files.
- Next session: Phase 2 - invoke the reflect / simplify / codemap skill
  trio to produce a prioritized debt list with file:line evidence, then
  close the app/thirteenf.py / app/scheduler.py / app/run.py test
  gaps and audit for other shared-component extractions with the same
  risk profile as tickerTable.js.


