# Portfolio columns restored + per-portfolio state (2026-09-07)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Portfolio columns restored + per-portfolio state (2026-09-07)

**Status:** confirmed + shipped (commits `75b7c70` + `a8b60d2`).

**Request:** bring back the 8 columns the Earnings watchlist removal
had stripped from the Portfolio table (7-day %, 30-day %, Earnings
date, Marketcap, Forward PE, Forward PEG, 52W high, Sector) AND make
column settings independent per portfolio.

**Data sources (per "never fabricate" rule):**

| Column | Source |
|---|---|
| pct_7d, pct_30d, high_52w | `market.get_histories_bulk(symbols, days=260)` — one bulk yfinance download |
| sector, marketcap, forward_pe, forward_peg | `Ticker.info` per symbol |
| next_earnings | `Ticker.calendar` per symbol |

Per-symbol fetches cached via `functools.lru_cache(maxsize=128)` keyed
by `(symbol_upper, time_bucket)` where `bucket = int(time.time() // 300)`
(5 minutes). Cold-cache cost is one HTTP per unique symbol; warm-cache
is instant. Single `Ticker` instance shared between info + calendar to
avoid the 2-fetch pattern the old `app.earnings` had.

**Per-portfolio column state:** previous design used a single shared
`pfVisible.portfolio` / `pfOrder.portfolio` localStorage key — hiding
7-day % in Fidelity Cash also hid it in Roth IRA. New design namespaces
by `portfolio.<pid>`:

- `pfVisible.portfolio.<pid>` / `pfOrder.portfolio.<pid>`
- `pfSort.portfolio.<pid>`
- backend `column_order['portfolio.<pid>']` /
  `column_visibility['portfolio.<pid>']`

The bare `portfolio` key remains the default that new portfolios
inherit; existing portfolios continue to work. Two portfolios can show
different columns; hiding/showing one column in Portfolio A never
affects Portfolio B.

**`tickerTable.js` section validation** accepts the `portfolio.*`
prefix in addition to canonical `"portfolio"`. Any non-matching section
throws immediately (per the project's "shared-component persistence key"
rule — hardcoding or defaulting silently merges state across every
caller).

**Columns dropdown lives inside each expanded portfolio** now
(`controlsMode: 'columnsOnly'`). The header-level Columns dropdown is
gone — no single "active" portfolio anymore. Portfolio's bespoke
`+Add holding` / `+Add cash` buttons stay in the body alongside the
new dropdown.

**User clarification:** "all 8 visible by default" so new portfolios
show all the data immediately; user hides what they don't want per
portfolio. Default visibility set in
`app/portfolio.py:DEFAULT_COLUMN_VISIBILITY`.

**Pre-existing column order preserved:** the user listed the restored
columns in the order 7-day %, 30-day %, Earnings date, Marketcap,
Forward PE, Forward PEG, 52W high, Sector — that's the order they
appear after `pct_daily` (the 8 base columns first, then 8 restored
in user's listed order).

**Trade-off:** initial dashboard load is slower on a cold cache
because `enrich_portfolios` now does up to N+1 HTTP calls (one bulk
history + one `Ticker.info` per unique symbol). With ~10 holdings
this adds ~10-15s on first load; the 5-min cache amortizes within
the window. Next step if UX becomes a problem: defer per-symbol
info fetch behind an async `/api/portfolios/fundamentals/{pid}`
endpoint that fires only on portfolio expand.

**Regression coverage:**

- `tests/test_portfolio.py` — 9 new tests (enrich history derivation,
  enrich fundamentals, cache hit, per-portfolio PUT round-trip,
  per-portfolio 404 on unknown pid, default column set includes all 16).
- `tests/frontend/portfolio.spec.mjs` — 3 existing column tests updated
  for the new dropdown location + `_star` prepending index shift; +2
  new tests (per-portfolio visibility isolation, per-portfolio order
  isolation) — both FAIL on the pre-refactor shared-key code.

**Pre-existing test failures (unrelated):** the `dash-layout-*` and
`portfolio-star-scope*` Playwright specs were failing before this
change (confirmed against the pre-changes commit). They exercise
unrelated reload + star-scope paths and were not touched by this
refactor.


