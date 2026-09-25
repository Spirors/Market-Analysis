---
type: source
title: "One cached value per number — the reader owns the cross-view invariant"
status: evergreen
created: 2026-09-25
updated: 2026-09-25
source_kind: decision
tags:
  - source
  - decision
  - data-integrity
---

# One cached value per number — the reader owns the cross-view invariant

Cross-view consistency is a project hard rule: a number that appears in two views
must agree. Four defects found while building the topic-driven Bottleneck section
all had the same shape — **one displayed value computed from two
independently-expiring sources** — and in every case the fix that held moved the
guarantee out of the caller and into the code that owns the data.

## The instances

1. **Two PE sources, and a third about to be added.** `breadth_ai`'s
   `forward_pe` is *defined* as "whatever `ai_valuation`'s cache says", while
   `portfolio` reads `info["forwardPE"]` on its own 5-minute bucket. A
   section-local fetch would have made three. Resolved by extending
   `ai_valuation` additively: one cache document, one writer, one `.info` read
   per symbol populating both key sets. `per_ticker_metrics` carries arbitrary
   display tickers; `per_ticker_pe` stays **cohort-only**, because
   `compute_valuation` medians every numeric top-level entry and a display ticker
   landing there would contaminate the AI-gauge median and could flip
   `stretched`.
2. **A frozen copy of a live value.** `load_ticker_metrics()` served the stored
   metrics PE, which drifts the moment the cohort set refreshes. The **reader**
   now overlays the live cohort PE, so a card built from it cannot disagree with
   `breadth_ai`.
3. **A render-path fetch on a second cache.** `bottleneck_read` fell back to a
   per-symbol history download when the snapshot lacked a symbol — a different
   cache key and a different download path from the refresh — so the dashboard
   and the render could report different momentum, and a cold cache fetched on
   render. The fallback is **deleted**: the engine reads the snapshot only, and
   both views address one bulk key built by `market.history_universe_symbols()`.
4. **An indicator reading someone else's payload.** The section's header
   coverage badge counted the dashboard snapshot while the body rendered from the
   topics payload, so the badge could disagree with the body it annotates.

## The rule

> A value shown in more than one view must be read from one place, at the moment
> it is shown.

Corollaries, each earned by an instance above:

- **A guard that depends on the caller remembering something is not a
  guarantee.** A truthy empty-`list` marker was introduced to suppress the
  history fetch; it worked, and it was rejected, because the network fallback was
  still live for the next caller.
- **Never persist a copy of a value another view computes.** Persist the inputs
  or the provenance, and read the value live.
- **A sibling key set needs a single writer.** `save_cache` was a
  last-writer-wins full-file rewrite and `fetch_beneficiary_pe` runs on every
  serve, so a second key set would have been deleted every TTL. Writes are now
  one read-modify-write function that preserves the key set it is not updating.
- **A stale-but-same-definition indicator still misleads.** The badge never
  showed a wrong number; it showed *nothing* in the one state it existed to
  explain.
- **A null and a number are not a disagreement.** A dash versus a value is
  tolerable; two different numbers for one ticker is the bug. This is also why a
  loss-maker's signed `forward_pe` is shown on a card even though the cohort
  median must exclude non-positive values.

## Verified by

`tests/test_ai_valuation.py` (reader overlay, sibling-key survival, signed PE
stored but excluded from the cohort median), `tests/test_bottleneck.py` (purity
proven with an *empty* snapshot, two-view momentum equality),
`tests/test_api_bottleneck.py` (no fetch on a cold cache),
`tests/test_market_cache.py` (reader and writer share one key), and
`tests/frontend/bottleneck.spec.mjs` (the badge follows its own payload, with the
mocked dashboard deliberately disagreeing).
