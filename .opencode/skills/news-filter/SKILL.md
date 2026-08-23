---
name: news-filter
description: Dedupe and classify market events for the Market Analysis Tool. Use when ingesting news, tuning the event classifier, or asking what news is market-moving.
---

# News Filter

Ingest market events from two paths, dedupe by link + cross-source title
similarity, and tag every event with five dimensions.

## The five tag dimensions

Every event carries one value per dimension (actor may be absent):

- `impact` — High | Critical (Low/Medium are dropped at ingest)
- `category` — macro | micro
- `actor` — government | company (nullable)
- `direction` — bullish | bearish | neutral
- `region` — us | japan | china | middle-east | europe | korea |
  russia-ukraine | global

## Where the code lives

- `app/seed_data.py` — the curated 2026 timeline (1/1/2026 → now), hand-tagged.
  Add a historical event HERE (explicit tags, real link or `seed://<slug>`).
- `app/news.py` — `analyze()` (keyword heuristics for the live feed) and
  `fetch_and_store()` (single MarketWatch feed; stores only events published
  within `NEWS_INGEST_WINDOW_HOURS` that score >= `IMPORTANCE_THRESHOLD` =
  6.0, i.e. High/Critical), plus `seed_events()`.
- `app/store.py` — `upsert_events()` / `list_events()` backed by SQLite
  (`data/news.db`); `tags` list is computed at read time from the explicit
  tag columns.

## Tuning the classifier

Edit `MACRO_TERMS`, `MICRO_TERMS`, `BULLISH_TERMS`, `BEARISH_TERMS`,
`GOV_TERMS`, `COMPANY_TERMS`, `REGION_TERMS` in `app/news.py`.
Classification is intentionally heuristic — it is a filter aid, not a model.
Seed events bypass the heuristics entirely (hand-tagged).

## Notes

- Dedupe key is the item link (unique column); re-running `seed_events()` is
  idempotent. Cross-source dedupe merges similar titles within 2 days.
- Manual removal: delete one event (with confirmation) or hide a whole source
  via the UI.
- Feed list lives in `app/config.py` under `NEWS_FEEDS` (a single source).
