# 2026-09-07 — Earnings date column fix (user-reported follow-up to P0)

Full text of the entry from `project_rules/SESSION_LOG.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds the full text for the
latest entry and a pointer for older entries).

---

## 2026-09-07 -- Earnings date column fix (user-reported follow-up to P0)

After the P0 perf fix shipped, the user reported that the portfolio
table's earnings date column was rendering as "--" for every holding.
Root cause was a yfinance shape compatibility bug in
`_extract_next_earnings` (`app/portfolio.py:340`) — pre-fix code
checked `isinstance(ed, datetime)` (i.e. `datetime.datetime`) but
yfinance 1.6.0 returns `datetime.date` for `Earnings Date`, so the
check fell through to `return None`. Verified live:
`yf.Ticker('NVDA').calendar` returns
`{'Earnings Date': [datetime.date(2026, 11, 17)], ...}`.

Fix: broaden the check from `datetime` to `date` and call
`.isoformat()` directly (`datetime.datetime` is a subclass of
`datetime.date`, so the broader check covers both historical and
current yfinance versions). Added `date` to the existing
`from datetime import date, datetime, timezone` import.

Regression coverage: 6 new tests in `tests/test_portfolio.py`:
- `test_extract_next_earnings_handles_datetime_date` (yfinance 1.6.0
  shape — was the bug)
- `test_extract_next_earnings_handles_datetime_datetime` (older
  yfinance — forward compat)
- `test_extract_next_earnings_handles_multiple_dates` (yfinance
  sometimes returns [confirmed, tentative] — use first)
- `test_extract_next_earnings_handles_string_fallback` (some yfinance
  proxies return strings)
- `test_extract_next_earnings_returns_none_for_missing_or_empty`
  (missing key, empty list, None value — all return None, no
  fabrication)
- `test_extract_next_earnings_returns_none_for_non_dict` (defensive:
  non-dict payloads don't raise)

Red-green verified: pre-fix the 2 `datetime.date` tests FAIL
(`assert None == '2026-11-17'`); the other 4 PASS as controls.
Post-fix all 6 PASS.

User-facing caveat: because the P0 fix made `_patch_dashboard_cache`
structural-only, any holding added since the P0 fix has
`next_earnings=None` in the cached `data/dashboard.json`. The fix
above makes the *next* enrichment populate the column correctly, but
existing cached holdings need a one-time manual Refresh (forces full
rebuild via `service.refresh_all`) to surface their earnings dates.
Logged to the user via the `HANDOFF.md` Current state section.

Verification:

- `python -m pytest tests/ --ignore=tests/test_thirteenf.py
  --ignore=tests/test_service_coverage.py`: 384 passed (27.96 s),
  up from 378 in the previous session — the +6 are the new earnings
  tests.
- `app/changelog.log_change("fix", ...)` logged at the time of the
  fix.

Updated:

- `project_rules/HANDOFF.md`: "Last updated" line + "Current state"
  paragraph updated to lead with both P0 and earnings date fixes;
  next 3 actions unchanged (still P4/P6/P3 audit follow-ups).
- `project_rules/DECISIONS.md`: new entry "Next earnings date
  extraction — yfinance 1.6.0 returns datetime.date, not
  datetime.datetime (2026-09-07)" with root cause + fix + rule
  (prefer base class for yfinance shape compat).
- `project_rules/SESSION_LOG.md`: this entry.

Working tree at session end: `data/events.json` (scheduler-owned,
ignore). One commit lands the work.

