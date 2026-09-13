---
type: source
title: "News Section Overhaul — Design"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/superpowers/specs/2026-08-18-news-section-overhaul-design.md"
original_sha256: "3d8daacbbdecc5f32d2f962456f5ddc09015178300e2b8b0b438472090363fa12"
stored_path: ".raw/captured/3d8daacbbdecc5f32d2f962456f5ddc09015178300e2b8b0b438472090363fa12.md"
source_kind: "news-overhaul-design"
tags:
  - source
  - news-overhaul-design
---

# News Section Overhaul — Design

Design spec for replacing the news firehose with a curated market-events timeline. Defines 5 tag dimensions (impact, category, actor, direction, region), the events table schema with explicit columns, curated seed from 3 sources (gauge events, Wikipedia seed, gap-fill research), strict High/Critical-only RSS ingestion at threshold 6.0, and frontend seed:// link rendering as plain text.

## Citation

- **Original:** `inbox/docs/superpowers/specs/2026-08-18-news-section-overhaul-design.md`
  - SHA-256: `3d8daacbbdecc5f32d2f962456f5ddc09015178300e2b8b0b438472090363fa12`
- **Captured:** `.raw/captured/3d8daacbbdecc5f32d2f962456f5ddc09015178300e2b8b0b438472090363fa12.md`

## Key claims

- Only High and Critical events are stored; Low/Medium are dropped at ingest with threshold importance >= 6.0.
  - *Evidence:* "only High and Critical events are stored. Low/Medium are dropped at ingest (threshold: importance >= 6.0)."
- The actor tag is nullable — neither government nor company gets no tag instead of a forced label.
  - *Evidence:* "Actor tag: nullable — an event that is neither government nor company gets no actor tag instead of a forced label."
- Curated seed entries trace to the frozen gauge file, Wikipedia, or public reporting already captured in-repo.
  - *Evidence:* "No fabrication — each entry traces to the frozen gauge file, a Wikipedia article, or public reporting already captured in-repo."

## Concepts

- `news-section`
- `tag-taxonomy`
- `events-schema`
- `curated-seed`
- `importance-threshold`

## Entities

- `store.py`
- `news.py`
- `seed_data.py`
- `config.py`
