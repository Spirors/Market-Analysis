# Earnings cache-miss path must not trigger a full universe rebuild (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Earnings cache-miss path must not trigger a full universe rebuild (2026-09-06)

**Status:** confirmed + fixed (commit `80d0fef`).

Pre-fix `app/earnings.py:add_ticker` (lines 304-345) fell through to
`earnings_calendar()` (which fetches yfinance for EVERY ticker in the
universe, ~30-60 seconds) when `_cached_calendar()` returned None
(cache missing or beyond `EARNINGS_TTL`). The frontend's
`addEarningsSymbol` fetch at `static/js/api.js:199-203` has no
explicit timeout and just awaits — the user clicked Add, saw no
progress, hit F5, by then the rebuild completed and the ticker
appeared. The earlier `a2c793a` `validate_symbol` retry fix
couldn't help because validation succeeded; the hang was in the
post-validation cache-rebuild path.

This regression re-introduced the exact failure mode the earlier
"validate_symbol distinguishes network errors" decision
(`a2c793a`) was trying to prevent — a user-visible hang that masks
itself as a different bug (invalid symbol) when yfinance is slow.

**Fix:** When the cache is missing, build just the new ticker's
enriched row via `_enrich(sym, quotes)` and write a minimal cache
with just that ticker. `remove_ticker` similarly invalidates the
cache instead of rebuilding. The user's earnings watchlist is the
source of truth for what they care about; the full universe
rebuild is owned by the section's Refresh button + scheduled task.

**Rule for cache-patching helpers:** When patching a cache after a
mutation, don't fall through to a full rebuild if the cache is
missing. Either build the minimal affected state inline, or
invalidate and return what you have. A full rebuild should only
run from explicit user action (Refresh button) or the scheduled
task — never from an additive mutation's side-effect.

**Plus UX fix:** `static/js/tickerTable.js:402-411` `tryAdd` now
shows "Adding…" + disabled state on the Add button during the
request, so even if the request takes a few seconds the user gets
feedback. `finally` re-enables the button and resets the label.

