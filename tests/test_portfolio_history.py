"""Tests for app/portfolio_history.py + GET /api/portfolios/history.

Covers: writer idempotency (write-if-absent), missing-close null semantics
(no partial sum), the settled-bar guard, the endpoint shape (nulls + empty
store), the retrospective computation on mocked bulk data, and that the
static ``/history`` route is not shadowed by a dynamic portfolio route.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import portfolio, portfolio_history
from app.api import app


@pytest.fixture(autouse=True)
def _accept_symbols(monkeypatch):
    monkeypatch.setattr(
        "app.validation.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )


@pytest.fixture
def client():
    return TestClient(app, base_url="http://127.0.0.1:8000")


def _fake_bulk(mapping):
    """A get_histories_bulk stand-in returning only the supplied symbols."""
    return lambda symbols, days=260: {s: mapping[s] for s in symbols if s in mapping}


def _rows(*pairs):
    return [{"date": d, "close": c} for d, c in pairs]


# ---- Writer ---------------------------------------------------------------

def test_record_snapshot_writes_latest_eligible_close(monkeypatch):
    monkeypatch.setattr(
        "app.market.get_histories_bulk",
        _fake_bulk({"AAPL": _rows(("2020-01-01", 100.0), ("2020-01-02", 110.0))}),
    )
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "AAPL", 10, 1000.0)

    entry = portfolio_history.record_snapshot()
    assert entry is not None
    assert entry["close_date"] == "2020-01-02"
    assert entry["recorded_at"].endswith("Z")
    pf = entry["portfolios"]["main"]
    assert pf["total_value"] == 1100.0
    assert pf["total_cost"] == 1000.0
    assert pf["coverage"] == {"ok": 1, "total": 1}
    assert pf["holdings"]["AAPL"] == {"shares": 10.0, "close": 110.0, "value": 1100.0}


def test_record_snapshot_is_idempotent_same_close_date(monkeypatch):
    monkeypatch.setattr(
        "app.market.get_histories_bulk",
        _fake_bulk({"AAPL": _rows(("2020-01-02", 110.0))}),
    )
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "AAPL", 10, 1000.0)

    portfolio_history.record_snapshot()
    before = portfolio_history.HISTORY_PATH.read_text(encoding="utf-8")
    # Second run for the same close date must be a no-op (past entries are
    # never rewritten — recorded_at would otherwise change).
    second = portfolio_history.record_snapshot()
    after = portfolio_history.HISTORY_PATH.read_text(encoding="utf-8")

    assert before == after
    assert second["close_date"] == "2020-01-02"
    state = portfolio_history.load_history()
    assert list(state["snapshots"].keys()) == ["2020-01-02"]


def test_missing_close_yields_nulls_and_no_partial_sum(monkeypatch):
    # NVDA is a held symbol but has no rows for the close date.
    monkeypatch.setattr(
        "app.market.get_histories_bulk",
        _fake_bulk({"AAPL": _rows(("2020-01-02", 110.0))}),
    )
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "AAPL", 10, 1000.0)
    portfolio.add_holding("main", "NVDA", 5, 4000.0)
    portfolio.add_cash_row("main", "Cash", 500.0, 500.0)

    entry = portfolio_history.record_snapshot()
    pf = entry["portfolios"]["main"]

    assert pf["holdings"]["AAPL"]["value"] == 1100.0
    assert pf["holdings"]["NVDA"]["close"] is None
    assert pf["holdings"]["NVDA"]["value"] is None
    # Never a partial sum: one missing close nulls the whole total_value.
    assert pf["total_value"] is None
    # Cash cost still joins the cost sum (client-side parity).
    assert pf["total_cost"] == 1000.0 + 4000.0 + 500.0
    assert pf["coverage"] == {"ok": 1, "total": 2}


def test_settled_bar_guard_rejects_partial_in_session_bar(monkeypatch):
    today = "2026-10-12"
    monkeypatch.setattr(
        "app.market.get_histories_bulk",
        _fake_bulk({"AAPL": _rows(("2026-10-10", 100.0), (today, 105.0))}),
    )
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "AAPL", 10, 1000.0)

    # 15:00 ET (19:00 UTC) — today's bar is still in-session, not settled.
    mid_session = datetime(2026, 10, 12, 19, 0, tzinfo=timezone.utc)
    entry = portfolio_history.record_snapshot(now=mid_session)
    assert entry["close_date"] == "2026-10-10"

    # 16:20 ET (20:20 UTC) — today's bar is now settled and eligible.
    after_settle = datetime(2026, 10, 12, 20, 20, tzinfo=timezone.utc)
    entry2 = portfolio_history.record_snapshot(now=after_settle)
    assert entry2["close_date"] == today


def test_record_snapshot_skips_when_bulk_empty(monkeypatch):
    monkeypatch.setattr("app.market.get_histories_bulk", lambda symbols, days=260: {})
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "AAPL", 10, 1000.0)

    assert portfolio_history.record_snapshot() is None
    assert not portfolio_history.HISTORY_PATH.exists()


# ---- Endpoint -------------------------------------------------------------

def test_endpoint_shape_with_nulls(client, monkeypatch):
    from datetime import date as _date

    bulk = {
        "AAPL": _rows(("2020-01-01", 100.0), ("2020-01-02", 110.0)),
        "NVDA": _rows(("2020-01-02", 200.0)),
    }
    monkeypatch.setattr("app.market.get_histories_bulk", _fake_bulk(bulk))
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "AAPL", 10, 1000.0)
    portfolio.add_holding("main", "NVDA", 5, 4000.0)

    # Seed an earlier entry where NVDA has no close (null) through the same
    # builder the writer uses, then let the writer add the latest date.
    state = portfolio_history.load_history()
    state["snapshots"]["2020-01-01"] = {
        "close_date": "2020-01-01",
        "recorded_at": "2020-01-01T21:00:00Z",
        "portfolios": {
            "main": portfolio_history._build_portfolio_snapshot(
                portfolio.load_portfolios()["portfolios"]["main"],
                {"AAPL": bulk["AAPL"]},  # NVDA absent -> null
                _date(2020, 1, 1),
            )
        },
    }
    portfolio_history.save_history(state)
    portfolio_history.record_snapshot()  # adds 2020-01-02 (all closes present)

    r = client.get("/api/portfolios/history")
    assert r.status_code == 200
    body = r.json()

    assert body["portfolios"] == [{"id": "main", "name": "Main"}]
    assert body["meta"]["as_of"].endswith("Z")

    snaps = body["snapshots"]["main"]
    assert [p["date"] for p in snaps] == ["2020-01-01", "2020-01-02"]

    # 2020-01-01: NVDA has no close -> value null, gain null, coverage 1/2.
    d1 = snaps[0]
    assert d1["value"] is None
    assert d1["gain"] is None
    assert d1["cost"] == 5000.0
    assert d1["coverage"] == {"ok": 1, "total": 2}

    # 2020-01-02: all closes present -> value = 10*110 + 5*200, gain = value-cost.
    d2 = snaps[1]
    assert d2["value"] == 2100.0
    assert d2["cost"] == 5000.0
    assert d2["gain"] == -2900.0
    assert d2["coverage"] == {"ok": 2, "total": 2}


def test_endpoint_empty_store_still_works(client):
    r = client.get("/api/portfolios/history")
    assert r.status_code == 200
    body = r.json()
    assert body["snapshots"] == {}
    assert body["portfolios"] == []
    assert body["retrospective"] == {}
    assert body["meta"]["as_of"].endswith("Z")


def test_endpoint_route_not_shadowed(client):
    """The static /history segment resolves to the history handler, not a
    dynamic /api/portfolios/{pid} route."""
    r = client.get("/api/portfolios/history")
    assert r.status_code == 200, r.text
    assert "snapshots" in r.json()
    # And a portfolio named "history" doesn't change the routing outcome.
    portfolio.create_portfolio("history")
    r2 = client.get("/api/portfolios/history")
    assert r2.status_code == 200
    assert "snapshots" in r2.json()


# ---- Retrospective --------------------------------------------------------

def test_retro_series_applies_current_holdings_backwards(client, monkeypatch):
    monkeypatch.setattr(
        "app.market.get_histories_bulk",
        _fake_bulk({
            "AAPL": _rows(("2020-01-01", 100.0), ("2020-01-02", 110.0), ("2020-01-03", 120.0)),
            "MSFT": _rows(("2020-01-02", 50.0), ("2020-01-03", 60.0)),
        }),
    )
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "AAPL", 10, 1000.0)
    portfolio.add_holding("main", "MSFT", 4, 200.0)

    body = client.get("/api/portfolios/history").json()
    retro = body["retrospective"]["main"]
    assert [p["date"] for p in retro] == ["2020-01-01", "2020-01-02", "2020-01-03"]

    # 2020-01-01: MSFT missing -> whole value null, coverage 1/2.
    assert retro[0]["value"] is None
    assert retro[0]["gain"] is None
    assert retro[0]["coverage"] == {"ok": 1, "total": 2}
    # cost = current total cost, constant across the series.
    assert retro[0]["cost"] == 1200.0

    # 2020-01-03: value = 10*120 + 4*60 = 1440, gain = 1440 - 1200.
    assert retro[2]["value"] == 1440.0
    assert retro[2]["cost"] == 1200.0
    assert retro[2]["gain"] == 240.0
    assert retro[2]["coverage"] == {"ok": 2, "total": 2}


def test_retro_series_respects_settled_bar_guard(client, monkeypatch):
    today = "2026-10-12"
    monkeypatch.setattr(
        "app.market.get_histories_bulk",
        _fake_bulk({"AAPL": _rows(("2026-10-10", 100.0), (today, 105.0))}),
    )
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "AAPL", 10, 1000.0)

    mid_session = datetime(2026, 10, 12, 19, 0, tzinfo=timezone.utc)
    body = portfolio_history.build_history_payload(now=mid_session)
    dates = [p["date"] for p in body["retrospective"]["main"]]
    assert dates == ["2026-10-10"]


# ---- Refresh wiring -------------------------------------------------------

def test_refresh_all_invokes_snapshot_writer(monkeypatch):
    import contextlib

    from app import service

    calls = {"n": 0}
    monkeypatch.setattr(service, "refresh_lock", lambda: contextlib.nullcontext())
    monkeypatch.setattr(service, "refresh_market", lambda: {"vintage": {}})
    monkeypatch.setattr(service.news, "fetch_and_store", lambda: [])
    monkeypatch.setattr(service.regime, "get_regime", lambda: {})
    monkeypatch.setattr(
        service.portfolio_history, "record_snapshot", lambda: calls.__setitem__("n", calls["n"] + 1)
    )

    service.refresh_all(full=False)
    assert calls["n"] == 1


def test_refresh_all_survives_snapshot_failure(monkeypatch):
    import contextlib

    from app import service

    def _boom():
        raise RuntimeError("snapshot exploded")

    monkeypatch.setattr(service, "refresh_lock", lambda: contextlib.nullcontext())
    monkeypatch.setattr(service, "refresh_market", lambda: {"vintage": {}})
    monkeypatch.setattr(service.news, "fetch_and_store", lambda: [])
    monkeypatch.setattr(service.regime, "get_regime", lambda: {})
    monkeypatch.setattr(service.portfolio_history, "record_snapshot", _boom)

    result = service.refresh_all(full=False)
    assert isinstance(result, dict)
