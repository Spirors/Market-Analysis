"""Tests for app/sync.py — cloud export + local fold transport.

All paths are explicit (tmp_path); the real ``data/`` is never touched. The
fold redirects ``app.store`` at the given data dir only for the duration of an
upsert, and restores it on exit.
"""

from __future__ import annotations

import json

import pytest

from app import sync


def _repo(tmp_path, name="repo"):
    repo = tmp_path / name
    for sub in ("history", "events", "_status"):
        (repo / "captures" / sub).mkdir(parents=True)
    return repo


def _history_entry(close_date: str) -> dict:
    return {"close_date": close_date, "recorded_at": "2020-01-01T21:00:00Z", "portfolios": {}}


def _status(runid: str, finished: str, ok: bool = True, **extra) -> dict:
    doc = {
        "runid": runid, "mode": "local",
        "started_at": finished, "finished_at": finished,
        "ok": ok, "steps": [], "new_history_dates": [],
        "new_events": 0, "latest_close_date": None,
    }
    doc.update(extra)
    return doc


# --------------------------------------------------------------------------- #
# export
# --------------------------------------------------------------------------- #

def test_export_writes_history_events_and_status_only(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "portfolio_history.json").write_text(
        json.dumps({"version": 1, "snapshots": {"2020-01-01": _history_entry("2020-01-01")}}),
        encoding="utf-8",
    )
    (data / "events.json").write_text(
        json.dumps({"version": 1, "suppressed_sources": [], "events": [
            {"link": "a", "title": "A", "published": "2020-01-01T00:00:00Z"},
            {"link": "b", "title": "B", "published": "2020-01-01T00:00:00Z"},
        ]}),
        encoding="utf-8",
    )
    (data / "portfolios.json").write_text(
        json.dumps({"version": 1, "portfolios": {"main": {"id": "main", "name": "Main", "holdings": []}}}),
        encoding="utf-8",
    )
    before = tmp_path / "events.before.json"
    before.write_text(json.dumps({"version": 1, "events": [{"link": "a", "title": "A"}]}), encoding="utf-8")

    repo = _repo(tmp_path)
    result = sync.export_captures(
        data_dir=data, repo_dir=repo, runid="run1", mode="local",
        started_at="2020-01-01T00:00:00Z", finished_at="2020-01-01T00:05:00Z",
        steps=[{"name": "refresh", "ok": True}], events_before_path=before,
    )

    assert result["ok"] is True
    assert result["new_history_dates"] == ["2020-01-01"]
    assert result["new_events"] == 1
    assert (repo / "captures/history/2020-01-01.json").exists()
    events_doc = json.loads((repo / "captures/events/run1.json").read_text(encoding="utf-8"))
    assert [e["link"] for e in events_doc["events"]] == ["b"]
    status = json.loads((repo / "captures/_status/run1.json").read_text(encoding="utf-8"))
    assert status["ok"] is True
    assert status["new_events"] == 1
    assert status["latest_close_date"] == "2020-01-01"
    # Cloud export writes ONLY captures/** — state/** belongs to the local fold.
    assert not (repo / "state").exists()
    # Sanitized: the status never carries holdings/values.
    assert "holdings" not in json.dumps(status)
    assert "total_value" not in json.dumps(status)


def test_export_never_overwrites_existing_capture(tmp_path):
    repo = _repo(tmp_path)
    sentinel = repo / "captures/history/2020-01-01.json"
    sentinel.write_text('{"sentinel": true}', encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    (data / "portfolio_history.json").write_text(
        json.dumps({"version": 1, "snapshots": {"2020-01-01": _history_entry("2020-01-01")}}),
        encoding="utf-8",
    )

    result = sync.export_captures(
        data_dir=data, repo_dir=repo, runid="run1", mode="local",
        started_at="2020-01-01T00:00:00Z", finished_at="2020-01-01T00:05:00Z",
        steps=[{"name": "refresh", "ok": True}],
    )
    assert "history/2020-01-01.json" in result["skipped"]
    assert sentinel.read_text(encoding="utf-8") == '{"sentinel": true}'


def test_export_empty_data_dir_is_graceful(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    repo = tmp_path / "fresh-repo"  # does not exist yet

    result = sync.export_captures(
        data_dir=data, repo_dir=repo, runid="run1", mode="local",
        started_at="2020-01-01T00:00:00Z", finished_at="2020-01-01T00:05:00Z",
        steps=[{"name": "refresh", "ok": True}],
    )
    assert result["ok"] is True
    assert result["new_history_dates"] == []
    assert result["new_events"] == 0
    assert (repo / "captures/events/run1.json").exists()
    assert (repo / "captures/_status/run1.json").exists()


def test_export_marks_failure_status(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    repo = _repo(tmp_path)
    result = sync.export_captures(
        data_dir=data, repo_dir=repo, runid="run1", mode="local",
        started_at="2020-01-01T00:00:00Z", finished_at="2020-01-01T00:05:00Z",
        steps=[{"name": "refresh", "ok": False}], error="boom",
    )
    assert result["ok"] is False
    status = json.loads((repo / "captures/_status/run1.json").read_text(encoding="utf-8"))
    assert status["ok"] is False
    assert status["error"] == "boom"


# --------------------------------------------------------------------------- #
# validators / validate
# --------------------------------------------------------------------------- #

def test_validate_captures_flags_invalid_files(tmp_path):
    repo = _repo(tmp_path)
    (repo / "captures/history/bad.json").write_text("{ not json", encoding="utf-8")
    (repo / "captures/_status/x.json").write_text(json.dumps({"runid": "x"}), encoding="utf-8")
    result = sync.validate_captures(repo)
    assert result["ok"] is False
    assert any("bad.json" in p for p in result["problems"])
    assert any("x.json" in p for p in result["problems"])


def test_validators_pure():
    assert sync.validate_history_entry({"close_date": "2020-01-01", "recorded_at": "x", "portfolios": {}}) == []
    assert sync.validate_history_entry([]) == ["not a JSON object"]
    assert sync.validate_events_doc({"runid": "r", "captured_at": "x", "events": []}) == []
    assert "events missing/not a list" in sync.validate_events_doc({"runid": "r", "captured_at": "x"})
    assert sync.validate_status(_status("r", "2020-01-01T00:00:00Z")) == []


def test_new_events_since_diffs_by_link():
    current = [{"link": "a"}, {"link": "b"}, {"link": "c"}]
    assert [e["link"] for e in sync.new_events_since(current, {"a", "c"})] == ["b"]


# --------------------------------------------------------------------------- #
# fold
# --------------------------------------------------------------------------- #

def _write_capture(repo, kind, name, doc):
    (repo / "captures" / kind / name).write_text(json.dumps(doc), encoding="utf-8")


def test_fold_applies_history_and_events_then_is_noop(tmp_path):
    repo = _repo(tmp_path)
    _write_capture(repo, "history", "2020-01-01.json", _history_entry("2020-01-01"))
    _write_capture(repo, "events", "run1.json", {
        "runid": "run1", "captured_at": "2020-01-01T00:05:00Z",
        "events": [{"link": "n1", "source": "S", "title": "N", "published": "2020-01-01T00:00:00Z", "impact": "High"}],
    })
    _write_capture(repo, "_status", "run1.json", _status("run1", "2020-01-01T00:05:00Z", new_events=1))

    data = tmp_path / "data"
    data.mkdir()
    first = sync.fold_captures(repo_dir=repo, data_dir=data)
    assert first["history_added"] == ["2020-01-01"]
    assert first["events_inserted"] == 1
    assert "2020-01-01" in json.loads((data / "portfolio_history.json").read_text(encoding="utf-8"))["snapshots"]
    assert any(e["link"] == "n1" for e in json.loads((data / "events.json").read_text(encoding="utf-8"))["events"])

    second = sync.fold_captures(repo_dir=repo, data_dir=data)
    assert second["history_added"] == []
    assert second["events_inserted"] == 0
    assert second["history_existing"] == ["2020-01-01"]


def test_fold_is_all_or_nothing_on_invalid_capture(tmp_path):
    repo = _repo(tmp_path)
    _write_capture(repo, "history", "2020-01-01.json", _history_entry("2020-01-01"))
    (repo / "captures/history/bad.json").write_text("{ not json", encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()

    with pytest.raises(sync.SyncValidationError):
        sync.fold_captures(repo_dir=repo, data_dir=data)
    assert not (data / "portfolio_history.json").exists()  # nothing applied


def test_fold_rejects_close_date_filename_mismatch(tmp_path):
    repo = _repo(tmp_path)
    _write_capture(repo, "history", "2020-01-01.json", _history_entry("2020-01-02"))
    data = tmp_path / "data"
    data.mkdir()
    with pytest.raises(sync.SyncValidationError):
        sync.fold_captures(repo_dir=repo, data_dir=data)


def test_fold_leaves_existing_user_edited_event_untouched(tmp_path):
    repo = _repo(tmp_path)
    _write_capture(repo, "events", "run1.json", {
        "runid": "run1", "captured_at": "2020-01-01T00:05:00Z",
        "events": [{"link": "L", "source": "S", "title": "cloud title", "published": "2020-01-01T00:00:00Z"}],
    })
    data = tmp_path / "data"
    data.mkdir()
    (data / "events.json").write_text(json.dumps({
        "version": 1, "suppressed_sources": [],
        "events": [{"link": "L", "title": "local title", "user_edited": True, "importance": 5,
                    "published": "2020-01-01T00:00:00Z"}],
    }), encoding="utf-8")

    result = sync.fold_captures(repo_dir=repo, data_dir=data)
    assert result["events_inserted"] == 0
    row = next(e for e in json.loads((data / "events.json").read_text(encoding="utf-8"))["events"]
               if e["link"] == "L")
    assert row["title"] == "local title"
    assert row["user_edited"] is True


def test_fold_reports_stale_and_failed_status(tmp_path):
    repo = _repo(tmp_path)
    _write_capture(repo, "_status", "old.json", _status("old", "2000-01-01T00:00:00Z"))
    _write_capture(repo, "_status", "new.json", _status("new", "2026-10-13T00:00:00Z", ok=False))
    data = tmp_path / "data"
    data.mkdir()

    result = sync.fold_captures(repo_dir=repo, data_dir=data, max_status_age_hours=6)
    # Latest status is picked by finished_at; it is failed, so stale.
    assert result["latest_status"]["runid"] == "new"
    assert result["status_stale"] is True


# --------------------------------------------------------------------------- #
# state mirroring
# --------------------------------------------------------------------------- #

def test_copy_state_round_trip(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "portfolios.json").write_text(json.dumps({"version": 1, "portfolios": {}}), encoding="utf-8")
    (data / "portfolio_history.json").write_text(json.dumps({"version": 1, "snapshots": {}}), encoding="utf-8")

    repo = tmp_path / "repo"
    (repo / "state").mkdir(parents=True)
    written = sync.copy_state_to_repo(data, repo)
    assert set(written) == {"state/portfolios.json", "state/portfolio_history.json"}

    data2 = tmp_path / "data2"
    data2.mkdir()
    result = sync.copy_state_from_repo(repo, data2)
    assert (data2 / "portfolios.json").exists()
    assert (data2 / "portfolio_history.json").exists()
    assert set(result["copied"]) == {"state/portfolios.json", "state/portfolio_history.json"}


def test_validate_state_dir_accepts_new_state_shapes(tmp_path):
    repo = tmp_path / "repo"
    (repo / "state").mkdir(parents=True)
    (repo / "state/watchlist.json").write_text(json.dumps({"tickers": []}), encoding="utf-8")
    (repo / "state/earnings_removed.json").write_text(json.dumps({"tickers": ["MSFT"]}), encoding="utf-8")
    assert sync.validate_state_dir(repo) == []

    # Forward-compatible but not sloppy: a non-list tickers value is a problem.
    (repo / "state/watchlist.json").write_text(json.dumps({"tickers": "AAPL"}), encoding="utf-8")
    problems = sync.validate_state_dir(repo)
    assert any("watchlist.json" in p and "tickers not a list" in p for p in problems)


def test_copy_state_from_repo_rejects_invalid(tmp_path):
    repo = tmp_path / "repo"
    (repo / "state").mkdir(parents=True)
    (repo / "state/portfolios.json").write_text(json.dumps({"version": 2}), encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    with pytest.raises(sync.SyncValidationError):
        sync.copy_state_from_repo(repo, data)
