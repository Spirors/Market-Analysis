---
type: source
title: "Portfolio add/delete latency fix"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/portfolio-add-delete-latency-fix-2026-09-07.md"
original_sha256: "9586f60573b24a0b64549195a5dada5134c2c71c5aaba9b6a383e82dfc27e873"
stored_path: ".raw/captured/9586f60573b24a0b64549195a5dada5134c2c71c5aaba9b6a383e82dfc27e873.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Portfolio add/delete latency fix

Three independent causes of ~3s mutation lag were fixed: _patch_dashboard_cache re-enriched all symbols on a 1-symbol change (now structural-only), _quote_snapshot had no disk cache (now routes through market.get_quotes), and six bespoke handlers called full refresh() after mutation (now use optimistic local state).

## Citation

- **Original:** `inbox/project_rules/archive/decisions/portfolio-add-delete-latency-fix-2026-09-07.md`
  - SHA-256: `9586f60573b24a0b64549195a5dada5134c2c71c5aaba9b6a383e82dfc27e873`
- **Captured:** `.raw/captured/9586f60573b24a0b64549195a5dada5134c2c71c5aaba9b6a383e82dfc27e873.md`

## Key claims

- _patch_dashboard_cache is now structural-only — it patches the cached portfolio state without re-enriching; newly added holdings show '-' until the next full refresh.
- Bespoke mutation handlers now use optimistic local state (push/filter closure, targeted re-render) instead of full refresh(), reducing mutation time from ~3s to ~130ms.

## Concepts

- `mutation-latency`
- `optimistic-ui`
- `cache-patching`

## Entities

- `_patch_dashboard_cache`
- `market.get_quotes`
- `renderHoldingsTable`
