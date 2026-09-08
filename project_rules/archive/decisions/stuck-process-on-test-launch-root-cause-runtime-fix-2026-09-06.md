# Stuck process on test launch — root cause + runtime fix (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Stuck process on test launch — root cause + runtime fix (2026-09-06)

**Status:** confirmed + fixed. Runtime backstop in `app/lifecycle.py`;
CLI flag `--auto-reap` + env var `MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S`
documented in `project_rules/RUNBOOK.md`.

**Trigger:** an interactive launch of `python run.py --open-browser`
on 2026-09-06 ended the turn before the reap step. The python child
stayed bound to `127.0.0.1:8000` for 54+ minutes until a later session
noticed `Test-NetConnection -Port 8000 = True`.

**Root cause:** `launch-test-reap` was purely procedural — no runtime
backstop. The previous scheduler fix (`cc7f476`) hardened the *launch*
side (pythonw ban, lockfile, PID liveness) but not the *reap* side.

**Fix (`app/lifecycle.py`):**

- `write_server_pid_file()` — records pid / parent_pid / started at
  startup under `data/server.pid`. Lets the next session locate a stray
  instance immediately.
- `remove_server_pid_file()` — best-effort cleanup on `/api/shutdown` +
  `atexit`. Refuses to unlink a foreign pid so a previous orphan isn't
  silently hidden.
- `start_auto_reap_watchdog(s)` — daemon thread polls parent PID via
  `app.lockfile._pid_alive` and `os._exit(0)` once the parent has been
  gone for the configured grace. Default 0 = disabled (desktop launches
  where parent is `wscript.exe`). Agent terminals pass `--auto-reap 60`
  so a forgotten reap becomes "agent reaps itself".

**Runbook additions (see `project_rules/RUNBOOK.md`):**

- Agent terminal launches MUST use `--auto-reap 60` (or the env var).
- Desktop `.lnk` launches leave `--auto-reap` at 0 (normal lifecycle is
  `launch.vbs` → python → browser → `/api/shutdown` → exit with
  `wscript.exe` as parent for the whole session).

Regression coverage: `tests/test_lifecycle.py` (13 tests) +
`tests/test_run.py` (6 new) cover the watchdog, pid-file helpers, CLI
flag, env-var fallback, atexit cleanup, `/api/shutdown` pid-file cleanup.
Red-green verified: with the fix reverted,
`test_shutdown_endpoint_removes_server_pid` fails.

