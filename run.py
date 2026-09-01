"""Run the Market Analysis Tool (local webapp).

Usage:
    python run.py                 # serve at http://127.0.0.1:8000
    python run.py --port 9000     # custom port
    python run.py --refresh       # run a full refresh once and exit
    python run.py --news-refresh  # fast news-only ingest once and exit
    python run.py --backfill      # seed the curated event timeline then exit
    python run.py --commit-events # stage data/events.json and commit
    python run.py --install-shortcut  # create desktop shortcut
    python run.py --remove-shortcut   # remove desktop shortcut
    python run.py --open-browser      # open default browser after server binds
                                       # (used by the desktop shortcut launcher)

The Windows scheduled tasks (app/scheduler.py) additionally pass
``--logfile-prefix data/logs/refresh`` so each run appends to a daily-dated
log file that is pruned automatically after LOG_RETENTION_DAYS days.
"""

from __future__ import annotations

import argparse
import datetime
import os
import pathlib
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from app import config

# Delay (seconds) before opening the user's default browser when
# ``--open-browser`` is set.  Gives uvicorn enough time to bind so the
# browser does not hit "connection refused" on a fast cold start.
_BROWSER_OPEN_DELAY_S = 1.5

# Scheduled-task logs older than this many days are deleted on startup when
# --logfile-prefix is used; without it, one log file per day would grow the
# data/logs directory without bound.
LOG_RETENTION_DAYS = 30


def _setup_logfile(prefix: str) -> None:
    """Redirect stdout/stderr to ``<prefix>-YYYYMMDD.log`` and prune old logs.

    Each day gets its own append-mode log file next to ``prefix``; sibling
    logs from the same prefix older than LOG_RETENTION_DAYS are removed.
    Uses os.dup2 (rather than reassigning sys.stdout) so output from child
    processes — e.g. the regime-detector subprocess — is captured too.
    """
    prefix_path = Path(prefix)
    prefix_path.parent.mkdir(parents=True, exist_ok=True)

    log_path = prefix_path.with_name(f"{prefix_path.name}-{time.strftime('%Y%m%d')}.log")

    # Best-effort pruning of this prefix's expired daily logs.
    cutoff = time.time() - LOG_RETENTION_DAYS * 86400
    for old in prefix_path.parent.glob(f"{prefix_path.name}-*.log"):
        try:
            if old.is_file() and old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:
            pass  # never block a refresh over log cleanup

    sys.stdout.flush()
    sys.stderr.flush()
    with open(log_path, "a", encoding="utf-8", errors="replace") as log_file:
        os.dup2(log_file.fileno(), sys.stdout.fileno())
        os.dup2(log_file.fileno(), sys.stderr.fileno())

    # Keep writes flushed per line now that stdout targets a file.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(line_buffering=True)
            except ValueError:
                pass


def commit_events() -> int:
    """Stage data/events.json and commit with a timestamped message.

    No-op if there is no diff.  Returns 0 on success or no-diff, 1 on
    git error.
    """
    from app.changelog import log_change

    events_path = config.EVENTS_PATH  # already exists in config
    if not events_path.exists():
        print(f"no events file at {events_path}", file=sys.stderr)
        return 1

    # Check for diff first (avoid empty commits).
    diff = subprocess.run(
        ["git", "diff", "--quiet", str(events_path)],
        capture_output=True,
    )
    if diff.returncode == 0:
        log_change("commit", "events.json auto-commit: no changes", day=datetime.date.today())
        print("no changes to commit")
        return 0

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"events: auto-commit {timestamp}"

    add = subprocess.run(["git", "add", str(events_path)], capture_output=True, text=True)
    if add.returncode != 0:
        print(f"git add failed: {add.stderr}", file=sys.stderr)
        return 1

    commit = subprocess.run(["git", "commit", "-m", msg], capture_output=True, text=True)
    if commit.returncode != 0:
        print(f"git commit failed: {commit.stderr}", file=sys.stderr)
        return 1

    log_change("commit", f"events.json auto-commit succeeded: {msg}")
    print(f"committed: {msg}")
    return 0


def install_shortcut() -> int:
    """Create launch.bat + launch.vbs at repo root and a Desktop shortcut.

    The desktop .lnk points at ``wscript.exe`` running ``launch.vbs`` so
    no console window appears when the user double-clicks. ``launch.bat``
    is kept as a visible-cmd fallback for debugging (Ctrl+C, live logs).
    """
    from app.changelog import log_change

    repo = pathlib.Path(__file__).resolve().parent

    # Visible-cmd fallback. See the comment block above the python line
    # for the pythonw-vs-python rationale; this bat is for users who want
    # to see uvicorn's logs.
    bat_path = repo / "launch.bat"
    bat_path.write_text(
        "@echo off\r\n"
        "rem Visible-cmd launcher. For the hidden-window variant used by the\r\n"
        "rem desktop shortcut, see launch.vbs (the .lnk targets wscript.exe).\r\n"
        "rem Use python (not pythonw). pythonw tries to detach from the parent\r\n"
        "rem console on startup; when launched from cmd.exe via a .lnk\r\n"
        "rem ShellExecute, that detach can leave OS console-handle state\r\n"
        "rem inconsistent and pythonw aborts silently before uvicorn binds.\r\n"
        "rem python inherits cmd's console cleanly.\r\n"
        'cd /d "%~dp0"\r\n'
        "python run.py --open-browser\r\n",
        encoding="ascii",
    )

    # Hidden launcher. WScript.Shell.Run with WindowStyle=0 (SW_HIDE) +
    # False (do not wait) means python starts with no console window and
    # WScript exits immediately so nothing lingers. The .vbs sets its own
    # CurrentDirectory so `python run.py` resolves regardless of how it
    # was launched.
    vbs_path = repo / "launch.vbs"
    vbs_path.write_text(
        "' Hidden launcher for python run.py --open-browser.\r\n"
        "'\r\n"
        "' Used by the desktop shortcut. No console window is shown.\r\n"
        "' See launch.bat for the visible-cmd variant (shows uvicorn's\r\n"
        "' logs, Ctrl+C to stop).\r\n"
        "Set fso = CreateObject(\"Scripting.FileSystemObject\")\r\n"
        "Set shell = CreateObject(\"WScript.Shell\")\r\n"
        "shell.CurrentDirectory = fso.GetParentFolderName(WScript.ScriptFullName)\r\n"
        "shell.Run \"python run.py --open-browser\", 0, False\r\n",
        encoding="ascii",
    )

    desktop = pathlib.Path(os.environ["USERPROFILE"]) / "Desktop"
    lnk_path = desktop / "Market Analysis.lnk"

    # Generate the .ico from the favicon design (pure-Python, no Pillow)
    # if it is missing. The renderer is deterministic and fast, but we
    # skip regeneration when the file already exists so repeated
    # --install-shortcut invocations are idempotent.
    icon_path = repo / "static" / "launcher.ico"
    if not icon_path.exists():
        from app.launcher_icon import build_launcher_ico
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        icon_path.write_bytes(build_launcher_ico())

    # The .lnk targets wscript.exe (no console) with the .vbs as its
    # argument, and uses the favicon-derived .ico for its display icon.
    # Single quotes in PowerShell avoid escape gymnastics with the
    # embedded spaces in the repo path.
    ps_script = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{lnk_path}'); "
        f"$s.TargetPath = 'wscript.exe'; "
        f"$s.Arguments = '//nologo \"{vbs_path}\"'; "
        f"$s.WorkingDirectory = '{repo}'; "
        f"$s.WindowStyle = 7; "
        f"$s.IconLocation = '{icon_path},0'; "
        f"$s.Description = 'Market Analysis Tool'; "
        f"$s.Save()"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"shortcut creation failed: {result.stderr}", file=sys.stderr)
        return 1

    log_change("shortcut", f"installed desktop shortcut -> {bat_path}")
    print(f"shortcut installed at {lnk_path}")
    print(f"launch script at {bat_path}")
    return 0


def remove_shortcut() -> int:
    """Remove the desktop shortcut and the launch.bat file."""
    from app.changelog import log_change

    repo = pathlib.Path(__file__).resolve().parent
    bat_path = repo / "launch.bat"
    desktop = pathlib.Path(os.environ["USERPROFILE"]) / "Desktop"
    lnk_path = desktop / "Market Analysis.lnk"

    if lnk_path.exists():
        lnk_path.unlink()
    if bat_path.exists():
        bat_path.unlink()

    log_change("shortcut", "removed desktop shortcut and launch.bat")
    print("shortcut removed")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Market Analysis Tool")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--refresh", action="store_true", help="full refresh then exit")
    parser.add_argument("--news-refresh", action="store_true", help="fast news-only refresh then exit")
    parser.add_argument("--backfill", action="store_true", help="seed the curated event timeline then exit")
    parser.add_argument("--schedule-install", action="store_true", help="install the Windows scheduled tasks (daily full + 4-hourly news) then exit")
    parser.add_argument("--schedule-remove", action="store_true", help="remove the Windows scheduled tasks then exit")
    parser.add_argument("--schedule-status", action="store_true", help="show scheduled task status then exit")
    parser.add_argument("--commit-events", action="store_true", help="stage data/events.json and commit then exit")
    parser.add_argument("--install-shortcut", action="store_true", help="create desktop shortcut then exit")
    parser.add_argument("--remove-shortcut", action="store_true", help="remove desktop shortcut then exit")
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="open the dashboard URL in the system default browser after the server binds "
             "(used by the desktop shortcut launcher)",
    )
    parser.add_argument(
        "--logfile-prefix",
        default=None,
        metavar="PATH",
        help=(
            "append stdout/stderr to PATH-YYYYMMDD.log and delete sibling "
            f"logs older than {LOG_RETENTION_DAYS} days (used by the scheduled tasks)"
        ),
    )
    args = parser.parse_args()

    if args.logfile_prefix:
        _setup_logfile(args.logfile_prefix)

    config.ensure_dirs()

    if args.refresh:
        from app import service
        from app.lockfile import RefreshBusy

        try:
            service.refresh_all(full=True)
            print("Refresh complete.")
        except RefreshBusy:
            # Another process (usually the server) is mid-refresh; skipping
            # is safe — the next scheduled run covers it.
            print("Another refresh is already running; skipped this run.")
        return

    if args.news_refresh:
        from app import service

        result = service.refresh_news()
        print(
            "News refresh complete: "
            f"checked {result.get('feeds_checked', 0)} feed(s), "
            f"{result.get('collected', 0)} High/Critical candidate(s), "
            f"{result.get('inserted', 0)} new event(s) stored."
        )
        return

    if args.backfill:
        from app import service

        result = service.backfill_news()
        print("Backfill complete:", result)
        return

    if args.schedule_install:
        from app import scheduler

        result = scheduler.install_task()
        if result.get("success"):
            print("Scheduled tasks installed.")
            for task in result.get("tasks", []):
                print(f"  {task['task_name']}")
                print(f"    Schedule: {task['schedule']}")
                print(f"    Log file: {task['log_file']}")
        else:
            print("Failed to install one or more scheduled tasks.")
            for task in result.get("tasks", []):
                state = "installed" if task.get("success") else "FAILED"
                print(f"  {task['task_name']}: {state}")
                if not task.get("success"):
                    if task.get("error"):
                        print(f"    Error: {task['error']}")
                    if task.get("stderr"):
                        print(f"    stderr: {task['stderr']}")
                    if task.get("stdout"):
                        print(f"    stdout: {task['stdout']}")
            if result.get("error"):
                print(f"  Error: {result['error']}")
        return

    if args.schedule_remove:
        from app import scheduler

        result = scheduler.remove_task()
        if result.get("success"):
            print("Scheduled tasks removed.")
            for task in result.get("tasks", []):
                print(f"  Removed {task['task_name']}.")
        else:
            print("Failed to remove one or more scheduled tasks (they may not exist).")
            for task in result.get("tasks", []):
                state = "removed" if task.get("success") else "not found / failed"
                print(f"  {task['task_name']}: {state}")
                if not task.get("success") and task.get("stderr"):
                    print(f"    stderr: {task['stderr']}")
            if result.get("error"):
                print(f"  Error: {result['error']}")
        return

    if args.schedule_status:
        from app import scheduler

        result = scheduler.status()
        for task in result.get("tasks", []):
            print(
                f"Scheduled task '{task['task_name']}':",
                "installed" if task.get("installed") else "not installed",
            )
        if result.get("error"):
            print(f"  Error: {result['error']}")
        return

    if args.commit_events:
        rc = commit_events()
        raise SystemExit(rc)

    if args.install_shortcut:
        rc = install_shortcut()
        raise SystemExit(rc)

    if args.remove_shortcut:
        rc = remove_shortcut()
        raise SystemExit(rc)

    import uvicorn

    if args.open_browser:
        # Schedule a delayed browser open so the server has time to bind.
        # ``webbrowser.open`` is non-blocking on Windows (uses os.startfile),
        # so the timer thread can run alongside uvicorn.
        url = f"http://{args.host}:{args.port}"
        timer = threading.Timer(_BROWSER_OPEN_DELAY_S, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()

    print(f"Serving Market Analysis Tool at http://{args.host}:{args.port}")
    uvicorn.run("app.api:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
