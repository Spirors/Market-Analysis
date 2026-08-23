"""Cross-process refresh lock (lockfile under data/).

The in-process ``service._refresh_lock`` already serializes refreshes within
the uvicorn server; this lockfile covers separate OS processes — the 09:00
daily ``--refresh`` task and the 4-hourly ``--news-refresh`` task can overlap
the server's own refreshes. Without it, two processes race yfinance (rate-limit
bait) and the SQLite event store.

Semantics: non-blocking. ``refresh_lock()`` raises :class:`RefreshBusy` when
another process holds the lock; callers decide whether to skip-and-log (CLI
tasks) or serve cached data (server). A lock older than STALE_LOCK_SECONDS is
broken automatically, e.g. after a hard crash or power loss mid-refresh.
"""

import os
import time
from contextlib import contextmanager
from typing import Iterator

from . import config

LOCK_PATH = config.DATA_DIR / "refresh.lock"
# Matches the scheduler's 4-hour hard kill limit: a live task can never be
# wrongly considered stale, while a killed one cannot wedge future runs.
STALE_LOCK_SECONDS = 4 * 3600


class RefreshBusy(RuntimeError):
    """Another process currently holds the refresh lock."""


def _break_stale_lock() -> None:
    try:
        age = time.time() - LOCK_PATH.stat().st_mtime
    except OSError:
        return  # no lock file (or unreadable) -> nothing to break
    if age > STALE_LOCK_SECONDS:
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
