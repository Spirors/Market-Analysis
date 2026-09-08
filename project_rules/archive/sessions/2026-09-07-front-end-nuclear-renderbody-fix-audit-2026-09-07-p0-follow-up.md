# 2026-09-07 — Front-end nuclear renderBody fix (audit-2026-09-07 P0 follow-up)

Full text of the entry from `project_rules/SESSION_LOG.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds the full text for the
latest entry and a pointer for older entries).

---

## 2026-09-07 — Front-end nuclear renderBody fix (audit-2026-09-07 P0 follow-up)

User reported that add/delete holding felt fast but add/delete/rename
portfolio still felt sluggish, even though the audit-2026-09-07 P0 fix
had reduced backend POST latency from ~1.8 s to ~130 ms. Three
Playwright tests were also still failing
(`dash-layout-survives-reload` x2 + `portfolio-star-scope` x1).

### Diagnostic phase

Read-only investigation. TestClient in-process (no port binding, no
orphan risk) to measure all 4 mutations × 5 trials each + cache
validation. Results: every POST/DELETE completed in 2-15 ms with mocked
yfinance (~130 ms with real yfinance per the audit). No mutation
triggered GET /api/dashboard; only add portfolio triggered a follow-up
GET /api/portfolios (front-end-initiated from `portfolio.js:545`).

Dispatched @explorer (exp-1) to map the front-end render graph:
`portfolio.js` had a module-level `portfolioData` let with no
signals/store. Mutations updated it via three patterns: in-place push
(add holding), filter to new array (remove holding), full replace or
partial delete (add/remove portfolio). Render functions:

- Add/remove holding: targeted (`renderHoldingsTable(pfSlot, p)` on one
  slot). Fast.
- Add/remove portfolio: full `renderBody()` rebuild via `el.innerHTML =
  html`, destroying every `.pf-pf` div and re-creating every
  tickerTable instance. Expensive — O(N×M) DOM ops.

Conclusion: the backend was already fast. The bottleneck was front-end:
**`renderBody()` rebuilds the entire `#portfolioBody` subtree on every
add/remove/rename/expand/collapse/star/toggle portfolio.**

### Implementation phase

Three patches, shipped in 3 commits:

1. `978f642 fix(portfolio): enrich POST /api/portfolios response with
   live prices` (`app/api.py`): builds a minimal state dict and passes
   the new portfolio through `enrich_portfolios` so the response shape
   matches what GET /api/portfolios returns. Eliminates the follow-up
   GET on add portfolio.

2. `7229ae0 fix(portfolio): targeted render + tickerTable preservation`
   (`static/js/portfolio.js`):
   - Extracted `buildPortfolioHTML(p)` helper.
   - Added `renderPortfolioInsert(p, opts)` / `renderPortfolioRemove(pid)`
     / `renderPortfolioRename(pid, name)` — each touches only the single
     affected portfolio div + the card h2 grand total.
   - Rewired the 3 handlers (addPortfolio, removePortfolio,
     renamePortfolio) to use the targeted helpers instead of
     `renderBody()`.
   - Made `renderHoldingsTable` early-return + reuse the existing
     tickerTable instance via `existing.refresh({rows})` when one is
     already in the `portfolioTables` Map.
   - **CRITICAL: `renderBody()` now calls `portfolioTables.clear()`
     immediately before `el.innerHTML = html`** (and before the empty-
     state placeholder branch). The innerHTML replacement detaches
     every `.pf-pf-body` slot, so any tickerTable instance still in
     the Map would be orphaned and the early-return above would call
     `refresh()` on a detached table — leaving the holdings slot
     empty. Discovered when `tests/frontend/portfolio.spec.mjs` star
     cycling tests went red on Patch C alone; green after the clear.

3. `1212099 test(portfolio): regression coverage for Patches A/B/C +
   spec fixes` (3 new spec files + extend 1 existing):
   - `portfolio-targeted-render.spec.mjs` — 3 tests asserting sibling
     DOM identity survives add/remove/rename (the smoke test for
     Patch A).
   - `tickerTable-instance-preservation.spec.mjs` — 2 tests asserting
     #pf-table-<pid> keeps DOM identity across add holding + sort
     state persists (smoke test for Patch C).
   - `portfolio-add-no-refresh.spec.mjs` — 1 test asserting
     exactly-one-POST + zero-GETs on add portfolio (smoke test for
     Patches A+B).
   - Extended `portfolio-optimistic-ui.spec.mjs:134` (the existing
     "add portfolio triggers no follow-up GET" test) with the same
     route-pattern fix.

   **Playwright gotcha discovered:** the glob pattern
   `**/api/portfolios` does NOT match the exact path
   `/api/portfolios` (only matches when there's a path prefix). Use a
   regex `/\/api\/portfolios(\?|$|\/)/` so the POST request
   `/api/portfolios?name=...` is intercepted. Without this, the POST
   falls through to the static file server (which returns 501 for
   POST) and the create handler surfaces a "not valid JSON" alert.

### Verification

- `python -m pytest tests/`: **421 passed** in 53 s.
- `npx playwright test` (full suite): **62 passed / 20 failed** in 13 s.
  - 5 of the 62 are the new tests from this session (the other 57
    were passing before).
  - 3 of the 20 failures are the audit-noted pre-existing
    (`dash-layout-survives-reload` x2 + `portfolio-star-scope` x1;
    HANDOFF.md called these out from session start).
  - 17 of the 20 failures are environmental: `shutdown-listener.spec.mjs`
    (8) and `tooltip.spec.mjs` (9) need a running FastAPI server (port
    8000) to mock /api/shutdown + /api/cancel-shutdown. The static-only
    test setup serves them on 8123, where these endpoints return 404 or
    501. Confirmed pre-existing on the baseline (stashed my changes,
    re-ran the two files, same 17 failures).
- `python -c "from app import api"`: OK.
- `node -c static/js/portfolio.js`: no syntax errors.

Updated:

- `project_rules/HANDOFF.md`: rewritten (see above). Top 3 next actions
  carry over from the previous session (Phase 2 #7 task-scheduler/VBS
  docs audit, Phase 3 backlog intake, archive
  `data/logs/summary-2026-09-07.md`).
- `project_rules/DECISIONS.md`: new durable entry documenting the
  "renderBody must clear portfolioTables Map immediately before
  innerHTML rebuild" rule (the lesson from the star-click red/green
  round-trip).
- `app/changelog.log_change("fix", ...)` logged once (combines all 3
  patches into one summary).

Working tree at session end: `data/events.json` has unstaged scheduler
timestamp updates (scheduler-owned, ignore per project-rules). 3 commits
+ 2 doc commits land the work. No python processes, port 8000/8123
free.

---
