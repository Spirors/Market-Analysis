# AI Capex Cycle Gauge — Design Spec

## Goal
Add a new dashboard card below the existing risk banner that measures the **health of the AI capex cycle** through the lens of *Capex Spenders vs. Beneficiaries*. It answers: "Is the AI trade healthy, extended, or cracking?"

The existing risk banner remains untouched; it continues to measure macro structure/fragility. This card adds a **theme-specific narrative layer** that the current engine lacks.

## Design principles
- Use only data already pulled (yfinance/Stooq histories, news events, earnings valuation cache).
- Never fabricate data; valuation uses fetched forward PE/PEG, and missing values are shown as `—`.
- The gauge is interpretive, not predictive. It surfaces tension/divergence, not a price target.

## Cohorts

| Cohort | Role | Tickers |
|---|---|---|
| Capex Spenders | Demand side — hyperscalers/big tech deploying AI capex | AMZN, MSFT, GOOGL, META, ORCL, CRM, NOW |
| Compute / Accelerators | Silicon layer | NVDA, AMD, AVGO, TSM, QCOM, ARM, CRDO, ALAB |
| Memory | HBM/DRAM/storage | MU, WDC, STX |
| Photonics / Optics | 800G/1.6T interconnects | LITE, COHR, AAOI |
| Equipment / Packaging | Foundry + semi cap equipment | AMAT, LRCX, KLAC, TSM |
| Neocloud / Infrastructure | Server/networking/deployed capacity | DELL, SMCI, ANET, NBIS |
| Power / Data Center | Power & real estate constraint | VST, CEG, NRG, XLU, PLD, DLR, EQIX |
| Applications | End-user monetization | PLTR, CRM, NOW, SHOP, ADBE |

Tickers overlap by design (e.g., TSM appears in compute and equipment; CRM/PLTR/NOW appear in spenders and applications). Each cohort keeps its own list so the code and UI are readable.

## Inputs & scoring

For each cohort:
1. **3-month ROC** of an equal-weighted cohort index built from available histories.
2. **Breadth** — % of cohort tickers with price above 50-day MA.
3. **Cohort tone** — bullish/neutral/bearish based on ROC and breadth together.

Cross-cohort:
4. **Spenders vs. Beneficiaries spread** — equal-weight ROC of all beneficiary cohorts minus equal-weight ROC of Capex Spenders. Positive = beneficiaries leading; negative = spenders leading while suppliers lag.
5. **AI news flow** — net signed score from events whose title/summary contains AI/semiconductor keywords, using the event's explicit `direction` tag (bullish/bearish/neutral) weighted by `impact`.
6. **Valuation** — median forward PE and forward PEG across all cohort tickers that have earnings data. Flagged "stretched" only when the median forward PE is in the top historical quartile of observed values in the local earnings cache; otherwise shown as a level with no flag.

## Gauge output

A single needle from **−100 (cycle broken)** to **+100 (euphoric/extended)** with zones:
- −100 to −60: Cycle under pressure
- −60 to −20: Cooling / divergence
- −20 to +20: Balanced
- +20 to +60: Healthy expansion
- +60 to +100: Euphoric / fragility setup

Plus:
- Verdict sentence, e.g. "Healthy expansion: capex spenders and beneficiaries both participating."
- Component table: cohort, 3m ROC, breadth, tone.
- "What would flip it" list.
- `as_of` timestamp matching the snapshot.

## Backend changes

1. **config.py**
   - Add `AI_CAPEX_COHORTS: dict[str, list[str]]` mapping cohort names to ticker lists.
   - Add `AI_NEWS_KEYWORDS: list[str]` for identifying AI-relevant events by title/summary text.

2. **market.py**
   - Include all `AI_CAPEX_COHORTS` tickers in the bulk history fetch.
   - Store AI cohort histories in `snapshot["histories"]["extra"]` so `ai_sentiment.py` can access them.
   - Use a SHA1 hash of the sorted symbol list for the bulk-history cache key to avoid Windows long-filename errors.

3. **app/ai_sentiment.py** (new)
   - `cohort_roc(histories, tickers) -> Optional[float]`
   - `cohort_breadth(histories, tickers, n=50) -> Optional[float]`
   - `cohort_tone(roc, breadth) -> str`
   - `compute_ai_news_sentiment(events) -> dict`
   - `compute_valuation_flag(earnings_data) -> dict`
   - `compute_ai_sentiment(snapshot, events, earnings) -> dict` — main entry point.

4. **service.py**
   - Import `ai_sentiment`.
   - Attach `ai_sentiment` key to the dashboard dict in `refresh_market()` and `refresh_all()`.

5. **api.py**
   - No new route needed; dashboard payload carries the new key.

## Frontend changes

1. **static/index.html**
   - Add `<section id="aiSentimentCard" class="card wide">` below the risk banner and above the main grid.

2. **static/app.js**
   - `renderAISentiment(ai)` — gauge needle, verdict, component table, flip conditions.
   - Add gauge CSS to `static/style.css` (horizontal track + marker).
   - Include `ai_sentiment` in `renderSection()`.

## Error handling
- If no histories are available, return `error` string and the frontend shows `—`.
- Missing individual tickers are ignored for cohort aggregates; cohorts with fewer than 2 available tickers are marked `—`.
- Valuation stretched flag defaults to `false` when insufficient data.

## Testing
- Run `python run.py --refresh` and load `http://127.0.0.1:8000`.
- Verify the new card renders, the needle position is plausible, and no values are fabricated.
- Check that adding/removing earnings tickers still works and the dashboard refresh still completes.

## Out of scope (noted for later)
- Fragility flags expansion.
- Macro regime plain-English simplification.
- Indices/rates/commodities display tweaks.
