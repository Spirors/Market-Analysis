# 2026-09-06 — Phase 0 stuck-process regression closed (commit pending)

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

## 2026-09-06 - Phase 0 stuck-process regression closed (commit pending)

Trigger observed mid-session: an interactive test launch left
python run.py --open-browser bound to 127.0.0.1:8000 for 54+ minutes
because the agent's turn ended before the documented reap step. PID 9224
seen via Get-NetTCPConnection -LocalPort 8000, confirmed
python run.py --open-browser via Get-CimInstance Win32_Process.
Reaped during this session after the fix shipped.

Root cause: launch-test-reap is documented in AGENTS.md and
project_rules/RUNBOOK.md but enforcement is purely procedural. No runtime
backstop existed. Previous scheduler fix cc7f476 made the launch side
reliable (pythonw ban, lockfile, PID liveness) but did not address the
reap side.

Fix shipped in this session:

- New module app/lifecycle.py with write_server_pid_file(),
  
emove_server_pid_file(), start_auto_reap_watchdog(seconds).
  Server.pid records pid + parent_pid + started at startup, is
  cleaned on /api/shutdown and atexit, refuses to unlink foreign
  pids. Watchdog polls os.getppid() via app.lockfile._pid_alive
  every 10s and calls os._exit(0) once the parent has been gone for
  the configured grace (default 0 = disabled for desktop).
- 
un.py now writes data/server.pid at startup (also atexit-cleaned)
  and accepts --auto-reap <seconds> (or the env var
  MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S).
- app/api.py /api/shutdown removes the pid file before scheduling
  os._exit(0).
- project_rules/RUNBOOK.md ┬ºStep 3a documents the new flag + the manual orphan-
  recovery recipe (Get-Content data\server.pid -> Stop-Process -Id
  <pid> -Force -> Remove-Item data\server.pid).
- project_rules/DECISIONS.md Open entry replaced with confirmed root cause,
  fix details, and runbook additions.

Tests:

- tests/test_lifecycle.py (new, 13 tests): watchdog zero/negative/no-op,
  watchdog spawns thread, watchdog exits on parent-dead, watchdog does
  NOT exit when parent is alive, watchdog no-ops when os.getppid()==0,
  server.pid write/remove semantics (matching pid, foreign pid, missing
  file), /api/shutdown integration, env var name stability, clean
  import.
- tests/test_run.py (6 new tests): --auto-reap 0 no-op,
  --auto-reap N forwarded, env var fallback, flag overrides env,
  server.pid written at startup, atexit cleanup.
- Red-green verified: with the fix reverted, 	est_shutdown_endpoint_
  removes_server_pid fails.
- Full suite: 425 passed (excluding 	est_thirteenf.py, network-heavy
  and slow). 	est_service_coverage.py ran cleanly alone (62s, 25 tests).

Also reconciled ROADMAP.md:

- Phase 1 checkboxes flipped to done (docs split + project-rules skill
  shipped in commits 52e5b92, 8583711). Status line added noting
  the close.
- Phase 0 #1 flipped to done. Phase 0 #5 (session-continuity docs)
  also flipped to done (the docs split covered it). Phase 0 #6
  (full test suite) marked partially done ΓÇö current suite passes; a
  final re-run after the remaining Phase 0 fixes close is queued.
- One-line note added to project_rules/DECISIONS.md explaining why Phase 1
  ran ahead of Phase 0 (docs were a prerequisite for preserving
  Phase 0 root-cause context across sessions).

Next session: Phase 0 #2 (section-position not persisting) and #3
(earnings-watchlist add) - both share the same `tickerTable.js`
cross-section-state risk profile; fix both in one change with per-section
round-trip regression tests.


