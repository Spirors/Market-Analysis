"""Tests for scripts/check_capture_freshness.py (stdlib-only freshness gate)."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "check_capture_freshness",
    Path(__file__).resolve().parent.parent / "scripts" / "check_capture_freshness.py",
)
assert _SPEC and _SPEC.loader
fresh = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fresh)


def _status(runid: str, finished: str, ok: bool = True) -> dict:
    return {
        "runid": runid, "mode": "local", "started_at": finished, "finished_at": finished,
        "ok": ok, "steps": [], "new_history_dates": [], "new_events": 0, "latest_close_date": None,
    }


def _write(captures: Path, runid: str, doc: dict) -> None:
    d = captures / "_status"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{runid}.json").write_text(json.dumps(doc), encoding="utf-8")


def test_missing_status_dir_fails(tmp_path):
    result = fresh.check(tmp_path / "captures", max_age_hours=6)
    assert result["ok"] is False
    assert result["status"] is None


def test_fresh_ok_status_passes(tmp_path):
    captures = tmp_path / "captures"
    now = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
    _write(captures, "r1", _status("r1", (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")))
    result = fresh.check(captures, max_age_hours=6, now=now)
    assert result["ok"] is True
    assert result["age_hours"] == 1.0


def test_stale_status_fails(tmp_path):
    captures = tmp_path / "captures"
    now = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
    _write(captures, "r1", _status("r1", (now - timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%SZ")))
    result = fresh.check(captures, max_age_hours=6, now=now)
    assert result["ok"] is False
    assert any("stale" in p for p in result["problems"])


def test_failed_status_fails(tmp_path):
    captures = tmp_path / "captures"
    now = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
    _write(captures, "r1", _status("r1", now.strftime("%Y-%m-%dT%H:%M:%SZ"), ok=False))
    result = fresh.check(captures, max_age_hours=6, now=now)
    assert result["ok"] is False
    assert any("not ok" in p for p in result["problems"])


def test_latest_status_is_picked_by_finished_at(tmp_path):
    captures = tmp_path / "captures"
    now = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
    _write(captures, "old", _status("old", (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")))
    _write(captures, "new", _status("new", (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")))
    result = fresh.check(captures, max_age_hours=6, now=now)
    assert result["ok"] is True
    assert result["status"]["runid"] == "new"


def test_main_exit_codes(tmp_path, capsys):
    captures = tmp_path / "captures"
    now = datetime.now(timezone.utc)
    _write(captures, "r1", _status("r1", now.strftime("%Y-%m-%dT%H:%M:%SZ")))
    assert fresh.main(["--captures-dir", str(captures), "--max-age-hours", "6"]) == 0
    assert fresh.main(["--captures-dir", str(tmp_path / "nope"), "--max-age-hours", "6"]) == 1
