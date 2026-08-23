"""Tests for the cross-process refresh lockfile (app/lockfile.py)."""

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
    tmp_lock.write_text("pid=1234 started=long ago\n")
    old = time.time() - (lockfile.STALE_LOCK_SECONDS + 60)
    import os
    os.utime(tmp_lock, (old, old))

    with lockfile.refresh_lock():  # must not raise
        pass


def test_fresh_foreign_lock_is_respected(tmp_lock):
    tmp_lock.write_text("pid=9999 started=just now\n")

    with pytest.raises(lockfile.RefreshBusy):
        with lockfile.refresh_lock():
            pass
