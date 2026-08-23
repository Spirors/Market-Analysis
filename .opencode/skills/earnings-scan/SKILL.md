---
name: earnings-scan
description: Produce the macro earnings picture (upcoming earnings calendar for the tracked mega-cap universe). Use when asked about earnings dates, earnings concentration, or the earnings calendar in this repo.
---

# Earnings Scan

Track the upcoming earnings calendar for the mega-cap universe (see
`EARNINGS_UNIVERSE` in `app/config.py`) through a macro lens: concentration of
earnings growth, not single-stock calls.

## Where the code lives

- `app/earnings.py` — `earnings_calendar()` (cached) and
  `earnings_force_refresh()`.

## Notes

- Uses yfinance `Ticker.calendar` for the next earnings date, falling back to
  the last known earnings date from `get_earnings_dates(limit=1)`.
- Result is cached to `data/cache/earnings.json`; call `earnings_force_refresh()`
  to invalidate.
- Add a ticker to `EARNINGS_UNIVERSE` in `app/config.py` to extend coverage.
