---
type: source
title: "Session Handoff — Current State and Next Actions"
status: retired
imported_at: 2026-09-13
retired_at: 2026-09-13
superseded_by: "wiki/hot.md + wiki/overview.md"
original_path: "inbox/project_rules/HANDOFF.md"
original_sha256: "bdfd15938570bfada744c71093f16261592d281bed9012f0d185e17dede7f994"
stored_path: ".raw/captured/bdfd15938570bfada744c71093f16261592d281bed9012f0d185e17dede7f994.md"
source_kind: "handoff"
tags:
  - source
  - handoff
  - retired
---

# Session Handoff — Current State and Next Actions

> [!deprecated] This umbrella page was retired 2026-09-13. The wiki-native
> session-memory protocol now lives in [[wiki/hot.md]] (current context)
> and [[wiki/overview.md]] (vault map). The captured source content is
> preserved below for historical reference; the 99 source pages and 47
> decisions listed in [[wiki/index.md]] are the live knowledge base.

Current session state (last updated 2026-09-11 19:25 UTC): Portfolio holdings reorder persistence and per-section refresh cooldowns shipped. Live-price columns now always refresh (cooldown skip removed for portfolios). ▲/▼ reorder survives collapse+expand. News overhaul with editable pills and user_edited lock complete. Top 3 next actions: Phase 3 backlog, module-graph discipline for cross-module imports, and archiving the daily changelog. No blockers.

## Citation

- **Original:** `inbox/project_rules/HANDOFF.md`
  - SHA-256: `bdfd15938570bfada744c71093f16261592d281bed9012f0d185e17dede7f994`
- **Captured:** `.raw/captured/bdfd15938570bfada744c71093f16261592d281bed9012f0d185e17dede7f994.md`

## Key claims

- Portfolio enrichment always runs — the cooldown skip was removed because it blanked live-price columns.
  - *Evidence:* "Portfolio live-price columns are now populated on every refresh (the cooldown skip that reused the unenriched cached payload is removed for portfolios)"
- Per-section refresh cooldowns are gated on `vintage` stamps in `data/dashboard.json`; Breadth — AI proxies has a 30-min cooldown.
  - *Evidence:* "Breadth — AI proxies cooldown is unchanged. (2) ▲/▼ reorder now mirrors the new order into the closure's `p.holdings`"
- Module-graph discipline: never add a `?v=…` query to one JS import side without the other, to avoid silent module duplication.
  - *Evidence:* "Module-graph discipline — when extending events.js ↔ cards.js imports, do NOT add a `?v=…` query to one side without the other."
- Playwright frontend tests require a static server on port 8123; reaping must happen before turn end.
  - *Evidence:* "Playwright frontend tests need a static server on port 8123 (`python -m http.server 8123 --bind 127.0.0.1` from the repo root)."

## Concepts

- `per-section-cooldowns`
- `holdings-reorder-persistence`
- `module-graph-discipline`
- `process-hygiene`
- `data-events-json-ownership`

## Entities

- `app/config.py`
- `app/service.py`
- `app/portfolio.py`
- `static/js/tickerTable.js`
- `static/js/cards.js`
- `app/validation.py`
- `app/lifecycle.py`
- `tests/conftest.py`
- `data/portfolios.json`
- `data/events.json`
- `data/bottleneck_prefs.json`
