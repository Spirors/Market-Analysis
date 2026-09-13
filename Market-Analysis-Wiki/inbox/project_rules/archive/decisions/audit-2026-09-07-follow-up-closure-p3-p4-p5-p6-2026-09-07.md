# Audit-2026-09-07 follow-up closure -- P3/P4/P5/P6 (2026-09-07)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Audit-2026-09-07 follow-up closure -- P3/P4/P5/P6 (2026-09-07)

Closed the remaining audit-2026-09-07 follow-ups this session (3 commits:
`4f8d92f`, `a8dbe7f`, `d91b519`). P0 (perf) and the earnings-date fix
shipped in the prior session. P1/P2/P7 were already CLEARED by the audit.
This entry records the durable decisions behind the cleanup so a future
session doesn't re-litigate.

**P4 critical (`tests/test_service_coverage.py`).** The file was excluded
from the default pytest run per the historical AGENTS.md note ("network-
heavy + long-running"). The exclusion was hiding 5 broken tests for
months: 3 with `from app import earnings` (ImportError -- module deleted
2026-09-06), 1 with an outdated `_recompute_ai_sentiment(events,
earnings)` 2-arg signature, and 1 with `cov["earnings"]` assertion
(earnings is no longer a coverage section in `_coverage_counts`).

**Rule (durable):** test files in `tests/` should run by default. Don't
add files to the `--ignore=` list for long-runtime or network-heavy
reasons -- fix the slowness (mock the network, parallelize the suite)
or accept the cost. Hiding broken tests via exclusion creates silent
regressions. `test_thirteenf.py` is now in the default run too (196
lines, properly mocked EDGAR responses); the historical "network-heavy"
exclusion was outdated.

**P5 (stale code).** Two flavors:

1. Stale docstrings pointing at deleted artifacts. `app/market.py:4,33`
   still named `earnings.py` as a caller; `:155` still mentioned the
   "user-editable earnings watchlist"; `app/portfolio.py:29` still
   pointed at the earnings cache pattern. All 4 fixed.

2. Dead skill file: `.opencode/skills/earnings-scan/SKILL.md` referenced
   `app/earnings.py`, `data/cache/earnings.json`, and `EARNINGS_UNIVERSE`
   -- all deleted 2026-09-06 with the watchlist section. Pruned (the
   whole directory was just SKILL.md; no consumers).

**Rule (durable):** when removing an `app/...py` module, grep for the
module name across `app/`, `static/js/`, `tests/`, `project_rules/`,
`.opencode/skills/`, and `docs/logs/` in one pass. Each match is either
a stale docstring/skill/test/doc reference to fix in the same commit, or
a historical audit-trail entry in `DECISIONS.md` to keep as-is. The
distinction: live code + runnable docs = fix; prose in `DECISIONS.md` /
`SESSION_LOG.md` = keep.

**P3 (shared-component regression test).** The audit claimed
`static/js/tickerTable.js` had no per-portfolio isolation regression
test for its sole consumer (`portfolio.js`). Two such tests already
exist in `tests/frontend/portfolio.spec.mjs` (lines 686 + 778, added
in `a8b60d2`): per-portfolio column visibility + column order isolation.
The audit's fix sketch (`Add tests/frontend/tickerTable-section-
isolation.spec.mjs... Or amend portfolio.spec.mjs with the cross-
portfolio isolation assertion.`) acknowledged `portfolio.spec.mjs` as
an acceptable alternative.

**Rule (durable):** the shared-component persistence rule ("new section
in `VALID_SECTIONS` requires a paired regression test") is satisfied by
either a dedicated `tickerTable-section-isolation.spec.mjs` or by
assertions in the consumer's own spec file. Document the chosen
location in `project_rules/TESTING.md` so future extractions know where
to add paired coverage. The tickerTable factory is currently consumed
by `portfolio.js` only -- the prior Earnings watchlist removal dropped
the second consumer.

**P6 (doc drift).** Six docs files were out of sync with the codebase
after the 2026-09-06 Earnings watchlist removal + the 2026-09-07 P0 perf
fix + the 2026-09-07 earnings-date fix. `project_rules/API.md` listed 14
routes (actual 25) + 3 deleted earnings routes. `project_rules/
ARCHITECTURE.md` listed `app/earnings.py` as active (deleted) and was
missing 4 modules (`validation.py`, `lifecycle.py`, `launcher_icon.py`,
`changelog.py`). `project_rules/TESTING.md` was claiming 3 closed test
gaps as open. `project_rules/ROADMAP.md` Phase 2 #5 was still "open"
despite the gaps being closed. `project_rules/HANDOFF.md` had
duplicated "Top 3 next actions" blocks + stale Notes section references
to removed earnings artifacts. `README.md` claimed RSS sources were
"MarketWatch / SCMP China / SCMP Business / Korea Herald" but the live
`app/config.py` has MarketWatch + BBC Business only.

**Rule (durable):** doc drift is a maintenance debt that compounds
quietly. After any module removal + 2+ related fixes, audit the
referencing docs (`project_rules/*.md` + `README.md` + `.opencode/
skills/*/SKILL.md`) in the same session that ships the removal. The
audit-2026-09-07 + this closure commit pair took ~2 hours end-to-end;
without it the drift would have grown for another quarter.

**Verification at session end:**

- `python -m pytest tests/`: 421 passed in 50.11 s (up from 384 in the
  prior session; the +37 are the re-included `test_service_coverage` +
  `test_thirteenf` files).
- `cd tests/frontend && npx playwright test --reporter=list`: 72 passed,
  3 failed (same pre-existing failures as the prior session --
  `dash-layout-survives-reload` x2 + `portfolio-star-scope` x1; unrelated
  to audit work).
- 3 commits land the work; working tree clean except for
  `data/events.json` (scheduler-owned, per AGENTS.md).


