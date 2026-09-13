---
type: source
title: "Stuck process on test launch — root cause + runtime fix"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/stuck-process-on-test-launch-root-cause-runtime-fix-2026-09-06.md"
original_sha256: "beabab0452712b9c40eec35269703d782dd2903da2aaf677c1924e31fcb9dc44"
stored_path: ".raw/captured/beabab0452712b9c40eec35269703d782dd2903da2aaf677c1924e31fcb9dc44.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Stuck process on test launch — root cause + runtime fix

A python child bound to port 8000 for 54+ minutes after an interactive launch ended before the reap step. The fix adds write_server_pid_file / remove_server_pid_file / start_auto_reap_watchdog to app/lifecycle.py, with agent terminals using --auto-reap 60.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/stuck-process-on-test-launch-root-cause-runtime-fix-2026-09-06.md`
  - SHA-256: `beabab0452712b9c40eec35269703d782dd2903da2aaf677c1924e31fcb9dc44`
- **Captured:** `.raw/captured/beabab0452712b9c40eec35269703d782dd2903da2aaf677c1924e31fcb9dc44.md`

## Key claims

- write_server_pid_file records pid/parent_pid/started_at at startup; start_auto_reap_watchdog polls parent PID and calls os._exit(0) once the parent has been gone for the grace period.
- Agent terminal launches MUST use --auto-reap 60; desktop .lnk launches leave it at 0.

## Concepts

- `process-lifecycle`
- `auto-reap`
- `server-pid`

## Entities

- `app/lifecycle.py`
- `--auto-reap`
- `data/server.pid`
