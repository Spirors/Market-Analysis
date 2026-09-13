---
type: source
title: "Agent terminal servers — Start-Process and manual reap is a trap"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/agent-terminal-servers-start-process-and-manual-reap-is-a-trap-2026-09-08.md"
original_sha256: "e81408ca111e7c8b62b331a2b79baf55bb492f22b548bf8b8f830a0664abebfb"
stored_path: ".raw/captured/e81408ca111e7c8b62b331a2b79baf55bb492f22b548bf8b8f830a0664abebfb.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Agent terminal servers — Start-Process and manual reap is a trap

Using Start-Process to launch a static HTTP server from an agent terminal is always wrong: the launcher exits immediately, leaving an orphaned python child with no trackable parent, and the manual reap fails on PID 0 / TimeWait entries. The approved paths are Playwright webServer for test-only servers and --auto-reap for agent-launched processes.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/agent-terminal-servers-start-process-and-manual-reap-is-a-trap-2026-09-08.md`
  - SHA-256: `e81408ca111e7c8b62b331a2b79baf55bb492f22b548bf8b8f830a0664abebfb`
- **Captured:** `.raw/captured/e81408ca111e7c8b62b331a2b79baf55bb492f22b548bf8b8f830a0664abebfb.md`

## Key claims

- Start-Process / nohup / & / Invoke-Expression must never be used to launch long-running processes from an agent terminal; use Playwright webServer or --auto-reap instead.
- When reaping by Get-NetTCPConnection, filter PID 0 (OwningProcess -gt 0) to avoid Access Denied errors from TimeWait entries.

## Concepts

- `process-hygiene`
- `runbook-compliance`
- `reap-discipline`

## Entities

- `Start-Process`
- `webServer`
- `project_rules/RUNBOOK.md`
