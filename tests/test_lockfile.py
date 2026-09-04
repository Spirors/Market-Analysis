"""Tests for the cross-process refresh lockfile (app/lockfile.py)."""

import os
import time

import pytest

from app import lockfile


@pytest.fixture
def tmp_lock(monkeypatch, tmp_path):
    monkeypatch.setattr(lockfile, "LOCK_PATH", tmp_path / "refresh.lock")
    return lockfile.LOCK_PATH


def test_acquire_and_release(tmp_lock):
    with lockfile.refresh_lock():
        assert tmp_lock.exists()
    assert not tmp_lock.exists()  # released


def test_second_acquire_raises_while_held(tmp_lock):
    with lockfile.refresh_lock():
        with pytest.raises(lockfile.RefreshBusy):
            with lockfile.refresh_lock():
                pass
    # After release the lock is free again.
    with lockfile.refresh_lock():
        pass


def test_stale_lock_is_broken(tmp_lock):
    """A lock older than STALE_LOCK_SECONDS is broken automatically."""
    tmp_lock.write_text(f"pid={os.getpid()} started=long ago\n")
    old = time.time() - (lockfile.STALE_LOCK_SECONDS + 60)
    os.utime(tmp_lock, (old, old))

    with lockfile.refresh_lock():  # must not raise
        pass


def test_fresh_foreign_lock_held_by_live_pid_is_respected(tmp_lock):
    """A fresh lock whose holding PID is still alive is respected.

    We write the current process's PID (guaranteed alive) so the PID
    liveness check passes and we exercise the age-based freshness path.
    """
    tmp_lock.write_text(f"pid={os.getpid()} started=just now\n")

    with pytest.raises(lockfile.RefreshBusy):
        with lockfile.refresh_lock():
            pass


def test_lock_held_by_dead_pid_is_broken_immediately(tmp_lock):
    """A fresh-AGE lock whose holding PID is no longer alive is broken
    immediately (not waiting for STALE_LOCK_SECONDS).  Uses a PID that
    is highly unlikely to exist on any real system.
    """
    # 999_999 is far above typical user-mode PID ranges on Windows.
    tmp_lock.write_text("pid=999999 started=just now\n")

    # Must not raise: the dead-PID branch in _break_stale_lock unlinks
    # the file before refresh_lock tries to acquire.
    with lockfile.refresh_lock():
        pass


def test_read_lock_pid_returns_none_for_missing_file(tmp_lock):
    """_read_lock_pid returns None when the lock file does not exist."""
    assert lockfile._read_lock_pid() is None


def test_read_lock_pid_parses_valid_content(tmp_lock):
    """_read_lock_pid returns the parsed int PID from a valid file."""
    tmp_lock.write_text("pid=4242 started=2026-09-04 10:00:00\n")
    assert lockfile._read_lock_pid() == 4242


def test_read_lock_pid_returns_none_for_garbage_content(tmp_lock):
    """_read_lock_pid returns None for malformed content."""
    tmp_lock.write_text("not a pid line\n")
    assert lockfile._read_lock_pid() is None


def test_pid_alive_returns_false_for_zero_or_negative():
    """_pid_alive returns False for non-positive PIDs (defensive guard)."""
    assert lockfile._pid_alive(0) is False
    assert lockfile._pid_alive(-1) is False


def test_pid_alive_returns_true_for_current_process():
    """_pid_alive returns True for the currently-running PID."""
    assert lockfile._pid_alive(os.getpid()) is True


def test_pid_alive_returns_false_for_nonexistent_pid():
    """_pid_alive returns False for a PID that doesn't exist on this host."""
    # 999_999 is far above typical Windows user-mode PID ranges.
    assert lockfile._pid_alive(999_999) is False


def test_stale_lock_seconds_is_10_minutes():
    """Regression guard: the threshold is 10 min, not the old 4 hours."""
    assert lockfile.STALE_LOCK_SECONDS == 10 * 60
