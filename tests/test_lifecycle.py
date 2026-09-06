"""Tests for ``app/lifecycle.py`` — the server.pid tracking and auto-reap
watchdog that backstops the documented ``launch-test-reap`` cycle.

The watchdog is the runtime fix for the "stuck process on launch" regression
(``docs/DECISIONS.md`` — Open entry as of 2026-09-05, confirmed 2026-09-06).
Without it, an agent-spawned ``python run.py --open-browser`` whose turn
ends without the documented reap step leaks a python.exe bound to port 8000
until the user manually ``Stop-Process``-es it.

Regression test priorities (in order):

1. The watchdog fires ``os._exit(0)`` when the launching parent is dead.
2. The watchdog does NOT fire when the launching parent is alive.
3. Disabling (timeout <= 0) means no watchdog thread at all.
4. ``server.pid`` is written at startup with current pid + parent_pid.
5. ``remove_server_pid_file`` refuses to unlink another process's file.
6. ``/api/shutdown`` removes the pid file as part of graceful exit.
"""

from __future__ import annotations

import os
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from app import lifecycle


# ---- auto-reap watchdog -------------------------------------------------------

def _wait_for_threads_matching(predicate, timeout_s: float = 5.0) -> bool:
    """Poll until ``predicate`` returns True or the timeout elapses.

    Threads are scanned by name. Used so the test doesn't have to know the
    watchdog's exact polling interval (currently 10s) — we wait briefly and
    check if the watchdog's internal state has progressed far enough.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_start_auto_reap_watchdog_zero_is_noop():
    """timeout_after_parent_dead_s=0 must NOT spawn the watchdog thread.

    Desktop launches leave this at 0; the watchdog firing during a normal
    user session would be the worst possible failure mode.
    """
    before = {t.name for t in threading.enumerate()}
    lifecycle.start_auto_reap_watchdog(0)
    after = {t.name for t in threading.enumerate()}
    assert "auto-reap-watchdog" not in after - before, (
        "watchdog thread should not be spawned when timeout <= 0"
    )


def test_start_auto_reap_watchdog_negative_is_noop():
    """Negative timeouts are treated as disabled (defensive)."""
    before = {t.name for t in threading.enumerate()}
    lifecycle.start_auto_reap_watchdog(-1)
    after = {t.name for t in threading.enumerate()}
    assert "auto-reap-watchdog" not in after - before


def test_start_auto_reap_watchdog_spawns_thread():
    """Positive timeout spawns exactly one auto-reap-watchdog thread."""
    before = {t.name for t in threading.enumerate()}
    lifecycle.start_auto_reap_watchdog(60)
    try:
        assert _wait_for_threads_matching(
            lambda: any(t.name == "auto-reap-watchdog" for t in threading.enumerate())
        ), "auto-reap-watchdog thread did not appear within 5s"
    finally:
        # The thread runs forever (sleep loop); we can't easily stop it
        # without an injected cancel flag, so we just let it sit. The
        # test process exits at session end and daemon=True reaps it.
        pass


def test_watchdog_exits_when_parent_is_dead(monkeypatch):
    """The watchdog calls ``os._exit(0)`` when the parent PID is dead and
    the grace timeout has elapsed. This is the actual fix for the
    stuck-process regression — the auto-reap turns "agent forgot to reap"
    into "agent reaps itself" once the parent is gone.

    We patch the watchdog's poll interval down to a few ms so the test
    doesn't have to wait the full 10s production interval.
    """
    # Speed up: replace the module's interval constant with 0.05s.
    monkeypatch.setattr(lifecycle, "AUTO_REAP_PARENT_CHECK_INTERVAL_S", 0.05)
    # Pretend the parent PID is already dead (a sentinel that _pid_alive
    # treats as not-alive).
    with patch.object(lifecycle.os, "getppid", return_value=999_999), \
         patch("app.lockfile._pid_alive", return_value=False), \
         patch("app.lifecycle.os._exit") as mock_exit:
        lifecycle.start_auto_reap_watchdog(0.2)
        assert _wait_for_threads_matching(
            lambda: mock_exit.called,
            timeout_s=3.0,
        ), "watchdog did not call os._exit within 3s"
        mock_exit.assert_called_with(0)


def test_watchdog_does_not_exit_when_parent_is_alive(monkeypatch):
    """The watchdog MUST NOT fire while the parent PID is alive.

    If this test ever fails it means a normal desktop session would have
    its server killed mid-use — the worst-case failure mode for the
    auto-reap feature.
    """
    monkeypatch.setattr(lifecycle, "AUTO_REAP_PARENT_CHECK_INTERVAL_S", 0.05)
    with patch.object(lifecycle.os, "getppid", return_value=999_999), \
         patch("app.lockfile._pid_alive", return_value=True), \
         patch("app.lifecycle.os._exit") as mock_exit:
        lifecycle.start_auto_reap_watchdog(60)
        # Let the watchdog spin a few intervals; mock_exit must not be called.
        time.sleep(0.3)
        mock_exit.assert_not_called()


def test_watchdog_noop_when_parent_pid_is_zero():
    """``os.getppid() == 0`` means "no trackable parent" (e.g. the child
    was reparented to ``services.exe``). The watchdog must not spawn in
    that case — otherwise it would reap the first time it noticed its own
    untrackable state.
    """
    with patch.object(lifecycle.os, "getppid", return_value=0):
        before = {t.name for t in threading.enumerate()}
        lifecycle.start_auto_reap_watchdog(60)
        after = {t.name for t in threading.enumerate()}
        assert "auto-reap-watchdog" not in after - before, (
            "watchdog must not spawn when parent PID is 0 (no trackable parent)"
        )


# ---- server.pid file helpers --------------------------------------------------

def test_write_server_pid_file_records_pid_and_parent(monkeypatch, tmp_path):
    """write_server_pid_file() records pid + parent_pid + start timestamp."""
    pid_path = tmp_path / "server.pid"
    monkeypatch.setattr(lifecycle.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(lifecycle, "SERVER_PID_PATH", pid_path)
    with patch.object(lifecycle.os, "getpid", return_value=12345), \
         patch.object(lifecycle.os, "getppid", return_value=67890):
        lifecycle.write_server_pid_file()
    content = pid_path.read_text(encoding="utf-8")
    assert "pid=12345" in content
    assert "parent_pid=67890" in content
    assert "started=" in content


def test_remove_server_pid_file_removes_matching_pid(monkeypatch, tmp_path):
    """remove_server_pid_file() unlinks the file when it belongs to us."""
    pid_path = tmp_path / "server.pid"
    monkeypatch.setattr(lifecycle.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(lifecycle, "SERVER_PID_PATH", pid_path)
    pid_path.write_text(f"pid={os.getpid()} parent_pid=0 started=now\n", encoding="utf-8")
    lifecycle.remove_server_pid_file()
    assert not pid_path.exists()


def test_remove_server_pid_file_refuses_foreign_pid(monkeypatch, tmp_path):
    """remove_server_pid_file() must NOT unlink a file belonging to a
    different (still-running, or previously-orphan) process.

    Otherwise a stale file from a previous orphan could be silently deleted
    by the next session, hiding the leak instead of surfacing it.
    """
    pid_path = tmp_path / "server.pid"
    monkeypatch.setattr(lifecycle.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(lifecycle, "SERVER_PID_PATH", pid_path)
    pid_path.write_text("pid=999999 parent_pid=0 started=earlier\n", encoding="utf-8")
    lifecycle.remove_server_pid_file()
    assert pid_path.exists(), "foreign server.pid was deleted by remove_server_pid_file"


def test_remove_server_pid_file_handles_missing_file(monkeypatch, tmp_path):
    """remove_server_pid_file() must not raise when the file does not exist."""
    pid_path = tmp_path / "server.pid"
    monkeypatch.setattr(lifecycle.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(lifecycle, "SERVER_PID_PATH", pid_path)
    assert not pid_path.exists()
    lifecycle.remove_server_pid_file()  # must not raise


# ---- /api/shutdown integration ------------------------------------------------

def test_shutdown_endpoint_removes_server_pid(monkeypatch, tmp_path):
    """Graceful shutdown via /api/shutdown must clear data/server.pid so
    the next session doesn't see a stale entry."""
    from fastapi.testclient import TestClient

    from app import api

    pid_path = tmp_path / "server.pid"
    monkeypatch.setattr(lifecycle.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(lifecycle, "SERVER_PID_PATH", pid_path)

    # Pre-create a pid file that matches the current process so remove
    # is allowed to fire.
    pid_path.write_text(f"pid={os.getpid()} parent_pid=0 started=now\n", encoding="utf-8")

    client = TestClient(api.app, base_url="http://127.0.0.1:8000")

    # Patch out the actual os._exit so the test process doesn't die.
    with patch("app.api.os._exit") as mock_exit:
        # Cancel the auto-actual-exit: the timer would otherwise call
        # os._exit before we can assert.
        api._shutdown_timer = None
        response = client.post("/api/shutdown")

    assert response.status_code == 200
    assert not pid_path.exists(), (
        "/api/shutdown did not remove data/server.pid; next session will "
        "see a stale entry from this process"
    )
    # Cleanup any leftover timer from the test.
    if api._shutdown_timer is not None:
        api._shutdown_timer.cancel()
        api._shutdown_timer = None


# ---- module surface -----------------------------------------------------------

def test_auto_reap_env_var_name_is_stable():
    """The env var name is part of the public surface — agents set it
    per the runbook, so renaming it requires a coordinated update.
    """
    assert lifecycle.AUTO_REAP_ENV_VAR == "MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S"


def test_module_imports_dont_trigger_side_effects():
    """``import app.lifecycle`` must not start the watchdog or touch disk."""
    # Count watchdog threads before and after a re-import. A clean import
    # neither spawns nor joins threads, so the count must not change.
    import importlib
    before = sum(1 for t in threading.enumerate() if t.name == "auto-reap-watchdog")
    importlib.reload(lifecycle)
    after = sum(1 for t in threading.enumerate() if t.name == "auto-reap-watchdog")
    assert before == after, (
        f"re-importing app.lifecycle spawned or reaped watchdog threads "
        f"(before={before}, after={after})"
    )
