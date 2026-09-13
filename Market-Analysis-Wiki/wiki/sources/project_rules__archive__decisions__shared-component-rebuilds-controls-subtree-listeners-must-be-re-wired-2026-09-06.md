---
type: source
title: "Shared component rebuilds controls subtree — listeners must be re-wired"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/shared-component-rebuilds-controls-subtree-listeners-must-be-re-wired-2026-09-06.md"
original_sha256: "09864eb4aa1637d1d64ae4808544ffd398ae3b2978c2092701f2504fce27e787"
stored_path: ".raw/captured/09864eb4aa1637d1d64ae4808544ffd398ae3b2978c2092701f2504fce27e787.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Shared component rebuilds controls subtree — listeners must be re-wired

When drawControls() rebuilds the controls subtree via innerHTML, any one-shot wireAddInput() call from the initial render is lost. wireAddInput() now runs at the end of drawControls() so listeners are re-attached on every rebuild; event delegation on a stable container is the safer alternative.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/shared-component-rebuilds-controls-subtree-listeners-must-be-re-wired-2026-09-06.md`
  - SHA-256: `09864eb4aa1637d1d64ae4808544ffd398ae3b2978c2092701f2504fce27e787`
- **Captured:** `.raw/captured/09864eb4aa1637d1d64ae4808544ffd398ae3b2978c2092701f2504fce27e787.md`

## Key claims

- wireAddInput() now runs inside drawControls() so listeners are re-attached on every controls rebuild.
- Shared components that rebuild subtrees with interactive elements must re-wire listeners inside the rebuild path, not rely on a one-shot setup.

## Concepts

- `shared-component`
- `listener-rebinding`
- `controls-rebuild`

## Entities

- `tickerTable.js`
- `drawControls`
- `wireAddInput`
