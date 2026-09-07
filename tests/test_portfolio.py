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
    # Only "portfolio" remains after the Earnings watchlist section was removed.
    assert "portfolio" in state["column_order"]
    assert "portfolio" in state["column_visibility"]


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
        "app.validation.validate_symbol",
        lambda s: {"valid": False, "symbol": s, "name": None, "sector": None, "reason": "nope"},
    )
    portfolio.create_portfolio("Test")
    with pytest.raises(ValueError):
        portfolio.add_holding("test", "BOGUS", 10, 100.0)


def test_add_holding_rejects_negative_shares(tmp_portfolios, monkeypatch):
    monkeypatch.setattr(
        "app.validation.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    portfolio.create_portfolio("Test")
    with pytest.raises(ValueError):
        portfolio.add_holding("test", "AAPL", -1, 100.0)


def test_add_then_edit_holding(tmp_portfolios, monkeypatch):
    monkeypatch.setattr(
        "app.validation.validate_symbol",
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
        "app.validation.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    monkeypatch.setattr(
        "app.market._quote_snapshot",
        lambda syms: {"AAPL": {"price": 200.0, "pct_change": 1.5}, "NVDA": {"price": 900.0, "pct_change": -2.0}},
    )
    # Stub history so 7d/30d/52w can be derived without hitting yfinance.
    def _fake_hist(syms, days=260):
        return {s: [{"date": f"2024-{i // 30 + 1:02d}-{i % 28 + 1:02d}", "close": 100.0 + i}
                    for i in range(260)] for s in syms}
    monkeypatch.setattr("app.market.get_histories_bulk", _fake_hist)
    monkeypatch.setattr(
        "app.portfolio.get_info_snapshot",
        lambda s: {"sector": None, "marketcap": None, "forward_pe": None, "forward_peg": None, "next_earnings": None},
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
        "app.validation.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    monkeypatch.setattr("app.market._quote_snapshot", lambda syms: {})  # all rate-limited
    monkeypatch.setattr("app.market.get_histories_bulk", lambda syms, days=260: {})
    monkeypatch.setattr("app.portfolio.get_info_snapshot",
                        lambda s: {"sector": None, "marketcap": None, "forward_pe": None, "forward_peg": None, "next_earnings": None})
    portfolio.create_portfolio("Test")
    portfolio.add_holding("test", "AAPL", 10, 1500.0)
    state = portfolio.load_portfolios()
    enriched = portfolio.enrich_portfolios(state)
    aapl = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("symbol") == "AAPL")
    assert aapl["last_price"] is None
    assert aapl["pct_daily"] is None
    assert aapl["pct_7d"] is None
    assert aapl["pct_30d"] is None
    assert aapl["high_52w"] is None
    assert aapl["sector"] is None
    assert aapl["marketcap"] is None
    assert aapl["forward_pe"] is None
    assert aapl["forward_peg"] is None
    assert aapl["next_earnings"] is None


def test_enrich_derives_history_fields(tmp_portfolios, monkeypatch):
    """pct_7d, pct_30d, high_52w are derived from 260-day history, no info needed."""
    monkeypatch.setattr(
        "app.validation.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    monkeypatch.setattr("app.market._quote_snapshot", lambda syms: {"AAPL": {"price": 110.0, "pct_change": 0.0}})
    # Synthesize a 260-day series where the 7-days-ago close was 100 and the
    # 30-days-ago close was 90. The series must be ascending so high_52w >=
    # current close and pct changes are positive.
    closes = [90.0 + (i * (20.0 / 259)) for i in range(260)]
    monkeypatch.setattr(
        "app.market.get_histories_bulk",
        lambda syms, days=260: {s: [{"date": f"d{i}", "close": closes[i]} for i in range(260)] for s in syms},
    )
    monkeypatch.setattr("app.portfolio.get_info_snapshot",
                        lambda s: {"sector": None, "marketcap": None, "forward_pe": None, "forward_peg": None, "next_earnings": None})
    portfolio.create_portfolio("Test")
    portfolio.add_holding("test", "AAPL", 10, 1000.0)
    enriched = portfolio.enrich_portfolios(portfolio.load_portfolios())
    aapl = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("symbol") == "AAPL")
    # Last close = closes[-1] = 110.0
    # 7-days-ago close = closes[-8] (i.e. 7 trading days back)
    expected_7d = round((closes[-1] / closes[-8] - 1) * 100, 3)
    expected_30d = round((closes[-1] / closes[-31] - 1) * 100, 3)
    assert aapl["pct_7d"] == expected_7d
    assert aapl["pct_30d"] == expected_30d
    assert aapl["high_52w"] == round(max(closes), 4)


def test_enrich_includes_fundamentals(tmp_portfolios, monkeypatch):
    """sector, marketcap, forward_pe, forward_peg, next_earnings come from
    get_info_snapshot (Ticker.info + calendar)."""
    monkeypatch.setattr(
        "app.validation.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    monkeypatch.setattr("app.market._quote_snapshot", lambda syms: {})
    monkeypatch.setattr("app.market.get_histories_bulk", lambda syms, days=260: {})
    monkeypatch.setattr(
        "app.portfolio.get_info_snapshot",
        lambda s: {"sector": "Technology", "marketcap": 3000.0, "forward_pe": 25.5,
                   "forward_peg": 1.2, "next_earnings": "2026-10-30"},
    )
    portfolio.create_portfolio("Test")
    portfolio.add_holding("test", "NVDA", 5, 4000.0)
    enriched = portfolio.enrich_portfolios(portfolio.load_portfolios())
    nvda = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("symbol") == "NVDA")
    assert nvda["sector"] == "Technology"
    assert nvda["marketcap"] == 3000.0
    assert nvda["forward_pe"] == 25.5
    assert nvda["forward_peg"] == 1.2
    assert nvda["next_earnings"] == "2026-10-30"


def test_get_info_snapshot_empty_symbol_returns_none():
    """Defensive: empty / whitespace symbols short-circuit to all-None without
    hitting the lru_cache key (lru_cache requires hashable, and a cache hit on
    '' would be wrong across symbols)."""
    out = portfolio.get_info_snapshot("")
    assert out == {"sector": None, "marketcap": None, "forward_pe": None,
                   "forward_peg": None, "next_earnings": None}
    out2 = portfolio.get_info_snapshot("   ")
    assert out2["sector"] is None


# ---- _extract_next_earnings: yfinance shape compatibility --------------------
#
# yfinance 1.6.0 returns datetime.date for Earnings Date; older versions returned
# datetime.datetime. Pre-fix this function only matched datetime (not date), so
# the column rendered as "—" for every holding — the bug the user reported.

def test_extract_next_earnings_handles_datetime_date():
    """yfinance 1.6.0 returns datetime.date in a single-element list.

    Pre-fix this returned None (the function only matched datetime.datetime),
    so every freshly-enriched holding's earnings date column showed "—".
    """
    from datetime import date
    assert portfolio._extract_next_earnings({"Earnings Date": [date(2026, 11, 17)]}) == "2026-11-17"


def test_extract_next_earnings_handles_datetime_datetime():
    """Older yfinance versions returned datetime.datetime objects.

    datetime is a subclass of date, so the broader isinstance check still
    matches and returns the YYYY-MM-DD string.
    """
    from datetime import datetime
    assert portfolio._extract_next_earnings(
        {"Earnings Date": [datetime(2026, 11, 17, 0, 0, 0)]}
    ) == "2026-11-17"


def test_extract_next_earnings_handles_multiple_dates():
    """yfinance sometimes returns [confirmed, tentative]; use the first."""
    from datetime import date
    assert portfolio._extract_next_earnings(
        {"Earnings Date": [date(2026, 11, 17), date(2026, 11, 18)]}
    ) == "2026-11-17"


def test_extract_next_earnings_handles_string_fallback():
    """Defensive: a plain string (some yfinance proxies / mocks) still works."""
    assert portfolio._extract_next_earnings({"Earnings Date": "2026-11-17"}) == "2026-11-17"


def test_extract_next_earnings_returns_none_for_missing_or_empty():
    """Missing key, empty list, and None value all resolve to None (no fabrication)."""
    assert portfolio._extract_next_earnings({}) is None
    assert portfolio._extract_next_earnings({"Earnings Date": []}) is None
    assert portfolio._extract_next_earnings({"Earnings Date": None}) is None


def test_extract_next_earnings_returns_none_for_non_dict():
    """Non-dict calendar payloads (None, string, list) don't raise — they return None."""
    assert portfolio._extract_next_earnings(None) is None
    assert portfolio._extract_next_earnings("not a dict") is None
    assert portfolio._extract_next_earnings([{"Earnings Date": "2026-11-17"}]) is None


def test_info_cached_is_cached(monkeypatch):
    """Within a 5-min bucket, repeated ``get_info_snapshot`` calls do not
    re-hit yfinance. Mock Ticker + calendar and count how many times
    they're constructed. lru_cache(maxsize=128) plus a bucket key = one
    inner fetch per (symbol, 5-min window)."""
    import app.portfolio as pf
    import yfinance as yf

    calls = {"n": 0}
    real_ticker = yf.Ticker

    def fake_ticker(sym):
        calls["n"] += 1
        t = real_ticker.__new__(real_ticker)
        # yfinance Ticker.info is a property; bypass with __dict__.
        object.__setattr__(t, "_mock_info", {"sector": "Technology", "marketCap": 3000,
                                             "forwardPE": 25, "pegRatio": 1.2})
        return t

    # Make Ticker.info return our fake dict via type-level monkey patch.
    class FakeTicker:
        def __init__(self, sym):
            calls["n"] += 1
            self._info = {"sector": "Technology", "marketCap": 3000,
                          "forwardPE": 25, "pegRatio": 1.2}

        @property
        def info(self):
            return self._info

        @property
        def calendar(self):
            return {"Earnings Date": [__import__("datetime").datetime(2026, 10, 30)]}

    monkeypatch.setattr(yf, "Ticker", FakeTicker)
    pf._info_cached.cache_clear()
    try:
        # Three calls within the same bucket: only the first should hit yfinance.
        a = pf.get_info_snapshot("AAPL")
        b = pf.get_info_snapshot("AAPL")
        c = pf.get_info_snapshot("AAPL")
        assert a == b == c
        assert a["sector"] == "Technology"
        assert a["marketcap"] == 3000.0
        assert a["next_earnings"] == "2026-10-30"
        # FakeTicker is constructed exactly once for the first call; second +
        # third return from the lru_cache without constructing it.
        assert calls["n"] == 1, f"expected 1 inner fetch, got {calls['n']}"
    finally:
        pf._info_cached.cache_clear()


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
    assert "portfolio" in body["column_order"]


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
        "app.validation.validate_symbol",
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
        "app.validation.validate_symbol",
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


def test_api_columns_per_portfolio_round_trip(client):
    """PUT /api/portfolios/columns/portfolio.<pid> stores per-portfolio prefs
    without touching the default ``portfolio`` key. Two portfolios can have
    independent column orders."""
    pid_a = client.post("/api/portfolios", params={"name": "Account A"}).json()["id"]
    pid_b = client.post("/api/portfolios", params={"name": "Account B"}).json()["id"]
    # Account A: only symbol + pct_daily visible
    r = client.put(
        f"/api/portfolios/columns/portfolio.{pid_a}",
        json={"order": ["symbol", "pct_daily"], "visibility": {"symbol": True, "pct_daily": True}},
    )
    assert r.status_code == 200
    # Account B: different custom order
    r = client.put(
        f"/api/portfolios/columns/portfolio.{pid_b}",
        json={"order": ["symbol", "shares", "high_52w"], "visibility": {"symbol": True, "shares": True, "high_52w": True}},
    )
    assert r.status_code == 200
    # Both prefs persisted independently; default untouched
    state = client.get("/api/portfolios").json()
    assert state["column_order"][f"portfolio.{pid_a}"] == ["symbol", "pct_daily"]
    assert state["column_order"][f"portfolio.{pid_b}"] == ["symbol", "shares", "high_52w"]
    # Default key still has the full 16-column list
    assert len(state["column_order"]["portfolio"]) == 16


def test_api_columns_per_portfolio_rejects_unknown_pid(client):
    """PUT to portfolio.<pid> where <pid> doesn't exist -> 404, not silent 200."""
    r = client.put(
        "/api/portfolios/columns/portfolio.does-not-exist",
        json={"order": ["symbol"], "visibility": {"symbol": True}},
    )
    assert r.status_code == 404


def test_default_column_order_includes_all_restored_columns():
    """The restored columns (7d, 30d, earnings, marketcap, forward pe/peg,
    52W high, sector) must be in the default column order so new portfolios
    see them and the columns dropdown lists them."""
    keys = set(portfolio.DEFAULT_COLUMN_ORDER["portfolio"])
    expected = {"_star", "symbol", "shares", "total_cost", "last_price",
                "total_value", "gain_loss", "pct_daily",
                "pct_7d", "pct_30d", "next_earnings", "marketcap",
                "forward_pe", "forward_peg", "high_52w", "sector"}
    assert keys == expected
    assert portfolio.DEFAULT_COLUMN_VISIBILITY["portfolio"]["pct_7d"] is True
    assert portfolio.DEFAULT_COLUMN_VISIBILITY["portfolio"]["pct_30d"] is True
    assert portfolio.DEFAULT_COLUMN_VISIBILITY["portfolio"]["next_earnings"] is True
    assert portfolio.DEFAULT_COLUMN_VISIBILITY["portfolio"]["marketcap"] is True
    assert portfolio.DEFAULT_COLUMN_VISIBILITY["portfolio"]["forward_pe"] is True
    assert portfolio.DEFAULT_COLUMN_VISIBILITY["portfolio"]["forward_peg"] is True
    assert portfolio.DEFAULT_COLUMN_VISIBILITY["portfolio"]["high_52w"] is True
    assert portfolio.DEFAULT_COLUMN_VISIBILITY["portfolio"]["sector"] is True


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


def test_api_portfolio_state_fresh_after_mutation(client, monkeypatch):
    """After a portfolio mutation (add/edit/remove holding), GET /api/portfolios
    must return the updated state immediately — no stale data."""
    monkeypatch.setattr(
        "app.validation.validate_symbol",
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


def test_post_holdings_add_completes_under_500ms_with_15_holdings(tmp_path, monkeypatch):
    """Regression for audit-2026-09-07 P0.

    With N=15 holdings and mocked yfinance injecting 100ms latency per call,
    POST /api/portfolios/{pid}/holdings must complete in <500ms. Pre-fix
    this took ~3s because _patch_dashboard_cache re-enriched ALL symbols
    on every 1-symbol mutation (1 bulk quote snapshot + 1 bulk history +
    15 per-symbol Ticker.info = ~17 calls x 100ms = ~1700ms + overhead).
    Post-fix the cache patch is structural-only and the POST itself only
    does 1 cached get_quotes call (~100ms on miss, ~5ms on hit).
    """
    import time
    from fastapi.testclient import TestClient
    from app import api as api_mod
    from app import portfolio as portfolio_mod
    from app import config

    # Redirect portfolios.json + dashboard.json to tmp so the test doesn't
    # touch the user's real data.
    monkeypatch.setattr(portfolio_mod, "PORTFOLIOS_PATH", tmp_path / "portfolios.json")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    (tmp_path / "dashboard.json").write_text("{}")

    # Latency injector — simulates a cold yfinance call.
    LATENCY_S = 0.1

    def _slow_quote_snapshot(symbols):
        time.sleep(LATENCY_S)
        return {s: {"price": 100.0, "pct_change": 0.5, "change": 0.5} for s in symbols}

    def _slow_histories_bulk(symbols, days=260):
        time.sleep(LATENCY_S)
        return {s: [{"date": f"2024-{i // 30 + 1:02d}-{i % 28 + 1:02d}", "close": 100.0 + i}
                    for i in range(260)] for s in symbols}

    def _slow_info(sym):
        time.sleep(LATENCY_S)
        return {"sector": None, "marketcap": None, "forward_pe": None,
                "forward_peg": None, "next_earnings": None}

    monkeypatch.setattr("app.market._quote_snapshot", _slow_quote_snapshot)
    monkeypatch.setattr("app.market.get_histories_bulk", _slow_histories_bulk)
    monkeypatch.setattr("app.market.get_quotes", _slow_quote_snapshot)
    monkeypatch.setattr("app.portfolio.get_info_snapshot", _slow_info)
    monkeypatch.setattr(
        "app.validation.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )

    # Build a portfolio with 15 holdings.
    portfolio_mod.create_portfolio("Stress Test")
    for i in range(15):
        sym = f"SYM{i:02d}"
        portfolio_mod.add_holding("stress-test", sym, 1.0, 100.0)

    client = TestClient(api_mod.app)
    headers = {"Host": "127.0.0.1:8000"}
    start = time.perf_counter()
    r = client.post(
        "/api/portfolios/stress-test/holdings",
        params={"symbol": "NEW", "shares": 1, "total_cost": 50.0},
        headers=headers,
    )
    elapsed = time.perf_counter() - start
    assert r.status_code == 200, r.text
    # Pre-fix: ~1.7s. Post-fix: ~100ms (one get_quotes call with no cache).
    assert elapsed < 0.5, f"POST took {elapsed:.3f}s (expected <0.5s)"


def test_post_holdings_add_does_not_call_enrich_portfolios(tmp_path, monkeypatch):
    """Regression for audit-2026-09-07 P0.

    _patch_dashboard_cache must NOT re-enrich all symbols on a 1-symbol
    mutation. Pre-fix it called enrich_portfolios(state) inline, which
    triggered _quote_snapshot + get_histories_bulk + per-symbol
    _info_cached for every holding. Post-fix the cache patch is
    structural-only.
    """
    from fastapi.testclient import TestClient
    from app import api as api_mod
    from app import portfolio as portfolio_mod
    from app import config

    monkeypatch.setattr(portfolio_mod, "PORTFOLIOS_PATH", tmp_path / "portfolios.json")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    (tmp_path / "dashboard.json").write_text("{}")

    call_log = {"_quote_snapshot": 0, "get_histories_bulk": 0, "_info_cached": 0, "enrich_portfolios": 0}

    def _spy_quote_snapshot(symbols):
        call_log["_quote_snapshot"] += 1
        return {s: {"price": 100.0, "pct_change": 0.5, "change": 0.5} for s in symbols}

    def _spy_histories_bulk(symbols, days=260):
        call_log["get_histories_bulk"] += 1
        return {s: [{"date": "2024-01-01", "close": 100.0}] for s in symbols}

    def _spy_info(sym):
        call_log["_info_cached"] += 1
        return {"sector": None, "marketcap": None, "forward_pe": None,
                "forward_peg": None, "next_earnings": None}

    monkeypatch.setattr("app.market._quote_snapshot", _spy_quote_snapshot)
    monkeypatch.setattr("app.market.get_histories_bulk", _spy_histories_bulk)
    monkeypatch.setattr("app.market.get_quotes", _spy_quote_snapshot)
    monkeypatch.setattr("app.portfolio.get_info_snapshot", _spy_info)
    monkeypatch.setattr(
        "app.validation.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )

    portfolio_mod.create_portfolio("Test")
    for i in range(15):
        portfolio_mod.add_holding("test", f"SYM{i:02d}", 1.0, 100.0)

    # Reset counts — only count the POST itself, not the setup adds.
    for k in call_log:
        call_log[k] = 0

    client = TestClient(api_mod.app)
    r = client.post(
        "/api/portfolios/test/holdings",
        params={"symbol": "NEW", "shares": 1, "total_cost": 50.0},
        headers={"Host": "127.0.0.1:8000"},
    )
    assert r.status_code == 200, r.text

    # Critical assertion: the POST must NOT have triggered a full enrichment.
    # get_histories_bulk (260-day bulk download) must NOT have been called at all.
    # _info_cached (per-symbol Ticker.info) must NOT have been called at all.
    # _quote_snapshot should only be called once (for the new symbol's response
    # via get_quotes), NOT once per holding.
    assert call_log["get_histories_bulk"] == 0, (
        f"get_histories_bulk was called {call_log['get_histories_bulk']} times — "
        "cache patch should be structural-only, not re-enrich"
    )
    assert call_log["_info_cached"] == 0, (
        f"_info_cached was called {call_log['_info_cached']} times — "
        "cache patch should be structural-only, not re-enrich"
    )
    assert call_log["_quote_snapshot"] <= 1, (
        f"_quote_snapshot was called {call_log['_quote_snapshot']} times — "
        "should be at most once (for the new symbol's response)"
    )
