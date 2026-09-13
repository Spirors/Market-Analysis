---
type: source
title: "renderBody must clear portfolioTables Map before innerHTML rebuild"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/renderbody-must-clear-portfoliotables-map-before-innerhtml-rebuild-2026-09-07.md"
original_sha256: "1a33e06b055af5ee4d22eda0c866fea29bef52e19fbb50beea007e525646d4f2"
stored_path: ".raw/captured/1a33e06b055af5ee4d22eda0c866fea29bef52e19fbb50beea007e525646d4f2.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# renderBody must clear portfolioTables Map before innerHTML rebuild

renderBody() must call portfolioTables.clear() before the innerHTML assignment so that renderHoldingsTable creates fresh tickerTable instances bound to the new DOM slots. Without the clear, the Map held instances bound to detached old slots, and the user saw their holdings table disappear after a star click.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/renderbody-must-clear-portfoliotables-map-before-innerhtml-rebuild-2026-09-07.md`
  - SHA-256: `1a33e06b055af5ee4d22eda0c866fea29bef52e19fbb50beea007e525646d4f2`
- **Captured:** `.raw/captured/1a33e06b055af5ee4d22eda0c866fea29bef52e19fbb50beea007e525646d4f2.md`

## Key claims

- portfolioTables.clear() must be called before el.innerHTML = html to prevent stale DOM handles from outliving their slots.
- The failure mode (empty section after star click) only surfaces via UI tests, not Python backend tests.

## Concepts

- `portfolio-rendering`
- `dom-handles`
- `detached-slots`

## Entities

- `portfolioTables`
- `renderBody`
- `renderHoldingsTable`
