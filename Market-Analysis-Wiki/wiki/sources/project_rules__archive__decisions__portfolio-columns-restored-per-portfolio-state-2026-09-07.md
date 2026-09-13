---
type: source
title: "Portfolio columns restored + per-portfolio state"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/portfolio-columns-restored-per-portfolio-state-2026-09-07.md"
original_sha256: "abe1e0efc984f325433035b3ac92d0d23f651d86e093411b4720de9b9454c50e"
stored_path: ".raw/captured/abe1e0efc984f325433035b3ac92d0d23f651d86e093411b4720de9b9454c50e.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Portfolio columns restored + per-portfolio state

Eight columns stripped by the earnings watchlist removal were restored (7-day %, 30-day %, earnings date, marketcap, forward PE, forward PEG, 52W high, sector) and column settings are now independent per portfolio via namespace keys like pfVisible.portfolio.<pid>.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/portfolio-columns-restored-per-portfolio-state-2026-09-07.md`
  - SHA-256: `abe1e0efc984f325433035b3ac92d0d23f651d86e093411b4720de9b9454c50e`
- **Captured:** `.raw/captured/abe1e0efc984f325433035b3ac92d0d23f651d86e093411b4720de9b9454c50e.md`

## Key claims

- Column visibility and order are now namespaced per portfolio (pfVisible.portfolio.<pid>) so hiding a column in Portfolio A never affects Portfolio B.
- All 8 restored columns visible by default; per-symbol Ticker.info fetches cached via lru_cache with 5-minute bucket.

## Concepts

- `portfolio-columns`
- `per-portfolio-state`
- `column-persistence`

## Entities

- `pfVisible.portfolio.<pid>`
- `pfOrder.portfolio.<pid>`
- `enrich_portfolios`
