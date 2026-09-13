---
type: source
title: "AI capex-cycle gauge does NOT auto-refresh on tag edits"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/news-ai-gauge-no-auto-refresh-2026-09-11.md"
original_sha256: "143403d0a62aef52afa43d3b32e693e6e72f03de156f144df54c7741a2c1c170"
stored_path: ".raw/captured/143403d0a62aef52afa43d3b32e693e6e72f03de156f144df54c7741a2c1c170.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# AI capex-cycle gauge does NOT auto-refresh on tag edits

The AI capex-cycle gauge should not auto-refresh when a user edits a news tag; it only updates on the explicit global Refresh button. Tag curation and gauge recompute are two distinct user moments that should remain separated.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/news-ai-gauge-no-auto-refresh-2026-09-11.md`
  - SHA-256: `143403d0a62aef52afa43d3b32e693e6e72f03de156f144df54c7741a2c1c170`
- **Captured:** `.raw/captured/143403d0a62aef52afa43d3b32e693e6e72f03de156f144df54c7741a2c1c170.md`

## Key claims

- POST /api/events/tags no longer returns ai_sentiment or triggers gauge recompute.
- The gauge updates only via the global Refresh button -> /api/dashboard -> _recompute_ai_sentiment path.

## Concepts

- `ai-gauge`
- `news-tags`
- `auto-refresh`

## Entities

- `POST /api/events/tags`
- `renderAISentiment`
- `service._recompute_ai_sentiment`
