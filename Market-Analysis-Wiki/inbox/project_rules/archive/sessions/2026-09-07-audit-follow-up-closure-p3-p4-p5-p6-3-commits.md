# 2026-09-07 — Audit follow-up closure: P3/P4/P5/P6 (3 commits)

Full text of the entry from `project_rules/SESSION_LOG.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds the full text for the
latest entry and a pointer for older entries).

---

## 2026-09-07 -- Audit follow-up closure: P3/P4/P5/P6 (3 commits)

Closed the remaining audit-2026-09-07 follow-ups. P0 (perf) and the
earnings-date fix shipped in the prior session; this session clears
P3/P4/P5/P6 (P1/P2/P7 were already CLEARED).

**Commits:**
- `4f8d92f` chore(tests): re-enable test_service_coverage.py in default
  pytest run + clean up 5 broken tests
- `a8dbe7f` chore(cleanup): prune earnings-scan skill + fix 4 stale
  docstrings
- `d91b519` docs(project-rules): close audit-2026-09-07 P3/P6 doc drift

**P4 critical (test cleanup).** `tests/test_service_coverage.py` had 5
broken tests at audit time: 3 with `from app import earnings`
(ImportError -- module deleted 2026-09-06 with the watchlist removal),
1 with an outdated `_recompute_ai_sentiment(events, earnings)` 2-arg
signature (the function is now single-arg), and 1 asserting on the
removed `cov["earnings"]` key (earnings is no longer a coverage
section in `service._coverage_counts`). All 5 cleaned up. Re-enabled
the file in the default pytest run, plus `tests/test_thirteenf.py`
(both were excluded historically). +37 tests recovered.

**P5 (stale code).** Docstrings in `app/market.py:4,33,155` and
`app/portfolio.py:29` still pointed at `app/earnings.py` / the
earnings watchlist. All 4 fixed: callers updated to current
`service.py` + `portfolio.py` + `validation.py`; cache-key sanitization
comment rephrased from "user-editable earnings watchlist" to
"user-editable sources (portfolio holdings, validate input)";
`_patch_dashboard_cache` docstring points at the current
"earnings-derived cache pattern" model instead of the deleted
earnings cache pattern. Pruned `.opencode/skills/earnings-scan/`
(referenced `app/earnings.py`, `data/cache/earnings.json`,
`EARNINGS_UNIVERSE` -- all dead).

**P3 (shared-component regression test gap).** The audit claimed
`static/js/tickerTable.js` had no per-portfolio isolation regression
test. Two such tests already exist in `tests/frontend/portfolio.spec.mjs`
(lines 686 + 778, added in `a8b60d2`): "per-portfolio column
visibility: hiding a column in Portfolio A does not affect Portfolio B"
and "per-portfolio column order: reordering in Portfolio A does not
affect Portfolio B". The audit fix-sketch acknowledged `portfolio.spec.mjs`
as an acceptable alternative. Recorded in `project_rules/TESTING.md` so
future extractions know where to add paired coverage when
`VALID_SECTIONS` grows.

**P6 (doc drift).** Six docs files were out of sync:
- `project_rules/API.md` listed 14 routes (actual 25) + 3 deleted
  earnings routes. Rewritten; each route now carries 400/404 contract
  and per-portfolio section-key rules; "Dashboard payload sections"
  reference enumerates every top-level payload key.
- `project_rules/ARCHITECTURE.md` module map listed deleted
  `app/earnings.py` as active, missing `validation.py` /
  `lifecycle.py` / `launcher_icon.py` / `changelog.py`. Section-to-code
  table missing the portfolio card row, listed deleted earnings card
  row. Backend quick-reference included `refresh_earnings` (function
  doesn't exist). Skills list still listed `earnings-scan`. Dead
  "Earnings watchlist supports show/hide columns" quirk kept. News
  sources quirk listed SCMP China / SCMP Business / Korea Herald which
  were removed when the User-Agent / timeout path was hardened. All
  fixed.
- `project_rules/TESTING.md` was claiming 3 closed gaps as open
  (`test_thirteenf.py`, `test_scheduler.py`, `test_run.py`) +
  demanding a paired regression test for the tickerTable shared-
  component refactor that already exists. Rewritten; coverage map
  lists every test file.
- `project_rules/ROADMAP.md` Phase 2 #5 closed (3 test gaps all
  closed).
- `project_rules/HANDOFF.md` had duplicated "Top 3 next actions"
  blocks from two sessions + stale Notes section references to
  removed earnings artifacts (`tests/test_earnings.py`,
  `app/earnings.py`). Rewritten; Current state leads with this
  session's audit closure; Notes section points at
  `tests/test_validation.py` / `app/validation.py`.
- `README.md` claimed RSS sources were "MarketWatch / SCMP China /
  SCMP Business / Korea Herald" but the live `app/config.py` has
  MarketWatch + BBC Business only. Fixed.

**Verification:**

- `python -m pytest tests/`: 421 passed in 50.11 s (up from 384 --
  the +37 are the re-included test_service_coverage + test_thirteenf
  files, both now cleaned up).
- `cd tests/frontend && npx playwright test --reporter=list`: 72
  passed, 3 failed (same pre-existing failures as last session --
  `dash-layout-survives-reload` x2 + `portfolio-star-scope` x1; tracked
  in `project_rules/HANDOFF.md` notes section as unrelated to audit
  work).
- `python -c "from app import service"` + `python -c "from app import
  validation"`: OK. Module surface confirmed unchanged.

Updated:

- `project_rules/HANDOFF.md`: rewritten (see above). Top 3 next
  actions now: Phase 2 #7 (task scheduler / VBS docs audit), Phase 3
  feature backlog intake, archive `data/logs/summary-2026-09-07.md`.
- `project_rules/DECISIONS.md`: new entry "Audit-2026-09-07 follow-up
  closure -- P3/P4/P5/P6 (2026-09-07)" with root-cause rationale for
  each cleanup + the rule for keeping the default pytest run
  exclusion-free.
- `project_rules/ROADMAP.md`: Phase 2 #5 flipped to done.
- `app/changelog.log_change(...)` logged 3 times (one per commit).

Working tree at session end: `data/events.json` (scheduler-owned,
ignore). 3 commits land the work.

---

