---
type: source
title: "Runbook — Operational Procedures"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/RUNBOOK.md"
original_sha256: "3425c26559751a10652d1478e7e58d6df0f3395c6ca0ea354cde732453392a27"
stored_path: ".raw/captured/3425c26559751a10652d1478e7e58d6df0f3395c6ca0ea354cde732453392a27.md"
source_kind: "runbook"
tags:
  - source
  - runbook
---

# Runbook — Operational Procedures

Exact operational procedures: server lifecycle checklist (TestClient first, hidden launch with VBS, --auto-reap 60, reap before turn end, verify gone, clear PID file), 3-task Windows Task Scheduler setup (DailyRefresh 09:00, NewsRefresh every 4h, EventsCommit 17:00), anti-patterns for launch paths that bypass the runtime backstop, commit conventions (events.json is scheduler-owned), and future browser automation stealth guidance.

## Citation

- **Original:** `inbox/project_rules/RUNBOOK.md`
  - SHA-256: `3425c26559751a10652d1478e7e58d6df0f3395c6ca0ea354cde732453392a27`
- **Captured:** `.raw/captured/3425c26559751a10652d1478e7e58d6df0f3395c6ca0ea354cde732453392a27.md`

## Key claims

- Always try TestClient first before launching a real server; it needs a Host header to pass DNS-rebinding middleware.
  - *Evidence:* "Step 1 — try `TestClient` first. In-process, no port binding, no orphan risk."
- Never use Start-Process, nohup, & , or pythonw.exe — use VBS wrapper with shell.Run or --auto-reap 60.
  - *Evidence:* "Never `Start-Process`, `nohup`, `&`, or `Invoke-Expression`. Never `pythonw.exe`"
- data/events.json is owned by the MarketAnalysis-EventsCommit scheduled task; never commit it from interactive sessions.
  - *Evidence:* "`data/events.json` changes are batched and committed once daily by the `MarketAnalysis-EventsCommit` scheduled task (17:00 local)."
- Scheduled tasks run as InteractiveToken and silently do NOT run while the user is logged off.
  - *Evidence:* "All three are installed as **InteractiveToken** (no admin, no password), which means they silently do NOT run while the user is logged off"
- Do NOT pass --auto-reap to a scheduled refresh — the watchdog would kill the refresh within seconds because scheduler.vbs returns immediately (do-not-wait).
  - *Evidence:* "Do NOT pass `--auto-reap <n>` to a scheduled refresh — the watchdog's "parent gone" trigger would fire within `n` seconds of `wscript.exe` exiting"

## Concepts

- `server-lifecycle`
- `process-hygiene`
- `auto-reap-watchdog`
- `anti-patterns`
- `scheduled-tasks`
- `commit-conventions`
- `browser-automation-stealth`

## Entities

- `app/lifecycle.py`
- `app/scheduler.py`
- `app/run.py`
- `app/lockfile.py`
- `app/api.py`
- `data/server.pid`
- `data/refresh.lock`
- `wscript.exe`
- `scheduler.vbs`
- `launch.vbs`
- `launch.bat`
