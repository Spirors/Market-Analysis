---
type: source
title: "Portfolio mutations must patch the cached dashboard payload"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/portfolio-mutations-must-patch-the-cached-dashboard-payload-2026-09-06.md"
original_sha256: "09c80de0a01901bc7803a7d239d5f788ed263a4a22c725c2dc5ba087b6a4f8df"
stored_path: ".raw/captured/09c80de0a01901bc7803a7d239d5f788ed263a4a22c725c2dc5ba087b6a4f8df.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Portfolio mutations must patch the cached dashboard payload

Portfolio mutations wrote data/portfolios.json correctly but never touched data/dashboard.json, so service.get_dashboard served stale cached data until QUOTE_TTL expired. A _patch_dashboard_cache helper is now called after every save_portfolios to patch the cached payload in place.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/portfolio-mutations-must-patch-the-cached-dashboard-payload-2026-09-06.md`
  - SHA-256: `09c80de0a01901bc7803a7d239d5f788ed263a4a22c725c2dc5ba087b6a4f8df`
- **Captured:** `.raw/captured/09c80de0a01901bc7803a7d239d5f788ed263a4a22c725c2dc5ba087b6a4f8df.md`

## Key claims

- Every portfolio mutation must call _patch_dashboard_cache(state) after saving, or the dashboard cache stays stale.
- The patch is best-effort: a failed patch degrades to stale data until QUOTE_TTL, never a hard error.

## Concepts

- `dashboard-cache`
- `portfolio-mutations`
- `cache-patching`

## Entities

- `_patch_dashboard_cache`
- `data/dashboard.json`
- `b45858e`
