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
