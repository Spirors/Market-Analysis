---
type: source
title: "tickerTable.js section gating must mirror _assertValidSection"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/tickertable-js-section-gating-must-mirror-assertvalidsection-not-collapse-to-single-string-2026-09-08.md"
original_sha256: "e4b19d70ecf6089dbb3fc5581a3f2bb0bd832cbe3bef53ce74a1d958c2926287"
stored_path: ".raw/captured/e4b19d70ecf6089dbb3fc5581a3f2bb0bd832cbe3bef53ce74a1d958c2926287.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# tickerTable.js section gating must mirror _assertValidSection

The reorderEnabled check in tickerTable.js was section === 'portfolio' but every instance uses 'portfolio.<pid>' keys, so reorder buttons never rendered. Feature gates must mirror the validation function's conditions exactly, and every rendered button must have a test.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/tickertable-js-section-gating-must-mirror-assertvalidsection-not-collapse-to-single-string-2026-09-08.md`
  - SHA-256: `e4b19d70ecf6089dbb3fc5581a3f2bb0bd832cbe3bef53ce74a1d958c2926287`
- **Captured:** `.raw/captured/e4b19d70ecf6089dbb3fc5581a3f2bb0bd832cbe3bef53ce74a1d958c2926287.md`

## Key claims

- Feature gates must mirror _assertValidSection exactly; section === 'portfolio' was widened to also match 'portfolio.*'.
- Every button rendered to the DOM needs a test — 'wired but not rendered' is one regression from 'wired but broken'.

## Concepts

- `section-gating`
- `feature-gates`
- `per-portfolio-scoping`

## Entities

- `_assertValidSection`
- `reorderEnabled`
- `VALID_SECTIONS`
