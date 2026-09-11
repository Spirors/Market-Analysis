# Portfolio enrichment always runs (no cooldown skip) — 2026-09-11

## Problem

The 2026-09-11 morning session added a per-section refresh cooldown
(`PORTFOLIO_REFRESH_COOLDOWN_S = 900`, mapped via
`REFRESH_SECTION_COOLDOWNS["portfolios"]`) so that the portfolio section
would skip `enrich_portfolios` when the cached `vintage["portfolios"]` was
within 15 min. The user's intent: save cycles on the per-symbol
`Ticker.info` calls inside `enrich_portfolios`.

The implementation gated the ENTIRE `enrich_portfolios` call on the
cooldown, not just the `info` portion:

```python
if _in_cooldown("portfolios"):
    result["portfolios"] = (cached.get("portfolios") or {})
    ...
else:
    result["portfolios"] = _portfolio.enrich_portfolios(_portfolio.load_portfolios()).get("portfolios", {})
    ...
```

But the cache is patched structurally via `_patch_dashboard_cache`
(`app/portfolio.py:25-68`) — it carries the user's `symbol / shares /
total_cost` (and any other fields set by mutations) but NOT the
live-price enrichment (`last_price / pct_daily / pct_7d / pct_30d /
high_52w / sector / marketcap / forward_pe / forward_peg /
next_earnings`). When the cooldown skipped `enrich_portfolios`, the
frontend received the cached payload with all live-price fields at
`None` and rendered them as "—".

User symptom: "Cache data got wiped when refreshed and now I have to
wait till cooldown is over." (Clarification: portfolios + holdings
still visible, but the live-price columns all showed "—".)

## Decision

Remove the portfolio cooldown skip. Always run `enrich_portfolios` for
the portfolios section. Keep the cooldown for the `breadth_ai` /
`indicators` section.

Concretely, in `app/service.py:refresh_market`:

```python
# Always enrich portfolios (live prices on every refresh). The
# per-section cooldown only applies to breadth_ai (see below).
result["portfolios"] = _portfolio.enrich_portfolios(_portfolio.load_portfolios()).get("portfolios", {})
_stamp("portfolios")
```

The `cooldown_skip` field stays in the payload (and still carries
`"breadth_ai"` when the indicators cooldown is active). The
`"portfolio"` entry will just never be appended.

## Rationale

- **`enrich_portfolios` cost is mostly cached anyway.**
  `get_info_snapshot` is `lru_cache`-backed with a 5-min TTL
  (`_INFO_CACHE_BUCKET_S = 300`, `app/portfolio.py:344`). Within a
  15-min cooldown window, the second call hits the cache; only the
  first call (within the first 5 min) triggers a fresh fetch. The
  bulk `quote_snapshot` + `histories_bulk` are single HTTP calls to
  yfinance — comparable to the cost of `_enrich` recomputing the rest
  of the dashboard.
- **Within a 15-min window, the "savings" was at most 1 saved HTTP
  call.** Not worth blanking prices for the duration of the cooldown.
- **The dashboard's "As of" footer already shows the timestamp**, so
  the user can still tell when the data was last refreshed. The
  `cooldown_skip` badge for portfolio is now never set — the badge
  just won't render for portfolio. The breadth_ai badge still works
  because the indicators computation genuinely benefits from the
  cooldown (cohort histories are expensive).
- **The cooldown config (`PORTFOLIO_REFRESH_COOLDOWN_S`,
  `REFRESH_SECTION_COOLDOWNS["portfolios"]`) is left dormant** rather
  than deleted. The dashboard still consumes the config (so external
  readers / future sessions can see the history); the only consumer
  of the skip behaviour was the `refresh_market` block that this
  commit removed.

## What was kept

- `app/config.py` — `PORTFOLIO_REFRESH_COOLDOWN_S` and the
  `"portfolios"` key in `REFRESH_SECTION_COOLDOWNS` are untouched.
- `static/js/cards.js:CARD_TOOLTIPS["portfolio"]` — the cooldown
  sentence was REMOVED from the tooltip (no longer applicable). The
  rest of the tooltip text (▲/▼ reorder persists, etc.) is preserved.
- `static/js/cards.js:applyCooldownBadge` and the `COOLDOWN_SECTION_MAP`
  — the badge logic still works; it just never gets called for
  portfolio now (because `cooldown_skip` never contains `"portfolio"`).
  Kept dormant.
- `static/style.css:.cov-cooldown` — the badge styling stays in case
  future sections re-enable the cooldown.

## What was changed

- `app/service.py:refresh_market` — removed the
  `_in_cooldown("portfolios")` branch; unconditional
  `enrich_portfolios` call.
- `tests/test_service_cooldown.py` — deleted
  `test_refresh_market_respects_portfolio_cooldown`; added
  `test_refresh_market_always_enriches_portfolios_regardless_of_cooldown`.
- `tests/frontend/refresh-cooldown.spec.mjs` — deleted the
  "Portfolio card shows cached Xm badge" test; added
  "Portfolio prices are not blank after refresh" test.
- `static/js/cards.js:CARD_TOOLTIPS["portfolio"]` — removed the
  cooldown sentence from the tooltip text.

## Mistakes to avoid

- **Do NOT delete `PORTFOLIO_REFRESH_COOLDOWN_S` from `app/config.py`.**
  The config is dormant but still present — external readers
  (e.g. /api/meta) might reference it. A clean removal would be a
  separate change.
- **Do NOT bring back the "skip the whole `enrich_portfolios`" pattern**
  with a different trigger (e.g. "skip if user hasn't looked at the
  card"). The cost of `enrich_portfolios` is dominated by
  `lru_cache`-backed calls; skipping the whole thing blanks prices.
  If you ever need to skip something, split `enrich_portfolios` into
  the price path (always run) and the info path (optional).
- **Do NOT add the cooldown sentence back to the card tooltip.** The
  portfolio card no longer has a cooldown; saying it does misleads
  the user.
- **Do NOT change `cooldown_skip` payload semantics.** The field
  still exists for `breadth_ai`. Adding `"portfolio"` back without
  actually skipping the enrichment would be a no-op that confuses
  future readers.

## Verification

- `python -m pytest tests/test_service_cooldown.py tests/test_portfolio.py
  tests/test_api_contract.py` → **104 passed** in 6.84s.
- `npx playwright test --config=tests/frontend/playwright.config.mjs
  tests/frontend/portfolio-holdings-reorder.spec.mjs
  tests/frontend/refresh-cooldown.spec.mjs` → **19 passed** in 7.1s.
- Manual: after this commit, clicking the global Refresh button always
  shows fresh live prices (last_price, pct_daily, etc.) in the
  Portfolio card, regardless of when the previous refresh was.
