---
type: source
title: "Card-level totals must refresh after any sub-table mutation"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/card-level-totals-must-refresh-after-any-sub-table-mutation-2026-09-06.md"
original_sha256: "559d0c98df46af00f88ab2bac7fd039f1e0cbcc43661bd96967eb63778d88f7d"
stored_path: ".raw/captured/559d0c98df46af00f88ab2bac7fd039f1e0cbcc43661bd96967eb63778d88f7d.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Card-level totals must refresh after any sub-table mutation

After any per-holding add/remove/edit mutation, the card-level grand header total must be re-rendered via renderGrandHeader(), not just the per-table totals row. A top-level refresh() should never be relied upon to cascade card-level aggregates.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/card-level-totals-must-refresh-after-any-sub-table-mutation-2026-09-06.md`
  - SHA-256: `559d0c98df46af00f88ab2bac7fd039f1e0cbcc43661bd96967eb63778d88f7d`
- **Captured:** `.raw/captured/559d0c98df46af00f88ab2bac7fd039f1e0cbcc43661bd96967eb63778d88f7d.md`

## Key claims

- Every per-table mutation callback that affects a card-level aggregate must also call renderGrandHeader() to keep the card header in sync.
- Top-level refresh() only fires on explicit user action; per-table mutations must be self-contained.

## Concepts

- `card-rendering`
- `sub-table-mutation`
- `grand-header`

## Entities

- `renderGrandHeader`
- `static/js/portfolio.js`
- `8f3a82e`
