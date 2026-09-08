# validate_symbol must distinguish "yfinance unavailable" from "no profile" (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## validate_symbol must distinguish "yfinance unavailable" from "no profile" (2026-09-06)

**Status:** confirmed + fixed (commit `a2c793a`).

Pre-fix `app/earnings.py:68-89` `validate_symbol()` made two
sequential yfinance calls (`_yf_info` and `_validate_by_history`
fallback). Both wrappers caught exceptions silently with
`except Exception: return {}` / `return []`. On rate-limit (very
common when validating several tickers in quick succession), both
calls failed and the user saw "invalid symbol" when the real problem
was "yfinance unavailable."

**Two-axis fix:**
1. Distinguish network errors from genuinely-invalid symbols in the
   `reason` field so the frontend can show a meaningful error.
2. Don't make two sequential yfinance calls when one suffices — the
   first call's sparse-info check (`_CONFIRMATION_FIELDS`:
   exchange/currency/quoteType/regularMarketPrice) accepts symbols
   even without `longName`, so the history fallback is rarely needed.
   Reducing 2 calls per validation to ~1 reduces rate-limit pressure.

**Plus a retry-with-1s-backoff** on transient network errors
(`requests.exceptions` family, `yfinance.YFRateLimitError`), and a
60s TTL `lru_cache` to absorb bursts (e.g. validating 5 tickers in a
row calls yfinance 5× in 30 seconds today — cached, it's 5 in 60+
seconds).

**Rule for any future yfinance wrapper:** Network errors must be
distinguishable from "yfinance returned empty." `_yf_info` now
returns `(dict, error_str)` so callers can branch on `error_str`.
The next wrapper that needs a "transient, retry once" path should
use `_yf_info_with_retry()` as the template.

**LSP note:** The 12 new mocked tests in `tests/test_earnings.py`
intentionally call `validate_symbol(None)` to verify the empty-input
path. The function signature `def validate_symbol(sym: str)` types
`sym` as `str` but the runtime handles `None` via `(sym or "").strip()`
— the test exercises that defensive behavior. LSP flags this as a
type mismatch; the runtime is correct. A future cleanup could
broaden the signature to `sym: str | None`, but it's a cosmetic
change, not a correctness fix.

