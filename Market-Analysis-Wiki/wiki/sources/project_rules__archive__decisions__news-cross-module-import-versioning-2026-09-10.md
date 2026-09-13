---
type: source
title: "Cross-module imports in the news stack — never version one side without the other"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/news-cross-module-import-versioning-2026-09-10.md"
original_sha256: "c7c7be1c05037372ec800ec7e395fac841ddc0065df122d00cb2d55e82a9208b"
stored_path: ".raw/captured/c7c7be1c05037372ec800ec7e395fac841ddc0065df122d00cb2d55e82a9208b.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Cross-module imports in the news stack — never version one side without the other

Adding a ?v= query to one side of a mutual-import pair (events.js <-> cards.js) without the other creates a silent module-graph split: four module records for two logical modules, each with separate top-level bindings. Both import URLs must always be byte-identical.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/news-cross-module-import-versioning-2026-09-10.md`
  - SHA-256: `c7c7be1c05037372ec800ec7e395fac841ddc0065df122d00cb2d55e82a9208b`
- **Captured:** `.raw/captured/c7c7be1c05037372ec800ec7e395fac841ddc0065df122d00cb2d55e82a9208b.md`

## Key claims

- For any pair of modules that import each other, both import URLs must be byte-identical including query strings.
- A version bump on one import in a mutual-import pair creates a hidden duplicate with separate state.

## Concepts

- `cross-module-imports`
- `module-versioning`
- `silent-state-bug`

## Entities

- `events.js`
- `cards.js`
- `static/js/main.js`
