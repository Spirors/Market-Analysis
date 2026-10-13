"""Tests for the missed-date backfill in app/portfolio_history.py.

Policy under test: never fabricate history. A missing settled date is
backfilled only when the current book is provably identical to the book
recorded in the last stored entry (so the book did not change in the window),
and reconstruction uses only those recorded holdings + bulk-history prices.
Portfolios that changed are omitted; their gap is preserved.
"""

from datetime import date, datetime, timezone

import pytest

from app import portfolio, portfolio_history

NOW = datetime(2026, 1, 1, 21, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _accept_symbols(monkeypatch):
    monkeypatch.setattr(
        "app.validation.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )


def _rows(*pairs):
    return [{"date": d, "close": c} for d, c in pairs]


def _fake_bulk(mapping):
    return lambda symbols, days=260: {s: mapping[s] for s in symbols if s in mapping}


FULL = {
    "SPY": _rows(
        ("2020-01-01", 100.0), ("2020-01-02", 101.0), ("2020-01-03", 102.0),
        ("2020-01-04", 103.0), ("2020-01-05", 104.0), ("2020-01-06", 105.0),
    ),
    "AAPL": _rows(
        ("2020-01-01", 50.0), ("2020-01-02", 51.0), ("2020-01-03", 52.0),
        ("2020-01-04", 53.0), ("2020-01-05", 54.0), ("2020-01-06", 55.0),
    ),
}


def _seed_entry(close_date: str, portfolios: dict, histories: dict, recorded_at="2020-01-01T21:00:00Z"):
    """Seed the store with a real entry built by the live builder (as a prior run would)."""
    state = portfolio_history.load_history()
    state["snapshots"][close_date] = {
        "close_date": close_date,
        "recorded_at": recorded_at,
        "portfolios": {
            pid: portfolio_history._build_portfolio_snapshot(p, histories, date.fromisoformat(close_date))
            for pid, p in portfolios.items()
        },
    }
    portfolio_history.save_history(state)


def _current() -> dict:
    return portfolio.load_portfolios()["portfolios"]


def _close(symbol: str, d: str) -> float:
    return {r["date"]: r["close"] for r in FULL[symbol]}[d]


# ---- gaps filled ----------------------------------------------------------

def test_backfill_fills_gap_when_book_unchanged(monkeypatch):
    monkeypatch.setattr("app.market.get_histories_bulk", _fake_bulk(FULL))
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "SPY", 10, 1000.0)
    _seed_entry("2020-01-01", _current(), FULL)

    entry = portfolio_history.record_snapshot(now=NOW)
    assert entry["close_date"] == "2020-01-06"

    snaps = portfolio_history.load_history()["snapshots"]
    assert set(snaps) == {
        "2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05", "2020-01-06",
    }
    # Backfilled dates carry provenance; the latest (live) date does not.
    for d in ("2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05"):
        assert snaps[d]["backfilled"] is True
        assert snaps[d]["recorded_at"].endswith("Z")
        assert snaps[d]["portfolios"]["main"]["holdings"]["SPY"]["close"] == _close("SPY", d)
    assert "backfilled" not in snaps["2020-01-06"]
    # Value reconstructed from the recorded shares × the historical close.
    assert snaps["2020-01-02"]["portfolios"]["main"]["total_value"] == 1010.0


def test_backfill_marks_provenance_and_is_bounded(monkeypatch):
    monkeypatch.setattr("app.market.get_histories_bulk", _fake_bulk(FULL))
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "SPY", 10, 1000.0)
    _seed_entry("2020-01-01", _current(), FULL)

    portfolio_history.record_snapshot(now=NOW)
    snaps = portfolio_history.load_history()["snapshots"]
    # Nothing before the last stored date is invented.
    assert "2019-12-31" not in snaps
    assert min(snaps) == "2020-01-01"


# ---- gap preserved --------------------------------------------------------

def test_backfill_blocked_when_book_changed(monkeypatch):
    monkeypatch.setattr("app.market.get_histories_bulk", _fake_bulk(FULL))
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "SPY", 10, 1000.0)
    _seed_entry("2020-01-01", _current(), FULL)

    # The book changes: shares edited after the reference was recorded.
    portfolio.edit_holding("main", "SPY", 20, None)

    entry = portfolio_history.record_snapshot(now=NOW)
    assert entry["close_date"] == "2020-01-06"
    snaps = portfolio_history.load_history()["snapshots"]
    # The gap is preserved: only the reference and the live latest date exist.
    assert set(snaps) == {"2020-01-01", "2020-01-06"}


def test_backfill_blocked_when_holding_added(monkeypatch):
    monkeypatch.setattr("app.market.get_histories_bulk", _fake_bulk(FULL))
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "SPY", 10, 1000.0)
    _seed_entry("2020-01-01", _current(), FULL)

    portfolio.add_holding("main", "AAPL", 5, 250.0)
    portfolio_history.record_snapshot(now=NOW)
    assert set(portfolio_history.load_history()["snapshots"]) == {"2020-01-01", "2020-01-06"}


# ---- mixed portfolios -----------------------------------------------------

def test_backfill_mixed_only_unchanged_portfolios_included(monkeypatch):
    monkeypatch.setattr("app.market.get_histories_bulk", _fake_bulk(FULL))
    portfolio.create_portfolio("Steady")
    portfolio.create_portfolio("Churn")
    portfolio.add_holding("steady", "SPY", 10, 1000.0)
    portfolio.add_holding("churn", "AAPL", 4, 200.0)
    _seed_entry("2020-01-01", _current(), FULL)

    portfolio.edit_holding("churn", "AAPL", 8, None)  # churn's book changed

    portfolio_history.record_snapshot(now=NOW)
    snaps = portfolio_history.load_history()["snapshots"]
    assert snaps["2020-01-02"]["backfilled"] is True
    assert set(snaps["2020-01-02"]["portfolios"]) == {"steady"}
    # The churned portfolio's gap remains (it is simply absent from the entry).
    assert "churn" not in snaps["2020-01-02"]["portfolios"]
    # The live latest date still records both (unchanged behavior).
    assert set(snaps["2020-01-06"]["portfolios"]) == {"steady", "churn"}


# ---- never rewrite / idempotency ------------------------------------------

def test_backfill_never_rewrites_existing_dates(monkeypatch):
    monkeypatch.setattr("app.market.get_histories_bulk", _fake_bulk(FULL))
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "SPY", 10, 1000.0)
    _seed_entry("2020-01-01", _current(), FULL, recorded_at="2020-01-01T21:00:00Z")
    before = portfolio_history.load_history()["snapshots"]["2020-01-01"]

    portfolio_history.record_snapshot(now=NOW)
    after = portfolio_history.load_history()["snapshots"]["2020-01-01"]
    assert after == before  # byte-for-byte deep equality


def test_backfill_idempotent_on_rerun(monkeypatch):
    monkeypatch.setattr("app.market.get_histories_bulk", _fake_bulk(FULL))
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "SPY", 10, 1000.0)
    _seed_entry("2020-01-01", _current(), FULL)

    portfolio_history.record_snapshot(now=NOW)
    first = portfolio_history.HISTORY_PATH.read_text(encoding="utf-8")
    portfolio_history.record_snapshot(now=NOW)
    second = portfolio_history.HISTORY_PATH.read_text(encoding="utf-8")
    assert first == second  # no rewrite, no duplicate dates


# ---- no reference / no detail ---------------------------------------------

def test_backfill_empty_store_records_only_latest(monkeypatch):
    monkeypatch.setattr("app.market.get_histories_bulk", _fake_bulk(FULL))
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "SPY", 10, 1000.0)

    entry = portfolio_history.record_snapshot(now=NOW)
    assert entry["close_date"] == "2020-01-06"
    assert set(portfolio_history.load_history()["snapshots"]) == {"2020-01-06"}


def test_backfill_skipped_when_reference_lacks_detail(monkeypatch):
    monkeypatch.setattr("app.market.get_histories_bulk", _fake_bulk(FULL))
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "SPY", 10, 1000.0)

    state = portfolio_history.load_history()
    state["snapshots"]["2020-01-01"] = {"close_date": "2020-01-01", "recorded_at": "x"}
    portfolio_history.save_history(state)

    portfolio_history.record_snapshot(now=NOW)
    assert set(portfolio_history.load_history()["snapshots"]) == {"2020-01-01", "2020-01-06"}


# ---- reconstruction fidelity ----------------------------------------------

def test_backfill_null_close_never_partial_sum(monkeypatch):
    # AAPL has no rows for the gap days -> that holding's close is null and the
    # portfolio total_value is null (never a partial sum).
    sparse = {
        "SPY": FULL["SPY"],
        "AAPL": _rows(("2020-01-01", 50.0), ("2020-01-06", 55.0)),
    }
    monkeypatch.setattr("app.market.get_histories_bulk", _fake_bulk(sparse))
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "SPY", 10, 1000.0)
    portfolio.add_holding("main", "AAPL", 4, 200.0)
    _seed_entry("2020-01-01", _current(), sparse)

    portfolio_history.record_snapshot(now=NOW)
    gap = portfolio_history.load_history()["snapshots"]["2020-01-02"]["portfolios"]["main"]
    assert gap["holdings"]["AAPL"]["close"] is None
    assert gap["holdings"]["AAPL"]["value"] is None
    assert gap["total_value"] is None
    assert gap["coverage"] == {"ok": 1, "total": 2}


def test_backfill_carries_recorded_cash(monkeypatch):
    monkeypatch.setattr("app.market.get_histories_bulk", _fake_bulk(FULL))
    portfolio.create_portfolio("Main")
    portfolio.add_holding("main", "SPY", 10, 1000.0)
    portfolio.add_cash_row("main", "Cash", 500.0, 500.0)
    _seed_entry("2020-01-01", _current(), FULL)

    portfolio_history.record_snapshot(now=NOW)
    gap = portfolio_history.load_history()["snapshots"]["2020-01-03"]["portfolios"]["main"]
    assert gap["cash"] == 500.0
    assert gap["total_cost"] == 1500.0
    assert gap["total_value"] == 10 * 102.0 + 500.0
