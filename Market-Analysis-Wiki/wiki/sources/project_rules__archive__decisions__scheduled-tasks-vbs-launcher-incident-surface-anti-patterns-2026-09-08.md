---
type: source
title: "Scheduled tasks + VBS launcher — incident surface + anti-patterns"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/scheduled-tasks-vbs-launcher-incident-surface-anti-patterns-2026-09-08.md"
original_sha256: "6e75118a9097bcc4e07c8a98a2e3f4b94bcfc4f1abfd7c9837e579f8f3b50725"
stored_path: ".raw/captured/6e75118a9097bcc4e07c8a98a2e3f4b94bcfc4f1abfd7c9837e579f8f3b50725.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Scheduled tasks + VBS launcher — incident surface + anti-patterns

The 3-task Windows Task Scheduler setup and VBS launch pattern were audited and documented in RUNBOOK.md, including the 'stuck scheduled refresh' recovery procedure, anti-patterns for wrong launch paths, and the boundary between --auto-reap (python-side watchdog) and EXECUTION_TIME_LIMIT (schtasks-side hard kill).

## Citation

- **Original:** `inbox/project_rules/archive/decisions/scheduled-tasks-vbs-launcher-incident-surface-anti-patterns-2026-09-08.md`
  - SHA-256: `6e75118a9097bcc4e07c8a98a2e3f4b94bcfc4f1abfd7c9837e579f8f3b50725`
- **Captured:** `.raw/captured/6e75118a9097bcc4e07c8a98a2e3f4b94bcfc4f1abfd7c9837e579f8f3b50725.md`

## Key claims

- RUNBOOK.md now documents the 3-task scheduler setup, recovery procedures, and enumerated launch-path anti-patterns.
- launch.vbs had zero test coverage — 4 tests added mirroring the scheduler.vbs test shape.

## Concepts

- `scheduled-tasks`
- `vbs-launcher`
- `incident-documentation`

## Entities

- `scheduler.vbs`
- `launch.vbs`
- `project_rules/RUNBOOK.md`
