---
type: source
title: "Bottleneck category user prefs live in data/bottleneck_prefs.json"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/bottleneck-category-user-prefs-live-in-data-bottleneck-prefs-json-2026-09-08.md"
original_sha256: "1971a99889812729a3c485ad7c46f0766ce545c0a30f226fa548662eb10d11f7"
stored_path: ".raw/captured/1971a99889812729a3c485ad7c46f0766ce545c0a30f226fa548662eb10d11f7.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Bottleneck category user prefs live in data/bottleneck_prefs.json

User-customizable bottleneck category order and rename prefs are persisted in data/bottleneck_prefs.json, separate from the BOTTLENECK_CATEGORIES module constant. The canonical list is never mutated; prefs are applied at serve time, with graceful fallback for stale or invalid orderings.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/bottleneck-category-user-prefs-live-in-data-bottleneck-prefs-json-2026-09-08.md`
  - SHA-256: `1971a99889812729a3c485ad7c46f0766ce545c0a30f226fa548662eb10d11f7`
- **Captured:** `.raw/captured/1971a99889812729a3c485ad7c46f0766ce545c0a30f226fa548662eb10d11f7.md`

## Key claims

- BOTTLENECK_CATEGORIES constant is never mutated by user prefs; prefs applied at serve time via _apply_prefs().
- Each category dict carries a category_original field so the frontend always sends the canonical key for API calls.

## Concepts

- `bottleneck-prefs`
- `persistence`
- `graceful-degradation`

## Entities

- `app/bottleneck_prefs.py`
- `BOTTLENECK_CATEGORIES`
- `data/bottleneck_prefs.json`
