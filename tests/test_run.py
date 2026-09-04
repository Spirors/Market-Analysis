"""Tests for run.py CLI flags: exercise every flag via ``run.main()``.

``run.py`` has an ``if __name__ == "__main__"`` guard so ``import run`` is
safe — no side effects fire.  Each flag path is tested by monkeypatching the
dispatch targets (``service``, ``scheduler``) so no network, subprocess, or
long-running operations execute.
"""

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


# ---- _setup_logfile real-function behavior ---------------------------------

def test_setup_logfile_pythonw_branch_binds_stdout_to_log(tmp_path, monkeypatch):
    """_setup_logfile must work when sys.stdout/sys.stderr are None (pythonw.exe).

    Simulates the GUI-subsystem Python launcher: no console was allocated,
    so stdout/stderr are None at startup. After _setup_logfile returns,
    sys.stdout and sys.stderr must be live file objects pointing at the
    daily-dated log file, and that log file must exist on disk.
    """
    import os
    import sys
    from run import _setup_logfile

    prefix = tmp_path / "logs" / "refresh"
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    # Save OS-level fd 1/2 so we can restore them after _setup_logfile
    # dup2's the log file onto them.
    saved_fd1 = os.dup(1)
    saved_fd2 = os.dup(2)
    try:
        sys.stdout = None
        sys.stderr = None
        _setup_logfile(str(prefix))
        # stdout/stderr must now be bound to a file object, not None
        assert sys.stdout is not None
        assert sys.stderr is not None
        # The daily-dated log file must exist on disk
        log_files = list((tmp_path / "logs").glob("refresh-*.log"))
        assert len(log_files) == 1
        # Calling print() must write into the log file (not crash on None)
        sys.stdout.write("pythonw log entry\n")
        sys.stdout.flush()
        log_text = log_files[0].read_text(encoding="utf-8", errors="replace")
        assert "pythonw log entry" in log_text
    finally:
        # Restore OS-level fds before restoring Python-level objects.
        os.dup2(saved_fd1, 1)
        os.dup2(saved_fd2, 2)
        os.close(saved_fd1)
        os.close(saved_fd2)
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def test_setup_logfile_pythonw_branch_dup2_for_child_inheritance(tmp_path, monkeypatch):
    """The pythonw branch dup2's the log file onto fd 1/2 so child
    subprocesses inherit the redirect.
    """
    import os
    import sys
    from run import _setup_logfile

    prefix = tmp_path / "logs" / "refresh"
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    # Save OS-level fd 1/2 so we can restore them after _setup_logfile
    # dup2's the log file onto them.
    saved_fd1 = os.dup(1)
    saved_fd2 = os.dup(2)
    try:
        sys.stdout = None
        sys.stderr = None
        _setup_logfile(str(prefix))
        log_files = list((tmp_path / "logs").glob("refresh-*.log"))
        assert len(log_files) == 1
        log_path = log_files[0]
        # Verify fd 1 now targets the log by writing directly.
        os.write(1, b"fd1-direct write\n")
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        assert "fd1-direct write" in log_text
    finally:
        # Restore OS-level fds before restoring Python-level objects.
        os.dup2(saved_fd1, 1)
        os.dup2(saved_fd2, 2)
        os.close(saved_fd1)
        os.close(saved_fd2)
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def test_setup_logfile_python_exe_branch(tmp_path):
    """The python.exe branch: existing flush+dup2+reconfigure flow."""
    import os
    import sys
    from run import _setup_logfile

    # In a test runner sys.stdout/sys.stderr are real (pytest captures
    # via its own capture mechanism, not by setting None). This is the
    # python.exe branch.
    prefix = tmp_path / "logs" / "refresh"
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    # _setup_logfile's python.exe branch calls:
    #   os.dup2(log_file.fileno(), sys.stdout.fileno())
    #   os.dup2(log_file.fileno(), sys.stderr.fileno())
    # In pytest, sys.stdout.fileno() is NOT fd 1 — it's a separate capture
    # fd.  We must save and restore *all* fds that dup2 will overwrite.
    cap_out_fd = original_stdout.fileno()
    cap_err_fd = original_stderr.fileno()
    saved_cap_out = os.dup(cap_out_fd)
    saved_cap_err = os.dup(cap_err_fd)
    saved_fd1 = os.dup(1)
    saved_fd2 = os.dup(2)
    try:
        assert sys.stdout is not None
        _setup_logfile(str(prefix))
        log_files = list((tmp_path / "logs").glob("refresh-*.log"))
        assert len(log_files) == 1
    finally:
        # Restore all fds that _setup_logfile may have replaced.
        os.dup2(saved_fd1, 1)
        os.dup2(saved_fd2, 2)
        os.dup2(saved_cap_out, cap_out_fd)
        os.dup2(saved_cap_err, cap_err_fd)
        os.close(saved_fd1)
        os.close(saved_fd2)
        os.close(saved_cap_out)
        os.close(saved_cap_err)
        sys.stdout = original_stdout
        sys.stderr = original_stderr
