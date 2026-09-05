"""Tests for app/portfolio.py: CRUD on data/portfolios.json."""

import json
import pytest

from app import portfolio


@pytest.fixture
def tmp_portfolios(monkeypatch, tmp_path):
    monkeypatch.setattr(portfolio, "PORTFOLIOS_PATH", tmp_path / "portfolios.json")
    return tmp_path / "portfolios.json"


def test_load_returns_default_when_missing(tmp_portfolios):
    state = portfolio.load_portfolios()
    assert state["version"] == 1
    assert state["portfolios"] == {}
    assert "earnings" in state["column_order"]
    assert "portfolio" in state["column_order"]
    assert "earnings" in state["column_visibility"]


def test_create_derives_slug_id(tmp_portfolios):
    result = portfolio.create_portfolio("Fidelity Cash")
    assert result["id"] == "fidelity-cash"
    assert result["portfolio"]["name"] == "Fidelity Cash"
    assert result["portfolio"]["holdings"] == []


def test_create_collision_appends_suffix(tmp_portfolios):
    portfolio.create_portfolio("Fidelity Cash")
    second = portfolio.create_portfolio("Fidelity Cash")
    assert second["id"] == "fidelity-cash-2"


def test_create_rejects_empty_name(tmp_portfolios):
    with pytest.raises(ValueError):
        portfolio.create_portfolio("   ")


def test_rename_updates_name_keeps_id(tmp_portfolios):
    created = portfolio.create_portfolio("Old Name")
    renamed = portfolio.rename_portfolio(created["id"], "New Name")
    assert renamed is not None
    assert renamed["id"] == created["id"]
    assert renamed["name"] == "New Name"


def test_delete_removes_portfolio(tmp_portfolios):
    created = portfolio.create_portfolio("To Delete")
    assert portfolio.delete_portfolio(created["id"]) is True
    assert created["id"] not in portfolio.load_portfolios()["portfolios"]


def test_delete_missing_returns_false(tmp_portfolios):
    assert portfolio.delete_portfolio("nope") is False


def test_add_holding_validates_symbol(tmp_portfolios, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": False, "symbol": s, "name": None, "sector": None, "reason": "nope"},
    )
    portfolio.create_portfolio("Test")
    with pytest.raises(ValueError):
        portfolio.add_holding("test", "BOGUS", 10, 100.0)


def test_add_holding_rejects_negative_shares(tmp_portfolios, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    portfolio.create_portfolio("Test")
    with pytest.raises(ValueError):
        portfolio.add_holding("test", "AAPL", -1, 100.0)


def test_add_then_edit_holding(tmp_portfolios, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    portfolio.create_portfolio("Test")
    portfolio.add_holding("test", "AAPL", 10, 1500.0)
    edited = portfolio.edit_holding("test", "AAPL", shares=12, total_cost=None)
    assert edited is not None
    assert edited["shares"] == 12
    assert edited["total_cost"] == 1500.0


def test_cash_row_added_last_and_unique(tmp_portfolios):
    portfolio.create_portfolio("Test")
    cash = portfolio.add_cash_row("test", "Cash", 1000.0, 1000.0)
    assert cash["kind"] == "cash"
    with pytest.raises(ValueError):
        portfolio.add_cash_row("test", "Cash 2", 500.0, 500.0)


def test_save_and_load_round_trip(tmp_portfolios):
    portfolio.create_portfolio("Persistence Test")
    state = portfolio.load_portfolios()
    assert "persistence-test" in state["portfolios"]


def test_enrich_merges_live_prices(tmp_portfolios, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    monkeypatch.setattr(
        "app.market._quote_snapshot",
        lambda syms: {"AAPL": {"price": 200.0, "pct_change": 1.5}, "NVDA": {"price": 900.0, "pct_change": -2.0}},
    )
    portfolio.create_portfolio("Test")
    portfolio.add_holding("test", "AAPL", 10, 1500.0)
    portfolio.add_holding("test", "NVDA", 5, 4000.0)
    state = portfolio.load_portfolios()
    enriched = portfolio.enrich_portfolios(state)
    aapl = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("symbol") == "AAPL")
    assert aapl["last_price"] == 200.0
    assert aapl["pct_daily"] == 1.5


def test_enrich_handles_missing_prices(tmp_portfolios, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    monkeypatch.setattr("app.market._quote_snapshot", lambda syms: {})  # all rate-limited
    portfolio.create_portfolio("Test")
    portfolio.add_holding("test", "AAPL", 10, 1500.0)
    state = portfolio.load_portfolios()
    enriched = portfolio.enrich_portfolios(state)
    aapl = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("symbol") == "AAPL")
    assert aapl["last_price"] is None
    assert aapl["pct_daily"] is None


def test_enrich_skips_cash_row(tmp_portfolios):
    portfolio.create_portfolio("Test")
    portfolio.add_cash_row("test", "Cash", 1000.0, 1000.0)
    state = portfolio.load_portfolios()
    enriched = portfolio.enrich_portfolios(state)
    cash = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("kind") == "cash")
    assert "last_price" not in cash
    assert cash["total_value"] == 1000.0


from fastapi.testclient import TestClient
from app.api import app


@pytest.fixture
def client(tmp_portfolios):
    return TestClient(app, base_url="http://127.0.0.1:8000")


def test_api_get_empty_returns_default(client):
    r = client.get("/api/portfolios")
    assert r.status_code == 200
    body = r.json()
    assert body["portfolios"] == {}
    assert "earnings" in body["column_order"]


def test_api_create_then_get(client):
    r = client.post("/api/portfolios", params={"name": "Fidelity Cash"})
    assert r.status_code == 200
    pid = r.json()["id"]
    r2 = client.get("/api/portfolios")
    assert pid in r2.json()["portfolios"]


def test_api_create_rejects_empty_name(client):
    r = client.post("/api/portfolios", params={"name": "  "})
    assert r.status_code == 400


def test_api_delete_then_404(client):
    r = client.post("/api/portfolios", params={"name": "Temp"})
    pid = r.json()["id"]
    d = client.delete(f"/api/portfolios/{pid}")
    assert d.status_code == 204
    r2 = client.delete(f"/api/portfolios/{pid}")
    assert r2.status_code == 404


def test_api_full_holding_flow(client, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    pid = client.post("/api/portfolios", params={"name": "Test"}).json()["id"]
    # Add
    r = client.post(
        f"/api/portfolios/{pid}/holdings",
        params={"symbol": "AAPL", "shares": 10, "total_cost": 1500.0},
    )
    assert r.status_code == 200
    # Edit
    r = client.put(
        f"/api/portfolios/{pid}/holdings/AAPL",
        params={"shares": 12, "total_cost": 1800.0},
    )
    assert r.status_code == 200
    assert r.json()["shares"] == 12
    # Remove
    r = client.delete(f"/api/portfolios/{pid}/holdings/AAPL")
    assert r.status_code == 204
    # 404 second time
    r = client.delete(f"/api/portfolios/{pid}/holdings/AAPL")
    assert r.status_code == 404


def test_api_add_holding_rejects_invalid_symbol(client, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": False, "symbol": s, "name": None, "sector": None, "reason": "nope"},
    )
    pid = client.post("/api/portfolios", params={"name": "Test"}).json()["id"]
    r = client.post(
        f"/api/portfolios/{pid}/holdings",
        params={"symbol": "BOGUS", "shares": 1, "total_cost": 1.0},
    )
    assert r.status_code == 400


def test_api_cash_flow(client):
    pid = client.post("/api/portfolios", params={"name": "Test"}).json()["id"]
    r = client.post(
        f"/api/portfolios/{pid}/cash",
        params={"label": "Cash", "total_cost": 1000.0, "total_value": 1000.0},
    )
    assert r.status_code == 200
    # Duplicate
    r = client.post(
        f"/api/portfolios/{pid}/cash",
        params={"label": "Cash2", "total_cost": 1.0, "total_value": 1.0},
    )
    assert r.status_code == 400
    # Edit
    r = client.put(
        f"/api/portfolios/{pid}/cash",
        params={"label": "Spending", "total_value": 1500.0},
    )
    assert r.status_code == 200
    assert r.json()["label"] == "Spending"
    assert r.json()["total_value"] == 1500.0


def test_api_columns_round_trip(client):
    r = client.put(
        "/api/portfolios/columns/portfolio",
        json={"order": ["shares", "symbol"], "visibility": {"shares": True, "symbol": False}},
    )
    assert r.status_code == 200
    r2 = client.get("/api/portfolios")
    co = r2.json()["column_order"]["portfolio"]
    cv = r2.json()["column_visibility"]["portfolio"]
    assert co == ["shares", "symbol"]
    assert cv["symbol"] is False
    assert cv["shares"] is True


def test_api_columns_rejects_unknown_section(client):
    r = client.put(
        "/api/portfolios/columns/bogus",
        json={"order": [], "visibility": {}},
    )
    assert r.status_code == 400
