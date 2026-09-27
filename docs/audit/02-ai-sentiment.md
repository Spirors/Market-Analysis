# Section 02 — AI Sentiment (capex-cycle gauge)

**Status:** `FIXED-PARTIAL` (deep audit 2026-09-27; 02-A..02-F fixed; 02-G/H/K
await decisions)
**Priority:** 7 of 9
**Last updated:** 2026-09-27

**Covers (raw parts):** `ai-sentiment` card (`static/index.html:44-51`,
`id="aiSentimentCard"`, `data-card="ai-sentiment"`), renderer `renderAISentiment`
(`static/js/cards.js:207-250`).
**Backend:** `app/ai_sentiment.py` (`compute_ai_sentiment`), `app/ai_valuation.py`,
serve-time recompute `app/service.py:_recompute_ai_sentiment` (`:393-438`), payload
via `/api/dashboard` → `ai_sentiment`.
**Evidence:** static + grep recon of the renderer, the vintage plumbing, the
producer, the cache-key path and the tests. No runtime probe needed.

---

## 1. Purpose

The AI capex-cycle gauge: a composite score from AI-tagged news, per-cohort
momentum and breadth, and a beneficiary-cohort forward-PE valuation overlay. It
renders a gauge + meta row + a cohort table + a "what would flip it" block.

## 2. Data path (verified)

```
data/events.json (ai_only, last NEWS_LOOKBACK_DAYS=30) ─┐
cohort histories (service.py:414-417 cache key)        ─┼→ ai_sentiment.compute_ai_sentiment
ai_valuation (12h TTL cache)                           ─┘        │
                                                                  ▼
service.py:_recompute_ai_sentiment(events, as_of)   ← recomputed on EVERY serve (:336-338)
                                        │  snapshot = {"as_of": …, "histories": …}
                                        ▼
                     /api/dashboard → data.ai_sentiment
                                        │
                                        ▼
           cards.js:renderAISentiment  +  CARD_TOOLTIPS["ai-sentiment"] (:609-612)
```

Freshness plumbing (shared): `SECTION_CARDS` `ai_sentiment` → `CARD_VINTAGE_KEY`
(`cards.js:582`) → `applyVintageStamp` (`cards.js:731-754`) renders the card's
"As of … ET" note from `vintage.ai_sentiment`, stamped per refresh (`service.py:203`).

## 3. Findings

1. **`TOOLTIP` · P2 — 02-A · the gauge tooltip omitted point 5 (as-of). FIXED**
   (`a00edac`). *Why:* the one field answering "how current is this?" was missing
   from the most data-dependent card.

2. **`DATA` · P2 — 02-B · the served `ai_sentiment.as_of` was always null
   (cache ≠ wire). FIXED** (`80d9bd1`): the serve-time recompute now threads the
   cached dashboard's `as_of`; a cold cache still yields `null`, never a fabricated
   date. *Why:* a freshness field that is always null looks like data.

3. **`DATA` · P2 — 02-C · an unavailable valuation read as an affirmative "ok".
   FIXED** (`5820786`). The producer's missing valuation is
   `{"median_pe": null, "stretched": false, "note": ""}` — truthy — so the renderer
   printed `Valuation (Beneficiary) — · ok`. The `· ok` / `· stretched` suffix now
   requires `median_pe != null`. *Why:* converts "unavailable" into "healthy",
   violating the unavailable→`—` rule.

4. **`DATA` · P2 — 02-D · a missing score fabricated a midpoint needle. FIXED**
   (`5820786`). `pct = Math.max(-100, Math.min(100, ai.score ?? 0))` drew the marker
   at the exact centre while the meta row said `Score —`. The marker is now omitted
   when `ai.score == null`. *Why:* a chart that invents a neutral reading.

5. **`ACCESSIBILITY` · P2 — 02-E · the decorative gauge was exposed to AT.
   FIXED** (`5820786`). `.ai-gauge-track` (marker + `← Broken/Balanced/Euphoric →`)
   exposed the value only via CSS `content: attr(data-pct)`; `aria-hidden="true"`
   now hides it, and the "Score N" meta text carries the accessible value. *Why:*
   generated content is not reliably announced.

6. **`TEST` · P2 — 02-F · the card's freshness stamp and null paths were untested.
   FIXED** (`5820786`). New `tests/frontend/ai-sentiment-null.spec.mjs` covers the
   `— · ok` case, the missing-score case, and the `.vintage-note` (added via a
   per-test `vintage.ai_sentiment` override — the shared fixture still omits it).
   *Why:* the 02-A/02-B plumbing had no frontend regression guard.

7. **`DATA` · P2 — 02-G · the gauge reads a different history cache than every
   other view (cross-view consistency). DECISION NEEDED.**
   `service.py:414-417` builds `HISTORY_CORE_SYMBOLS + ai_tickers` and calls the
   fetch-capable `market.get_histories_bulk(...)`, whereas `build_market_snapshot`
   (`market.py:323-324`), `bottleneck_read_cached` (`service.py:386-387`) and
   `api.py:470` all read `market.history_universe_symbols()` — whose docstring
   states it is the "one source of truth … a number shown in two views reads the
   same cached dataset". Consequence: the gauge's cohort ROC/breadth can come from
   a second, independently-expiring dataset vs the BREADTH — AI Proxies chart
   (`indicators.py:258-266`) and the risk engine. *Why:* the project's
   cross-view-consistency hard rule; same number, two views, possible disagreement.
   *Not fixed — aligning the symbol set could change displayed values; needs a
   decision.*

8. **`ARCHITECTURE` · P2 — 02-H · the recompute is on every serve with no guard.**
   `_enrich` calls `_recompute_ai_sentiment` with no `try/except`
   (`service.py:336-338`), so a throw there 500s the whole dashboard; and a
   valuation-cache expiry triggers a serial ~50-ticker `yf.Ticker(sym).info` walk
   inside the request (`ai_valuation.py:253-268`). *Why:* one optional card on the
   critical path of every payload. *Not fixed — changes error semantics; document.*

9. **`DESIGN` · P2 — 02-K · the gauge's axis and its verdict colour contradict.
   DECISION NEEDED.** The track gradients red→green left-to-right
   (`style.css:974`) with `← Broken … Euphoric →`, yet `Euphoric` is coloured
   `tone-bear` red and `Healthy expansion` green (`cards.js:216`). The right end
   reads "good" green while its verdict reads red. *Why:* two opposite colour
   encodings on one element. Visual redesign is flagged as `DESIGN`, never
   implemented in the audit (README §1).

10. **`UX` · P3 — 02-L · partial payloads bypass the `—` policy.** An empty `{}`
    payload renders score 0 / empty verdict (neutral-looking); empty `cohorts` or
    `flip_conditions` render header-only/empty blocks with no state message
    (contrast the regime grid's explicit `—` fallback). Corroborated: no
    `ai.error` path is reachable from the producer. *Document.*

11. **`DATA` · P3 — 02-M · valuation freshness is dropped upstream.**
    `ai_valuation.py` returns `fetched_at` + `cache_ttl_hours`, but
    `ai_sentiment.py:129-133` copies only `median_pe`/`stretched`/`note`, so the
    card cannot state the PE age while the tooltip asserts the 12h TTL.
    *DECISION: surface it or keep the prose.*

12. **`ARCHITECTURE` · P3 — 02-I · disk cache ≠ wire for the valuation shift.**
    The refresh-time compute (`service.py:200-203`) omits `valuation=`, so
    `data/dashboard.json` holds a score without the +25 shift that the serve path
    (`:436-437`) adds. Any direct reader of the file sees a different score.
    *Document.*

13. **`ARCHITECTURE` · P3 — 02-O · the tooltip hard-codes backend constants**
    (`2.0 / 1.5 / 0.3 / 25 / 30× / ±60,±20` in `cards.js:610`) while the producer
    reads `config.AI_SENTIMENT_*` / `AI_SENTIMENT_VERDICT_CUTOFFS`
    (`config.py:241-250`) / `NEWS_LOOKBACK_DAYS` (`:332`). In sync today; drift is
    silent. *Why:* a second source of truth for backend numbers.

14. **`TOOLTIP` · P3 — 02-Q · ② interpretation is partial.** The tooltip lists
    verdict names and cutoffs but not which direction is healthy; "Balanced" (axis)
    vs `"Balanced / mixed"` (payload) vs "Broken" (no payload counterpart).
    *Document.*

15. **`UX` · P3 — 02-N · naming drift.** Three names for one card (`h2` "AI capex
    cycle gauge", on-card "Net AI capex cycle health", aria-label "About the
    ai-sentiment card"); cohort table header "Read" renders `c.note` while other
    cards label the same thing "Note"; the coverage badge says "n of m **sources**
    live" but counts cohorts with a computable 3m ROC (`service.py:113-116`).
    *Document.*

16. **`ARCHITECTURE` · P3 — 02-P · stale comments describe a removed behaviour.**
    `cards.js:204-206` claims `events.js` re-renders the gauge from a tag-update
    payload (removed); `events.js:503-504` keeps an orphaned header above the
    contradictory no-refresh rule. *Document.*

17. **`TEST` · P2 — 02-R · no coverage for verdict cutoffs, `flip_conditions`,
    `spread_pct`, cohort shape, `news.note`/`event_count`, or the
    history-cache-key alignment (02-G).** *Document.*

## 4. Fixes completed

- [x] **FIX-02-A** `TOOLTIP` P2 — tooltip now points at the card's "As of … ET"
      stamp. Commit `a00edac`.
- [x] **FIX-02-B** `DATA` P2 — the serve-time recompute threads the cached
      dashboard's `as_of`; cold cache → `null`, never a fabricated date. Commit
      `80d9bd1`.
- [x] **FIX-02-C** `DATA` P2 — the `· ok` / `· stretched` suffix requires
      `median_pe != null`; unavailable valuation shows `—` alone. Commit `5820786`.
- [x] **FIX-02-D** `DATA` P2 — the gauge marker is omitted when `score == null`
      (no fabricated midpoint). Commit `5820786`.
- [x] **FIX-02-E** `ACCESSIBILITY` P2 — `.ai-gauge-track` is `aria-hidden="true"`.
      Commit `5820786`.
- [x] **FIX-02-F** `TEST` P2 — `ai-sentiment-null.spec.mjs` guards the `— · ok`
      case, the missing-score case, and the freshness stamp. Commit `5820786`.

## 5. Tracked TODOs / open decisions

- [ ] **DECISION 02-G** — should the gauge read the same `history_universe_symbols()`
      dataset as every other view (cross-view consistency), or keep its own fetch
      set? Changing it could move displayed ROC/breadth.
- [ ] **DECISION 02-H** — wrap `_recompute_ai_sentiment` so one optional card cannot
      500 the dashboard (and/or move the PE walk off the request path)?
- [ ] **DECISION 02-K** (`DESIGN`) — reconcile the gauge axis gradient with the
      verdict colours (Euphoric = fragile).
- [ ] **DECISION 02-M** (`DATA`) — surface the valuation cache age (`fetched_at`)
      or keep the 12h-TTL prose.
- [ ] `UX` P3 — `{}`/empty-payload state messages; 02-L.
- [ ] `ARCHITECTURE` P3 — de-duplicate the tooltip's hard-coded constants; 02-O.
- [ ] `ARCHITECTURE` P3 — refresh-time compute omits `valuation=`; 02-I.
- [ ] `ARCHITECTURE` P3 — remove the stale comments; 02-P.
- [ ] `UX` P3 — naming drift (card names, "Read" header, coverage "sources"); 02-N.
- [ ] `TOOLTIP` P3 — add the healthy/fragile direction to ②; 02-Q.
- [ ] `TEST` P2 — cutoffs/flip/spread/news + cache-key alignment; 02-R.

## 6. Coverage notes

- Backend: `tests/test_ai_sentiment.py` (news leg, `_cohort_tone`, valuation
  shift), `tests/test_service_coverage.py:336-416` (ai_only/limit/since + 02-B
  served `as_of`), `tests/test_api_contract.py:500-528` (tags endpoint does not
  recompute). **No `as_of` assertion in `test_ai_sentiment.py` itself.**
- Frontend: `breadth-ai-valuation.spec.mjs:80-207` (valuation + tooltip),
  `news-grouping.spec.mjs:305-334` (no auto-refresh on tag edits),
  `global-refresh.spec.mjs:25-31` (one `.card-info`), and the new
  `ai-sentiment-null.spec.mjs`.
- Not covered: renderer null/partial paths (now partly covered), verdict cutoffs,
  `flip_conditions`, `spread_pct`, cohort shape, the 02-G cache-key alignment.
- Suite state is recorded in `README.md` §10.
