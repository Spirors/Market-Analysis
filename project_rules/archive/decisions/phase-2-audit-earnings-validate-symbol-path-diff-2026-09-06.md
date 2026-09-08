# Phase 2 audit — earnings `validate_symbol` path diff (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Phase 2 audit — earnings `validate_symbol` path diff (2026-09-06)

**Status:** root cause confirmed; fix landed in the same commit
(per the SESSION_LOG of 2026-09-06).

**Bug repro:** entering "NVDA" into the Earnings Watchlist Add field
returns "invalid symbol."

**Path diff — earnings vs portfolio yfinance surfaces:** the two call
paths hit *different* yfinance endpoints. Portfolio enrichment uses the
bulk-download surface (`yf.download`, documented in `app/market.py:97-98`
as "reliable in yfinance 1.6.0"). Earnings validation used the per-symbol
info surface (`yf.Ticker.info`), which is rate-limited independently of
symbol validity by Yahoo.

```
Portfolio enrichment (works for NVDA, AAPL, …):
  GET /api/dashboard → service._enrich → enrich_portfolios
    → market._quote_snapshot(symbols)
      → yf.download(symbols, period="7d", group_by="column")   [BULK]
  (app/portfolio.py:284, 361; app/market.py:94-130)

Earnings validation (fails for NVDA when Yahoo rate-limits):
  POST /api/earnings/watchlist → earnings.add_ticker
    → earnings.validate_symbol
      → _validate_uncached
        → _yf_info_with_retry → _yf_info
          → yf.Ticker(sym).info                                [PER-SYMBOL]
        → fallback: market.get_history(sym, days=5)
          → yf.download(symbol, period="5d")                   [BULK]
  (app/earnings.py:106-131, 56-89)
```

The pre-fix `validate_symbol` (`a2c793a` predecessor) called *both*
`Ticker.info` AND history in sequence and silently swallowed exceptions
in both wrappers, so a rate-limit hit both surfaces and produced
`valid: False`.

**Reproduction (mocked yfinance, no network):** four scenarios, `yf.Ticker`
+ `yf.download` both mocked, cache cleared between scenarios:

| Scenario | Ticker.info | yf.download | CURRENT result |
|---|---|---|---|
| A (live happy) | full dict | works | `valid=True, name="NVIDIA Corporation", sector="Technology"` |
| B (rate-limit) | empty | works | `valid=True, name="NVDA", sector=None` |
| C (full outage) | empty | empty | **`valid=False, reason="no yfinance profile and no price history found for NVDA"`** (THE BUG) |
| D (info only) | works | empty | `valid=True, name="NVIDIA Corporation", sector="Technology"` |

Scenario C reproduces the bug; B/D explain why it's intermittent (one
surface still working lets the fallback rescue). C fires when *both*
are rate-limited.

**Why `a2c793a` didn't stick:** earlier fix added retry-with-1s-backoff
+ 60s LRU around `Ticker.info`, but kept `Ticker.info` as PRIMARY.
Retrying a fundamentally-flaky call just delays the user's verdict by
1s. The right shape of fix is to validate existence the same way
portfolio already does successfully — not add retry/error-handling
around a flaky call.

**Fix:** `_validate_uncached` now uses `market.get_history(sym, days=5)`
(bulk-download, same as portfolio) as PRIMARY. `Ticker.info` becomes
SECONDARY (no retry). Same verdicts in every scenario, but the common
rate-limit case (B) now succeeds without depending on the fallback
rescue, and the full-outage case (C) is still caught. Removed
`_yf_info_with_retry`; kept the `_yf_info` `(dict, error_str)` shape
so "yfinance unavailable" vs "symbol genuinely not found" still
surfaces to the user.

**Regression coverage:** new tests in `tests/test_earnings.py` mock
`market.get_history` + `yf.Ticker` independently — no network, no rate
limit dependency. All four scenarios + `add_ticker` + `add_holding`
paths.

---

