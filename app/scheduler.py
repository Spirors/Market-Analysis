"""Windows scheduled-task helpers for background refreshes.

Two tasks are managed:

- ``MarketAnalysis-DailyRefresh``  — daily 9:00 AM local: full refresh
  (``python run.py --refresh``).
- ``MarketAnalysis-NewsRefresh``   — every 4 hours all day: fast news-only
  ingest (``python run.py --news-refresh``).

Both are installed as interactive-user tasks, so they run in the same context
as the user who installed them and do not require admin rights on most
Windows setups.

**Logged-off limitation:** InteractiveToken tasks silently do NOT run while
the user is logged off — Windows skips the trigger entirely, and
StartWhenAvailable only catches up after you log back in. If refreshes must
happen while you are away, either reinstall the tasks to "run whether user is
logged on or not" (``schtasks /RU <user> /RP <password>``, which requires
admin rights / the account password) or keep an always-on session.

Both tasks pass ``--logfile-prefix`` so each run appends to a daily-dated log
(``<prefix>-YYYYMMDD.log``, pruned after 30 days by run.py) instead of one
unbounded ``>>``-appended file.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from . import config

DAILY_TASK_NAME = r"MarketAnalysis-DailyRefresh"
NEWS_TASK_NAME = r"MarketAnalysis-NewsRefresh"

# Backward-compatible alias (the original single task).
TASK_NAME = DAILY_TASK_NAME

DAILY_TASK_DESCRIPTION = "Daily 9:00 AM refresh for Market Analysis Tool"
NEWS_TASK_DESCRIPTION = "Every-4-hours news-only refresh for Market Analysis Tool"

TRIGGER_HOUR = 9
TRIGGER_MINUTE = 0

# Hard kill after this long. A full refresh (regime detection + slow EDGAR
# pulls) can exceed one hour, and being killed mid-write corrupts caches —
# so the limit is generous rather than tight.
EXECUTION_TIME_LIMIT = "PT4H"

LOG_DIR = config.DATA_DIR / "logs"
# Daily-dated log prefixes handed to ``run.py --logfile-prefix``. Each run
# appends to ``<prefix>-YYYYMMDD.log`` and prunes siblings older than 30 days
# (retention constant lives in run.py: LOG_RETENTION_DAYS).
DAILY_LOG_PREFIX = LOG_DIR / "refresh"
NEWS_LOG_PREFIX = LOG_DIR / "news-refresh"


def _project_root() -> Path:
    return config.BASE_DIR


def _python_exe() -> str:
    return sys.executable


def _ensure_log_dir() -> None:
    """Make sure data\\logs exists before any task writes to it."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _next_run_date(hour: int, minute: int) -> str:
    """Return tomorrow's date if we are already past hour:minute, else today."""
    now = dt.datetime.now()
    trigger = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if trigger <= now:
        trigger += dt.timedelta(days=1)
    return trigger.strftime("%Y-%m-%d")


def _news_start_boundary() -> str:
    """Today's date for the news task: its StartBoundary anchors midnight,
    and the PT4H repetition fires 00:00 / 04:00 / ... / 20:00 every day."""
    return dt.date.today().strftime("%Y-%m-%d")


def _task_xml(
    description: str,
    arguments: str,
    start_boundary: str,
    repetition_interval: str | None = None,
) -> str:
    """Build a Task Scheduler 1.2 XML document.

    ``repetition_interval`` (e.g. "PT4H") adds a <Repetition> block so the
    daily trigger re-fires throughout the day.
    """
    python_exe = _python_exe()
    project_root = _project_root()

    repetition_block = ""
    if repetition_interval:
        repetition_block = f"""      <Repetition>
        <Interval>{repetition_interval}</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
"""

    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{xml_escape(description)}</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start_boundary}</StartBoundary>
{repetition_block}      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <!-- InteractiveToken: runs only while the user is logged on. See the
           module docstring for the logged-off limitation. -->
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <!-- WakeToRun: wake the machine from sleep so triggers fire on time;
         the OS returns to sleep shortly after the run finishes. -->
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>{EXECUTION_TIME_LIMIT}</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{xml_escape(python_exe)}</Command>
      <Arguments>{xml_escape(arguments)}</Arguments>
      <WorkingDirectory>{xml_escape(str(project_root))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""
    return xml


def _daily_task_xml() -> str:
    """XML for the daily 9 AM full-refresh task."""
    start_date = _next_run_date(TRIGGER_HOUR, TRIGGER_MINUTE)
    arguments = (
        f'"{_project_root() / "run.py"}" --refresh '
        f'--logfile-prefix "{DAILY_LOG_PREFIX.as_posix()}"'
    )
    return _task_xml(DAILY_TASK_DESCRIPTION, arguments, f"{start_date}T{TRIGGER_HOUR:02d}:{TRIGGER_MINUTE:02d}:00")


def _news_task_xml() -> str:
    """XML for the news-only task repeating every NEWS_REFRESH_INTERVAL_HOURS."""
    interval_hours = config.NEWS_REFRESH_INTERVAL_HOURS
    arguments = (
        f'"{_project_root() / "run.py"}" --news-refresh '
        f'--logfile-prefix "{NEWS_LOG_PREFIX.as_posix()}"'
    )
    return _task_xml(
        NEWS_TASK_DESCRIPTION,
        arguments,
        f"{_news_start_boundary()}T00:00:00",
        repetition_interval=f"PT{interval_hours}H",
    )


def _run_schtasks(args: list[str]) -> subprocess.CompletedProcess:
    """Run schtasks.exe with the given arguments and return the result."""
    return subprocess.run(
        ["schtasks.exe", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _create_task(task_name: str, xml_content: str) -> dict[str, Any]:
    """Create one scheduled task from an XML document, overwriting any
    existing task of the same name.

    Uses a single ``schtasks /create /f`` (force-overwrite) rather than the
    old delete-then-create sequence: if the create failed there, the task
    was left deleted; now a failed create leaves the previous schedule in
    place.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-16", suffix=".xml", delete=False
    ) as tmp:
        tmp.write(xml_content)
        xml_path = tmp.name

    try:
        result = _run_schtasks(["/CREATE", "/TN", task_name, "/XML", xml_path, "/F"])
        success = result.returncode == 0
        info: dict[str, Any] = {
            "success": success,
            "task_name": task_name,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
        if not success:
            info["error"] = f"schtasks.exe exited with code {result.returncode}"
        return info
    finally:
        try:
            os.unlink(xml_path)
        except OSError:
            pass


def install_task() -> dict[str, Any]:
    """Create or overwrite both Market Analysis scheduled tasks.

    - DailyRefresh: daily at 09:00 local time (full refresh).
    - NewsRefresh: every NEWS_REFRESH_INTERVAL_HOURS hours, all day
      (fast news-only refresh).
    """
    if sys.platform != "win32":
        return {"success": False, "error": "Scheduled tasks are only supported on Windows."}

    # Ensure the log directory exists before the tasks are registered.
    _ensure_log_dir()

    interval_hours = config.NEWS_REFRESH_INTERVAL_HOURS
    specs = [
        {
            **_create_task(DAILY_TASK_NAME, _daily_task_xml()),
            "schedule": f"Daily at {TRIGGER_HOUR:02d}:{TRIGGER_MINUTE:02d} local time",
            "log_file": f"{DAILY_LOG_PREFIX.as_posix()}-YYYYMMDD.log",
        },
        {
            **_create_task(NEWS_TASK_NAME, _news_task_xml()),
            "schedule": f"Every {interval_hours} hours (daily boundary + PT{interval_hours}H repetition)",
            "log_file": f"{NEWS_LOG_PREFIX.as_posix()}-YYYYMMDD.log",
        },
    ]

    return {
        "success": all(s["success"] for s in specs),
        "tasks": specs,
    }


def remove_task() -> dict[str, Any]:
    """Remove both Market Analysis scheduled tasks."""
    if sys.platform != "win32":
        return {"success": False, "error": "Scheduled tasks are only supported on Windows."}

    specs = []
    for task_name in (DAILY_TASK_NAME, NEWS_TASK_NAME):
        result = _run_schtasks(["/DELETE", "/TN", task_name, "/F"])
        specs.append({
            "success": result.returncode == 0,
            "task_name": task_name,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        })

    return {
        "success": all(s["success"] for s in specs),
        "tasks": specs,
    }


def status() -> dict[str, Any]:
    """Return whether each scheduled task is currently installed."""
    if sys.platform != "win32":
        return {"installed": False, "tasks": [], "error": "Scheduled tasks are only supported on Windows."}

    specs = []
    for task_name in (DAILY_TASK_NAME, NEWS_TASK_NAME):
        result = _run_schtasks(["/QUERY", "/TN", task_name])
        specs.append({
            "installed": result.returncode == 0,
            "task_name": task_name,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        })

    return {
        "installed": all(s["installed"] for s in specs),
        "tasks": specs,
    }
