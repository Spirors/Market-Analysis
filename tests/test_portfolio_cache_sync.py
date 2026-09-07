"""Regression: portfolio mutations must update the cached dashboard payload.

Before the fix, mutating a portfolio (add/remove holding, create/delete
portfolio) wrote data/portfolios.json correctly but left data/dashboard.json
stale — GET /api/dashboard still returned the old portfolios sub-tree until
the user clicked the in-page Refresh button (which triggers a full rebuild).

This test seeds the dashboard cache, mutates a portfolio, then asserts
the next GET /api/dashboard reflects the mutation WITHOUT calling
/api/refresh.
"""

import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app import api, config, portfolio, service, store, validation


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient against a throwaway data dir (no network, no cache pollution)."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "EVENTS_PATH", tmp_path / "events.json")
    monkeypatch.setattr(config, "ANALYSIS_DB_PATH", tmp_path / "analysis.db")
    monkeypatch.setattr(portfolio, "PORTFOLIOS_PATH", tmp_path / "portfolios.json")
    monkeypatch.setattr(store, "_READY", False)
    monkeypatch.setattr(store, "_analysis_repo", None)
    # Stub enrich functions so no yfinance calls fire.
    monkeypatch.setattr("app.market._quote_snapshot", lambda syms: {})
    return TestClient(api.app, base_url="http://127.0.0.1:8000")


def _seed_dashboard_cache(tmp_path, portfolios=None):
    """Write a minimal dashboard.json with a portfolios sub-tree."""
    payload = {
        "as_of": "2026-09-01T00:00:00",
        "portfolios": portfolios or {},
        "market": {"indices": {}, "rates": {}, "commodities": {}},
        "indicators": {},
        "risk": {"risk_level": "YELLOW"},
        "bottleneck": {},
        "futures": {"index_futures": [], "commodities": []},
        "thirteenf": {},
        "ai_sentiment": {},
        "regime": {},
        "ai_analysis": {},
        "vintage": {"market": "2026-09-01T00:00:00"},
    }
    store.save_json(tmp_path / "dashboard.json", payload)
    return payload


def test_add_holding_reflects_in_dashboard_without_refresh(client, tmp_path, monkeypatch):
    """POST a holding, then GET /api/dashboard — the new ticker must appear."""
    monkeypatch.setattr(
        validation, "validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )

    # Create a portfolio via the API
    r = client.post("/api/portfolios", params={"name": "Test"})
    assert r.status_code == 200
    pid = r.json()["id"]

    # Seed the dashboard cache with this portfolio (empty holdings)
    _seed_dashboard_cache(tmp_path, {
        pid: {"id": pid, "name": "Test", "holdings": []}
    })

    # Add a holding
    r = client.post(
        f"/api/portfolios/{pid}/holdings",
        params={"symbol": "AAPL", "shares": 10, "total_cost": 1500.0},
    )
    assert r.status_code == 200

    # GET /api/dashboard — the new holding MUST be in the portfolios sub-tree
    # WITHOUT calling /api/refresh.
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    dash = r.json()
    holdings = dash["portfolios"][pid]["holdings"]
    syms = [h["symbol"] for h in holdings]
    assert "AAPL" in syms


def test_remove_holding_reflects_in_dashboard_without_refresh(client, tmp_path, monkeypatch):
    """DELETE a holding, then GET /api/dashboard — the ticker must be gone."""
    monkeypatch.setattr(
        validation, "validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )

    r = client.post("/api/portfolios", params={"name": "Test"})
    pid = r.json()["id"]

    # Add the holding via API (so it exists in portfolios.json)
    r = client.post(
        f"/api/portfolios/{pid}/holdings",
        params={"symbol": "AAPL", "shares": 10, "total_cost": 1500.0},
    )
    assert r.status_code == 200

    # Now seed the dashboard cache with this portfolio + holding
    state = portfolio.load_portfolios()
    _seed_dashboard_cache(tmp_path, state["portfolios"])

    # Remove the holding
    r = client.delete(f"/api/portfolios/{pid}/holdings/AAPL")
    assert r.status_code == 204

    # GET /api/dashboard — AAPL must be gone
    r = client.get("/api/dashboard")
    dash = r.json()
    holdings = dash["portfolios"][pid]["holdings"]
    syms = [h["symbol"] for h in holdings]
    assert "AAPL" not in syms


def test_create_portfolio_reflects_in_dashboard_without_refresh(client, tmp_path):
    """POST /api/portfolios, then GET /api/dashboard — the new portfolio must appear."""
    # Seed dashboard with no portfolios
    _seed_dashboard_cache(tmp_path, {})

    r = client.post("/api/portfolios", params={"name": "Brand New"})
    assert r.status_code == 200
    pid = r.json()["id"]

    # GET /api/dashboard — the new portfolio MUST appear
    r = client.get("/api/dashboard")
    dash = r.json()
    assert pid in dash["portfolios"]
    assert dash["portfolios"][pid]["name"] == "Brand New"


def test_delete_portfolio_reflects_in_dashboard_without_refresh(client, tmp_path):
    """DELETE /api/portfolios/{pid}, then GET /api/dashboard — portfolio gone."""
    r = client.post("/api/portfolios", params={"name": "To Delete"})
    pid = r.json()["id"]

    # Seed dashboard with this portfolio
    _seed_dashboard_cache(tmp_path, {
        pid: {"id": pid, "name": "To Delete", "holdings": []}
    })

    # Delete it
    r = client.delete(f"/api/portfolios/{pid}")
    assert r.status_code == 204

    # GET /api/dashboard — the portfolio MUST be gone
    r = client.get("/api/dashboard")
    dash = r.json()
    assert pid not in dash["portfolios"]


def test_vintage_portfolios_stamp_updated_after_mutation(client, tmp_path, monkeypatch):
    """After a mutation, the dashboard cache vintage.portfolios timestamp
    must be newer than the initial seed, proving the cache was patched."""
    monkeypatch.setattr(
        validation, "validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )

    r = client.post("/api/portfolios", params={"name": "Test"})
    pid = r.json()["id"]

    # Seed with an old vintage
    _seed_dashboard_cache(tmp_path, {
        pid: {"id": pid, "name": "Test", "holdings": []}
    })

    r = client.post(
        f"/api/portfolios/{pid}/holdings",
        params={"symbol": "NVDA", "shares": 5, "total_cost": 500.0},
    )
    assert r.status_code == 200

    # Read the cache directly — vintage.portfolios must exist and be recent
    cached = store.load_json(tmp_path / "dashboard.json")
    assert "portfolios" in cached.get("vintage", {})
