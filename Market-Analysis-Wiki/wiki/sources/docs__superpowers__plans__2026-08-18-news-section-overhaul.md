---
type: source
title: "News Section Overhaul Implementation Plan"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/superpowers/plans/2026-08-18-news-section-overhaul.md"
original_sha256: "b6f1452e9cc1fe7ceb1502c90b0de9300e1329144caed2711ce3cdfc566a402e"
stored_path: ".raw/captured/b6f1452e9cc1fe7ceb1502c90b0de9300e1329144caed2711ce3cdfc566a402e.md"
source_kind: "news-overhaul-plan"
tags:
  - source
  - news-overhaul-plan
---

# News Section Overhaul Implementation Plan

6-task implementation plan to replace the news firehose + GDELT/Wikipedia backfill with a curated tagged market-events timeline (seeded once from 3 sources) plus strict High/Critical-only live RSS flow. Covers seed data rewrite, storage rework with explicit tag columns, classifier + ingestion rewrite, service/API wiring, frontend updates, and docs sync.

## Citation

- **Original:** `inbox/docs/superpowers/plans/2026-08-18-news-section-overhaul.md`
  - SHA-256: `b6f1452e9cc1fe7ceb1502c90b0de9300e1329144caed2711ce3cdfc566a402e`
- **Captured:** `.raw/captured/b6f1452e9cc1fe7ceb1502c90b0de9300e1329144caed2711ce3cdfc566a402e.md`

## Key claims

- Only High/Critical events are stored (importance threshold 6.0).
  - *Evidence:* "Only High/Critical events are stored (importance threshold 6.0; bands [(9.0, 'Critical'), (6.0, 'High')])."
- Curated seed entries are hand-tagged, not heuristically classified.
  - *Evidence:* "seed_events(): import seed_data; for each entry build item dict ... verbatim from the seed (NO heuristic classification)."
- The importance threshold is 6.0 with impact bands Critical ≥ 9.0 and High ≥ 6.0.
  - *Evidence:* "IMPORTANCE_THRESHOLD = 6.0. IMPACT_BANDS = [(9.0, 'Critical'), (6.0, 'High')]"

## Concepts

- `news-section`
- `curated-seed`
- `rss-ingestion`
- `event-tags`
- `importance-threshold`

## Entities

- `seed_data.py`
- `store.py`
- `news.py`
- `config.py`
