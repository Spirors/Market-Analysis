# Portfolio add/delete latency fix (2026-09-07)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Portfolio add/delete latency fix (2026-09-07)

**Status:** confirmed + shipped (commit pending; red-green verified
against `audit-2026-09-07.md` P0 root cause). Audit doc reproduced
the finding end-to-end (min/avg/max over 5 trials with mocked yfinance
on N=10 holdings: 23.1 / 29.9 / 54.2 ms — confirming the ~3 s user-
visible lag is entirely from yfinance HTTP calls, not Python
overhead).

**Bug repro:** Open the dashboard, click `+ Add holding`, enter a
ticker. On a cold cache (or within ~5 min of a cold load with >5
holdings), the new row takes ~3 seconds to appear. Same for `+ Add
cash`, portfolio `✕` delete, rename, cash row edit/delete.

**Three independent contributors** (any one would cause visible lag;
the audit confirmed all three were active simultaneously):

1. **`_patch_dashboard_cache` re-enriched all symbols on a 1-symbol
   change** (`app/portfolio.py:47`). Pre-fix the patch path called
   `enrich_portfolios(state)` inline, which does 1 bulk
   `yf.download(7d)` + 1 bulk `yf.download(260d)` + N × `Ticker.info`
   + N × `Ticker.calendar`. For ~10 holdings this is ~22 yfinance
   HTTP calls (~3 s cold, ~2.4 s warm).
2. **`_quote_snapshot` had no disk cache** for the portfolio path.
   `market.get_quotes(symbols)` (`app/market.py:133`) exists with a
   30-min `QUOTE_TTL` disk cache, but `holdings_add` /
   `holdings_edit` (`app/api.py:216,235`) called `_quote_snapshot`
   directly so every mutation paid a fresh yfinance fetch.
3. **Frontend `await refresh()` after every mutation.** Six bespoke
   button handlers in `static/js/portfolio.js` (rename blur, delete
   portfolio, `+Add holding`, `+Add cash`, cash row edit, cash row
   delete) called `await refresh()` after the API call. `refresh()`
   is `GET /api/portfolios` → `enrich_portfolios(state)` → another
   ~3 s of yfinance calls. Every mutation paid the enrichment cost
   at least twice — once server-side in the POST response, once
   client-side in the follow-up GET. The tickerTable row-level
   callbacks (`addRow`/`removeRow`/`editCell` at lines 340-360)
   already proved the optimistic-update pattern works; the bespoke
   handlers just hadn't been brought in line.

**Fix shape:**

1. **`_patch_dashboard_cache` is now structural-only.** Replaced
   `cached["portfolios"] = enrich_portfolios(state).get("portfolios",
   {})` with `cached["portfolios"] = state.get("portfolios", {})`.
   The state's holdings already carry `symbol` / `shares` /
   `total_cost` (and any user-edited values). Live prices
   (`last_price`, `pct_daily`, `sector`, etc.) for newly-added
   holdings stay `None` until the next full enrichment pass; the
   UI already renders `None` as "—". Per the "Earnings cache-miss
   path must not trigger a full universe rebuild" decision
   (`80d0fef`), a cache-patching helper must NOT fall through to a
   full rebuild — either patch minimally or invalidate and return.
   This is the "patch minimally" path.
2. **`market.get_quotes` is now symbol-aware.** Cache key changed
   from the shared `"quotes"` to `f"quotes_{sha1(sorted_symbols)
   [:16]}"`. Pre-fix the shared key silently lost symbols when
   different callers asked for different sets — latent bug masked
   because the only caller that mattered (`build_market_snapshot`)
   always asks for the full universe. `build_market_snapshot` is
   unaffected (deterministic cache key for a deterministic symbol
   set). `build_futures_snapshot` uses its own `"quotes_futures"`
   key and is unaffected.
3. **`holdings_add` / `holdings_edit` route through `get_quotes`.**
   One-line change at each call site. Cold cache for a never-seen
   symbol still pays one yfinance call; warm cache is instant.
4. **Six bespoke handlers use optimistic local state.** After the
   API call, push / filter the closure-captured `p.holdings` in
   place, then re-render only the affected holdings table
   (`renderHoldingsTable(pfSlot, p)`) plus the card-level totals
   (`renderGrandHeader()`). No follow-up `refresh()`. The rename
   blur's catch path still calls `refresh()` for error recovery
   (the server's name is the source of truth — pull it on failure).
   The bespoke handlers' `slot` discovery uses the same DOM
   selector (`document.querySelector(\`.pf-pf[data-pid="…"] .pf-pf-body\`)`)
   that `renderBody()` builds; the targeted re-render preserves the
   surrounding card header (so column state, expand/collapse, and
   the per-portfolio tickerTable instance all stay intact).

**Red-green verification:**

| Test | Pre-fix | Post-fix |
|---|---|---|
| `test_post_holdings_add_completes_under_500ms_with_15_holdings` | FAIL (~1.8 s) | PASS (~130 ms) |
| `test_post_holdings_add_does_not_call_enrich_portfolios` | FAIL (`get_histories_bulk`=1, `_info_cached`=16) | PASS (zero enrichment calls) |
| `portfolio-optimistic-ui.spec.mjs` (`+Add holding`) | n/a (new) | PASS (no follow-up GET) |
| `portfolio-optimistic-ui.spec.mjs` (`+Add cash`) | n/a (new) | PASS (no follow-up GET) |

Verified by `git checkout HEAD -- app/{market,portfolio,api}.py
static/js/portfolio.js` then running the new tests (both FAIL),
then restoring the fix files (both PASS). Full Python suite:
378 passed. Playwright suite: 72 passed, 3 failed (all 3 pre-existing
in `dash-layout-survives-reload` and `portfolio-star-scope`,
exercise `layout.js` / `watchColors.js` paths I did not touch).

**Rules established by this fix:**

- **Cache-patching helpers must NOT fall through to a full rebuild
  on cache miss.** When patching a cache after a mutation, either
  patch the structural state minimally and let the next full
  enrichment pass fill in derived fields, or invalidate and return.
  A full rebuild should only run from explicit user action (Refresh
  button) or the scheduled task — never from an additive
  mutation's side-effect. This is the same shape as the earlier
  `80d0fef` decision (earnings cache-miss path); consolidate in
  future helpers.
- **Cache keys for batch data must include the symbol set.** Any
  helper that returns a dict keyed by symbol and caches it must
  hash the requested symbols into the cache key. A shared cache
  key across callers with different symbol sets silently loses
  symbols. `market.get_quotes` is now the reference shape; future
  batch helpers should follow the same `f"<name>_{sym_hash}"` key
  pattern.
- **Bespoke mutation handlers should use optimistic local state,
  not full refresh.** When a UI handler triggers a single-row
  mutation, the response already carries the new state; push /
  filter the closure-captured state in place, re-render only the
  affected sub-tree, and call the card-level aggregate re-render
  (`renderGrandHeader()` for portfolio; equivalent for other
  sections). A full `refresh()` call here is a 3-second tax for
  data the user just sent. The tickerTable row-level callbacks
  (lines 340-360) are the reference pattern.
- **`_quote_snapshot` no-disk-cache is intentional for
  `build_market_snapshot`** (the market section wants fresh quotes
  on every refresh). It's only a bug in the portfolio enrichment
  path where it's used as enrichment for already-cached data. Do
  not "fix" `_quote_snapshot` globally — route the portfolio
  path through `market.get_quotes` instead. (This note mirrors
  the audit's "Findings explicitly cleared" entry for `_quote_snapshot`.)

**Regression coverage:**

- `tests/test_portfolio.py` — 2 new tests (N=15 holdings + 100 ms
  injected latency; call-count spies on the 3 enrichment call
  families).
- `tests/frontend/portfolio-optimistic-ui.spec.mjs` — 2 new tests
  intercepting POST + counting follow-up GETs.
- `tests/test_market_cache.py` — 2 existing tests updated for the
  new hash-based cache key (`glob("quotes_*.json")` instead of
  literal `"quotes.json"`).


