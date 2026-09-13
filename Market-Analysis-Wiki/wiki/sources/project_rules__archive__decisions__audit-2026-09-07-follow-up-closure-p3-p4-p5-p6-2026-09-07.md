---
type: source
title: "Audit 2026-09-07 follow-up closure — P3/P4/P5/P6"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/audit-2026-09-07-follow-up-closure-p3-p4-p5-p6-2026-09-07.md"
original_sha256: "f187ef16894fb812ed3e4b51fb4ef5444b1af3736da2fc551ddfc526daa49dc4"
stored_path: ".raw/captured/f187ef16894fb812ed3e4b51fb4ef5444b1af3736da2fc551ddfc526daa49dc4.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Audit 2026-09-07 follow-up closure — P3/P4/P5/P6

Closed remaining audit follow-ups: test files must run by default (don't hide broken tests via exclusion), stale references must be cleaned on module removal, and doc drift must be audited after any module removal. Test suite grew from 384 to 421 passing tests.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/audit-2026-09-07-follow-up-closure-p3-p4-p5-p6-2026-09-07.md`
  - SHA-256: `f187ef16894fb812ed3e4b51fb4ef5444b1af3736da2fc551ddfc526daa49dc4`
- **Captured:** `.raw/captured/f187ef16894fb812ed3e4b51fb4ef5444b1af3736da2fc551ddfc526daa49dc4.md`

## Key claims

- Test files must not be added to --ignore= for long-runtime reasons; fix the slowness instead to prevent silent regressions.
- When removing a module, grep for its name across all code, tests, skills, and docs in one pass and fix every stale reference in the same commit.

## Concepts

- `test-hygiene`
- `module-removal`
- `doc-drift`

## Entities

- `tests/test_service_coverage.py`
- `tests/test_thirteenf.py`
- `app/earnings.py`
