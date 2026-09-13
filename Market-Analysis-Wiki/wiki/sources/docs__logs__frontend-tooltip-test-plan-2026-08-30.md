---
type: source
title: "Frontend tooltip / global refresh / news chips — manual test plan"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/logs/frontend-tooltip-test-plan-2026-08-30.md"
original_sha256: "b20c07c1314e656fad6383d5b0d618eb6bd51494d3b1cfef9f81c29d0bb64c6d"
stored_path: ".raw/captured/b20c07c1314e656fad6383d5b0d618eb6bd51494d3b1cfef9f81c29d0bb64c6d.md"
source_kind: "test-plan"
tags:
  - source
  - test-plan
---

# Frontend tooltip / global refresh / news chips — manual test plan

Manual test plan covering the tooltip system, single global Refresh affordance, and news filter chips. Defines 8 test sections: keyboard tab order, tooltip hover/focus/Escape behavior, narrow-viewport placement, global refresh flow, news filter chips (region/weight/topic), event row metadata, seed-only toggle persistence, and cross-reload state restoration.

## Citation

- **Original:** `inbox/docs/logs/frontend-tooltip-test-plan-2026-08-30.md`
  - SHA-256: `b20c07c1314e656fad6383d5b0d618eb6bd51494d3b1cfef9f81c29d0bb64c6d`
- **Captured:** `.raw/captured/b20c07c1314e656fad6383d5b0d618eb6bd51494d3b1cfef9f81c29d0bb64c6d.md`

## Key claims

- Per-card refresh icons are removed everywhere — the header Refresh button is the single refresh affordance.
  - *Evidence:* "Per-card ↻ is removed everywhere — no card carries a refresh icon. The header Refresh button is the single refresh affordance."
- The seed-only toggle is a hard rule that must never be removed.
  - *Evidence:* "The toggle must never be removed — it is the legacy Wikipedia view (hard rule)."
- Only one tooltip is open at a time.
  - *Evidence:* "Only one tooltip is open at a time."
- Card order (dashLayout) survives unchanged including layouts saved by older versions.
  - *Evidence:* "Card order (dashLayout) survives unchanged — including layouts saved by older versions (one-time migration on read)."

## Concepts

- `tooltip`
- `news-chips`
- `global-refresh`
- `seed-toggle`
- `persistence`

## Entities

- `tooltip.js`
- `events.js`
- `cards.js`
