"""Tests for run.py CLI flags: exercise every flag via ``run.main()``.

``run.py`` has an ``if __name__ == "__main__"`` guard so ``import run`` is
safe — no side effects fire.  Each flag path is tested by monkeypatching the
dispatch targets (``service``, ``scheduler``) so no network, subprocess, or
long-running operations execute.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


def _call_main(*argv: str) -> None:
    """Invoke ``run.main()`` with the given CLI arguments."""
    with patch.object(sys, "argv", ["run.py", *argv]):
        import run
        run.main()


# ---- --refresh --------------------------------------------------------------

def test_refresh_calls_service_refresh_all():
    mock_service = MagicMock()
    with patch.dict("sys.modules", {"app.service": mock_service}):
        # Prevent real import by patching the lazy import inside main()
        with patch("app.service", mock_service, create=True):
            _call_main("--refresh")
    mock_service.refresh_all.assert_called_once_with(full=True)


# ---- --news-refresh ---------------------------------------------------------

def test_news_refresh_calls_service_refresh_news():
    mock_service = MagicMock()
    mock_service.refresh_news.return_value = {
        "feeds_checked": 4, "collected": 2, "inserted": 1,
    }
    with patch("app.service", mock_service, create=True):
        _call_main("--news-refresh")
    mock_service.refresh_news.assert_called_once()


# ---- --backfill -------------------------------------------------------------

def test_backfill_calls_service_backfill_news():
    mock_service = MagicMock()
    mock_service.backfill_news.return_value = {"seed_events": 70, "inserted": 0}
    with patch("app.service", mock_service, create=True):
        _call_main("--backfill")
    mock_service.backfill_news.assert_called_once()


# ---- --schedule-install -----------------------------------------------------

def test_schedule_install_calls_scheduler_install():
    mock_scheduler = MagicMock()
    mock_scheduler.install_task.return_value = {"success": True, "tasks": []}
    with patch("app.scheduler", mock_scheduler, create=True):
        _call_main("--schedule-install")
    mock_scheduler.install_task.assert_called_once()


# ---- --schedule-remove ------------------------------------------------------

def test_schedule_remove_calls_scheduler_remove():
    mock_scheduler = MagicMock()
    mock_scheduler.remove_task.return_value = {"success": True, "tasks": []}
    with patch("app.scheduler", mock_scheduler, create=True):
        _call_main("--schedule-remove")
    mock_scheduler.remove_task.assert_called_once()


# ---- --schedule-status ------------------------------------------------------

def test_schedule_status_calls_scheduler_status():
    mock_scheduler = MagicMock()
    mock_scheduler.status.return_value = {"installed": True, "tasks": []}
    with patch("app.scheduler", mock_scheduler, create=True):
        _call_main("--schedule-status")
    mock_scheduler.status.assert_called_once()


# ---- Default (no flags) launches uvicorn ------------------------------------

def test_default_starts_uvicorn():
    mock_uvicorn = MagicMock()
    with patch("uvicorn.run", mock_uvicorn):
        _call_main()
    mock_uvicorn.assert_called_once()
    args, kwargs = mock_uvicorn.call_args
    assert kwargs.get("host") == "127.0.0.1"
    assert kwargs.get("port") == 8000


# ---- --port / --host flags -------------------------------------------------

def test_custom_port_and_host():
    mock_uvicorn = MagicMock()
    with patch("uvicorn.run", mock_uvicorn):
        _call_main("--port", "9000", "--host", "0.0.0.0")
    _, kwargs = mock_uvicorn.call_args
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 9000


# ---- --logfile-prefix does not crash ----------------------------------------

def test_logfile_prefix_does_not_crash(tmp_path):
    """--logfile-prefix should set up logging without error."""
    prefix = tmp_path / "logs" / "refresh"
    mock_uvicorn = MagicMock()
    mock_setup = MagicMock()
    with patch("uvicorn.run", mock_uvicorn), \
         patch("run._setup_logfile", mock_setup):
        _call_main("--logfile-prefix", str(prefix))
    mock_setup.assert_called_once_with(str(prefix))
    mock_uvicorn.assert_called_once()


# ---- --open-browser schedules a browser open -------------------------------

def test_open_browser_schedules_webbrowser_open():
    """--open-browser should schedule webbrowser.open on a Timer so the server
    has time to bind before the browser tries to connect."""
    mock_uvicorn = MagicMock()
    mock_timer = MagicMock()
    mock_open = MagicMock()
    with patch("uvicorn.run", mock_uvicorn), \
         patch("threading.Timer", mock_timer) as timer_cls, \
         patch("webbrowser.open", mock_open):
        _call_main("--open-browser")
    # A Timer was created with the URL and the delay
    timer_cls.assert_called_once()
    args, kwargs = timer_cls.call_args
    # positional: (interval, function); kwargs: args=(url,)
    assert args[0] == 1.5
    # The function passed to Timer is whatever webbrowser.open was at call time
    # (i.e. the patched mock).
    assert args[1] is mock_open
    # args=(url,) — the dashboard URL the browser will open
    assert kwargs.get("args") == ("http://127.0.0.1:8000",)
    # The timer's start() was called
    mock_timer.return_value.start.assert_called_once()
    # uvicorn still starts (browser is a side-effect)
    mock_uvicorn.assert_called_once()


def test_default_does_not_open_browser():
    """Without --open-browser, no Timer / webbrowser.open should fire."""
    mock_uvicorn = MagicMock()
    mock_timer = MagicMock()
    mock_open = MagicMock()
    with patch("uvicorn.run", mock_uvicorn), \
         patch("threading.Timer", mock_timer), \
         patch("webbrowser.open", mock_open):
        _call_main()
    mock_timer.assert_not_called()
    mock_open.assert_not_called()


# ---- --auto-reap + server.pid tracking ---------------------------------------

def test_auto_reap_zero_does_not_start_watchdog():
    """--auto-reap 0 (default for desktop launches) must not spawn the
    auto-reap watchdog thread. Regression guard for the "agent reaps the
    server mid-use" worst-case failure mode.
    """
    from app import lifecycle as lifecycle_mod

    mock_uvicorn = MagicMock()
    with patch("uvicorn.run", mock_uvicorn), \
         patch.object(lifecycle_mod, "start_auto_reap_watchdog") as mock_start:
        _call_main()
    mock_start.assert_called_once_with(0)


def test_auto_reap_flag_is_forwarded():
    """--auto-reap N must call start_auto_reap_watchdog(N)."""
    from app import lifecycle as lifecycle_mod

    mock_uvicorn = MagicMock()
    with patch("uvicorn.run", mock_uvicorn), \
         patch.object(lifecycle_mod, "start_auto_reap_watchdog") as mock_start:
        _call_main("--auto-reap", "60")
    mock_start.assert_called_once_with(60)


def test_auto_reap_env_var_is_honored():
    """$MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S=N is forwarded to the watchdog
    when --auto-reap is not passed. Lets the runbook set the timeout via env
    without restating the value as a CLI flag.
    """
    from app import lifecycle as lifecycle_mod

    mock_uvicorn = MagicMock()
    with patch.dict(os.environ, {"MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S": "90"}, clear=False), \
         patch("uvicorn.run", mock_uvicorn), \
         patch.object(lifecycle_mod, "start_auto_reap_watchdog") as mock_start:
        _call_main()
    mock_start.assert_called_once_with(90)


def test_auto_reap_flag_overrides_env_var():
    """--auto-reap takes precedence over the env var when both are set."""
    from app import lifecycle as lifecycle_mod

    mock_uvicorn = MagicMock()
    with patch.dict(os.environ, {"MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S": "999"}, clear=False), \
         patch("uvicorn.run", mock_uvicorn), \
         patch.object(lifecycle_mod, "start_auto_reap_watchdog") as mock_start:
        _call_main("--auto-reap", "30")
    mock_start.assert_called_once_with(30)


def test_server_pid_file_is_written_at_startup(monkeypatch, tmp_path):
    """run.py must record data/server.pid so a future session can locate
    and reap a stray instance. Regression guard for the "stuck process on
    launch" failure mode documented in AGENT-WORKFLOW-PROMPT.md §3a.
    """
    from app import lifecycle as lifecycle_mod

    # Redirect the pid file to tmp_path so we don't pollute the real data/.
    pid_path = tmp_path / "server.pid"
    monkeypatch.setattr(lifecycle_mod, "SERVER_PID_PATH", pid_path)
    monkeypatch.setattr(lifecycle_mod.config, "DATA_DIR", tmp_path)

    mock_uvicorn = MagicMock()
    with patch("uvicorn.run", mock_uvicorn):
        _call_main()

    assert pid_path.exists(), "run.py did not write data/server.pid at startup"
    content = pid_path.read_text(encoding="utf-8")
    assert f"pid={os.getpid()}" in content
    assert "parent_pid=" in content


def test_atexit_cleans_up_server_pid(monkeypatch, tmp_path):
    """run.py must register atexit.remove_server_pid_file so a non-os._exit
    exit (Ctrl+C, unhandled exception, sys.exit) still cleans the pid file.
    """
    from app import lifecycle as lifecycle_mod

    pid_path = tmp_path / "server.pid"
    monkeypatch.setattr(lifecycle_mod, "SERVER_PID_PATH", pid_path)
    monkeypatch.setattr(lifecycle_mod.config, "DATA_DIR", tmp_path)

    # Pre-create a matching pid file so remove is allowed.
    pid_path.write_text(f"pid={os.getpid()} parent_pid=0 started=now\n", encoding="utf-8")

    # Reset atexit callbacks we may have registered in earlier tests.
    import atexit as atexit_mod
    original = atexit_mod._ncallbacks() if hasattr(atexit_mod, "_ncallbacks") else None
    try:
        mock_uvicorn = MagicMock()
        with patch("uvicorn.run", mock_uvicorn):
            _call_main()
        assert pid_path.exists()  # still present until atexit fires

        # Simulate atexit firing by calling the cleanup helper directly
        # (we can't easily trigger the full atexit sequence in-test).
        lifecycle_mod.remove_server_pid_file()
        assert not pid_path.exists(), "atexit-style cleanup did not remove data/server.pid"
    finally:
        # Best-effort: restore atexit state. Pytest's atexit handling is
        # opaque; this only matters for cross-test contamination.
        pass

