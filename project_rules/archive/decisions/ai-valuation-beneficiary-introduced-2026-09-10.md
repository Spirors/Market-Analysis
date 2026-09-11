# AI Valuation (Beneficiary) introduced (2026-09-10)

Full text of the entry from `project_rules/DECISIONS.md`.

---

## Status

Confirmed + shipped. 4 feature commits: `339624e` (Task 1,
`app/ai_valuation.py` + config + conftest), `6d67bef` (Tasks 3+4
combined, frontend BREADTH hover + AI gauge meta cell + tooltip
addendum), `8c2a932` (Task 5, mock payload backward-compat), `4c2fd90`
(Task 2, `ai_sentiment.compute_ai_sentiment` valuation arg + service
wire). Plan:
`docs/superpowers/plans/2026-09-10-ai-valuation-breadth-hover.md`.

## Core problem

The 2026-09-06 earnings-watchlist section removal deleted
`compute_valuation_flag` (along with the entire `EARNINGS_CACHE_PATH`
artifact that fed it). The removal was correct per the "if a section's
only reason for existing is the data the section itself fetches, removing
the section means removing the data fetch too" rule, but it left two
user-visible loose ends:

1. The Risk Divergence tooltip still claimed "9 cross-asset signals"
   when the engine had been dropped to 8 strategies in the same commit
   (`RISK_SIGNAL_TOTAL` was already `8` at line 224 of `app/config.py`).
   The "7/8" badge the user sees in the card header comes from
   `len(signals) / RISK_SIGNAL_TOTAL` where the AI theme strategy
   (`_signal_ai_theme`, `app/risk.py:433-474`) only contributes a
   fragility flag — not a named signal — so the user-visible signal
   count is 7, not 8. (User caught this mid-session: I'd initially
   moved the tooltip from 9 → 8; they corrected to 7.)
2. The AI capex-cycle gauge's `Valuation` cell
   (`static/js/cards.js:209`) read `ai.valuation?.note || "—"`; with
   no `valuation` key in the backend response, the cell rendered a
   permanent dashline.

The valuation signal itself was worth bringing back — high beneficiary
cohort forward PE is a meaningful "AI trade is crowded" reading — but
the new shape needed to be cheaper, more focused, and scoped to the
cohorts that actually matter for the AI trade.

## Decision

Re-introduce valuation as a per-ticker forward-PE cache (12h on-disk
TTL, yfinance `Ticker.info["forwardPE"]`), scoped to **beneficiary
cohorts only** (everything in `config.AI_CAPEX_COHORTS` except
`"Capex Spenders"`). Median PE across the universe feeds the AI gauge
as a `+25` score shift when `median_pe >= 30` (the threshold). The
gauge cell label reads `Valuation (Beneficiary)` so the cohort scope
is explicit in the UI. The BREADTH - AI Proxies chart shows the
per-ticker PE + cohort median + the stretch annotation on hover
(`fwd PE ×××× (cohort median ××××; stretch ≥ 30×)`).

## Rationale

### Why beneficiary cohorts only (not all AI cohorts)

`config.AI_CAPEX_COHORTS` mixes the **demand side** (Capex Spenders:
MSFT/GOOGL/AMZN/META/ORCL — hyperscalers driving the AI capex) with
the **supply-side beneficiaries** (Compute/Memory/Photonics/Equipment/
Neocloud/Power/Applications). Spenders' PEs reflect the broader market
and trade at ~25-35×; beneficiaries can run 30-60× during AI euphoria.
Including spenders dilutes the median and weakens the signal of "is
the AI supply-side trade crowded?" — which is what the gauge is
asking. Excluding them keeps the signal sharp.

The user explicitly chose beneficiary-only during the brainstorming
phase, overriding the default "include all cohorts" proposal.

### Why stretch-only (no cheap-side signal)

Original `compute_valuation_flag` had a -15 penalty when median PE
≥ 30× — i.e. treated stretch as "cycle under pressure". The user's
mental model is the opposite: "PE >= 30× is more so euphoric than
broken. Balance is best and neither extreme is health for the market."
High PE = euphoria (push score UP toward `Euphoric / fragility setup`,
+60 to +100 zone); cheap PE ignored. Stretch-only matches that
framing without overreaching.

### Why on-disk cache (not just in-memory lru_cache)

The original earnings cache used `EARNINGS_CACHE_PATH` (an on-disk JSON
file with TTL). In-memory lru_cache (the pattern `enrich_portfolios`
uses) is faster for repeated refreshes within 5 min but cold-cache
first load is ~60-90 s and restarts wipe the cache. For a 30-day
snapshot of "is the AI trade crowded", a 12h TTL on disk is the right
freshness/durability balance — and mirrors the deleted cache pattern
so a future session that greps for `EARNINGS_CACHE_PATH` finds a
successor with similar semantics.

### Why `+25` (not +15 or +30)

The AI gauge verdict cutoffs are at ±60/±20
(`config.AI_SENTIMENT_VERDICT_CUTOFFS`). A borderline Balanced verdict
(score near 0) becomes `+25` after a stretch shift → Healthy expansion
(+20 to +60 zone). `+25` is large enough to nudge borderline readings
into a different verdict without overshadowing the existing ROC and
spread weights (×2.0 and ×1.5 respectively); it's small enough that
false-positive stretch signals don't single-handedly flip the verdict.
`+15` would barely move borderline scores; `+30` would risk
over-claiming based on stretch alone.

## Mistakes to avoid (anti-patterns future sessions will hit)

### 1. Don't forget to patch `ai_valuation._CACHE_PATH` in `tests/conftest.py`

Module-level path constants bind at import time. `ai_valuation.py:24`
binds `_CACHE_PATH = config.AI_VALUATION_CACHE_PATH` once when the
module loads; patching `config.AI_VALUATION_CACHE_PATH` later does
**not** update the bound name on the importing module. The autouse
fixture in `tests/conftest.py` patches `ai_valuation._CACHE_PATH`
directly to `tmp_path / "ai_valuation.json"`. Same anti-pattern that
motivated the test-isolation Core rule in 2026-09-08.

### 2. Don't return raw `forwardPE` < 0 / None / NaN / 0 values

`forwardPE < 0` means losses; `forwardPE is None` means yfinance
returned sparse info; `forwardPE == 0` is the "no estimate" sentinel.
All four are unusable for valuation — the median would skew or crash
on `statistics.median` if NaN slips through. `app/ai_valuation.py:30-39`
`_is_valid_pe()` filters them.

### 3. Don't fail the whole batch on one rate-limited ticker

yfinance rate-limits at ~2000 calls/hour. A 65-ticker fetch is ~32 s
on a cold cache; one `429 Too Many Requests` response should not abort
the batch. `fetch_beneficiary_pe()` (`app/ai_valuation.py:117-130`)
swallows network exceptions per-ticker and saves the partial map. The
median will reflect whatever subset succeeded.

### 4. Don't move the verdict classification BEFORE the valuation shift

`compute_ai_sentiment()` re-classifies the verdict in lines that must
run **after** the `+25` shift is applied — otherwise a Balanced score
+ stretch would still read "Balanced" instead of "Healthy expansion".
This is the kind of bug that doesn't show up in unit tests because
each test isolates the score or the verdict, not the integration.
The test `test_compute_ai_sentiment_valuation_stretched_adds_score_shift`
(`tests/test_ai_sentiment.py`) is the integration guard.

### 5. Don't add `?v=…` to one side of a cross-module import

Same anti-pattern class as the 2026-09-10
`events.js → cards.js` split-state incident
(see `archive/decisions/news-cross-module-import-versioning-2026-09-10.md`).
If a future iteration pins a cache-bust on one of the cards.js
imports, the `tooltipCallbacks` option (Task 3) and the
`Valuation (Beneficiary)` meta cell (Task 4) would silently disappear
from one of the duplicated module instances.

### 6. Don't call the cell just "Valuation" — the cohort scope must be visible in the UI

The user explicitly asked for the label to read `Valuation (Beneficiary)`.
A bare `Valuation` would invite a future reader to wonder whether
spenders are included (they're not) or whether the median covers all
70+ AI tickers (it doesn't). Explicit > implicit.

## Verification

### Backend

```bash
python -m pytest tests/test_ai_valuation.py -q
# 18 passed

python -m pytest tests/test_ai_sentiment.py -q
# 18 passed (14 existing + 4 new)

python -m pytest tests/ -k "not thirteenf and not service_coverage and not portfolio_cache_sync" -q
# 481 passed (was 459, net +22)
```

### Frontend

```bash
cd tests/frontend && npx playwright test
# 122 passed, 5 failed (the 5 failures are pre-existing baseline:
# bottleneck-move, dash-layout-survives-reload ×2, global-refresh,
# portfolio-star-scope star persistence — none caused by this change)
```

### Manual smoke (when the user clicks Refresh)

1. First refresh after the cache TTL expires: ~60-90 s (the yfinance
   walk fetches 65 Ticker.info calls). Subsequent refreshes within 12h:
   instant (reads the on-disk cache).
2. AI gauge meta row shows `Valuation (Beneficiary) 42.1× · stretched`
   when the median is at/above 30×; `· ok` when below.
3. Hovering an AI ticker bar in the BREADTH chart shows
   `TICKER — fwd PE ×××× (cohort median ××××; stretch ≥ 30×)`.
4. A previously-Balanced gauge score shifts by exactly +25 when the
   beneficiary median crosses 30×.

## File reference index

### Backend
- `app/ai_valuation.py` (new, 181 lines) — cache + fetch + valuation summary
- `app/config.py:228-235` — `AI_VALUATION_STRETCH_PE`, `AI_VALUATION_SCORE_SHIFT`, `AI_VALUATION_CACHE_TTL_HOURS`, `AI_VALUATION_CACHE_PATH`
- `app/ai_sentiment.py` — `compute_ai_sentiment(snapshot, events, valuation=None)` signature, +25 shift, verdict re-classification
- `app/service.py` — `_recompute_ai_sentiment` wires `ai_valuation.fetch_beneficiary_pe()` → `compute_valuation()` → `compute_ai_sentiment(valuation=...)`
- `app/indicators.py` — adds `breadth_ai["cohort_median_pe"]` for the BREADTH hover

### Frontend
- `static/js/cards.js` — `_renderBarChart` gains `tooltipCallbacks` option; `renderBreadthAIChart` registers custom PE tooltip; `renderAISentiment` re-introduces `Valuation (Beneficiary)` meta cell; `CARD_TOOLTIPS["ai-sentiment"]` gains one-line addendum

### Tests
- `tests/test_ai_valuation.py` (new, 196 lines) — 18 tests
- `tests/test_ai_sentiment.py` (+65 lines) — 4 new integration tests
- `tests/conftest.py` (+2 lines) — autouse `_isolate_data_files` patches `ai_valuation._CACHE_PATH`
- `tests/frontend/breadth-ai-valuation.spec.mjs` (new, 191 lines) — 7 tests
- `tests/frontend/mock-dashboard.mjs` (+38 lines) — `installMockDashboard` helper + default `ai_sentiment.valuation` shape
- 7 existing frontend spec files (`portfolio.spec.mjs`, `bottleneck-move.spec.mjs`, `bottleneck-rename.spec.mjs`, `portfolio-holdings-reorder.spec.mjs`, `portfolio-header-collapse.spec.mjs`, `portfolio-move.spec.mjs`, `portfolio-star-scope.spec.mjs`) — mechanical `valuation` field addition

### Plan + session docs
- `docs/superpowers/plans/2026-09-10-ai-valuation-breadth-hover.md` (new, 1152 lines)
- `project_rules/SESSION_LOG.md` — new dated entry
- `project_rules/HANDOFF.md` — timestamp + state updated
