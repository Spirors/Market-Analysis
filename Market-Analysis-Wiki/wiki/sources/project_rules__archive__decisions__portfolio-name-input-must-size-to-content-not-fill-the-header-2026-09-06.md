---
type: source
title: "Portfolio name input must size to content, not fill the header"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/portfolio-name-input-must-size-to-content-not-fill-the-header-2026-09-06.md"
original_sha256: "bbe87ff47eec7a9934ddf4c9c9c71b02b4d58bef3b33f8af213b951923ca15f4"
stored_path: ".raw/captured/bbe87ff47eec7a9934ddf4c9c9c71b02b4d58bef3b33f8af213b951923ca15f4.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Portfolio name input must size to content, not fill the header

The inline rename input had flex: 1 which stretched it to ~87% of header width, leaving no clickable area outside for blur/commit. Changed to flex: 0 0 auto; width: auto so the input sizes to content and the surrounding container remains clickable.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/portfolio-name-input-must-size-to-content-not-fill-the-header-2026-09-06.md`
  - SHA-256: `bbe87ff47eec7a9934ddf4c9c9c71b02b4d58bef3b33f8af213b951923ca15f4`
- **Captured:** `.raw/captured/bbe87ff47eec7a9934ddf4c9c9c71b02b4d58bef3b33f8af213b951923ca15f4.md`

## Key claims

- Transient edit inputs must not default to flex: 1 in flex containers; size to content so the click-outside-to-blur UX works.
- Superseded by the field-sizing: content refinement in a later decision.

## Concepts

- `portfolio-rename`
- `flex-sizing`
- `click-outside-to-blur`

## Entities

- `pf-name-input`
- `flex: 1`
- `4716e02`
