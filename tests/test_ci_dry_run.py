"""Tests for the CI dry-run helper (scripts/ci_dry_run.py).

The helper takes explicit paths, so every test uses ``tmp_path`` and never
touches the real ``data/`` (see the autouse ``_isolate_data_files`` fixture in
``tests/conftest.py`` — this module deliberately does not import ``app``).
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "ci_dry_run",
    Path(__file__).resolve().parent.parent / "scripts" / "ci_dry_run.py",
)
assert _SPEC and _SPEC.loader
ci = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ci)


def _recent_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dashboard(**overrides) -> dict:
    data = {
        "as_of": _recent_iso(),
        "market": {"indices": {}},
        "indicators": {},
        "risk": {},
        "portfolios": {"dry-run": {"id": "dry-run"}},
        "news": {},
        "vintage": {"market": _recent_iso()},
    }
    data.update(overrides)
    return data


# --------------------------------------------------------------------------- #
# seed
# --------------------------------------------------------------------------- #

def test_seed_writes_synthetic_portfolio(tmp_path):
    info = ci.seed(tmp_path)
    state = json.loads((tmp_path / "portfolios.json").read_text(encoding="utf-8"))

    assert info["tickers"] == ["SPY", "AAPL", "MSFT"]
    assert state["version"] == 1
    assert list(state["portfolios"]) == ["dry-run"]
    portfolio = state["portfolios"]["dry-run"]
    assert [h["symbol"] for h in portfolio["holdings"]] == ["SPY", "AAPL", "MSFT"]
    assert all({"symbol", "shares", "total_cost"} <= set(h) for h in portfolio["holdings"])


def test_seed_refuses_to_overwrite_without_force(tmp_path):
    ci.seed(tmp_path)
    with pytest.raises(FileExistsError):
        ci.seed(tmp_path)


def test_seed_force_overwrites(tmp_path):
    (tmp_path / "portfolios.json").write_text('{"version": 1, "portfolios": {}}', encoding="utf-8")
    ci.seed(tmp_path, force=True)
    state = json.loads((tmp_path / "portfolios.json").read_text(encoding="utf-8"))
    assert "dry-run" in state["portfolios"]


# --------------------------------------------------------------------------- #
# validate_dashboard
# --------------------------------------------------------------------------- #

def test_validate_dashboard_ok():
    assert ci.validate_dashboard(_dashboard()) == []


def test_validate_dashboard_flags_missing_section():
    data = _dashboard()
    del data["news"]
    problems = ci.validate_dashboard(data)
    assert any("news" in p for p in problems)


def test_validate_dashboard_flags_stale_as_of():
    stale = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    problems = ci.validate_dashboard(_dashboard(as_of=stale))
    assert any("stale" in p for p in problems)


def test_validate_dashboard_flags_empty_portfolios():
    problems = ci.validate_dashboard(_dashboard(portfolios={}))
    assert any("portfolios is empty" in p for p in problems)


def test_validate_dashboard_rejects_non_object():
    assert ci.validate_dashboard(["not", "a", "dict"]) == [
        "dashboard.json is not a JSON object"
    ]


# --------------------------------------------------------------------------- #
# validate_history
# --------------------------------------------------------------------------- #

def test_validate_history_ok():
    data = {"version": 1, "snapshots": {"2026-10-09": {"close_date": "2026-10-09"}}}
    problems, info = ci.validate_history(data)
    assert problems == []
    assert info["entries"] == 1
    assert info["close_dates"] == ["2026-10-09"]


def test_validate_history_flags_empty_snapshots():
    problems, _info = ci.validate_history({"version": 1, "snapshots": {}})
    assert any("no snapshots" in p for p in problems)


def test_validate_history_flags_invalid_date():
    data = {"version": 1, "snapshots": {"not-a-date": {}}}
    problems, _info = ci.validate_history(data)
    assert any("invalid close_date" in p for p in problems)


def test_validate_history_flags_future_date():
    future = (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat()
    problems, _info = ci.validate_history({"version": 1, "snapshots": {future: {}}})
    assert any("future" in p for p in problems)


# --------------------------------------------------------------------------- #
# check_idempotency
# --------------------------------------------------------------------------- #

def _hist(*dates: str, entry=None) -> dict:
    return {"version": 1, "snapshots": {d: (entry or {"close_date": d}) for d in dates}}


def test_check_idempotency_ok_when_only_one_date_added():
    before = _hist("2026-10-09")
    after = _hist("2026-10-09", "2026-10-12")
    problems, info = ci.check_idempotency(before, after)
    assert problems == []
    assert info["added"] == ["2026-10-12"]


def test_check_idempotency_flags_rewritten_entry():
    before = _hist("2026-10-09")
    after = {"version": 1, "snapshots": {"2026-10-09": {"close_date": "2026-10-09", "x": 1}}}
    problems, _info = ci.check_idempotency(before, after)
    assert any("rewritten" in p for p in problems)


def test_check_idempotency_flags_lost_date():
    before = _hist("2026-10-09", "2026-10-08")
    after = _hist("2026-10-09")
    problems, _info = ci.check_idempotency(before, after)
    assert any("lost" in p for p in problems)


def test_check_idempotency_flags_more_than_one_new_date():
    before = _hist("2026-10-09")
    after = _hist("2026-10-09", "2026-10-12", "2026-10-13")
    problems, _info = ci.check_idempotency(before, after)
    assert any("more than one new date" in p for p in problems)


def test_check_idempotency_flags_duplicate_dates():
    problems, _info = ci.check_idempotency(_hist("2026-10-09"), _hist("2026-10-09"), ["2026-10-09"])
    assert any("duplicate" in p for p in problems)


# --------------------------------------------------------------------------- #
# JSON loader + CLI end-to-end
# --------------------------------------------------------------------------- #

def test_load_json_with_dups_detects_duplicate_keys(tmp_path):
    path = tmp_path / "dup.json"
    path.write_text('{"snapshots": {"2026-10-09": {}, "2026-10-09": {}}}', encoding="utf-8")
    data, dups = ci.load_json_with_dups(path)
    assert dups == ["2026-10-09"]
    assert data["snapshots"] == {"2026-10-09": {}}


def test_cli_validate_end_to_end(tmp_path):
    (tmp_path / "dashboard.json").write_text(json.dumps(_dashboard()), encoding="utf-8")
    (tmp_path / "portfolio_history.json").write_text(
        json.dumps(_hist("2026-10-09")), encoding="utf-8"
    )
    report = tmp_path / "logs" / "report.txt"
    rc = ci.main(["validate", "--data-dir", str(tmp_path), "--report", str(report)])
    assert rc == 0
    assert "RESULT: OK" in report.read_text(encoding="utf-8")


def test_cli_validate_fails_on_missing_files(tmp_path):
    rc = ci.main(["validate", "--data-dir", str(tmp_path)])
    assert rc == 1


def test_cli_seed_then_validate_and_idempotency(tmp_path):
    assert ci.main(["seed", "--data-dir", str(tmp_path)]) == 0
    assert (tmp_path / "portfolios.json").exists()

    before = tmp_path / "history_before.json"
    after = tmp_path / "history_after.json"
    before.write_text(json.dumps(_hist("2026-10-09")), encoding="utf-8")
    after.write_text(json.dumps(_hist("2026-10-09")), encoding="utf-8")
    assert (
        ci.main(
            ["check-idempotency", "--before", str(before), "--after", str(after)]
        )
        == 0
    )
