"""Tests for app/scheduler.py: mock subprocess.run calls to schtasks.exe."""

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


def test_install_task_creates_both_tasks(monkeypatch):
    monkeypatch.setattr(scheduler.sys, "platform", "win32")
    monkeypatch.setattr(scheduler, "_ensure_log_dir", lambda: None)

    mock_result = MagicMock(returncode=0, stdout="Success", stderr="")
    with patch.object(scheduler, "_run_schtasks", return_value=mock_result) as mock_run:
        with patch.object(scheduler.os, "unlink"):
            result = scheduler.install_task()

    assert result["success"] is True
    assert len(result["tasks"]) == 2
    # Two /CREATE calls, one per task
    assert mock_run.call_count == 2
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


def test_remove_task_calls_delete_for_both_tasks(monkeypatch):
    monkeypatch.setattr(scheduler.sys, "platform", "win32")

    mock_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch.object(scheduler, "_run_schtasks", return_value=mock_result) as mock_run:
        result = scheduler.remove_task()

    assert result["success"] is True
    assert len(result["tasks"]) == 2
    # Two /DELETE calls
    assert mock_run.call_count == 2
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


def test_status_queries_both_tasks(monkeypatch):
    monkeypatch.setattr(scheduler.sys, "platform", "win32")

    mock_result = MagicMock(returncode=0, stdout="Status info", stderr="")
    with patch.object(scheduler, "_run_schtasks", return_value=mock_result) as mock_run:
        result = scheduler.status()

    assert result["installed"] is True
    assert len(result["tasks"]) == 2
    assert mock_run.call_count == 2
    for call_args in mock_run.call_args_list:
        args = call_args[0][0]
        assert "/QUERY" in args


def test_status_one_missing_task():
    """When one task is missing, installed is False."""
    mock_found = MagicMock(returncode=0, stdout="", stderr="")
    mock_missing = MagicMock(returncode=1, stdout="", stderr="not found")

    with patch("app.scheduler.sys") as mock_sys:
        mock_sys.platform = "win32"
        # First call = daily (found), second = news (missing)
        with patch.object(scheduler, "_run_schtasks", side_effect=[mock_found, mock_missing]):
            result = scheduler.status()

    assert result["installed"] is False
    assert result["tasks"][0]["installed"] is True
    assert result["tasks"][1]["installed"] is False


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
