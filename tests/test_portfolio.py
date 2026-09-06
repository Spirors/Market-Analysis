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
    # column_order / column_visibility still exist in the JSON state (needed
    # by the PUT /api/portfolios/columns/{section} route) but are write-only
    # dead data — the portfolio frontend uses localStorage instead.
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


def test_remove_cash_row_success(tmp_portfolios):
    portfolio.create_portfolio("Test")
    portfolio.add_cash_row("test", "Cash", 1000.0, 1000.0)
    assert portfolio.remove_cash_row("test") is True
    holdings = portfolio.load_portfolios()["portfolios"]["test"]["holdings"]
    assert all(h.get("kind") != "cash" for h in holdings)


def test_remove_cash_row_missing(tmp_portfolios):
    portfolio.create_portfolio("Test")
    assert portfolio.remove_cash_row("test") is False


def test_remove_cash_row_unknown_pid(tmp_portfolios):
    assert portfolio.remove_cash_row("nonexistent-id") is False


# ---- enrich_portfolios_with_earnings ----------------------------------------

import json
from pathlib import Path


def _write_earnings_cache(monkeypatch, earnings_rows, tmp_path):
    """Write a fixture earnings-cache JSON to tmp_path/earnings.json and patch
    EARNINGS_CACHE_PATH to point at it. The function under test reads the cache
    via store.load_json, so this exercises the real read path (no monkeypatch
    of load_json, which would intercept unrelated files like portfolios.json)."""
    from app import earnings
    cache = {
        "cached_at": 9999999999,  # far future; enrich function bypasses TTL
        "payload": {
            "as_of": "2026-09-05T00:00:00",
            "companies": earnings_rows,
            "watchlist": [],
        },
    }
    fixture = tmp_path / "earnings.json"
    fixture.write_text(json.dumps(cache))
    monkeypatch.setattr(earnings, "EARNINGS_CACHE_PATH", Path(fixture))


def test_enrich_with_earnings_basic(tmp_portfolios, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    portfolio.create_portfolio("Test")
    portfolio.add_holding("test", "AAPL", 10, 1500.0)

    earnings_row = {
        "symbol": "AAPL",
        "next_earnings": "2026-09-12",
        "last_earnings": None,
        "pct_7d": 3.5,
        "high_52w": 237.49,
        "forward_pe": 32.1,
        "forward_peg": 1.8,
        "market_cap_fmt": "3.54T",
        "sector": "Technology",
        "rec_signal": "Bullish",
        "rec_color": "#3B6D11",
        "rec_reason": "reasonable valuation; near 52W high",
    }
    _write_earnings_cache(monkeypatch, [earnings_row], tmp_path)

    state = portfolio.load_portfolios()
    enriched = portfolio.enrich_portfolios_with_earnings(state)
    aapl = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("symbol") == "AAPL")

    assert aapl["next_earnings"] == "2026-09-12"
    assert aapl["pct_7d"] == 3.5
    assert aapl["high_52w"] == 237.49
    assert aapl["forward_pe"] == 32.1
    assert aapl["forward_peg"] == 1.8
    assert aapl["market_cap_fmt"] == "3.54T"
    assert aapl["sector"] == "Technology"
    assert aapl["rec_signal"] == "Bullish"
    assert aapl["rec_color"] == "#3B6D11"
    assert "reasonable valuation" in aapl["rec_reason"]


def test_enrich_with_earnings_inline_enriches_missing_symbol(tmp_portfolios, monkeypatch, tmp_path):
    """Portfolio holdings absent from the earnings cache should be enriched
    on the fly using the same per-ticker enrichment API the Earnings section
    uses (earnings._enrich). The enrichment is INLINE — the on-disk
    earnings cache must NOT be mutated by the portfolio path (writing into
    it would re-introduce removed tickers on the next dashboard load and
    leak portfolio holdings into the Earnings section's view)."""
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    portfolio.create_portfolio("Test")
    portfolio.add_holding("test", "AAPL", 10, 1500.0)

    # Cache has NVDA — AAPL is not yet enriched.
    nvda_row = {
        "symbol": "NVDA",
        "next_earnings": "2026-09-20",
        "pct_7d": 5.0,
        "high_52w": 140.0,
        "forward_pe": 40.0,
        "forward_peg": 1.2,
        "market_cap_fmt": "2.5T",
        "sector": "Technology",
        "rec_signal": "Neutral",
        "rec_color": "#B9860B",
        "rec_reason": "mixed signals",
    }
    _write_earnings_cache(monkeypatch, [nvda_row], tmp_path)

    # Stub the per-ticker enricher + the quote snapshot so we don't hit
    # yfinance. Return a deterministic AAPL row for any unknown symbol.
    from app import earnings
    def fake_enrich(sym, quotes):
        if sym == "AAPL":
            return {
                "symbol": "AAPL",
                "next_earnings": "2026-09-12",
                "last_earnings": None,
                "pct_7d": 3.5,
                "high_52w": 237.49,
                "forward_pe": 32.1,
                "forward_peg": 1.8,
                "market_cap_fmt": "3.54T",
                "sector": "Technology",
                "rec_signal": "Bullish",
                "rec_color": "#3B6D11",
                "rec_reason": "reasonable valuation; near 52W high",
            }
        return {"symbol": sym}
    monkeypatch.setattr(earnings, "_enrich", fake_enrich)
    monkeypatch.setattr("app.market._quote_snapshot", lambda syms: {})

    state = portfolio.load_portfolios()
    enriched = portfolio.enrich_portfolios_with_earnings(state)
    aapl = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("symbol") == "AAPL")

    # AAPL fields must be populated (same _EARNINGS_FIELDS the Earnings
    # section renders), proving portfolio still goes through the same
    # per-ticker enrichment API as the earnings watchlist.
    assert aapl["next_earnings"] == "2026-09-12"
    assert aapl["pct_7d"] == 3.5
    assert aapl["forward_pe"] == 32.1
    assert aapl["market_cap_fmt"] == "3.54T"
    assert aapl["sector"] == "Technology"
    assert aapl["rec_signal"] == "Bullish"

    # The on-disk earnings cache must NOT have been mutated by the
    # portfolio path — it still contains only the pre-existing NVDA row.
    # Writing into it would re-introduce removed tickers on the next
    # dashboard load and pollute the Earnings section's view with
    # portfolio-only holdings.
    cache_after = json.loads(Path(earnings.EARNINGS_CACHE_PATH).read_text())
    cache_syms = {r["symbol"] for r in cache_after["payload"]["companies"]}
    assert cache_syms == {"NVDA"}


def test_enrich_with_earnings_inline_skips_cash(tmp_portfolios, monkeypatch, tmp_path):
    """A cash row has no symbol — _enrich must not be called for it, and
    enrich_portfolios_with_earnings must still leave the cash row alone."""
    portfolio.create_portfolio("Test")
    portfolio.add_cash_row("test", "Cash", 1000.0, 1000.0)
    _write_earnings_cache(monkeypatch, [], tmp_path)

    from app import earnings
    monkeypatch.setattr(earnings, "_enrich", lambda sym, q: {"symbol": sym})
    monkeypatch.setattr("app.market._quote_snapshot", lambda syms: {})

    state = portfolio.load_portfolios()
    enriched = portfolio.enrich_portfolios_with_earnings(state)
    cash = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("kind") == "cash")
    assert "next_earnings" not in cash
    assert cash["total_value"] == 1000.0

    # No holdings → no symbols to enrich → cache stays empty.
    cache_after = json.loads(Path(earnings.EARNINGS_CACHE_PATH).read_text())
    cache_syms = {r.get("symbol") for r in cache_after["payload"]["companies"]}
    assert cache_syms == set()


def test_enrich_with_earnings_inline_handles_missing_cache(tmp_portfolios, monkeypatch, tmp_path):
    """When the cache file is missing/corrupt, inline enrichment must still
    produce populated holdings. No cache file is created by the portfolio
    path — if it didn't exist before, it still doesn't exist after."""
    from app import earnings
    portfolio.create_portfolio("Test")
    portfolio.add_holding("test", "AAPL", 10, 1500.0)

    # Point the cache at a non-existent file.
    missing_path = tmp_path / "absent.json"
    monkeypatch.setattr(earnings, "EARNINGS_CACHE_PATH", missing_path)
    assert not missing_path.exists()

    monkeypatch.setattr(
        earnings, "_enrich",
        lambda sym, q: {
            "symbol": sym, "next_earnings": "2026-10-29", "last_earnings": None,
            "pct_7d": 2.0, "high_52w": 300.0, "forward_pe": 28.0, "forward_peg": 1.5,
            "market_cap_fmt": "1.0T", "sector": "Technology",
            "rec_signal": "Bullish", "rec_color": "#3B6D11", "rec_reason": "ok",
        },
    )
    monkeypatch.setattr("app.market._quote_snapshot", lambda syms: {})

    state = portfolio.load_portfolios()
    enriched = portfolio.enrich_portfolios_with_earnings(state)
    aapl = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("symbol") == "AAPL")
    assert aapl["next_earnings"] == "2026-10-29"
    assert aapl["pct_7d"] == 2.0

    # The portfolio path must not have created the cache file either.
    assert not missing_path.exists()


def test_enrich_with_earnings_skips_cash(tmp_portfolios, monkeypatch, tmp_path):
    portfolio.create_portfolio("Test")
    portfolio.add_cash_row("test", "Cash", 1000.0, 1000.0)

    earnings_row = {
        "symbol": "CASH",
        "next_earnings": "2026-09-12",
        "pct_7d": 1.0,
        "high_52w": None,
        "forward_pe": None,
        "forward_peg": None,
        "market_cap_fmt": None,
        "sector": None,
        "rec_signal": "Neutral",
        "rec_color": "#B9860B",
        "rec_reason": "n/a",
    }
    _write_earnings_cache(monkeypatch, [earnings_row], tmp_path)

    state = portfolio.load_portfolios()
    enriched = portfolio.enrich_portfolios_with_earnings(state)
    cash = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("kind") == "cash")

    # Cash row should not receive any earnings fields.
    assert "next_earnings" not in cash
    assert "pct_7d" not in cash
    assert cash["total_value"] == 1000.0


def test_api_portfolio_state_fresh_after_mutation(client, monkeypatch):
    """After a portfolio mutation (add/edit/remove holding), GET /api/portfolios
    must return the updated state immediately — no stale data."""
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    pid = client.post("/api/portfolios", params={"name": "Fresh Test"}).json()["id"]

    # Add holding
    r = client.post(
        f"/api/portfolios/{pid}/holdings",
        params={"symbol": "AAPL", "shares": 10, "total_cost": 1500.0},
    )
    assert r.status_code == 200

    # GET must immediately reflect the added holding
    state = client.get("/api/portfolios").json()
    holdings = state["portfolios"][pid]["holdings"]
    assert any(h["symbol"] == "AAPL" for h in holdings)

    # Edit holding
    r = client.put(
        f"/api/portfolios/{pid}/holdings/AAPL",
        params={"shares": 20, "total_cost": 3000.0},
    )
    assert r.status_code == 200

    # GET must immediately reflect the edited holding
    state = client.get("/api/portfolios").json()
    h = next(h for h in state["portfolios"][pid]["holdings"] if h["symbol"] == "AAPL")
    assert h["shares"] == 20
    assert h["total_cost"] == 3000.0

    # Remove holding
    r = client.delete(f"/api/portfolios/{pid}/holdings/AAPL")
    assert r.status_code == 204

    # GET must immediately reflect the removal
    state = client.get("/api/portfolios").json()
    holdings = state["portfolios"][pid]["holdings"]
    assert not any(h["symbol"] == "AAPL" for h in holdings)
