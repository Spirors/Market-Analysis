"""Cross-process refresh lock (lockfile under data/).

The in-process ``service._refresh_lock`` already serializes refreshes within
the uvicorn server; this lockfile covers separate OS processes — the 09:00
daily ``--refresh`` task and the 4-hourly ``--news-refresh`` task can overlap
the server's own refreshes. Without it, two processes race yfinance (rate-limit
bait) and the SQLite event store.

Semantics: non-blocking. ``refresh_lock()`` raises :class:`RefreshBusy` when
another process holds the lock; callers decide whether to skip-and-log (CLI
tasks) or serve cached data (server).  Stale locks are broken automatically in
two ways: (1) age-based — a lock older than STALE_LOCK_SECONDS (10 min) is
assumed dead, and (2) PID-based — if the holding PID is no longer alive
(determined by a platform-specific probe: Windows ``GetExitCodeProcess``,
POSIX ``os.kill(pid, 0)``), the lock is broken immediately regardless of age.
This recovers from crashes or hard kills within seconds rather than waiting
hours.
"""

import os
import sys
import time
from contextlib import contextmanager
from typing import Iterator

from . import config

LOCK_PATH = config.DATA_DIR / "refresh.lock"
# 10 minutes is generous for a full refresh (~1-2 min) while still recovering
# from crashes/kills within a reasonable window.  PID liveness (below) handles
# immediate recovery for still-tracked PIDs.
STALE_LOCK_SECONDS = 10 * 60


class RefreshBusy(RuntimeError):
    """Another process currently holds the refresh lock."""


def _pid_alive(pid: int) -> bool:
    """Best-effort, never-raising PID liveness check.

    Returns True iff the PID exists and is still active (i.e. has not
    exited).  Returns False for unknown / non-existent / non-permitted
    PIDs — callers treat False as "lock is stale, safe to break".

    Windows: ``GetExitCodeProcess`` distinguishes a live process from a
    PID that exists but has already exited.  POSIX: ``os.kill(pid, 0)``
    probes existence; ``PermissionError`` means the process exists but is
    owned by another user, which counts as alive.

    The whole body is wrapped so an unexpected failure (e.g. a missing
    ``ctypes.windll`` on a non-Windows host) degrades to False rather than
    escaping — the docstring's best-effort promise is load-bearing for
    ``_break_stale_lock`` / ``refresh_lock``.
    """
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return exit_code.value == STILL_ACTIVE
                return False
            finally:
                kernel32.CloseHandle(handle)

        # POSIX: signal 0 performs the permission / existence check without
        # delivering a signal.
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # exists but owned by another user
        except OSError:
            return False
        return True
    except Exception:
        return False


def _read_lock_pid() -> int | None:
    """Read the PID from the lock file, if present.

    Returns None when the file is missing, unreadable, or doesn't
    contain a parseable ``pid=N`` line.  Callers treat None as
    "fall back to age-based staleness".
    """
    try:
        with open(LOCK_PATH, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("pid="):
                    return int(line.split("=", 1)[1].split()[0])
    except (OSError, ValueError):
        pass
    return None


def _break_stale_lock() -> None:
    try:
        stat = LOCK_PATH.stat()
    except OSError:
        return  # no lock file (or unreadable) -> nothing to break
    age = time.time() - stat.st_mtime
    is_stale_by_age = age > STALE_LOCK_SECONDS
    if not is_stale_by_age:
        # Even within the staleness window, break the lock if the
        # holding PID is no longer alive — a crashed/killed task
        # shouldn't block future runs.
        pid = _read_lock_pid()
        if pid is not None and not _pid_alive(pid):
            pass  # stale by PID; break below
        else:
            return  # fresh and held by a live PID
    try:
        LOCK_PATH.unlink()
    except OSError:
        pass  # another process may have broken it first; O_EXCL still guards


@contextmanager
def refresh_lock() -> Iterator[None]:
    """Hold the cross-process refresh lock, or raise RefreshBusy immediately."""
    config.ensure_dirs()
    _break_stale_lock()
    try:
        fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RefreshBusy(f"another process holds {LOCK_PATH}")
    try:
        os.write(fd, f"pid={os.getpid()} started={time.strftime('%Y-%m-%d %H:%M:%S')}\n".encode())
    except OSError:
        pass  # diagnostics only
    finally:
        os.close(fd)
    try:
        yield
    finally:
        try:
            LOCK_PATH.unlink()
        except OSError:
            pass
