# AI gauge lookback window = 30 days (2026-09-09)

## Context

The user reported the AI gauge card's tooltip (ℹ icon next to "Net AI capex
cycle health" h2) was missing the news lookback window. The gauge had
been silently reading events from the last 60 days
(`config.NEWS_LOOKBACK_DAYS = 60`), but the tooltip only said "Reads
AI-tagged events from data/events.json" — no window, no weights, no
verdict thresholds. The user also confirmed they wanted the window to be
30 days (one month), not 60.

## Decision

Three connected changes, shipped together:

### 1. `static/js/cards.js` `CARD_TOOLTIPS["ai-sentiment"]`

The previous text was a single sentence that named the gauge's inputs
without any quantitative guidance. The new text spells out:

- The lookback window: "Reads AI-tagged events from the last 30 days
  (NEWS_LOOKBACK_DAYS) of data/events.json".
- The composite-score formula: "avg cohort 3m ROC × 2.0 + (beneficiaries
  − spenders) ROC × 1.5 + AI news score × 0.3, capped at ±100".
- The verdict thresholds: "Euphoric / Healthy expansion / Balanced /
  Cooling / Cycle under pressure at ±60 / ±20 / ±60 thresholds
  (AI_SENTIMENT_VERDICT_CUTOFFS)".
- The const names (`NEWS_LOOKBACK_DAYS`, `AI_SENTIMENT_VERDICT_CUTOFFS`)
  so a future reader can grep for them.

The `deps` pill list updated to "news events (last 30 days)" so the
header tag matches the new window.

### 2. `app/config.py:343` — `NEWS_LOOKBACK_DAYS = 30`

The comment was rewritten to match. The value change ripples through:

- `app/service.py:_recompute_ai_sentiment` (the gauge's actual filter,
  via `datetime.now(timezone.utc) - timedelta(days=NEWS_LOOKBACK_DAYS)`)
  — drops events older than 30 days from the gauge's news leg.
- `app/ai_sentiment.py:compute_ai_sentiment` — reads the gauge-side
  payload that was already filtered by `service.py`, so no direct change
  needed.
- `app/analysis.py:_events_tone` — same delta filter, smaller window.
  Docstring "≈ two months" → "≈ one month".
- `app/analysis.py:_WEIGHTS` — dict key `events_last_60d` →
  `events_last_30d` (was misleading after the value change).
- `app/analysis.py:_build_inputs` — `inputs_used["events_last_60d"]` →
  `inputs_used["events_last_30d"]`. The bullet text "Event flow (last N
  days)" auto-adapts via the f-string.
- Module-docstring table ("events tone (last 60 days)") → "last 30 days".
- `tests/test_analysis_golden.py` — 2 test cases updated to assert on
  `events_last_30d` and to use a 15-day-old event instead of 30-day-old
  (still well inside the new window).
- `tests/test_service_coverage.py` — comment refresh ("60-day cutoff"
  → "30-day cutoff"; assertion is parameterized on
  `cfg.NEWS_LOOKBACK_DAYS` so the value itself auto-adapts).

### 3. Re-classified 21 RSS events in the last 30 days

Per the news-filter skill, the RSS upsert path always recomputes
`category`/`actor`/`direction`/`region` from current text on every
ingest. The new heuristic from commit `d4a41a2` was therefore already
correct for any RSS event ingested after that commit landed — but
events ingested *before* the commit (and still in the 30-day window)
were stale. The user asked for the new heuristic to be applied to
the last month of news.

Wrote a one-shot script (`retag.py`):

- Reads `data/events.json`, filters to the last `NEWS_LOOKBACK_DAYS`.
- For each event, re-runs `news.analyze(title, summary, source)`.
- Compares old vs new `category`/`actor`/`direction`/`region` and the
  numeric `importance`/`finance_relevance`/`composite_importance`.
- **RSS events** (MarketWatch, BBC Business, Wikipedia RSS — anything
  without a `seed://` link): apply in place. Update `updated_at`.
- **Seed events** (link starts with `seed://`): per the news-filter
  skill rule that seed events are hand-curated and bypass the
  heuristic, the proposed changes are printed but NOT auto-applied.

**Result:** 21 RSS events re-tagged. Spotlight changes:

| Title (truncated) | Field | Old → New |
| --- | --- | --- |
| Oil's surge back above $100 fuels fresh inflation fears | direction | bullish → bearish |
| " | importance | 13.5 → 14.5 |
| Salesforce's stock rockets 20% | direction | bearish → bullish |
| US borrowing costs hit fresh highs over inflation fears | direction | neutral → bearish |
| Investors worried about rising bond yields | direction | neutral → bullish |
| With Warsh running the Fed ... bond investors worried | direction | neutral → bearish |
| Kevin Warsh ... bond market that ... | direction | neutral → bearish |
| HPE ... AI server boom | importance | 6.5 → 7.5 |
| AI chip stocks ... Micron and others | composite | 8.28 → 9.66 |
| Petrol prices rise 5p ... Iran war sends oil higher | direction | bearish → neutral |
| AI chip stocks were riding high. Here's why Micron and others are now ... | composite | 8.28 → 9.66 |

Plus 11 other reclassifications of inflation/concern/AI-headline
stories.

3 seed events (`Cargo vessel attacked in Strait of Hormuz`,
`Third ADNOC vessel attacked`, `UAE says two more ADNOC vessels attacked`)
would have lost `actor: government → None` and `direction: bearish → neutral`
under the heuristic (the seed titles don't carry enough macro/inflation
keywords for the new heuristic to fire). Reported but NOT applied —
the user can hand-edit them if desired, and the next refresh will not
clobber hand-curated seeds.

`data/events.json` was written to disk but **not committed** from this
interactive session — `RUNBOOK.md` §"Commit conventions" says the
`MarketAnalysis-EventsCommit` scheduled task owns `data/events.json`
(the next 17:00 run will pick up the diff).

## Verification

- Targeted suite: 151 passed in 31.81s.
- Spot-check after retag: oil headline `direction: bearish` (was
  `bullish` in the triggering bug report).
- AI-tagged events in last 30 days post-retag: 14, mix of bullish /
  neutral / bearish as expected from the underlying stories.

## Files touched

- `app/config.py` — `NEWS_LOOKBACK_DAYS = 30` + comment refresh.
- `app/analysis.py` — docstring "two months" → "one month";
  `events_last_60d` → `events_last_30d` (weight key + inputs_used
  dict); module docstring table updated.
- `static/js/cards.js` — `CARD_TOOLTIPS["ai-sentiment"]` text + deps.
- `tests/test_analysis_golden.py` — 2 test cases: dict key rename +
  30-day → 15-day event age.
- `tests/test_service_coverage.py` — comment refresh (assertion
  auto-adapts).
- `data/events.json` — 21 RSS events re-tagged in place (not
  committed).
- `data/logs/summary-2026-09-09.md` — changelog entry for the
  bulk-retag.

## Out of scope / future work

- The 30-day window now drops April–June events from the gauge's news
  leg. Anyone who relied on 60-day recall for chronic stories
  (e.g. tariff/election watch) will see them drop out. Watch for user
  feedback on whether 30 days is still the right choice.
- The "Trump says US will annex Strait of Hormuz" Wikipedia RSS event
  has `composite_importance: 0` (it slipped past the threshold on the
  first ingest and was never re-tagged until now). Its region also
  flipped to `us` (because the title carries "Trump" and the new
  heuristic's region-first-order matching picks `us` over
  `middle-east` when both could apply). Pre-existing data issue —
  not fixed here. Tracked separately.
- Seed events in the 30-day window (3 Hormuz stories) lost their
  `actor: government` tag under the heuristic (the heuristic's actor
  rule requires a `GOV_TERMS` hit, and the Hormuz headlines only
  mention ship names / UAE / Iran — none of which are in GOV_TERMS).
  Per the news-filter rule they stay hand-curated; the proposed
  changes are in the changelog if the user wants to apply them.