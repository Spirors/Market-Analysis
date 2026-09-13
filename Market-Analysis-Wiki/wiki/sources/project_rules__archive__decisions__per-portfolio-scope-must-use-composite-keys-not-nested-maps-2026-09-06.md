---
type: source
title: "Per-portfolio scope must use composite keys, not nested Maps"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/per-portfolio-scope-must-use-composite-keys-not-nested-maps-2026-09-06.md"
original_sha256: "1794473a61efc4954e938897a3ae7d45b62e3b0f806f0636abe4765a0fa781ee"
stored_path: ".raw/captured/1794473a61efc4954e938897a3ae7d45b62e3b0f806f0636abe4765a0fa781ee.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Per-portfolio scope must use composite keys, not nested Maps

Starring NVDA in 'Fidelity Main' also starred it in 'Fidelity Roth IRA' because watchColors.js used a symbol-only Map. Fix: use composite '<pid>::<sym>' keys in a flat Map, keeping localStorage serialization flat and compatible with the existing save/load infrastructure.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/per-portfolio-scope-must-use-composite-keys-not-nested-maps-2026-09-06.md`
  - SHA-256: `1794473a61efc4954e938897a3ae7d45b62e3b0f806f0636abe4765a0fa781ee`
- **Captured:** `.raw/captured/1794473a61efc4954e938897a3ae7d45b62e3b0f806f0636abe4765a0fa781ee.md`

## Key claims

- Per-(section, entity) persistence must use composite keys inside a flat Map, not nested Maps, to keep localStorage serialization flat.
- The SECTIONS config table carries a keyBy field to define the scope axis per section.

## Concepts

- `per-portfolio-state`
- `composite-keys`
- `localStorage`

## Entities

- `watchColors.js`
- `pfWatchColors`
- `keyBy`
