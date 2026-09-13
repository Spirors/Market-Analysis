---
type: source
title: "Earnings cache-miss path must not trigger a full universe rebuild"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/earnings-cache-miss-path-must-not-trigger-a-full-universe-rebuild-2026-09-06.md"
original_sha256: "1080e97128f7b943f0ccdeb3446eefe7c01512321a36e2c05a0b576b12b7bf51"
stored_path: ".raw/captured/1080e97128f7b943f0ccdeb3446eefe7c01512321a36e2c05a0b576b12b7bf51.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Earnings cache-miss path must not trigger a full universe rebuild

When a cache is missing after an additive mutation, the code must build just the affected state inline or invalidate and return — never fall through to a full universe rebuild. A full rebuild should only run from explicit user action or the scheduled task.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/earnings-cache-miss-path-must-not-trigger-a-full-universe-rebuild-2026-09-06.md`
  - SHA-256: `1080e97128f7b943f0ccdeb3446eefe7c01512321a36e2c05a0b576b12b7bf51`
- **Captured:** `.raw/captured/1080e97128f7b943f0ccdeb3446eefe7c01512321a36e2c05a0b576b12b7bf51.md`

## Key claims

- Cache-patching helpers must not fall through to a full rebuild on cache miss; either patch minimally or invalidate.
- Full rebuilds should only run from explicit user action (Refresh button) or the scheduled task, never from an additive mutation side-effect.

## Concepts

- `cache-patching`
- `earnings-cache`
- `mutation-latency`

## Entities

- `app/earnings.py`
- `80d0fef`
- `_enrich`
