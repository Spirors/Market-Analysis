---
type: source
title: "OPEN — tickerTable.js shared-component persistence"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/open-tickertable-js-shared-component-persistence-2026-09-05.md"
original_sha256: "7c71f8c14ef96d94e9c69197eb37db0114fec3f72d4e92f7825fd95d64f5117c"
stored_path: ".raw/captured/7c71f8c14ef96d94e9c69197eb37db0114fec3f72d4e92f7825fd95d64f5117c.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# OPEN — tickerTable.js shared-component persistence

Investigation confirmed per-section persistence keys (pfSort, pfVisible, pfOrder) are correctly namespaced. A defensive VALID_SECTIONS allowlist and _assertValidSection() guard were added so an undefined section throws immediately instead of silently templating bad keys.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/open-tickertable-js-shared-component-persistence-2026-09-05.md`
  - SHA-256: `7c71f8c14ef96d94e9c69197eb37db0114fec3f72d4e92f7825fd95d64f5117c`
- **Captured:** `.raw/captured/7c71f8c14ef96d94e9c69197eb37db0114fec3f72d4e92f7825fd95d64f5117c.md`

## Key claims

- Shared UI components must take their persistence key as a required prop, validated against an allowlist; never let a component default or hardcode a storage key.
- Adding a new section to VALID_SECTIONS requires a paired regression test covering the new key.

## Concepts

- `shared-component`
- `persistence-key`
- `section-validation`

## Entities

- `VALID_SECTIONS`
- `_assertValidSection`
- `tickerTable.js`
