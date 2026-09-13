---
type: source
title: "News heuristic expansion — noun-heavy bearish + AI capex coverage"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/news-heuristic-expansion-noun-heavy-bearish-ai-capex-coverage-2026-09-09.md"
original_sha256: "ed41929ed2f11c1ee0ecd7a0c830a96f9dc56e5c09b4fa2af70e980621d3be6b"
stored_path: ".raw/captured/ed41929ed2f11c1ee0ecd7a0c830a96f9dc56e5c09b4fa2af70e980621d3be6b.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# News heuristic expansion — noun-heavy bearish + AI capex coverage

All five keyword lists (BEARISH, BULLISH, MACRO, MICRO, AI_NEWS) were expanded to close the noun/verb gap and AI capex-cycle coverage gap. A MarketWatch oil headline falsely classified as bullish was the trigger; inflation/fear/concern/shock nouns were missing from BEARISH_TERMS.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/news-heuristic-expansion-noun-heavy-bearish-ai-capex-coverage-2026-09-09.md`
  - SHA-256: `ed41929ed2f11c1ee0ecd7a0c830a96f9dc56e5c09b4fa2af70e980621d3be6b`
- **Captured:** `.raw/captured/ed41929ed2f11c1ee0ecd7a0c830a96f9dc56e5c09b4fa2af70e980621d3be6b.md`

## Key claims

- BEARISH_TERMS expanded with noun-heavy lexicon (inflation, fear, concern, disruption, shock, taper, tightening, slowdown, contagion).
- AI_NEWS_KEYWORDS expanded with model families, hardware vendors, cloud providers, training concepts, power/grid terms; store._AI_TAG_KEYWORDS duplicate removed.

## Concepts

- `news-heuristic`
- `keyword-expansion`
- `ai-capex-coverage`

## Entities

- `app/news.py`
- `BEARISH_TERMS`
- `AI_NEWS_KEYWORDS`
