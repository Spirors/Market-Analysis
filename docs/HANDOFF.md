# Handoff

`Last updated`: 2026-09-06 17:30 UTC (all four Phase 0 items closed + tests green).

## Current state

**All four Phase 0 items closed** in a single autonomous loop:

- **#1 stuck-process on launch** — `app/lifecycle.py` adds the
  `--auto-reap` watchdog + `data/server.pid` + `/api/shutdown` cleanup.
- **#2 section-position not saving** — defensive fix in
  `static/js/tickerTable.js`: `VALID_SECTIONS` allowlist +
  `_assertValidSection()` guard throws on undefined/unknown section.
  Per-section keys (`pfSort.{section}`, `pfVisible.{section}`,
  `pfOrder.{section}`) are correctly isolated; the fix prevents future
  regressions.
- **#3 earnings watchlist add button broken** — root cause: `drawControls()`
  rebuilt the controls subtree on every column reorder/sort/reset but
  `wireAddInput()` was only called from the public `render()` (once).
  Fix: `wireAddInput()` now runs at the end of `drawControls()`.
- **#4 portfolio name input UX** — `.pf-name-input` switched from
  `flex: 1` to `flex: 0 0 auto; width: auto` so the input sizes to its
  content instead of dominating the header (~87% → <50% width ratio).

Phase 1 (docs split) + Phase 0 are both fully done. Phase 2 (refactor
debt) is the next phase; the codebase health audit item is the natural
entry point.

## Top 3 next actions

1. Phase 2: invoke the `reflect` / `simplify` / `codemap` skill trio to
   produce a prioritized debt list with file:line evidence. This is the
   prerequisite for any large refactor pass.
2. Phase 2: close known test gaps called out in the original `AGENTS.md`:
   `app/thirteenf.py` (network-heavy), `app/scheduler.py` (Windows-only,
   needs a mock), `app/run.py` CLI flags (partially covered by the
   recent `test_run.py` additions).
3. Phase 2: audit for other shared-component extractions with the same
   risk profile as `tickerTable.js` (any component consumed by 2+
   sections with independently-keyed persisted state) and add per-consumer
   regression tests proactively.

## Blockers

None. `data/events.json` has unstaged scheduler timestamp updates — per
`docs/RUNBOOK.md` the `MarketAnalysis-EventsCommit` task owns that file,
not interactive sessions, so they will be picked up at the next 17:00
scheduled run.

## Notes for the next session

- The auto-reap watchdog (`app/lifecycle.py`) is the runtime backstop for
  any future stuck-process regression. Agent terminal launches MUST use
  `--auto-reap 60` (or set
  `$env:MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S=60`). Documented in
  `docs/RUNBOOK.md` §Step 3a.
- `static/js/tickerTable.js` now exports `VALID_SECTIONS` and throws on
  unknown / undefined section. Any future extraction that consumes the
  factory MUST pass a section from that allowlist — extending the
  allowlist requires adding a regression test in
  `tests/frontend/section-position.spec.mjs`.
- The Playwright frontend tests are gated on the static file server
  running at `http://127.0.0.1:8123` (`python -m http.server 8123
  --bind 127.0.0.1` from the repo root). The pytest harness starts it
  automatically via `playwright.config.mjs`'s `webServer` block, but
  one-off runs need it started manually — and per the runbook, it
  must be reaped before the turn ends.
