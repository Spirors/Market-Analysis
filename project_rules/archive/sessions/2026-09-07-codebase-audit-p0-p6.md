# 2026-09-07 — Codebase audit (P0..P6)

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

## 2026-09-07 -- Codebase audit (P0..P6)

General codebase audit, post Phase 2 #1-#4 close. Documentation-only
deliverable: `docs/logs/audit-2026-09-07.md`. No code changes
this session.

Method: 4 parallel `@explorer` recon lanes (frontend P0 trace,
backend P0 trace, backend hygiene + data integrity, test coverage +
doc drift) + direct reads of `app/portfolio.py`, `app/api.py`,
`static/js/portfolio.js`, `static/js/api.js`,
`project_rules/ARCHITECTURE.md`, `project_rules/DECISIONS.md`.
Verified the critical P5 claim end-to-end:
`python -c "from app import earnings"` raises
`ImportError: cannot import name 'earnings' from 'app'`.

Findings:

- **P0 (user-visible latency, headline bug) -- root cause
  CONFIRMED.** `app/portfolio.py:47` calls `enrich_portfolios(state)`
  synchronously inside `_patch_dashboard_cache(state)`, which fires
  after every portfolio mutation. For ~10 holdings on cold cache
  this is ~22 HTTP calls (~3 s cold, ~2.4 s warm). Three independent
  contributors: (1) `_patch_dashboard_cache` re-enriches all symbols
  on a 1-symbol change, (2) `_quote_snapshot` has no disk cache
  (`market.get_quotes` exists with QUOTE_TTL=30min but the portfolio
  path doesn't use it), (3) frontend `await refresh()` after every
  mutation in the bespoke button handlers (`portfolio.js:392,396,
  273,428,437`). The tickerTable row-level callbacks already prove
  the optimistic-update pattern works. Fix sketch in the audit file
  with regression test design (mock yfinance + assert POST <500ms +
  assert row visible within one paint frame).
- **P1 (server lifecycle) -- CLEARED.** All subprocess calls safe
  (synchronous with timeouts), `wscript.exe scheduler.vbs` used for
  all 3 scheduled tasks, auto-reap watchdog defaults to 0 for
  desktop and is opt-in only, PID file written on startup + cleaned
  on atexit + `/api/shutdown`.
- **P2 (data integrity) -- CLEARED.** All `or 0`/`or ""`/
  `except Exception` patterns are type guards or sentinels, never
  fabricated market data. All snapshot builders carry `as_of`
  timestamps. Ticker display names have a single source of truth
  in `static/js/meta.js`.
- **P3 (shared components) -- one gap.** `static/js/tickerTable.js`
  has no dedicated regression test for its sole remaining consumer
  (`portfolio.js`) after `section-position.spec.mjs` was deleted
  with the Earnings watchlist removal. The shared-component
  persistence rule ("Adding a new section to `VALID_SECTIONS`
  requires a paired regression test") has no test file backing it
  anymore.
- **P4 (test coverage) -- CRITICAL bug found.** Three test
  functions in `tests/test_service_coverage.py` (lines 312, 358,
  453) do `from app import earnings as earnings_mod`; the module
  was deleted 2026-09-06 and the live successor is
  `app/validation.py`. These raise `ImportError` at module-load
  time. The file is excluded from the default pytest run per
  AGENTS.md (62s runtime budget) so this hasn't been caught.
  Follow-up: delete the three affected tests + audit the rest of
  the file for other deleted-earnings references (64 "earnings"
  matches across the test suite). Separately: ROADMAP Phase 2 #5
  lists 3 test gaps (`app/thirteenf.py`, `app/scheduler.py`,
  `app/run.py` CLI flags) that are ALL closed by existing test
  files (`test_thirteenf.py`, `test_scheduler.py`, `test_run.py`).
- **P5 (stale code) -- covered.** Production code is clean of
  `app.earnings` imports. Stale references in 4 docstrings
  (`app/market.py:4,33,155`, `app/portfolio.py:29`), 1 skill file
  (`.opencode/skills/earnings-scan/SKILL.md`), and the test file
  above. No dead branches / `if False` / `# FIXME` found in
  `app/`, `static/js/`, or `tests/`.
- **P6 (doc drift) -- severe on API.md, moderate on
  ARCHITECTURE.md / TESTING.md / HANDOFF.md, mild on ROADMAP.md.**
  API.md lists 14 routes but actual code has 25+ (all Portfolio
  CRUD undocumented); still lists 3 deleted earnings endpoints.
  ARCHITECTURE.md lists deleted `app/earnings.py` as active,
  missing 4 modules, missing portfolio card from section-to-code
  table. TESTING.md lists 3 closed test gaps as open. HANDOFF.md
  points at removed `tests/test_earnings.py` and
  `app/earnings.py`. DECISIONS.md stale references are correct as
  historical anchors (do not clean up).

"Findings explicitly cleared" section at the bottom of
`audit-2026-09-07.md` saves future sessions from re-checking every
subprocess / `or 0` / `except Exception` / ticker-name pattern.

Out-of-scope follow-ups (all deferred, not this session):
- Apply / verify P0 fix (targeted cache patch + route through
  `market.get_quotes` + drop `await refresh()` in bespoke button
  handlers).
- Delete the 3 stale-import test functions in
  `tests/test_service_coverage.py`.
- Rewrite `project_rules/API.md`, prune `project_rules/ARCHITECTURE.md`,
  strike closed gaps from `project_rules/TESTING.md`, update
  `project_rules/HANDOFF.md` notes, prune
  `.opencode/skills/earnings-scan/SKILL.md` (or repurpose).
- Add per-portfolio shared-component regression test for
  `tickerTable.js` (close the P3 gap).
- Close ROADMAP Phase 2 #5 (all 3 test gaps already closed).

4 `app.changelog.log_change("doc", ...)` calls logged the major
findings. No python processes, port 8000/8123 free at session end.
Working tree: `data/events.json` (scheduler-owned, ignore) +
`project_rules/HANDOFF.md` (modified) + `docs/logs/audit-2026-09-07.md`
(untracked, new).



