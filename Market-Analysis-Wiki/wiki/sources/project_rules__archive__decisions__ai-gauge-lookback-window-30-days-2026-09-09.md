---
type: source
title: "AI gauge lookback window = 30 days"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/ai-gauge-lookback-window-30-days-2026-09-09.md"
original_sha256: "c340d64781437bc816e0696f889ab3390e53550d139a3e50254fdb9df62946ab"
stored_path: ".raw/captured/c340d64781437bc816e0696f889ab3390e53550d139a3e50254fdb9df62946ab.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# AI gauge lookback window = 30 days

NEWS_LOOKBACK_DAYS was changed from 60 to 30 days to match the user's desired one-month window, the tooltip was updated with quantitative details (formula, thresholds, const names), and 21 RSS events were re-tagged under the new heuristic.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/ai-gauge-lookback-window-30-days-2026-09-09.md`
  - SHA-256: `c340d64781437bc816e0696f889ab3390e53550d139a3e50254fdb9df62946ab`
- **Captured:** `.raw/captured/c340d64781437bc816e0696f889ab3390e53550d139a3e50254fdb9df62946ab.md`

## Key claims

- NEWS_LOOKBACK_DAYS changed from 60 to 30; all downstream code references and weight keys updated accordingly.
- 21 RSS events re-tagged under the updated news heuristic; seed events were left untouched per the hand-curation rule.

## Concepts

- `ai-gauge`
- `news-heuristic`
- `lookback-window`

## Entities

- `NEWS_LOOKBACK_DAYS`
- `config.py`
- `analysis.py`
