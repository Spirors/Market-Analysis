"""Server-lifecycle helpers shared by ``run.py`` (startup) and ``app/api.py``
(graceful shutdown endpoint).

These exist because the previous "stuck process on launch" regression (see
``docs/DECISIONS.md``) had no runtime-enforced cleanup path — the agent
runbook said "reap before the turn ends" but nothing in the server itself
backstopped a forgotten reap. Splitting the helpers out of ``run.py``
keeps them importable from ``app.api`` without dragging in the
``uvicorn.run`` side effects.

Public surface:

- ``SERVER_PID_PATH`` — absolute path of the diagnostic pid file under
  ``data/``; written at startup, deleted on graceful shutdown.
- ``write_server_pid_file()`` — record this process's PID + parent PID +
  start time so an orchestrator can locate a stray instance.
- ``remove_server_pid_file()`` — delete the pid file iff it belongs to the
  current process (refuses to unlink a previous orphan's file).
- ``start_auto_reap_watchdog(timeout_after_parent_dead_s)`` — start a
  background thread that calls ``os._exit(0)`` if the launching parent
  process has been dead for ``timeout_after_parent_dead_s`` seconds.
  Pass 0 to disable (the default for desktop launches).
- ``AUTO_REAP_ENV_VAR`` — name of the env var the watchdog also reads, so
  ``$env:MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S=60; python run.py``
  works without restating the timeout as a CLI flag.
- ``AUTO_REAP_PARENT_CHECK_INTERVAL_S`` — how often the watchdog polls
  the parent PID's liveness.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

from . import config

SERVER_PID_PATH: Path = config.DATA_DIR / "server.pid"

AUTO_REAP_ENV_VAR = "MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S"
AUTO_REAP_PARENT_CHECK_INTERVAL_S = 10


def write_server_pid_file() -> None:
    """Record this server's PID + parent PID so any orchestrator can find
    and reap a stray instance.

    The file is rewritten on every startup so a previous orphan's stale
    info never blocks a fresh launch. ``/api/shutdown`` and the run.py
    atexit hook both remove it; if the server is hard-killed, the file
    goes stale and is overwritten on the next startup (no lockfile
    semantics — this is a diagnostic aid, not a serialization primitive).
    """
    try:
        config.ensure_dirs()
        SERVER_PID_PATH.write_text(
            f"pid={os.getpid()} parent_pid={os.getppid()} "
            f"started={time.strftime('%Y-%m-%d %H:%M:%S')}\n",
            encoding="utf-8",
        )
    except OSError:
        # Best-effort: a missing/inaccessible pid file should never
        # block the server from starting.
        pass


def remove_server_pid_file() -> None:
    """Delete ``data/server.pid`` iff it belongs to the current process.

    Refuses to unlink a stale file left by a previous orphan — that's
    deliberately overwritten on the next startup, see
    ``write_server_pid_file``.
    """
    try:
        if not SERVER_PID_PATH.exists():
            return
        first_line = SERVER_PID_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        if first_line and first_line[0].startswith(f"pid={os.getpid()} "):
            SERVER_PID_PATH.unlink()
    except OSError:
        pass  # best-effort cleanup


def start_auto_reap_watchdog(timeout_after_parent_dead_s: float) -> None:
    """Start a background watchdog that exits the server when its launching
    parent process is no longer alive.

    ``timeout_after_parent_dead_s`` is the wall-clock seconds to wait after
    the parent dies before calling ``os._exit(0)``. Pass 0 (or a negative
    value) to disable — desktop launches should always pass 0 so the
    server keeps running across a normal user session.

    Why this exists: ``docs/RUNBOOK.md`` documents the
    launch-test-reap cycle, but an orchestrator-spawned server whose turn
    ends without the reap step leaves a python.exe bound to port 8000 for
    the rest of the day. The watchdog turns "agent forgot to reap" into
    "agent reaps itself" as long as the launching parent process is
    actually traceable and dies when the agent's shell exits.

    False positives are guarded against by the grace timeout and by
    short-lived intermediate parents (PID 0, services.exe reparenting)
    being treated as "no trackable parent" (watchdog no-ops).
    """
    if timeout_after_parent_dead_s <= 0:
        return
    parent_pid = os.getppid()
    if parent_pid <= 0:
        return  # no trackable parent (e.g., services.exe reparenting)

    def _watch() -> None:
        # When the parent first disappears, start a deadline; reset it
        # back to None every time the parent comes back to life (in case
        # a child is briefly reparented across a parent restart).
        deadline = None
        while True:
            time.sleep(AUTO_REAP_PARENT_CHECK_INTERVAL_S)
            try:
                # Local import to keep the top-level dependency surface
                # of this module narrow (the lockfile module pulls in ctypes).
                from .lockfile import _pid_alive
                alive = _pid_alive(parent_pid)
            except Exception:
                continue  # transient: try again next tick
            if alive:
                deadline = None
                continue
            if deadline is None:
                deadline = time.time() + timeout_after_parent_dead_s
                continue
            if time.time() >= deadline:
                try:
                    sys.stderr.write(
                        f"[auto-reap] launching parent pid={parent_pid} has been "
                        f"gone for {timeout_after_parent_dead_s}s; exiting cleanly.\n"
                    )
                except Exception:
                    pass
                os._exit(0)
                # Defensive: os._exit never returns in production. This
                # break is only reached in tests that mock os._exit so
                # the watchdog thread doesn't loop forever and hang the
                # rest of the test run.
                break

    t = threading.Thread(target=_watch, name="auto-reap-watchdog", daemon=True)
    t.start()
