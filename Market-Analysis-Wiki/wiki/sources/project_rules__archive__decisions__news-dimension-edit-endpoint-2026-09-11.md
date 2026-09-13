---
type: source
title: "News dimension-edit endpoint — manual fix for heuristic mis-classifications"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/news-dimension-edit-endpoint-2026-09-11.md"
original_sha256: "ecc1de28551046759c8d88b8b1dd8844a489deac9b77629cbfb8ca4a8bd98598"
stored_path: ".raw/captured/ecc1de28551046759c8d88b8b1dd8844a489deac9b77629cbfb8ca4a8bd98598.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# News dimension-edit endpoint — manual fix for heuristic mis-classifications

POST /api/events/dimensions lets the user manually override fixed-dimension pills (category/actor/direction/region) with typed select values. Any change arms user_edited, locking the row from RSS overwrites. The endpoint validates against _DIMENSION_VALUES and returns 400/404 on bad input.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/news-dimension-edit-endpoint-2026-09-11.md`
  - SHA-256: `ecc1de28551046759c8d88b8b1dd8844a489deac9b77629cbfb8ca4a8bd98598`
- **Captured:** `.raw/captured/ecc1de28551046759c8d88b8b1dd8844a489deac9b77629cbfb8ca4a8bd98598.md`

## Key claims

- Fixed-dimension pills use <select> of valid values (not free-text rename) to prevent inconsistent state where the display name diverges from the column value.
- The dimension endpoint is separate from the tag endpoint because dimensions are typed slots with a closed allowed-value set, while tags are loose labels.

## Concepts

- `news-dimensions`
- `dimension-edit`
- `user-edited-lock`

## Entities

- `POST /api/events/dimensions`
- `update_event_dimensions`
- `_DIMENSION_VALUES`
