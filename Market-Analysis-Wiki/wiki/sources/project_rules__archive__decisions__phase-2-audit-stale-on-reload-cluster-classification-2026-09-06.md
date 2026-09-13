---
type: source
title: "Phase 2 audit — stale-on-reload cluster classification"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/phase-2-audit-stale-on-reload-cluster-classification-2026-09-06.md"
original_sha256: "a15145742be513261b55cfe0332a1c7b7f952071c43e31a57a3c350431e1df40"
stored_path: ".raw/captured/a15145742be513261b55cfe0332a1c7b7f952071c43e31a57a3c350431e1df40.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Phase 2 audit — stale-on-reload cluster classification

The stale-on-reload cluster was classified as two separate issues: dashboard-cache staleness (mutations didn't patch data/dashboard.json, fixed by _patch_dashboard_cache) and tickerTable.js shared-component state namespacing (a different bug class). Both are now fixed.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/phase-2-audit-stale-on-reload-cluster-classification-2026-09-06.md`
  - SHA-256: `a15145742be513261b55cfe0332a1c7b7f952071c43e31a57a3c350431e1df40`
- **Captured:** `.raw/captured/a15145742be513261b55cfe0332a1c7b7f952071c43e31a57a3c350431e1df40.md`

## Key claims

- Dashboard-cache staleness was caused by mutations writing data/portfolios.json but not patching data/dashboard.json.
- The _patch_dashboard_cache helper is now the reference pattern for future cache-invalidation logic.

## Concepts

- `dashboard-cache`
- `stale-on-reload`
- `cache-invalidation`

## Entities

- `_patch_dashboard_cache`
- `b45858e`
- `data/dashboard.json`
