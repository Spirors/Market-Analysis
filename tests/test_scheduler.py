"""Tests for app/scheduler.py: mock subprocess.run calls to schtasks.exe."""

import os
from unittest.mock import MagicMock, patch

import pytest

from app import scheduler


# ---- _run_schtasks -----------------------------------------------------------

def test_run_schtasks_calls_subprocess():
    mock_result = MagicMock(returncode=0, stdout="success", stderr="")
    with patch("app.scheduler.subprocess.run", return_value=mock_result) as mock_run:
        result = scheduler._run_schtasks(["/QUERY", "/TN", "TestTask"])

    mock_run.assert_called_once_with(
        ["schtasks.exe", "/QUERY", "/TN", "TestTask"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0


# ---- install_task ------------------------------------------------------------

def test_install_task_non_windows_returns_error():
    with patch("app.scheduler.sys") as mock_sys:
        mock_sys.platform = "linux"
        result = scheduler.install_task()
    assert result["success"] is False
    assert "Windows" in result["error"]


def test_install_task_creates_all_tasks(monkeypatch):
    monkeypatch.setattr(scheduler.sys, "platform", "win32")
    monkeypatch.setattr(scheduler, "_ensure_log_dir", lambda: None)

    mock_result = MagicMock(returncode=0, stdout="Success", stderr="")
    with patch.object(scheduler, "_run_schtasks", return_value=mock_result) as mock_run:
        with patch.object(scheduler.os, "unlink"):
            result = scheduler.install_task()

    assert result["success"] is True
    assert len(result["tasks"]) == 3
    # Three /CREATE calls, one per task
    assert mock_run.call_count == 3
    for call_args in mock_run.call_args_list:
        args = call_args[0][0]
        assert "/CREATE" in args
        assert "/F" in args


# ---- remove_task -------------------------------------------------------------

def test_remove_task_non_windows_returns_error():
    with patch("app.scheduler.sys") as mock_sys:
        mock_sys.platform = "linux"
        result = scheduler.remove_task()
    assert result["success"] is False
    assert "Windows" in result["error"]


def test_remove_task_calls_delete_for_all_tasks(monkeypatch):
    monkeypatch.setattr(scheduler.sys, "platform", "win32")

    mock_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch.object(scheduler, "_run_schtasks", return_value=mock_result) as mock_run:
        result = scheduler.remove_task()

    assert result["success"] is True
    assert len(result["tasks"]) == 3
    # Three /DELETE calls
    assert mock_run.call_count == 3
    for call_args in mock_run.call_args_list:
        args = call_args[0][0]
        assert "/DELETE" in args


# ---- status ------------------------------------------------------------------

def test_status_non_windows_returns_error():
    with patch("app.scheduler.sys") as mock_sys:
        mock_sys.platform = "linux"
        result = scheduler.status()
    assert result["installed"] is False
    assert "Windows" in result["error"]


def test_status_queries_all_tasks(monkeypatch):
    monkeypatch.setattr(scheduler.sys, "platform", "win32")

    mock_result = MagicMock(returncode=0, stdout="Status info", stderr="")
    with patch.object(scheduler, "_run_schtasks", return_value=mock_result) as mock_run:
        result = scheduler.status()

    assert result["installed"] is True
    assert len(result["tasks"]) == 3
    assert mock_run.call_count == 3
    for call_args in mock_run.call_args_list:
        args = call_args[0][0]
        assert "/QUERY" in args


def test_status_one_missing_task():
    """When one task is missing, installed is False."""
    mock_found = MagicMock(returncode=0, stdout="", stderr="")
    mock_missing = MagicMock(returncode=1, stdout="", stderr="not found")

    with patch("app.scheduler.sys") as mock_sys:
        mock_sys.platform = "win32"
        # First call = daily (found), second = news (missing), third = events commit (found)
        with patch.object(scheduler, "_run_schtasks", side_effect=[mock_found, mock_missing, mock_found]):
            result = scheduler.status()

    assert result["installed"] is False
    assert result["tasks"][0]["installed"] is True
    assert result["tasks"][1]["installed"] is False
    assert result["tasks"][2]["installed"] is True


# ---- _task_xml generation (structural) --------------------------------------

def test_task_xml_contains_python_exe_and_arguments():
    """Verify the generated XML includes the correct Python executable."""
    xml = scheduler._task_xml("Test task", "--refresh", "2026-08-30T09:00:00")
    assert "Test task" in xml
    assert "--refresh" in xml
    assert "2026-08-30T09:00:00" in xml
    assert "CalendarTrigger" in xml


def test_news_task_xml_has_repetition():
    """News task XML must include a Repetition block."""
    xml = scheduler._news_task_xml()
    assert "Repetition" in xml
    assert f"PT{scheduler.config.NEWS_REFRESH_INTERVAL_HOURS}H" in xml


# ---- pythonw.exe (no console flash) ----------------------------------------

def test_pythonw_exe_returns_pythonw_variant():
    """_pythonw_exe() should return the pythonw.exe sibling of sys.executable."""
    import sys
    result = scheduler._pythonw_exe()
    assert result.lower().endswith("pythonw.exe"), (
        f"_pythonw_exe() returned {result!r}, expected a path ending in pythonw.exe "
        f"(sys.executable={sys.executable!r})"
    )
    # Both should share the same directory.
    assert os.path.dirname(result).lower() == os.path.dirname(sys.executable).lower()


def test_task_xml_default_still_uses_python_exe():
    """Without an explicit python_exe kwarg, _task_xml falls back to _python_exe
    (python.exe). This preserves backward compatibility for callers that
    have not been updated to pass pythonw.
    """
    import sys
    xml = scheduler._task_xml("Test", "--refresh", "2026-08-30T09:00:00")
    # Default kwarg path goes through _python_exe -> sys.executable
    # (pythonw would be lowercase 'w'; python.exe is the default).
    assert sys.executable in xml


def test_task_xml_with_pythonw_exe_kwarg():
    """When python_exe is provided, _task_xml uses it verbatim in <Command>."""
    xml = scheduler._task_xml(
        "Test",
        "--refresh",
        "2026-08-30T09:00:00",
        python_exe="C:\\\\Python312\\\\pythonw.exe",
    )
    assert "C:\\\\Python312\\\\pythonw.exe" in xml


def test_daily_task_xml_uses_pythonw():
    """Daily task XML must launch pythonw.exe so no console window flashes."""
    xml = scheduler._daily_task_xml()
    assert "pythonw.exe" in xml


def test_news_task_xml_uses_pythonw():
    """News task XML must launch pythonw.exe so no console window flashes."""
    xml = scheduler._news_task_xml()
    assert "pythonw.exe" in xml


def test_events_commit_task_xml_uses_pythonw():
    """Events-commit task XML must launch pythonw.exe so no console window flashes."""
    xml = scheduler._events_commit_task_xml()
    assert "pythonw.exe" in xml
