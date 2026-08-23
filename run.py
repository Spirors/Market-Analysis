"""Run the Market Analysis Tool (local webapp).

Usage:
    python run.py                 # serve at http://127.0.0.1:8000
    python run.py --port 9000     # custom port
    python run.py --refresh       # run a full refresh once and exit
    python run.py --news-refresh  # fast news-only ingest once and exit
    python run.py --backfill      # seed the curated event timeline then exit
"""

import argparse

from app import config


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
    args = parser.parse_args()

    config.ensure_dirs()

    if args.refresh:
        from app import service

        service.refresh_all(full=True)
        print("Refresh complete.")
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

    import uvicorn

    print(f"Serving Market Analysis Tool at http://{args.host}:{args.port}")
    uvicorn.run("app.api:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
