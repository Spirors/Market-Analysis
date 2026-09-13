# Earnings watchlist section removed (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Earnings watchlist section removed (2026-09-06)

**Status:** confirmed + removed.

**Scope chosen:** strip everything except `validate_symbol` (which
`portfolio.add_holding` still uses to reject invalid symbols). Rejected
"UI only" and "UI + keep backend enrichment" — both would have left a
thin backend wrapper for a section nobody used.

**What was removed:**

- `app/earnings.py` (530 lines) — `add_ticker`, `remove_ticker`,
  `earnings_calendar`, `earnings_force_refresh`, `_enrich`, `_ai_rec`,
  `_ticker_calendar`, `cached_payload`, `_has_usable_prices`, the
  watchlist/removed JSON helpers, and the `EARNINGS_CACHE_PATH`
  filesystem artifact.
- `app/validation.py` (NEW, ~155 lines) — extracted `validate_symbol`
  + its dependencies (`_yf_info`, `_validate_uncached`,
  `_validate_cached`, `_cache_bucket`, `_TICKER_RE`,
  `_CONFIRMATION_FIELDS`). This module is the small footprint that
  survives the removal.
- `app/api.py` — four endpoints gone (`GET /api/earnings`,
  `GET /api/earnings/validate`, `POST /api/earnings/watchlist`,
  `DELETE /api/earnings/watchlist`) plus the `with_earnings` query
  param on `GET /api/portfolios`.
- `app/portfolio.py` — `enrich_portfolios_with_earnings` and the
  `_EARNINGS_FIELDS` constant are gone. `add_holding` calls
  `validation.validate_symbol` directly.
- `app/config.py` — `EARNINGS_TTL`, `EARNINGS_UNIVERSE`,
  `VALUATION_STRETCH_PE`, `AI_SENTIMENT_VALUATION_PENALTY` are gone.
  `RISK_SIGNAL_TOTAL` adjusted from 9 to 8. `EARNINGS` as a
  `FINANCE_KEYWORDS` string stays (still a finance-relevance signal
  for news classification).
- `app/service.py` — `refresh_earnings`, the `earnings` payload field,
  the `earnings` coverage entry, and the earnings arg passed through
  `compute_risk` / `compute_ai_sentiment` are gone.
- `app/risk.py` — `_valuation_stretched` and `_signal_valuation` are
  gone. Risk engine no longer reads any earnings-derived data.
- `app/ai_sentiment.py` — `compute_valuation_flag` is gone. Forward-PE
  references in the synthesis pipeline are removed.
- `app/analysis.py` — `earnings_recs` signal gone from the weight
  table. `_WEIGHTS` is now 9 entries summing to 13 (was 10 / 14).
- `app/news.py` — `config.EARNINGS_UNIVERSE` dropped from the ticker
  set (mega-caps already covered by `AI_CAPEX_COHORTS`).
- Frontend (`static/index.html`, `static/js/earnings.js` deleted,
  cards.js, api.js, portfolio.js, tickerTable.js, watchColors.js,
  layout.js) — all earnings column defs, section rendering, API
  helpers, watchColors section, CARD_BAND entry removed.
- 8 earnings-derived columns stripped from the Portfolio table
  (next_earnings, pct_7d, high_52w, forward_pe, forward_peg,
  market_cap_fmt, sector, AI rec).

**Rule for future sections:** if a dashboard section's only reason for
existing is the data the section itself fetches, removing the section
means removing the data fetch too. Don't keep a thin backend wrapper
"just in case" — `validate_symbol` is the *right* kind of thin wrapper
to keep (it's used by another section); the rest of the earnings module
wasn't.

---

