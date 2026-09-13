---
type: source
title: "Portfolio name input — use field-sizing: content, not a pixel floor"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/portfolio-name-input-use-field-sizing-content-not-a-pixel-floor-2026-09-06.md"
original_sha256: "fd3e8bf4d2f8b8700473c08b49de4aeac2a9c774750ae27626e96ec294b6bfd4"
stored_path: ".raw/captured/fd3e8bf4d2f8b8700473c08b49de4aeac2a9c774750ae27626e96ec294b6bfd4.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Portfolio name input — use field-sizing: content, not a pixel floor

The previous min-width: 160px layout-shift fix caused SHORT names like 'IRA' to render at 160px (wider than the 30px title), pushing siblings right. Replaced with field-sizing: content plus min-width: 8ch, which sizes to content and uses a character-width floor.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/portfolio-name-input-use-field-sizing-content-not-a-pixel-floor-2026-09-06.md`
  - SHA-256: `fd3e8bf4d2f8b8700473c08b49de4aeac2a9c774750ae27626e96ec294b6bfd4`
- **Captured:** `.raw/captured/fd3e8bf4d2f8b8700473c08b49de4aeac2a9c774750ae27626e96ec294b6bfd4.md`

## Key claims

- Inline-edit inputs should use field-sizing: content with min-width in ch units, not fixed pixel values.
- Fixed pixel floors regress for SHORT names; character widths scale with font size.

## Concepts

- `portfolio-rename`
- `field-sizing`
- `layout-shift`

## Entities

- `pf-name-input`
- `field-sizing: content`
- `min-width: 8ch`
