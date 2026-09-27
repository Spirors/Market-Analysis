# Section 02 — AI Sentiment (capex-cycle gauge)

**Status:** `FIXED-PARTIAL` (deep recon 2026-09-27; 02-A + 02-B fixed)
**Priority:** 7 of 9
**Last updated:** 2026-09-27

**Covers (raw parts):** `ai-sentiment` card (`index.html:37-44`), renderer
`renderAISentiment` (`static/js/cards.js`, around `:181-224`).
**Backend:** `app/ai_sentiment.py`, `app/ai_valuation.py`, serve-time recompute in
`app/service.py` (`_recompute_ai_sentiment`), payload via `/api/dashboard` →
`ai_sentiment`.
**Evidence:** static + grep recon of the renderer, the vintage plumbing, the
producer, and the tests. No runtime probe needed.

---

## 1. Purpose

The AI capex-cycle gauge: a composite score from AI-tagged news, per-cohort
momentum and breadth, and a beneficiary-cohort forward-PE valuation overlay. It
renders a gauge + meta row + a cohort table + a "what would flip it" block.

## 2. Data path (verified)

```
data/events.json (AI-tagged)  ─┐
cohort histories (cached)     ─┼→ app/ai_sentiment.py (composite, verdict)
ai_valuation (12h cache)      ─┘        │
                                        ▼
app/service.py:_recompute_ai_sentiment(events, as_of)   ← recomputed on EVERY serve
                                        │  snapshot = {"as_of": …, "histories": …}
                                        ▼
                     /api/dashboard → data.ai_sentiment
                                        │
                                        ▼
            cards.js:renderAISentiment  +  CARD_TOOLTIPS["ai-sentiment"]
```

Freshness plumbing (shared): `SECTION_CARDS` `ai_sentiment` → `CARD_VINTAGE_KEY`
→ `applyVintageStamp` renders the card's "As of … ET" note from
`vintage.ai_sentiment`, which `service.py` stamps per refresh.

## 3. Findings

1. **`TOOLTIP` · P2 — 02-A · the gauge tooltip omitted point 5 (as-of).**
   `CARD_TOOLTIPS["ai-sentiment"]` covered points 1–4 well (measure, verdict
   bands, causes, sources, even the 12h valuation-cache TTL) but never said where
   the card's freshness stamp lives — unlike the sibling `risk` and `regime`
   entries. *Why:* the one field that answers "how current is this?" was missing
   from the most data-dependent card.

2. **`DATA` · P2 — 02-B · the served `ai_sentiment.as_of` was always null
   (cache ≠ wire).** `_recompute_ai_sentiment` built its snapshot without
   `as_of` (`service.py`, around `:423`), while the producer already reads
   `snapshot.get("as_of")` (`ai_sentiment.py:160`) and the *cached* dashboard had
   a real value. So the served payload silently lost a field it computed — a
   cross-view inconsistency (cache vs wire) on the freshness axis. *Why:* the
   data-integrity rule; a freshness field that is always null is worse than
   absent, because it looks like data.

3. **`TEST` · P3 — the AI card's vintage stamp is untested.**
   `tests/frontend/mock-dashboard.mjs` has no `vintage.ai_sentiment` key, so the
   `.vintage-note` never renders under test; and no test pins the served
   `ai_sentiment.as_of`. *Why:* the plumbing that fixes 02-A/02-B has no
   regression guard on the frontend side.

4. **`DATA` · P3 — valuation freshness is dropped upstream.**
   `app/ai_valuation.py` returns `fetched_at` + `cache_ttl_hours`, but
   `ai_sentiment.py` copies only `median_pe`/`stretched`/`note`, so the
   valuation cache age is unreachable from the card. *Not fixed — the card
   tooltip states the 12h TTL in words instead.*

## 4. Fixes completed

- [x] **FIX-02-A** `TOOLTIP` P2 — the gauge tooltip now points at the card's
      "As of … ET" stamp, in the same voice as the `risk` entry. Commit `a00edac`.
- [x] **FIX-02-B** `DATA` P2 — the serve-time recompute now threads the cached
      dashboard's `as_of` (the same source `bottleneck_read_cached` uses), so the
      served field is non-null and equals the cache's value; a cold cache still
      yields `null`, never a fabricated date. New focused test. Commit `80d9bd1`.

## 5. Tracked TODOs

- [ ] `TEST` P3 — add `vintage.ai_sentiment` to the mock fixture and assert the
      card's `.vintage-note` renders (guards the 02-A/02-B plumbing).
- [ ] `DATA` P3 — decide whether the valuation cache age (`fetched_at`) should be
      surfaced on the card.

## 6. Verification notes

- Both fixes were static-verifiable; no runtime probe was needed.
- Suite state is recorded in `README.md` §10.
