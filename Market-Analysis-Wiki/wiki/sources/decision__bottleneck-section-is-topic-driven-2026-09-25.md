---
type: source
title: "Bottleneck section is topic-driven — the category model is gone"
status: evergreen
created: 2026-09-25
updated: 2026-09-25
source_kind: decision
tags:
  - source
  - decision
  - bottleneck
---

# Bottleneck section is topic-driven — the category model is gone

The Bottleneck (chokepoint) section no longer has a fixed list of categories.
`BOTTLENECK_CATEGORIES` and the category-preference model are deleted. The
section is driven by user-authored **topics** persisted in
`data/bottleneck_topics.json`: each topic names a demand driver, lists the
upstream layers that physically constrain it, and carries downstream per-stock
thesis cards.

This supersedes
[[sources/project_rules__archive__decisions__bottleneck-category-user-prefs-live-in-data-bottleneck-prefs-json-2026-09-08]]:
reordering and renaming five hardcoded categories is not a mechanism for
expressing a new thesis.

## What replaced what

| Old | New |
|---|---|
| `BOTTLENECK_CATEGORIES` (5 hardcoded) | `bottleneck_topics.load_topics()` — user-authored |
| `app/bottleneck_prefs.py` + 2 routes | topic CRUD, import/export, job polling, apply, skill status/refresh (13 routes) |
| `Layer / Why scarce / Proxy tickers / 40-day momentum` table | accordion topics with expandable per-stock thesis cards |
| `gauge` per layer | folded into the layer's `what_to_watch` |
| a bare ticker in a comma list | a full card: stance, chokepoint reasoning, tiered evidence, catalyst, invalidation, checklist flags, metrics, provenance |

## Decisions that are frozen

- **Downstream is two different things.** An **unranked `anchor` strip** of the
  obvious capex spenders (the demand trace, deliberately not ranked), then a
  **ranked `underdogs` list** filtered by a market-cap ceiling and ranked by
  40-day momentum.
- **The underdog ceiling is per topic**, printed on the section, default `$10B`,
  with `core` (< ~$3B) and `extended` ($3-10B) tier labels. A stock whose market
  cap is unavailable is **kept** with a dash tier — never dropped, never guessed.
- **The engine is a pure snapshot read.** `bottleneck_read()` takes histories
  from the snapshot it is handed and never fetches.
- **The agent drafts; the user applies.** A draft is reviewable and nothing
  reaches the topic store until `apply`. Applying appends one numbered revision
  and stamps every downstream card with the run's provenance.
- **Revisions are bounded** (20 per topic, newest first). Jobs are serial,
  cancellable, persisted with bounded retention, and a job left `running` by a
  restart is marked interrupted rather than blocking forever.
- **Empty by default.** No seed; the section renders an empty state offering
  create-or-generate.
- **Manual CRUD never depends on the key.** With no `OPENCODE_GO_API_KEY` only
  generation is disabled, and it says so by name; everything else works.

## Consequences

- `all_proxy_symbols()` is derived from topics, so a fresh install bulk-downloads
  no proxy histories.
- The old category-preference routes are gone and now 404.
- `data/bottleneck_prefs.json` is left on disk, not migrated (precedent: commit
  `8dedc18` left `data/analysis.db` and `data/thirteenf_snapshot.json`).
- The dashboard still publishes a `bottleneck` key; the section no longer reads
  it, and the header coverage badge counts the section's own payload instead.

## Commits

`261f72a` topic store — `b41c5ac` shared metrics cache — `62289b6` topic-driven
engine — `7e4d6c6` drafting agent — `a34c99d` API — `56ed1c0` metric units —
`099e932` front-end.
