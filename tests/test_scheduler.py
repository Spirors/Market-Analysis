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


# ---- VBS launcher (no console flash) ---------------------------------------

def test_wscript_exe_returns_wscript_path():
    """_wscript_exe() returns a path containing 'wscript' (Windows Script Host)."""
    result = scheduler._wscript_exe()
    assert "wscript" in result.lower()
    # Should be either an absolute path or the bare 'wscript.exe' fallback.
    assert result.lower().endswith("wscript.exe")


def test_task_xml_launches_vbs_wrapper():
    """Task XML must launch wscript.exe with scheduler.vbs in the arguments."""
    xml = scheduler._task_xml("Test", "--refresh", "2026-08-30T09:00:00")
    # The Command element must point at wscript.exe (no python.exe / pythonw.exe
    # direct invocation — those would flash a console window).
    assert "wscript.exe" in xml
    assert "pythonw.exe" not in xml  # we explicitly avoid pythonw
    # The Arguments element must forward to scheduler.vbs at the repo root.
    assert "scheduler.vbs" in xml
    assert "//nologo" in xml  # suppress the VBScript banner
    # The original run.py args must be forwarded verbatim.
    assert "--refresh" in xml


def test_daily_task_xml_uses_vbs_launcher():
    """Daily task XML must launch via the VBS wrapper (no console flash)."""
    xml = scheduler._daily_task_xml()
    assert "wscript.exe" in xml
    assert "scheduler.vbs" in xml
    assert "pythonw.exe" not in xml


def test_news_task_xml_uses_vbs_launcher():
    """News task XML must launch via the VBS wrapper (no console flash)."""
    xml = scheduler._news_task_xml()
    assert "wscript.exe" in xml
    assert "scheduler.vbs" in xml
    assert "pythonw.exe" not in xml


def test_events_commit_task_xml_uses_vbs_launcher():
    """Events-commit task XML must launch via the VBS wrapper (no console flash)."""
    xml = scheduler._events_commit_task_xml()
    assert "wscript.exe" in xml
    assert "scheduler.vbs" in xml
    assert "pythonw.exe" not in xml


def test_task_xml_forwards_logfile_prefix_arg():
    """The logfile-prefix path must be preserved through the VBS wrapper
    so run.py still routes stdout to data/logs/refresh-YYYYMMDD.log."""
    xml = scheduler._daily_task_xml()
    assert "--logfile-prefix" in xml
    # The DAILY_LOG_PREFIX path (data/logs/refresh) must survive intact.
    assert "refresh" in xml


def test_task_xml_working_directory_is_repo_root():
    """The <WorkingDirectory> must be the repo root so python resolves run.py
    and the VBS's CurrentDirectory override is consistent."""
    xml = scheduler._daily_task_xml()
    assert "<WorkingDirectory>" in xml
    assert str(scheduler.config.BASE_DIR) in xml


def test_pythonw_exe_does_not_exist():
    """Regression guard: _pythonw_exe must NOT exist in scheduler.py anymore.
    pythonw was tried for scheduled tasks but caused console-handle
    inconsistencies; the VBS wrapper replaced it. This test prevents
    accidental reintroduction of the pythonw path.
    """
    assert not hasattr(scheduler, "_pythonw_exe"), (
        "_pythonw_exe() was removed because pythonw detaches from the parent "
        "console and can leave OS console-handle state inconsistent (see "
        "launch.bat warning). The VBS wrapper pattern replaces it."
    )


def test_scheduler_vbs_file_exists():
    """scheduler.vbs must exist at the repo root for the launcher to work."""
    vbs_path = scheduler.config.BASE_DIR / "scheduler.vbs"
    assert vbs_path.is_file(), (
        f"scheduler.vbs missing at {vbs_path}. The scheduled tasks launch "
        "via this file; without it, tasks will fail to start python."
    )


def test_scheduler_vbs_runs_python_hidden():
    """scheduler.vbs must invoke python with WindowStyle=0 (SW_HIDE)."""
    vbs_path = scheduler.config.BASE_DIR / "scheduler.vbs"
    content = vbs_path.read_text(encoding="ascii", errors="replace")
    assert "shell.Run" in content
    # WindowStyle=0 is the second positional arg to shell.Run; the literal
    # `, 0, False` must appear (False = do not wait for python to exit).
    assert ", 0, False" in content
