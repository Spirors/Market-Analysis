---
type: source
title: "Rename input must not bubble clicks to header"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/rename-input-must-not-bubble-clicks-to-header-2026-09-06.md"
original_sha256: "44be98fbcbcae95643312493e0ef5d73913b1cf74725df727e3d04334be4d6d0c"
stored_path: ".raw/captured/44be98fbcbcae95643312493e0ef5d73913b1cf74725df727e3d04334be4d6d0c.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Rename input must not bubble clicks to header

Clicking inside the rename input bubbled to the header click handler and toggled collapse, destroying the input mid-rename. Fix: add .pf-name-input to the skip list AND call stopPropagation on the input's events (belt-and-suspenders).

## Citation

- **Original:** `inbox/project_rules/archive/decisions/rename-input-must-not-bubble-clicks-to-header-2026-09-06.md`
  - SHA-256: `44be98fbcbcae95643312493e0ef5d73913b1cf74725df727e3d04334be4d6d0c`
- **Captured:** `.raw/captured/44be98fbcbcae95643312493e0ef5d73913b1cf74725df727e3d04334be4d6d0c.md`

## Key claims

- Inline-edit controls inside clickable containers must either be in the parent's skip list or call stopPropagation — both, never just one.
- Icon-only buttons sharing a generic button class need their own explicit CSS class to avoid inherited sizing issues.

## Concepts

- `event-bubbling`
- `inline-edit`
- `portfolio-rename`

## Entities

- `pf-name-input`
- `stopPropagation`
- `static/js/portfolio.js`
