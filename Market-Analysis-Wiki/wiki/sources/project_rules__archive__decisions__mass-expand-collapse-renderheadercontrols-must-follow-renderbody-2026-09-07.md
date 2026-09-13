---
type: source
title: "Mass expand/collapse — renderHeaderControls must follow renderBody"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/mass-expand-collapse-renderheadercontrols-must-follow-renderbody-2026-09-07.md"
original_sha256: "866120862a92ec05c8944874324111242165fa2d5a23cadf7e4e69057d977736"
stored_path: ".raw/captured/866120862a92ec05c8944874324111242165fa2d5a23cadf7e4e69057d977736.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Mass expand/collapse — renderHeaderControls must follow renderBody

The toggle-all click handler must call both renderBody() and renderHeaderControls() because it mutates state read by both containers. Calling only renderBody left the label stuck on '▼ all' forever, making the button look unresponsive even though the bodies toggled correctly.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/mass-expand-collapse-renderheadercontrols-must-follow-renderbody-2026-09-07.md`
  - SHA-256: `866120862a92ec05c8944874324111242165fa2d5a23cadf7e4e69057d977736`
- **Captured:** `.raw/captured/866120862a92ec05c8944874324111242165fa2d5a23cadf7e4e69057d977736.md`

## Key claims

- Any click handler mutating state read by renderHeaderControls must call both renderBody() and renderHeaderControls().
- The same pattern applies to any sibling rebuilder — a state mutation affecting multiple containers must re-render all of them.

## Concepts

- `toggle-all`
- `render-order`
- `sibling-rebuilders`

## Entities

- `renderHeaderControls`
- `renderBody`
- `.pf-toggle-all`
