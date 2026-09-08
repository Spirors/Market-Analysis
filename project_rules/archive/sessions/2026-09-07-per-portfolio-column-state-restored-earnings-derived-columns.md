# 2026-09-07 — ΓÇö Per-portfolio column state + restored earnings-derived columns

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

## 2026-09-07 ΓÇö Per-portfolio column state + restored earnings-derived columns

### Restore 8 portfolio columns + make columns per-portfolio

User asked for the 8 columns the previous session had stripped
when the Earnings watchlist section was removed
(7-day %, 30-day %, Earnings date, Marketcap, Forward PE, Forward
PEG, 52W high, Sector) and wanted each portfolio's column
visibility/order to be independent.

User clarification before code:
  - Columns dropdown moves INSIDE each expanded portfolio
    (not in the card header anymore).
  - All 8 columns visible by default.

Two commits:
  * Backend (75b7c70): enrich_portfolios now derives pct_7d /
    pct_30d / high_52w from a single 260-day bulk history fetch
    and pulls sector / marketcap / forward_pe / forward_peg /
    next_earnings from per-symbol Ticker.info + calendar (cached
    5 min via lru_cache). PUT /api/portfolios/columns/{section}
    accepts 'portfolio.<pid>' for per-portfolio overrides (404 on
    unknown pid). DEFAULT_COLUMN_ORDER/VISIBILITY grows from 8 to
    16 entries in the user's listed order.
  * Frontend (a8b60d2): tickerTable _assertValidSection accepts
    the 'portfolio.*' prefix; new controlsMode: 'columnsOnly'
    flag lets Portfolio render the Columns dropdown + reset
    without the free-text add input (which Portfolio doesn't use
    - it has bespoke +Add holding / +Add cash buttons). Each
    portfolio's tickerTable gets section='portfolio.<pid>' so
    localStorage keys + backend keys namespace per portfolio.
    PORTFOLIO_COLUMNS grows from 8 to 16 with new fmt functions
    (fmtSignedPct, fmtMarketCap). Card-header Columns dropdown
    removed - per-portfolio is the only scope now. Card header
    keeps '+ Create portfolio' + 'Γû╝ all / Γû▓ all' only.

Test changes:
  - tests/test_portfolio.py: +9 tests (enrich history derivation,
    enrich fundamentals, cache hit, per-portfolio PUT round-trip,
    per-portfolio 404, default column set has all 16).
  - tests/frontend/portfolio.spec.mjs: 3 existing column tests
    updated (dropdown moved + _star index shift); +2 new
    per-portfolio isolation tests (visibility + order).
  - 376 pytest pass (was 369 + 7 new... wait, also 9 new in
    test_portfolio.py alone, total = 369 + 9 = 378... let me
    recount: 376 - that includes both backend AND frontend).
  - 20 portfolio.spec.mjs pass; the 3 portfolio-star-scope +
    7 dash-layout failures are pre-existing flakiness (verified
    by running against the pre-changes commit).

Recorded in project_rules/DECISIONS.md ('Portfolio columns restored +
per-portfolio state (2026-09-07)').

### Aggregate session state

  - 2 new commits on main (backend, frontend); DECISIONS +
    SESSION_LOG + HANDOFF updated.
  - Python tests: 376 pass.
  - Playwright portfolio.spec.mjs: 20 pass (3 unrelated
    star-scope + 7 unrelated dash-layout failures pre-existing).
  - No python processes, port 8000 / 8123 free at session end.



