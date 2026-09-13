# Next earnings date extraction — yfinance 1.6.0 returns datetime.date, not datetime.datetime (2026-09-07)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Next earnings date extraction — yfinance 1.6.0 returns datetime.date, not datetime.datetime (2026-09-07)

**Status:** confirmed + shipped (red-green verified). User-reported
follow-up to the P0 fix: portfolio `next_earnings` column rendered as
"—" for every holding.

**Root cause:** `app/portfolio.py:_extract_next_earnings(cal)` extracted
the earnings date from a `yf.Ticker.calendar` payload. The pre-fix
implementation was:

```python
ed = cal.get("Earnings Date")
if isinstance(ed, (list, tuple)) and ed:
    ed = ed[0]
if isinstance(ed, datetime):           # <-- BUG
    return ed.date().isoformat()
if isinstance(ed, str):
    return ed[:10]
return None
```

The check `isinstance(ed, datetime)` matches `datetime.datetime` but
**not** `datetime.date`. yfinance 1.6.0 returns `datetime.date`
instances for `Earnings Date` (verified live: `{'Earnings Date':
[datetime.date(2026, 11, 17)], ...}`), so the check fell through to
`return None`. Older yfinance versions returned `datetime.datetime`,
which the pre-fix check did handle — but `datetime.datetime` is a
subclass of `datetime.date`, so checking `isinstance(ed, date)` covers
both shapes.

**Fix:** broaden the check from `datetime` to `date` and call
`.isoformat()` directly (both classes implement it). Use `[:10]` to
strip the time portion if a `datetime.datetime` slips through.

```python
if isinstance(ed, date):
    return ed.isoformat()[:10]
```

Plus add `date` to the existing `from datetime import date, datetime,
timezone` import.

**Red-green verification:** 6 new tests in `tests/test_portfolio.py`.
Pre-fix: `test_extract_next_earnings_handles_datetime_date` and
`test_extract_next_earnings_handles_multiple_dates` FAIL (both rely on
the `datetime.date` shape). The other 4 tests (datetime.datetime,
string fallback, missing key, non-dict) PASS as controls. Post-fix:
all 6 PASS. Full Python suite: 384 passed.

**User-facing caveat:** because the P0 fix made `_patch_dashboard_cache`
structural-only, any holding added since the P0 fix has
`next_earnings=None` in the cached `data/dashboard.json`. The fix
above makes the *next* enrichment populate the column correctly, but
existing cached holdings need a one-time manual Refresh (forces full
rebuild via `service.refresh_all`) to surface their earnings dates.

**Rule for future yfinance shape compat:** when an extraction helper
inspects a yfinance field, check the **base class** that covers both
historical and current yfinance versions. `datetime.datetime` is the
specific class, but `datetime.date` is the base — prefer the base
when both have the methods you need (here: `.isoformat()`). The
broader check is forward-compatible with future yfinance shape
changes as long as the new type still subclasses `date`.

**Regression coverage:** `tests/test_portfolio.py` — 6 new tests
covering `datetime.date` (yfinance 1.6.0), `datetime.datetime`
(older yfinance), multi-element list (confirmed + tentative), string
fallback (some yfinance proxies), missing/empty/None values, and
non-dict payloads (defensive).


