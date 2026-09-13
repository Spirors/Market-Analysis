---
type: source
title: "News user_edited lock — preserve manual edits across RSS refreshes"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/news-user-edited-lock-2026-09-10.md"
original_sha256: "2924100597f9f0870e4b1e9de1086d282d8ba76f205c15fba6b179f60be27428"
stored_path: ".raw/captured/2924100597f9f0870e4b1e9de1086d282d8ba76f205c15fba6b179f60be27428.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# News user_edited lock — preserve manual edits across RSS refreshes

A user_edited boolean field locks an event row from RSS-side overwrites. update_event_tags sets it to True; upsert_events short-circuits the update branch when it's True, only refreshing updated_at. The lock is sticky — even tag removal sets user_edited.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/news-user-edited-lock-2026-09-10.md`
  - SHA-256: `2924100597f9f0870e4b1e9de1086d282d8ba76f205c15fba6b179f60be27428`
- **Captured:** `.raw/captured/2924100597f9f0870e4b1e9de1086d282d8ba76f205c15fba6b179f60be27428.md`

## Key claims

- user_edited=True locks a row from all RSS-side overwrites; only updated_at is refreshed.
- Lock fires on tag-removal too, matching 'user manually touched this row' semantics.

## Concepts

- `user-edited-lock`
- `news-refresh`
- `event-persistence`

## Entities

- `update_event_tags`
- `upsert_events`
- `user_edited`
