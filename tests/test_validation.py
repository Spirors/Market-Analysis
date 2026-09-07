"""Tests for app/validation.py validate_symbol (mocked yfinance, no network).

validate_symbol is the small helper kept after the Earnings watchlist
section was removed — it's still used by portfolio.add_holding to validate
new symbols before they reach the watchlist / cache filenames.

Scenario coverage mirrors docs/DECISIONS.md "Phase 2 audit — earnings
validate_symbol path diff":
  - Scenario A: yfinance both surfaces work → valid=True with metadata
  - Scenario B: Ticker.info rate-limited but yf.download works
    → valid=True via primary history check (THE BUG FROM a2c793a)
  - Scenario C: both surfaces fail → valid=False with yfinance-unavailable reason
  - Scenario D: Ticker.info works but yf.download empty
    → valid=True via secondary info fallback
"""

import pytest

from app import validation, market


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


def _stub_history(monkeypatch, rows: list[dict] | None):
    """Mock market.get_history to return the given rows (or None = no history)."""
    monkeypatch.setattr(validation.market, "get_history", lambda sym, days=5: rows)


def _stub_info(monkeypatch, info_dict: dict | None, error: str | None = None):
    """Mock _yf_info to return the given (info, error) tuple."""
    monkeypatch.setattr(validation, "_yf_info", lambda sym: (info_dict or {}, error))


def _bypass_cache(monkeypatch):
    """Run _validate_uncached directly (skip the 60s lru_cache)."""
    monkeypatch.setattr(validation, "_validate_cached", lambda s, b: validation._validate_uncached(s))


# ---------------------------------------------------------------------------
# Happy path — PRIMARY history check succeeds
# ---------------------------------------------------------------------------

def test_validate_symbol_primary_history_succeeds_when_ticker_info_empty(monkeypatch):
    """REGRESSION for the original 'invalid symbol' bug.

    Scenario B: Ticker.info is empty (rate-limited / sparse), yf.download
    returns real history. Under the pre-fix ordering (Ticker.info primary),
    this scenario returned valid=False unless the secondary history-fallback
    rescued it. Under the new PRIMARY=history / SECONDARY=Ticker.info
    ordering, validation succeeds immediately.
    """
    _stub_history(monkeypatch, [{"date": "2026-09-06", "close": 130.8}])
    _stub_info(monkeypatch, {})  # Ticker.info rate-limited / empty
    _bypass_cache(monkeypatch)

    result = validation.validate_symbol("NVDA")
    assert result["valid"] is True
    assert result["name"] == "NVDA"  # enrichment name falls back to sym
    assert result["sector"] is None
    assert "reason" not in result  # success path doesn't carry reason


def test_validate_symbol_primary_history_enriches_with_ticker_info(monkeypatch):
    """Happy path: PRIMARY history succeeds AND Ticker.info enriches name+sector."""
    _stub_history(monkeypatch, [{"date": "2026-09-06", "close": 220.0}])
    _stub_info(monkeypatch, {"longName": "Apple Inc.", "sector": "Technology"})
    _bypass_cache(monkeypatch)

    result = validation.validate_symbol("AAPL")
    assert result["valid"] is True
    assert result["name"] == "Apple Inc."
    assert result["sector"] == "Technology"


def test_validate_symbol_primary_history_enriches_with_confirmation_field(monkeypatch):
    """Ticker.info has exchange/currency/quoteType but no longName — still enriches."""
    _stub_history(monkeypatch, [{"date": "2026-09-06", "close": 50.0}])
    _stub_info(monkeypatch, {"exchange": "NMS", "quoteType": "EQUITY", "currency": "USD"})
    _bypass_cache(monkeypatch)

    result = validation.validate_symbol("AAPL")
    assert result["valid"] is True
    assert result["name"] == "AAPL"
    assert result["sector"] is None


# ---------------------------------------------------------------------------
# SECONDARY fallback path — Ticker.info when history is empty
# ---------------------------------------------------------------------------

def test_validate_symbol_secondary_info_recognises_sparse_history(monkeypatch):
    """Scenario D: yf.download returns no history but Ticker.info confirms."""
    _stub_history(monkeypatch, [])
    _stub_info(monkeypatch, {"longName": "NewTech Inc.", "sector": "Technology"})
    _bypass_cache(monkeypatch)

    result = validation.validate_symbol("NTCH")
    assert result["valid"] is True
    assert result["name"] == "NewTech Inc."
    assert result["sector"] == "Technology"


def test_validate_symbol_secondary_info_confirmation_field_only(monkeypatch):
    """Scenario D variant: Ticker.info has only confirmation fields."""
    _stub_history(monkeypatch, [])
    _stub_info(monkeypatch, {"exchange": "NMS", "quoteType": "EQUITY"})
    _bypass_cache(monkeypatch)

    result = validation.validate_symbol("SOMESYM")
    assert result["valid"] is True
    assert result["name"] == "SOMESYM"


# ---------------------------------------------------------------------------
# Failure path — both surfaces empty (the actual bug scenario)
# ---------------------------------------------------------------------------

def test_validate_symbol_both_surfaces_fail_returns_invalid_symbol(monkeypatch):
    """Scenario C — THE BUG. Both empty → valid=False with yfinance-unavailable reason."""
    _stub_history(monkeypatch, [])
    _stub_info(monkeypatch, {}, error="network: ConnectionError: timed out")
    _bypass_cache(monkeypatch)

    result = validation.validate_symbol("NVDA")
    assert result["valid"] is False
    assert "yfinance unavailable" in result["reason"]
    assert "NVDA" in result["reason"]


def test_validate_symbol_both_surfaces_empty_no_error(monkeypatch):
    """Both empty + no network error → 'symbol not found' reason."""
    _stub_history(monkeypatch, [])
    _stub_info(monkeypatch, {}, error=None)
    _bypass_cache(monkeypatch)

    result = validation.validate_symbol("ZZZZZ")
    assert result["valid"] is False
    assert "no price history" in result["reason"]
    assert "ZZZZZ" in result["reason"]


def test_validate_symbol_rate_limit_error_distinguishable(monkeypatch):
    """Rate-limit error → reason mentions 'unavailable'."""
    _stub_history(monkeypatch, [])
    _stub_info(monkeypatch, {}, error="rate-limited: Too Many Requests")
    _bypass_cache(monkeypatch)

    result = validation.validate_symbol("AAPL")
    assert result["valid"] is False
    assert "unavailable" in result["reason"]
    assert "rate-limit" in result["reason"]


# ---------------------------------------------------------------------------
# Input validation (no network involved)
# ---------------------------------------------------------------------------

def test_validate_symbol_empty_string():
    """Empty/whitespace input → valid:False, reason='empty symbol'."""
    assert validation.validate_symbol("")["valid"] is False
    assert validation.validate_symbol("")["reason"] == "empty symbol"
    assert validation.validate_symbol("   ")["valid"] is False
    assert validation.validate_symbol("   ")["reason"] == "empty symbol"
    assert validation.validate_symbol(None)["valid"] is False
    assert validation.validate_symbol(None)["reason"] == "empty symbol"


def test_validate_symbol_garbage_string(monkeypatch):
    """Random garbage that doesn't match _TICKER_RE → valid:False, invalid format."""
    result = validation.validate_symbol("!!!???")
    assert result["valid"] is False
    assert "invalid ticker format" in result["reason"]


def test_validate_symbol_too_long_rejected():
    """Symbol > 10 chars → valid:False."""
    result = validation.validate_symbol("VERYLONGSYMBOL")
    assert result["valid"] is False
    assert "invalid ticker format" in result["reason"]


def test_validate_symbol_lowercase_normalised(monkeypatch):
    """Lowercase input is uppercased before lookup."""
    _stub_history(monkeypatch, [{"date": "2026-09-06", "close": 220.0}])
    _stub_info(monkeypatch, {"longName": "Apple Inc."})
    _bypass_cache(monkeypatch)

    result = validation.validate_symbol("aapl")
    assert result["valid"] is True
    assert result["symbol"] == "AAPL"
    assert result["name"] == "Apple Inc."


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------

def test_validate_symbol_cache_does_not_re_call_yfinance(monkeypatch):
    """Two calls with same symbol within TTL bucket → only one underlying call."""
    call_count = 0

    def _fake_validate_uncached(sym):
        nonlocal call_count
        call_count += 1
        return {"valid": True, "symbol": sym, "name": "Test Co", "sector": None}

    validation._validate_cached.cache_clear()
    monkeypatch.setattr(validation, "_validate_uncached", _fake_validate_uncached)
    monkeypatch.setattr(validation, "_cache_bucket", lambda: 42)

    validation.validate_symbol("AAPL")
    validation.validate_symbol("AAPL")
    validation.validate_symbol("AAPL")

    assert call_count == 1, f"Expected 1 call, got {call_count}"


def test_validate_symbol_cache_miss_across_buckets(monkeypatch):
    """Different cache buckets → underlying call made again."""
    call_count = 0

    def _fake_validate_uncached(sym):
        nonlocal call_count
        call_count += 1
        return {"valid": True, "symbol": sym, "name": "Test Co", "sector": None}

    validation._validate_cached.cache_clear()
    monkeypatch.setattr(validation, "_validate_uncached", _fake_validate_uncached)
    monkeypatch.setattr(validation, "_cache_bucket", lambda: 42)
    validation.validate_symbol("AAPL")
    monkeypatch.setattr(validation, "_cache_bucket", lambda: 43)
    validation.validate_symbol("AAPL")

    assert call_count == 2, f"Expected 2 calls, got {call_count}"


# ---------------------------------------------------------------------------
# User-facing path: portfolio.add_holding (validates before persisting)
# ---------------------------------------------------------------------------

def test_add_holding_validates_via_primary_history_path(monkeypatch):
    """portfolio.add_holding uses validation.validate_symbol — when Ticker.info
    is rate-limited but yf.download still works, adding NVDA to a portfolio
    succeeds instead of raising 'invalid symbol'.
    """
    from app import portfolio
    _stub_history(monkeypatch, [{"date": "2026-09-06", "close": 130.8}])
    _stub_info(monkeypatch, {})  # Ticker.info rate-limited
    _bypass_cache(monkeypatch)

    pid = "diag-add-holding-pf"
    state = portfolio.load_portfolios()
    state["portfolios"][pid] = {"id": pid, "name": "Diag", "holdings": []}
    portfolio.save_portfolios(state)

    holding = portfolio.add_holding(pid, "NVDA", 1.0, 130.0)
    assert holding["symbol"] == "NVDA"
    assert holding["shares"] == 1.0
    assert holding["total_cost"] == 130.0


# ---------------------------------------------------------------------------
# Structural regression tests — verify call order, no retry-with-sleep
# ---------------------------------------------------------------------------

def test_validate_symbol_calls_history_before_ticker_info(monkeypatch):
    """STRUCTURAL regression. Pre-fix (a2c793a) ordering was
    PRIMARY=Ticker.info → FALLBACK=history.  Post-fix ordering is
    PRIMARY=history → SECONDARY=Ticker.info (enrichment only).  This test
    pins the call order so a future revert fails.
    """
    call_log: list[str] = []

    def _tracking_history(sym, days=5):
        call_log.append("history")
        return [{"date": "2026-09-06", "close": 130.8}]

    def _tracking_info(sym):
        call_log.append("info")
        return ({"longName": "NVIDIA Corporation", "sector": "Technology"}, None)

    monkeypatch.setattr(validation.market, "get_history", _tracking_history)
    monkeypatch.setattr(validation, "_yf_info", _tracking_info)
    _bypass_cache(monkeypatch)

    result = validation.validate_symbol("NVDA")
    assert result["valid"] is True
    # History MUST be called first.
    assert call_log == ["history", "info"], (
        f"Expected history first then info (primary=history), got {call_log}"
    )


def test_validate_symbol_history_primary_short_circuits(monkeypatch):
    """When PRIMARY history check succeeds, Ticker.info is called at most
    once (for enrichment) and only on the success path.  Pre-fix code
    called Ticker.info FIRST (and retried it on rate-limit error, adding
    1s of latency before the history fallback).  Post-fix skips the retry.
    """
    call_log: list[str] = []

    def _tracking_history(sym, days=5):
        call_log.append("history")
        return [{"date": "2026-09-06", "close": 130.8}]

    def _tracking_info(sym):
        call_log.append("info")
        return ({}, None)  # empty info, no exception

    monkeypatch.setattr(validation.market, "get_history", _tracking_history)
    monkeypatch.setattr(validation, "_yf_info", _tracking_info)
    _bypass_cache(monkeypatch)

    result = validation.validate_symbol("NVDA")
    assert result["valid"] is True
    assert call_log.count("history") == 1
    assert call_log.count("info") == 1


def test_validate_symbol_does_not_use_retry_helper():
    """The pre-fix ``_yf_info_with_retry`` helper applied retry-with-
    1s-backoff around ``_yf_info``.  That helper was removed in the
    Phase 2 fix — retrying a fundamentally flaky call was masking the
    bug, not fixing it.  This test pins that the helper is GONE.
    """
    assert not hasattr(validation, "_yf_info_with_retry"), (
        "_yf_info_with_retry was removed in the Phase 2 fix — retrying a "
        "fundamentally flaky call was masking the bug, not fixing it. "
        "If you need to re-add it, see docs/DECISIONS.md 'Phase 2 audit "
        "— earnings validate_symbol path diff' for the rationale."
    )


def test_validate_symbol_no_sleep_in_retry_path(monkeypatch):
    """Pre-fix code called ``time.sleep(1.0)`` between Ticker.info retries.
    Post-fix code has no retry path, so no sleep.
    """
    import time as _time
    sleeps: list[float] = []
    monkeypatch.setattr(_time, "sleep", lambda s: sleeps.append(s))

    _stub_history(monkeypatch, [{"date": "2026-09-06", "close": 130.8}])
    _stub_info(monkeypatch, {}, error="rate-limited: Too Many Requests")
    _bypass_cache(monkeypatch)

    validation.validate_symbol("NVDA")

    assert not any(s >= 0.5 for s in sleeps), (
        f"Found retry-style sleep in validate_symbol: {sleeps}"
    )
