# News Section Overhaul — Design

Date: 2026-08-18
Status: Approved (chat design review)

## Goal

Replace the current news section (RSS firehose + GDELT/Wikipedia backfill) with
a high-signal **market events timeline**: events from 2026-01-01 → now populated
once from a curated seed, plus a live present-tense flow of new events. Every
event carries five tag dimensions plus an impact level, is deduped, and can be
manually removed.

Quality bar: the archived `ai_market_sentiment_gauge.html` (~72 hand-curated,
market-correlated events with specific dates and directional reads).

## Decisions (user-confirmed)

1. **Sourcing**: curated deterministic seed for the backfill; existing free RSS
   feeds for live flow with a strict High/Critical-only filter. No new external
   dependencies; the no-key rule is preserved.
2. **Scope**: timeline only. No sentiment gauge; the risk-divergence engine
   already aggregates bull/bear.
3. **Impact**: only High and Critical events are stored. Low/Medium are dropped
   at ingest (threshold: importance >= 6.0).
4. **Actor tag**: nullable — an event that is neither government nor company
   gets no actor tag instead of a forced label.

## Tag taxonomy

Every event carries exactly one value per dimension (except actor, which may
be absent):

- `impact` — High | Critical
- `category` — macro | micro
- `actor` — government | company (nullable)
- `direction` — bullish | bearish | neutral
- `region` — us | japan | china | middle-east | europe | korea |
  russia-ukraine | global (global when none applies)

## Architecture

### Storage (`app/store.py`)

- `events` becomes the single source of truth with explicit columns:
  `id, link UNIQUE NOT NULL, source, title, published, summary, category,
  actor, direction, region, impact, first_seen, updated_at`.
- The `news` table (raw headlines) is dropped, along with `upsert_news`,
  `list_news`, `untagged_events`, `set_event_tags`.
- `list_events` computes the flat `tags` list at read time
  (`[category, actor?, direction, region]`) so the existing filter-chip UI
  keeps working.
- One-time destructive migration: drop old `events`/`news` tables, recreate
  with the new schema, re-seed from the curated list.
- Dedupe retained: unique link + cross-source title similarity
  (Jaccard / SequenceMatcher, 2-day window).
- Manual removal retained: `delete_event`, `delete_events_by_source`,
  `suppress_source`.

### Ingestion (`app/news.py`)

- `seed_events()`: loads the curated seed (below) verbatim — tags are
  hand-assigned, not heuristically guessed. Idempotent by link.
- `fetch_and_store()`: RSS fetch across `config.NEWS_FEEDS`, classified by the
  retuned keyword heuristic, inserts **only** events scoring >= 6.0
  (High/Critical).
- GDELT backfill (`backfill_events`) removed. `migrate_events` removed.
- Impact bands collapse to `[(9.0, "Critical"), (6.0, "High")]`;
  `IMPORTANCE_THRESHOLD = 6.0`.

### Curated seed (`app/seed_data.py`)

Rich event list 2026-01-01 → now, compiled from three sources:

1. ~72 events ported from `ai_market_sentiment_gauge.html` (source label
   "Curated (gauge)"), with date → `dateLabel`, summary → card text,
   direction ← column (bear/bull/neutral), category ← type, actor/region/impact
   assigned by curation. Links: real Wikipedia/article links where confident,
   otherwise a deterministic `seed://<date>-<slug>` internal link (frontend
   renders these without a hyperlink).
2. ~35 events from the existing Wikipedia-linked seed, kept where they add
   signal (source label "Wikipedia").
3. Gap-filling research events (e.g., Aug 2026, missing months).

Every entry: `date, title, summary, link, source, category, actor, direction,
region, impact`. No fabrication — each entry traces to the frozen gauge file,
a Wikipedia article, or public reporting already captured in-repo.

### Service / API (`app/service.py`, `app/api.py`, `run.py`)

- `service.backfill_news` → `seed_news()` (curated seed only).
- `service.refresh_news` → `fetch_and_store()`.
- `run.py --backfill` → runs the seed (rename help text).
- `/api/news` endpoint removed; `/api/events` (GET/DELETE) and
  `/api/events/suppress` retained.

### Frontend (`static/`)

- Impact filter chips: Critical / High only.
- Tag chips unchanged in mechanics; `TAG_ORDER` updated for the new
  dimensions; region pills keep the shared region style.
- `seed://` links render as plain text, no `<a>`.
- Card title becomes "Market events timeline".

## Verification (repo has no test framework)

- Python smoke check: seed idempotency (run twice → 0 new inserts),
  classifier unit checks (representative titles → expected tags), dedupe check.
- Run `python run.py`, load dashboard, verify timeline + filters + delete.
- Refresh RSS and confirm only High/Critical rows appear.
