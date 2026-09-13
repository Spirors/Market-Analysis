---
type: source
title: "Every data-card in index.html must also appear in CARD_BAND"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/every-data-card-in-index-html-must-also-appear-in-card-band-2026-09-06.md"
original_sha256: "96e05d71a7e326a7908e09536b7d61bf805a8287de515935ae776632b70e574a"
stored_path: ".raw/captured/96e05d71a7e326a7908e09536b7d61bf805a8287de515935ae776632b70e574a.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Every data-card in index.html must also appear in CARD_BAND

CARD_BAND in layout.js was missing the 'portfolio' entry, so persistLayoutFromDOM saved layouts containing it but applyLayoutOnLoad silently rejected them, reverting to HTML source order on every F5. A regression test now checks CARD_BAND includes every [data-card] in index.html.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/every-data-card-in-index-html-must-also-appear-in-card-band-2026-09-06.md`
  - SHA-256: `96e05d71a7e326a7908e09536b7d61bf805a8287de515935ae776632b70e574a`
- **Captured:** `.raw/captured/96e05d71a7e326a7908e09536b7d61bf805a8287de515935ae776632b70e574a.md`

## Key claims

- Any new <section data-card> in index.html must be added to CARD_BAND in layout.js in the same commit.
- A regression test checks CARD_BAND includes every [data-card] in index.html — extending either side without the other fails the test.

## Concepts

- `dashboard-layout`
- `card-band`
- `layout-persistence`

## Entities

- `CARD_BAND`
- `static/js/layout.js`
- `6825c0f`
