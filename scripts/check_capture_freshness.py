"""Freshness gate for the private data repo's capture status.

Used by ``.github/workflows/capture.yml`` as the continuity check, and runnable
by hand:

    python scripts/check_capture_freshness.py --captures-dir <repo>/captures --max-age-hours 6

The latest ``captures/_status/<runid>.json`` (by ``finished_at``) must exist,
be ``ok``, and be within ``--max-age-hours`` of now; otherwise exit 1 with a
sanitized report (runids, dates and ok flags only — no holdings or values).

Alerting to configure (owner):
  * healthchecks.io — create a check whose period equals the intended schedule
    and whose grace period covers the workflow's worst-case runtime; the capture
    workflow's success/failure heartbeats ping it via ``HEALTHCHECK_URL``. A
    missed run (no ping) alerts after period + grace.
  * GitHub — enable workflow failure notifications (Settings → Notifications)
    so a red run emails the owner.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STATUS_SUBDIR = "_status"


def _parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def latest_status(captures_dir: Path) -> tuple[dict | None, Path | None]:
    """The status doc with the greatest ``finished_at`` (or ``(None, None)``)."""
    status_dir = Path(captures_dir) / STATUS_SUBDIR
    if not status_dir.is_dir():
        return None, None
    best: dict | None = None
    best_path: Path | None = None
    for path in sorted(status_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if best is None or str(data.get("finished_at") or "") > str(best.get("finished_at") or ""):
            best, best_path = data, path
    return best, best_path


def check(captures_dir: Path, max_age_hours: float, now: datetime | None = None) -> dict:
    """Return ``{"ok", "status", "age_hours", "problems"}`` for the latest status."""
    status, _path = latest_status(captures_dir)
    if status is None:
        return {"ok": False, "status": None, "age_hours": None,
                "problems": [f"no status file found under {Path(captures_dir) / STATUS_SUBDIR}"]}

    now = now or datetime.now(timezone.utc)
    finished = _parse_ts(status.get("finished_at"))
    age = None if finished is None else (now - finished).total_seconds() / 3600.0
    problems: list[str] = []
    if not status.get("ok"):
        problems.append(f"latest status is not ok (runid={status.get('runid')})")
    if age is None:
        problems.append("latest status finished_at is missing/unparseable")
    elif age > max_age_hours:
        problems.append(f"latest status is stale ({age:.1f}h > {max_age_hours:g}h)")
    return {"ok": not problems, "status": status, "age_hours": age, "problems": problems}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture freshness gate (sanitized)")
    parser.add_argument("--captures-dir", required=True)
    parser.add_argument("--max-age-hours", type=float, default=6.0)
    args = parser.parse_args(argv)

    result = check(Path(args.captures_dir), args.max_age_hours)
    status = result["status"]
    print(f"capture freshness: ok={result['ok']} (max age {args.max_age_hours:g}h)")
    if status:
        print(
            "  latest: "
            f"runid={status.get('runid')} mode={status.get('mode')} "
            f"ok={status.get('ok')} finished={status.get('finished_at')} "
            f"latest_close_date={status.get('latest_close_date')}"
        )
    age = result["age_hours"]
    print(f"  age: {'unknown' if age is None else f'{age:.1f}h'}")
    for problem in result["problems"]:
        print(f"  - {problem}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
