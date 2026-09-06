"""Tests for app/earnings.py validate_symbol (mocked yfinance, no network)."""

import pytest

from app import earnings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeTicker:
    """Minimal yfinance.Ticker stand-in controlled by the test."""

    def __init__(self, info: dict | None = None, exc: Exception | None = None):
        self._info = info
        self._exc = exc

    @property
    def info(self):
        if self._exc:
            raise self._exc
        return self._info


# ---------------------------------------------------------------------------
# test_validate_symbol_valid_with_long_name
# ---------------------------------------------------------------------------

def test_validate_symbol_valid_with_long_name(monkeypatch):
    """_yf_info returns a dict with longName → valid, name, sector propagated."""
    fake = _FakeTicker(info={"longName": "Apple Inc.", "sector": "Technology"})
    monkeypatch.setattr(earnings, "_yf_info_with_retry", lambda sym, **kw: (fake.info, None))
    monkeypatch.setattr(earnings, "_validate_cached", lambda s, b: earnings._validate_uncached(s))

    result = earnings.validate_symbol("AAPL")
    assert result["valid"] is True
    assert result["name"] == "Apple Inc."
    assert result["sector"] == "Technology"


# ---------------------------------------------------------------------------
# test_validate_symbol_valid_via_confirmation_field
# ---------------------------------------------------------------------------

def test_validate_symbol_valid_via_confirmation_field(monkeypatch):
    """_yf_info returns a dict without longName/shortName but WITH exchange → valid."""
    fake_info = {"symbol": "AAPL", "exchange": "NMS", "quoteType": "EQUITY"}
    monkeypatch.setattr(earnings, "_yf_info_with_retry", lambda sym, **kw: (fake_info, None))
    monkeypatch.setattr(earnings, "_validate_cached", lambda s, b: earnings._validate_uncached(s))

    result = earnings.validate_symbol("AAPL")
    assert result["valid"] is True
    assert result["name"] == "AAPL"  # falls back to sym


# ---------------------------------------------------------------------------
# test_validate_symbol_valid_via_history_fallback
# ---------------------------------------------------------------------------

def test_validate_symbol_valid_via_history_fallback(monkeypatch):
    """_yf_info returns empty dict AND history returns rows → valid (fallback path)."""
    monkeypatch.setattr(earnings, "_yf_info_with_retry", lambda sym, **kw: ({}, None))
    monkeypatch.setattr(earnings, "_validate_by_history", lambda sym: {"symbol": sym, "name": sym})
    monkeypatch.setattr(earnings, "_validate_cached", lambda s, b: earnings._validate_uncached(s))

    result = earnings.validate_symbol("AAPL")
    assert result["valid"] is True
    assert result["name"] == "AAPL"


# ---------------------------------------------------------------------------
# test_validate_symbol_rejected_when_both_fail
# ---------------------------------------------------------------------------

def test_validate_symbol_rejected_when_both_fail(monkeypatch):
    """Both lookups return empty, no network error → 'no yfinance profile' reason."""
    monkeypatch.setattr(earnings, "_yf_info_with_retry", lambda sym, **kw: ({}, None))
    monkeypatch.setattr(earnings, "_validate_by_history", lambda sym: None)
    monkeypatch.setattr(earnings, "_validate_cached", lambda s, b: earnings._validate_uncached(s))

    result = earnings.validate_symbol("ZZZZZ")
    assert result["valid"] is False
    assert "no yfinance profile" in result["reason"]
    assert "ZZZZZ" in result["reason"]


# ---------------------------------------------------------------------------
# test_validate_symbol_network_error_distinguishable
# ---------------------------------------------------------------------------

def test_validate_symbol_network_error_distinguishable(monkeypatch):
    """_yf_info raises a network error AND history returns [] → reason mentions
    'yfinance unavailable' or 'rate-limit', NOT just 'no yfinance profile'."""
    monkeypatch.setattr(
        earnings, "_yf_info_with_retry",
        lambda sym, **kw: ({}, "network: ConnectionError: HTTPSConnectionPool"),
    )
    monkeypatch.setattr(earnings, "_validate_by_history", lambda sym: None)
    monkeypatch.setattr(earnings, "_validate_cached", lambda s, b: earnings._validate_uncached(s))

    result = earnings.validate_symbol("AAPL")
    assert result["valid"] is False
    reason = result["reason"]
    # Must clearly indicate it was a network issue, not invalid symbol
    assert "yfinance unavailable" in reason or "rate-limit" in reason or "network" in reason
    assert "no yfinance profile" not in reason


def test_validate_symbol_rate_limit_error_distinguishable(monkeypatch):
    """_yf_info returns a rate-limit error → reason mentions 'unavailable'."""
    monkeypatch.setattr(
        earnings, "_yf_info_with_retry",
        lambda sym, **kw: ({}, "rate-limited: Too Many Requests"),
    )
    monkeypatch.setattr(earnings, "_validate_by_history", lambda sym: None)
    monkeypatch.setattr(earnings, "_validate_cached", lambda s, b: earnings._validate_uncached(s))

    result = earnings.validate_symbol("AAPL")
    assert result["valid"] is False
    assert "unavailable" in result["reason"]


# ---------------------------------------------------------------------------
# test_validate_symbol_empty_string
# ---------------------------------------------------------------------------

def test_validate_symbol_empty_string():
    """Empty/whitespace input → valid:False, reason='empty symbol'."""
    assert earnings.validate_symbol("")["valid"] is False
    assert earnings.validate_symbol("")["reason"] == "empty symbol"

    assert earnings.validate_symbol("   ")["valid"] is False
    assert earnings.validate_symbol("   ")["reason"] == "empty symbol"

    assert earnings.validate_symbol(None)["valid"] is False
    assert earnings.validate_symbol(None)["reason"] == "empty symbol"


# ---------------------------------------------------------------------------
# test_validate_symbol_garbage_string
# ---------------------------------------------------------------------------

def test_validate_symbol_garbage_string(monkeypatch):
    """Random garbage that doesn't match _TICKER_RE → valid:False, invalid format."""
    result = earnings.validate_symbol("!!!???")
    assert result["valid"] is False
    assert "invalid ticker format" in result["reason"]


def test_validate_symbol_too_long_rejected():
    """Symbol > 10 chars → valid:False."""
    result = earnings.validate_symbol("VERYLONGSYMBOL")
    assert result["valid"] is False
    assert "invalid ticker format" in result["reason"]


# ---------------------------------------------------------------------------
# test_validate_symbol_cache_does_not_re_call_yfinance
# ---------------------------------------------------------------------------

def test_validate_symbol_cache_does_not_re_call_yfinance(monkeypatch):
    """Two calls with same symbol within TTL bucket → only one yfinance call."""
    call_count = 0

    def _fake_validate_uncached(sym):
        nonlocal call_count
        call_count += 1
        return {"valid": True, "symbol": sym, "name": "Test Co", "sector": None}

    # Reset the LRU cache so this test starts clean
    earnings._validate_cached.cache_clear()
    monkeypatch.setattr(earnings, "_validate_uncached", _fake_validate_uncached)
    monkeypatch.setattr(earnings, "_cache_bucket", lambda: 42)  # fixed bucket

    earnings.validate_symbol("AAPL")
    earnings.validate_symbol("AAPL")
    earnings.validate_symbol("AAPL")

    assert call_count == 1, f"Expected 1 yfinance call, got {call_count}"


def test_validate_symbol_cache_miss_across_buckets(monkeypatch):
    """Different cache buckets → yfinance called again."""
    call_count = 0

    def _fake_validate_uncached(sym):
        nonlocal call_count
        call_count += 1
        return {"valid": True, "symbol": sym, "name": "Test Co", "sector": None}

    earnings._validate_cached.cache_clear()
    monkeypatch.setattr(earnings, "_validate_uncached", _fake_validate_uncached)

    # Simulate different time buckets
    monkeypatch.setattr(earnings, "_cache_bucket", lambda: 42)
    earnings.validate_symbol("AAPL")

    monkeypatch.setattr(earnings, "_cache_bucket", lambda: 43)
    earnings.validate_symbol("AAPL")

    assert call_count == 2, f"Expected 2 yfinance calls, got {call_count}"


# ---------------------------------------------------------------------------
# test_validate_symbol_lowercase_normalised
# ---------------------------------------------------------------------------

def test_validate_symbol_lowercase_normalised(monkeypatch):
    """Lowercase input is uppercased before lookup."""
    fake = _FakeTicker(info={"longName": "Apple Inc."})
    monkeypatch.setattr(earnings, "_yf_info_with_retry", lambda sym, **kw: (fake.info, None))
    monkeypatch.setattr(earnings, "_validate_cached", lambda s, b: earnings._validate_uncached(s))

    result = earnings.validate_symbol("aapl")
    assert result["valid"] is True
    assert result["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# test_add_ticker_cache_miss_does_not_trigger_full_rebuild
# ---------------------------------------------------------------------------

def test_add_ticker_cache_miss_does_not_trigger_full_rebuild(monkeypatch):
    """When _cached_calendar() returns None (cache expired/missing),
    add_ticker must NOT call earnings_calendar() (which would trigger a
    30-60s full universe rebuild). It should instead build just the new
    ticker and return a minimal payload."""
    # Stub validation to always pass
    monkeypatch.setattr(earnings, "_validate_cached", lambda s, b: {"valid": True, "symbol": s, "name": s, "sector": None})

    # Stub _cached_calendar to return None (cache miss)
    monkeypatch.setattr(earnings, "_cached_calendar", lambda: None)

    # Track whether earnings_calendar was called
    calendar_called = []
    original_earnings_calendar = earnings.earnings_calendar
    def tracking_earnings_calendar():
        calendar_called.append(True)
        return original_earnings_calendar()
    monkeypatch.setattr(earnings, "earnings_calendar", tracking_earnings_calendar)

    # Stub _enrich to avoid yfinance calls
    def fake_enrich(sym, quotes):
        return {"symbol": sym, "next_earnings": "2026-10-01", "price": 100.0}
    monkeypatch.setattr(earnings, "_enrich", fake_enrich)

    # Stub _quote_snapshot
    monkeypatch.setattr("app.market._quote_snapshot", lambda syms: {})

    # Stub watchlist persistence to avoid filesystem
    monkeypatch.setattr(earnings, "load_watchlist", lambda: ["existing"])
    monkeypatch.setattr(earnings, "save_watchlist", lambda t: None)
    monkeypatch.setattr(earnings, "load_removed", lambda: [])
    monkeypatch.setattr(earnings, "save_removed", lambda t: None)

    # Stub store.save_json to avoid filesystem
    monkeypatch.setattr(earnings.store, "save_json", lambda p, d: None)

    result = earnings.add_ticker("AAPL")

    # earnings_calendar must NOT have been called
    assert not calendar_called, "earnings_calendar() should not be called on cache miss"

    # The result should contain the new ticker in companies
    assert "companies" in result
    companies = result.get("companies") or []
    symbols = {r["symbol"] for r in companies}
    assert "AAPL" in symbols, f"Expected AAPL in companies, got {symbols}"
