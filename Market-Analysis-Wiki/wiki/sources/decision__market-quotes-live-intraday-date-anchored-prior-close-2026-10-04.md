---
type: source
title: "Market quotes are the latest live intraday print, with a date-anchored settled prior close"
status: evergreen
created: 2026-10-04
updated: 2026-10-04
source_kind: decision
tags:
  - source
  - decision
  - market-quotes
  - data-freshness
---

# Market quotes are the latest live intraday print, with a date-anchored settled prior close

## The bug

A user reported that a portfolio holding's **last price** — and by extension its
**daily %** — looked a full session old during US market hours, then appeared
"caught up" over the weekend. Root cause: the shared quote provider
`app/market.py::_quote_snapshot` built both numbers from **settled daily bars**
(`yf.download(symbols, period="7d", interval="1d")`), so during a live session the
last bar was the *previous* session's close. Over a weekend there is no newer bar,
so it coincidentally looked correct.

`_quote_snapshot` is not portfolio-specific: it also feeds the dashboard
indices/rates/commodities cards (`build_market_snapshot`) and the futures card
(`build_futures_snapshot`). Every quote card carried the same latent staleness.

## Decision: one shared live provider, app-wide

Fix the shared provider, not a portfolio-only path. A portfolio-only lane would
have created a third freshness rule and guaranteed that a symbol shown in two
views (e.g. an `XLK`/`GC=F`/`BTC-USD` holding vs. a dashboard card) disagreed
during a session — a direct violation of the cross-view-consistency rule. The
dashboard had the identical bug; it was just less visible because those cards have
no per-row "as of".

## The prior-close rule (the correctness core)

**`price`** is the latest intraday print from one bulk **5m / 5d** download across
all asset classes (equities, indices, `^VIX`/`^TNX`, futures `ES=F`/`GC=F`,
crypto, foreign). **`prior_close`** is the most recent settled daily close
**strictly before the intraday bar's session date** — never wall-clock "now".

Date-anchoring is what makes one rule correct in every state:

- **Live session:** live print vs last settled close → today's move.
- **After close:** the session's final print vs the prior day → unchanged.
- **Pre-open / weekend:** the last session's print vs the day before → that
  session's move, stable.
- **24/7 crypto:** the daily bar already includes today, and the anchor picks the
  prior calendar day.

A **stale-intraday guard** discards an intraday print older than a settled daily
bar we already hold, so a lagging intraday feed can never beat a settled close.

`fast_info` is a fallback only. Its `previous_close` disagrees with the settled
daily prior close (AAPL: 330.80 vs 330.32), so it is never used as the anchor for
a symbol that produced an intraday print — that would make the daily % inconsistent
with the same daily series that drives `pct_7d` / `pct_30d` / `high_52w`.

## Caching

`get_quotes` became a **per-symbol** cache (`quote_<sym>`, `LIVE_QUOTE_TTL = 120s`)
rather than a per-symbol-set hash key, so the dashboard, futures and portfolios
read the *same* cached value for an overlapping symbol instead of fetching
independent copies that could drift. Null/partial-null entries are never cached
(unchanged honesty rule). The explicit **Refresh** path calls
`enrich_portfolios(..., ttl=0)` to preserve the "fresh on every click" contract.

## Consequences

- One provider, one prior-close rule, one freshness window — all quote views agree.
- Unavailable data degrades to `—`; nothing is fabricated.
- `fast_info` is no longer treated as broken; the old code comment was outdated
  for yfinance 1.6.0.
- Evidence: live probe returned AAPL 333.79 vs prior 330.32 (+1.05%) with a
  graceful rate-limit fallback on one symbol; 132 relevant backend tests and the
  774-test backend suite pass. Commit `68f1538`.

## Rejected

- **Portfolio-only live prices** — leaves the dashboard stale and lets two views
  disagree; rejected above.
- **`fast_info` per symbol for every fetch** — one HTTP per symbol per refresh is
  the latency profile the codebase's earlier P0 fix removed; the bulk 5m/5d pull
  stays one request.
- **Using `fast_info.previous_close` as the daily anchor** — self-inflicted
  cross-source inconsistency with the daily series.
