# News heuristic expansion — noun-heavy bearish + AI capex coverage (2026-09-09)

## Context

The user noticed that a MarketWatch live-feed event ingested on 2026-09-09 was
tagged `direction: bullish` despite being unambiguously bearish:

> **Title:** "Oil's surge back above $100 fuels fresh inflation fears at a
> crucial time for interest rates"
>
> **Summary:** "Oil prices rose above $100 a barrel on Wednesday for the
> first time in seven weeks, reviving concerns about global energy supply
> disruptions and a fresh inflationary shock just as major central banks
> prepare to make key interest-rate decisions later this month."
>
> **URL:** `brent-crude-reaches-100-as-war-in-iran-intensifies-b73832e2`

The title's "surge" hit BULLISH_TERMS once; nothing in either title or
summary hit BEARISH_TERMS. The classifier computed `bull=1, bear=0` →
`bullish`. The actual story (war-driven oil shock, inflation fears, rate
decisions upcoming) is bearish for the inflation/rates picture.

## Root cause

`app/news.py:185-192 _direction()` is a bag-of-words count over the combined
title + summary text:

```python
def _direction(text: str) -> str:
    bull = _count_hits(text, BULLISH_TERMS)
    bear = _count_hits(text, BEARISH_TERMS)
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"
```

The keyword lists (`app/news.py:83-99`) were tuned for *verb*-heavy
headlines: misses, plunges, routs, tariffs, warnings. They missed the entire
*noun*-heavy class of bearish stories that just *describe* inflation,
disruption, shock, fear, concern. The headline's "surge" was a false
positive for the equity-direction interpretation, but the rest of the
story was bearish — and the classifier couldn't see it.

## Decision

Expand all five keyword lists in the news classifier to close the noun /
verb gap and the AI capex-cycle coverage gap. Add a regression test for the
exact headline + summary that triggered this report. De-duplicate the AI
keyword list (it was defined twice — once in `app/config.py:166`, once in
`app/store.py:94` — and the two copies could drift).

### BEARISH_TERMS additions (`app/news.py:90-`)

- Inflation lexicon: `inflation`, `inflationary`, `stagflation`
- Sentiment nouns: `fear`, `fears`, `concern`, `concerns`, `concerned`
- Supply-chain nouns: `disruption`, `disruptions`, `disrupted`
- Price/demand shock: `shock`, `shocks`, `shocked`
- Policy verbs: `taper`, `tapering`, `tapers`, `tighten`, `tightens`,
  `tightening`, `warn`, `warns`, `warned`
- Growth conditions: `slowdown`, `slowing`, `slows`, `weakens`, `weakening`,
  `weakness`, `strain`, `strains`, `strained`, `stagnant`, `stagnation`,
  `contagion`
- Analyst-action phrases: `guidance cut`, `estimates cut`

### BULLISH_TERMS additions

- Price-action verbs: `jump`, `jumps`, `jumped`, `climb`, `climbs`,
  `climbed`, `rise`, `rises`, `rose`, `rising`, `gain`, `gains`, `gained`,
  `advance`, `advances`, `advanced`
- Single-stock / sector catalysts: `approval`, `approves`, `approved`,
  `approve`, `deal`, `deals`, `partnership`, `partnerships`, `rebound`,
  `rebounds`, `rebounded`, `optimism`, `optimistic`, `breakthrough`,
  `breakthroughs`, `lift`, `lifts`, `lifted`
- Shareholder returns: `dividend hike`, `dividend increase`

### MACRO_TERMS additions

- Real rates / inflation expectations: `breakeven`, `breakevens`,
  `real yield`, `real yields`
- Swaps: `swap`, `swaps`
- Commodities beyond oil/energy: `gold`, `silver`, `crude`, `brent`, `wti`,
  `natural gas`, `commodity`, `commodities`
- FX / dollar: `dollar`, `dxy`, `greenback`, `currency`, `currencies`
- Central-bank umbrella: `central bank`, `central banks`
- Activity surveys: `ism`, `pmi`, `manufacturing pmi`, `services pmi`
- Consumption: `retail sales`, `consumer spending`, `consumer confidence`
- Labor: `wage`, `wages`, `labor market`
- Fiscal: `shutdown`, `government shutdown`
- Plumbing: `liquidity`, `balance sheet`
- Monetary policy: `quantitative easing`, `qe`

### MICRO_TERMS additions

- Forecasts: `forecast`, `forecasts`, `forecasted`
- Per-share metrics: `eps`, `ebitda`
- Margins / cash flow: `margin`, `margins`, `gross margin`, `free cash flow`,
  `fcf`
- Analyst coverage: `analyst`, `analysts`
- Corporate actions: `delisting`, `delisted`, `lawsuit`, `lawsuits`
- SEC filings: `10-k`, `10-q`, `8-k`

### AI_NEWS_KEYWORDS additions (`app/config.py:166-`)

- Umbrella: `ai`, `artificial intelligence`, `genai`, `generative ai`
- Frontier-model labs / families: `openai`, `anthropic`, `chatgpt`, `gpt`,
  `claude`, `gemini`, `llama`, `mistral`, `deepseek`, `llm`, `llms`
- Hardware vendors in the AI supply chain: `nvidia`, `amd`, `tsmc`, `intel`,
  `arm`, `asml`, `micron`, `hynix`, `western digital`, `sandisk`
- Big-tech AI exposure: `microsoft`, `google`, `alphabet`, `meta`, `amazon`
- Cloud / hyperscale providers: `aws`, `amazon web services`, `azure`,
  `gcp`, `oracle cloud`, plus the existing `datacenter`, `data center`,
  `hyperscaler`
- Compute substrate: existing list expanded to include `semiconductor`,
  `semiconductors`, `chip`, `chips`, `foundry`, `accelerator`, `gpu`,
  `compute`, `photonics`, `optic`, `optics`, `memory`, `hbm`, `dram`
- Memory/storage: `ssd`, `nand`, `nand flash`
- Specific accelerator products: `blackwell`, `hopper`, `h100`, `h200`,
  `b200`, `b100`, `mi300`, `mi400`, `rubin`, `grace`, `bluefield`
- Networking: `arista`, `cisco`, `palo alto networks`, `palo alto`
- Power / grid tailwind: `power demand`, `grid`, `nuclear`,
  `small modular reactor`, `smr`
- Training / inference concepts: `training`, `inference`, `neural network`,
  `neural networks`, `machine learning`, `deep learning`, `transformer`,
  `transformers`, `foundation model`, `foundation models`, `rag`,
  `retrieval augmented generation`, `fine tuning`, `fine-tuning`,
  `agentic`, `agents`, `copilot`

### De-duplication (`app/store.py:90-104`)

`store._AI_TAG_KEYWORDS` (lines 94-99 of the pre-change file) was an exact
duplicate of `config.AI_NEWS_KEYWORDS`. Removed the local copy; `_is_ai_text`
now references `config.AI_NEWS_KEYWORDS` directly. Single source of truth.

## Verification

- Smoke test on the triggering headline + summary: bull hits 2 (`surge`,
  `rose`), bear hits 6 (`inflation`, `fears`, `concerns`, `disruptions`,
  `inflationary`, `shock`). `analyze()` returns `direction: bearish`.
- Targeted suite (`tests/test_news_analyze.py` + `tests/test_ai_sentiment.py`
  + `tests/test_store.py`): **116 passed**.
- Full suite excluding `tests/test_portfolio_cache_sync.py` (pre-existing
  infrastructure hang, also reproduces on the git-stashed baseline):
  **439 passed, 1 warning in 122.79s**.
- `tests/test_portfolio_cache_sync.py` in isolation: 5 passed both before
  and after the change.

## Tests added

- `tests/test_news_analyze.py`:
  - `test_direction_bearish_inflation_fears_oil_headline` — exact
    regression for the triggering MarketWatch story.
  - `test_direction_bearish_recession_concerns`,
    `test_direction_bearish_shock_disruption`,
    `test_direction_bearish_taper_tightening` — noun / policy coverage.
  - `test_direction_bullish_approval`, `test_direction_bullish_rebound`,
    `test_direction_bullish_partnership` — new bullish coverage.
  - `test_macro_breakeven_real_yield`,
    `test_macro_central_banks_dollar_commodities`,
    `test_macro_surveys_labor_fiscal` — new macro coverage.
  - `test_micro_earnings_metrics_forecast` — new micro coverage.
- `tests/test_ai_sentiment.py`:
  - `test_ai_keyword_coverage_model_families` — OpenAI/Anthropic/Gemini/etc.
  - `test_ai_keyword_coverage_hardware_vendors` — Intel/ASML/Micron/etc.
  - `test_ai_keyword_coverage_cloud_hyperscale` — AWS/Azure/Oracle Cloud.
  - `test_ai_keyword_coverage_training_concepts` — training/inference/etc.
  - `test_ai_keyword_coverage_power_grid` — nuclear/SMR/grid.
  - `test_ai_keyword_coverage_omits_unrelated_finance` — non-AI headlines
    don't trip the filter.
  - `test_ai_sentiment_uses_model_family_keyword` — model-lab headlines
    count as AI events in the gauge.
- `tests/test_store.py`:
  - `test_ai_tag_uses_canonical_keyword_list` — store follows the config
    list (no frozen duplicate).
  - `test_ai_tag_uses_configured_keywords_for_insert` — end-to-end: a
    "OpenAI GPT-5 release drives datacenter capex" headline gets the tag.

## Out of scope / future work

- `app/validation.py` already powers `validate_symbol` for portfolio add.
  It's not part of the news classifier path. Not touched here.
- A negation-aware / asset-aware layer (e.g. "oil surge + inflation fears"
  → bearish, "stocks surge on earnings beat" → bullish) is still on the
  wishlist — see SESSION_LOG 2026-09-09 entry on this same change for the
  discussion. The current expansion is the safest, lowest-risk path: it
  adds nouns that are *always* bearish, no context-disambiguation required.
- The pre-existing pytest teardown hang on
  `tests/test_portfolio_cache_sync.py` when run as part of the full suite
  is unchanged by this work. File passes 5/5 in isolation both before and
  after the change; full-suite hang is an unrelated infra issue. Tracked
  separately.

## Files touched

- `app/news.py` — BULLISH_TERMS, BEARISH_TERMS, MACRO_TERMS, MICRO_TERMS.
- `app/config.py` — AI_NEWS_KEYWORDS.
- `app/store.py` — removed `_AI_TAG_KEYWORDS` duplicate; `_is_ai_text`
  references `config.AI_NEWS_KEYWORDS`.
- `tests/test_news_analyze.py` — regression + coverage tests.
- `tests/test_ai_sentiment.py` — AI keyword coverage + gauge end-to-end.
- `tests/test_store.py` — canonical-list + insert tests.
- `project_rules/SESSION_LOG.md` — appended 2026-09-09 entry.
- `project_rules/DECISIONS.md` — pointer entry (this file is the verbose
  detail).
- `data/logs/summary-2026-09-09.md` — daily changelog (gitignored).