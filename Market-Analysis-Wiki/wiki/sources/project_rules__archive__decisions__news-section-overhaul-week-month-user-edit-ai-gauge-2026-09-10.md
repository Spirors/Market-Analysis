---
type: source
title: "News section overhaul — umbrella decision"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/news-section-overhaul-week-month-user-edit-ai-gauge-2026-09-10.md"
original_sha256: "0acf89cb86dc61b50c11662656586962b28d7b17ddf91e9bb9b9613ddfe06640"
stored_path: ".raw/captured/0acf89cb86dc61b50c11662656586962b28d7b17ddf91e9bb9b9613ddfe06640.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# News section overhaul — umbrella decision

Three coordinated news features shipped in one commit (4734cc9): week/month grouping toggle with persistence, user_edited lock for tag preservation, and AI gauge auto-refresh after AI tag edits. Bundled to avoid intermediate import-before-export states.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/news-section-overhaul-week-month-user-edit-ai-gauge-2026-09-10.md`
  - SHA-256: `0acf89cb86dc61b50c11662656586962b28d7b17ddf91e9bb9b9613ddfe06640`
- **Captured:** `.raw/captured/0acf89cb86dc61b50c11662656586962b28d7b17ddf91e9bb9b9613ddfe06640.md`

## Key claims

- Three features shipped as one commit to avoid intermediate states where events.js imports cards.js export before it exists.
- Week/month grouping toggle persists via tlGroupingMode + tlSelectedMonth; generic buildGroups(items, mode) in events.js.

## Concepts

- `news-overhaul`
- `umbrella-decision`
- `single-commit`

## Entities

- `4734cc9`
- `buildGroups`
- `tlGroupingMode`
