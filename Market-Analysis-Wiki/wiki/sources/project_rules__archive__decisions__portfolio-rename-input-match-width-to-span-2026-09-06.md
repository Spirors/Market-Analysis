---
type: source
title: "Portfolio rename input — match width to span"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/portfolio-rename-input-match-width-to-span-2026-09-06.md"
original_sha256: "e32bf0e91439106825e22e59ea96493ed981e76792499366fc0f699f52813123"
stored_path: ".raw/captured/e32bf0e91439106825e22e59ea96493ed981e76792499366fc0f699f52813123.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Portfolio rename input — match width to span

Entering rename mode shifted sibling elements left because the input was narrower than the span it replaced. startEditForPid now measures the span's box width via getBoundingClientRect() and sets inp.style.minWidth to match, keeping pencil/totals/close in place.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/portfolio-rename-input-match-width-to-span-2026-09-06.md`
  - SHA-256: `e32bf0e91439106825e22e59ea96493ed981e76792499366fc0f699f52813123`
- **Captured:** `.raw/captured/e32bf0e91439106825e22e59ea96493ed981e76792499366fc0f699f52813123.md`

## Key claims

- startEditForPid measures the span width before swapping in the input and sets minWidth to prevent layout shift.
- CSS field-sizing: content alone cannot match a sibling; JS measurement is the only exact-match approach.

## Concepts

- `portfolio-rename`
- `layout-shift`
- `inline-edit`

## Entities

- `startEditForPid`
- `getBoundingClientRect`
- `pf-name-input`
