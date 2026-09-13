# 2026-09-06 — Earnings watchlist section removed + portfolio rename CSS shift fixed

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

## 2026-09-06 -- Earnings watchlist section removed + portfolio rename CSS shift fixed

User-driven scope outside the Phase 2 roadmap.  Two asks:

### Remove the earnings watchlist section entirely

Three scope options presented via question; user picked
"Remove section + portfolio earnings columns" (cleanest).  The
dashboard Earnings card, all 4 /api/earnings* endpoints, the
earnings-derived columns on the Portfolio table, the watchlist
persistence, the AI valuation signal, and the cache-patching
helper are all gone.  Only validation.validate_symbol survives
(it's still used by portfolio.add_holding to reject invalid symbols).

Two commits:
  * Backend removal (one commit, 11 files changed): app/earnings.py
    DELETED, app/validation.py NEW, plus slimming of app/api.py /
    app/portfolio.py / app/config.py / app/service.py / app/risk.py /
    app/ai_sentiment.py / app/analysis.py / app/news.py.  The
    portfolio defaults dropped the 'earnings' column-order /
    column-visibility key.
  * Frontend removal (one commit, 8 files changed):
    static/index.html Earnings section gone, static/js/earnings.js
    DELETED, all 8 earnings-derived columns stripped from
    static/js/portfolio.js PORTFOLIO_COLUMNS, CARD_BAND 'earnings'
    entry gone, watchColors section gone, VALID_SECTIONS slimmed
    to ['portfolio'].

### Fix the shifting css when renaming portfolio

@observer task ses_f8665749 analyzed the user's screenshot:
pencil, totals, and close all shift LEFT ~25-30px when entering
rename mode.  Root cause: span has flex: 1 (grows to fill), input
has field-sizing: content (sizes to text only).  The fix is in
static/js/portfolio.js startEditForPid -- measure the span's
bounding-rect width BEFORE swapping in the input and set
inp.style.minWidth = spanWidth + 'px'.  CSS field-sizing: content
+ the plain min-width: 8ch floor from commit 55400a9 stays as
the sizing mechanism; the JS just adds the per-instance match.

### Tests + docs

  * 369 Python tests pass (tests/ excluding tests/test_thirteenf.py
    network-heavy and tests/test_service_coverage.py long-running,
    both still excluded).
  * 5 Playwright portfolio-name-input tests pass (3 originals + 2
    new short-name layout-shift regression tests).  Other frontend
    specs were updated for the removed earnings references;
    tests/frontend/earnings.spec.mjs, earnings-watch.spec.mjs,
    watchlist-add.spec.mjs, and section-position.spec.mjs were
    DELETED as the functionality they tested is gone.
  * tests/test_earnings.py renamed to tests/test_validation.py;
    tests/test_earnings_rec.py DELETED.
  * Decision recorded in project_rules/DECISIONS.md (two entries: "Earnings
    watchlist section removed" and "Portfolio rename input -- match
    width to span").  Red-green verified for the CSS shift fix --
    reverting the JS measure-and-set causes the no-shift regression
    test to fail.

### Aggregate session state

  * 3 new commits on main (backend removal, frontend removal,
    test updates); DECISIONS + SESSION_LOG + README updated.
  * Python tests: 369 pass.  Playwright portfolio-name-input: 5 pass.
  * No python processes, port 8000 / 8123 free at session end.
  * Phase 2 #5 (test gaps in app/thirteenf.py, app/scheduler.py,
    app/run.py) and Phase 2 #7 (task scheduler docs audit) are
    the remaining open items from the prior session.



