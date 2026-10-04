"""Live-quote composition + per-symbol cache regression suite — fully offline.

Every yfinance-facing helper in ``app/market.py`` is monkeypatched, so no test
here ever touches the network.  The assertions cover:

* date-anchored composition (intraday last vs the settled close *strictly
  before* its session date),
* the weekend / pre-open prior selection,
* the stale-intraday guard (an intraday print older than the latest settled
  daily bar is discarded in favour of the daily last/prior),
* the fallback ladder (fast_info, then latest daily close, else omit),
* the failure-aware per-symbol cache (nulls never cached; fresh entries served
  without a re-fetch; one symbol cached once is shared across symbol sets).

See ``app/market.py::_quote_snapshot`` / ``get_quotes``.
"""

from datetime import date

import pytest

from app import config, market


# ---- Fixtures / stubs --------------------------------------------------------

@pytest.fixture
def cache_dir(monkeypatch, tmp_path):
    d = tmp_path / "cache"
    monkeypatch.setattr(config, "CACHE_DIR", d)
    return d


def _tripwire(*args, **kwargs):
    raise AssertionError("unexpected network-bound call")


def _patch_intraday(monkeypatch, mapping):
    monkeypatch.setattr(market, "_intraday_last", lambda symbols: dict(mapping))


def _patch_daily(monkeypatch, mapping):
    monkeypatch.setattr(market, "_daily_closes", lambda symbols: dict(mapping))


def _patch_fast_info(monkeypatch, mapping):
    monkeypatch.setattr(
        market, "_fast_info_quote", lambda sym: mapping.get(sym, (None, None)),
    )


# ---- a. Composition ----------------------------------------------------------

def test_intraday_composition_uses_daily_close_before_session(monkeypatch):
    _patch_intraday(monkeypatch, {"X": (105.0, date(2026, 1, 6))})
    _patch_daily(monkeypatch, {"X": [(date(2026, 1, 5), 100.0)]})
    monkeypatch.setattr(market, "_fast_info_quote", _tripwire)

    q = market._quote_snapshot(["X"])["X"]

    assert q["price"] == 105.0
    assert q["change"] == 5.0
    assert q["pct_change"] == 5.0  # (105 - 100) / 100 * 100


# ---- b. Weekend / pre-open prior ---------------------------------------------

def test_weekend_prior_is_daily_close_strictly_before_session(monkeypatch):
    thursday, friday = date(2026, 1, 8), date(2026, 1, 9)
    # Friday's live tick, plus Friday's settled close already available.
    _patch_intraday(monkeypatch, {"X": (103.0, friday)})
    _patch_daily(monkeypatch, {"X": [(thursday, 100.0), (friday, 101.0)]})
    monkeypatch.setattr(market, "_fast_info_quote", _tripwire)

    q = market._quote_snapshot(["X"])["X"]

    assert q["price"] == 103.0
    assert q["change"] == 3.0
    # Prior is Thursday (strictly before Friday), so this is Friday's move —
    # not a comparison against Friday's own settled close.
    assert q["pct_change"] == 3.0


# ---- c. Stale-intraday guard -------------------------------------------------

def test_stale_intraday_discarded_for_newer_daily_bar(monkeypatch):
    # Intraday print is from Jan 5, but Jan 6 already settled.
    _patch_intraday(monkeypatch, {"X": (50.0, date(2026, 1, 5))})
    _patch_daily(monkeypatch, {
        "X": [(date(2026, 1, 5), 100.0), (date(2026, 1, 6), 110.0)],
    })
    monkeypatch.setattr(market, "_fast_info_quote", _tripwire)

    q = market._quote_snapshot(["X"])["X"]

    # The stale 50.0 tick is thrown away; daily last/prior win.
    assert q["price"] == 110.0
    assert q["change"] == 10.0
    assert q["pct_change"] == 10.0


# ---- d. Fallback ladder ------------------------------------------------------

def test_intraday_absent_falls_back_to_fast_info(monkeypatch):
    _patch_intraday(monkeypatch, {})
    _patch_daily(monkeypatch, {})
    _patch_fast_info(monkeypatch, {"X": (200.0, 195.0)})

    q = market._quote_snapshot(["X"])["X"]

    assert q["price"] == 200.0
    assert q["change"] == 5.0
    assert q["pct_change"] == round(5.0 / 195.0 * 100, 3)


def test_fast_info_absent_falls_back_to_latest_daily_close(monkeypatch):
    _patch_intraday(monkeypatch, {})
    _patch_daily(monkeypatch, {
        "X": [(date(2026, 1, 5), 100.0), (date(2026, 1, 6), 110.0)],
    })
    _patch_fast_info(monkeypatch, {})  # -> (None, None)

    q = market._quote_snapshot(["X"])["X"]

    assert q["price"] == 110.0
    assert q["change"] == 10.0
    assert q["pct_change"] == 10.0


def test_all_sources_absent_omits_symbol(monkeypatch):
    _patch_intraday(monkeypatch, {})
    _patch_daily(monkeypatch, {})
    _patch_fast_info(monkeypatch, {})

    assert market._quote_snapshot(["X"]) == {}


# ---- e. Per-symbol cache -----------------------------------------------------

def test_null_price_entry_is_never_cached(cache_dir, monkeypatch):
    def snap(symbols):
        return {s: {"price": None, "change": None, "pct_change": None} for s in symbols}

    monkeypatch.setattr(market, "_quote_snapshot", snap)

    assert market.get_quotes(["X"]) == {}
    assert list(cache_dir.glob("quote_*.json")) == []


def test_all_empty_snapshot_never_cached_and_retried(cache_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(
        market, "_quote_snapshot",
        lambda symbols: calls.append(list(symbols)) or {},
    )

    assert market.get_quotes(["X"]) == {}
    assert market.get_quotes(["X"]) == {}
    assert len(calls) == 2  # retried instead of serving a poisoned cache
    assert list(cache_dir.glob("quote_*.json")) == []


def test_fresh_per_symbol_entry_served_without_refetch(cache_dir, monkeypatch):
    calls = {"n": 0}

    def snap(symbols):
        calls["n"] += 1
        return {"X": {"price": 1.0, "change": 0.5, "pct_change": 100.0}}

    monkeypatch.setattr(market, "_quote_snapshot", snap)

    first = market.get_quotes(["X"])
    second = market.get_quotes(["X"])

    assert first == second == {"X": {"price": 1.0, "change": 0.5, "pct_change": 100.0}}
    assert calls["n"] == 1  # second call never hit the snapshot builder
    assert (cache_dir / f"quote_{market._safe_key('X')}.json").exists()


# ---- f. Cross-view consistency ----------------------------------------------

def test_shared_per_symbol_cache_agrees_across_symbol_sets(cache_dir, monkeypatch):
    fixed = {"X": {"price": 5000.0, "change": 10.0, "pct_change": 0.2}}
    monkeypatch.setattr(market, "_quote_snapshot", lambda symbols: dict(fixed))

    a = market.get_quotes(["X"])
    b = market.get_quotes(["X", "Y"])

    assert a["X"]["price"] == b["X"]["price"] == 5000.0
    assert a["X"]["pct_change"] == b["X"]["pct_change"] == 0.2


def test_enrich_and_market_snapshot_agree_on_overlapping_symbol(cache_dir, monkeypatch):
    from app import portfolio

    fixed = {"^GSPC": {"price": 5000.0, "change": 10.0, "pct_change": 0.2}}
    monkeypatch.setattr(market, "_quote_snapshot", lambda symbols: dict(fixed))
    # Both readers otherwise pull the bulk history download; keep it offline.
    monkeypatch.setattr(market, "get_histories_bulk", lambda symbols, days=250: {})
    monkeypatch.setattr(portfolio, "get_info_snapshot", lambda sym: {})

    state = {"portfolios": {"p": {"holdings": [{"symbol": "^GSPC", "shares": 1}]}}}
    enriched = portfolio.enrich_portfolios(state, ttl=config.LIVE_QUOTE_TTL)
    holding = enriched["portfolios"]["p"]["holdings"][0]
    quote = market.build_market_snapshot()["indices"]["^GSPC"]

    assert holding["last_price"] == quote["price"] == 5000.0
    assert holding["pct_daily"] == quote["pct_change"] == 0.2
