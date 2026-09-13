---
type: source
title: "Why Phase 1 ran ahead of Phase 0"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/why-phase-1-ran-ahead-of-phase-0-2026-09-06.md"
original_sha256: "09e86b40e1e41a1606396b98bee81509a9f3d71c8851531bce296da65f23909e"
stored_path: ".raw/captured/09e86b40e1e41a1606396b98bee81509a9f3d71c8851531bce296da65f23909e.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Why Phase 1 ran ahead of Phase 0

Phase 1 docs split went in while Phase 0 still had open bugs because Phase 0's bugs needed durable root-cause records (DECISIONS.md, HANDOFF.md, SESSION_LOG.md) that survive context resets. Diagnosing Phase 0 bugs without those docs would re-introduce the 'rediscover the failed approach' failure mode.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/why-phase-1-ran-ahead-of-phase-0-2026-09-06.md`
  - SHA-256: `09e86b40e1e41a1606396b98bee81509a9f3d71c8851531bce296da65f23909e`
- **Captured:** `.raw/captured/09e86b40e1e41a1606396b98bee81509a9f3d71c8851531bce296da65f23909e.md`

## Key claims

- Phase 1 docs split was a prerequisite for Phase 0 bug diagnosis — the docs provide durable root-cause records that survive context resets.

## Concepts

- `roadmap-discipline`
- `docs-infrastructure`
- `session-continuity`

## Entities

- `ROADMAP.md`
- `DECISIONS.md`
- `HANDOFF.md`
