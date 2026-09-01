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
