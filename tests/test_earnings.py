"""Tests for app/earnings.py validate_symbol (mocked yfinance, no network).

The validator now uses ``market.get_history`` (the bulk-download surface,
same as portfolio's enrichment path) as PRIMARY existence check, with
``yf.Ticker.info`` as secondary fallback + best-effort enrichment.

Regression coverage for the ROADMAP.md Phase 2 "Diagnose earnings watchlist
false-positive 'invalid symbol' error" item:

- test_validate_symbol_primary_history_succeeds_when_ticker_info_empty
  (Scenario B — the actual user-reported bug: Ticker.info rate-limited,
  yf.download works, validation still succeeds)

- test_validate_symbol_secondary_info_recognises_sparse_history
  (Scenario D — yf.download empty but Ticker.info has data, validation
  succeeds via the secondary path)

- test_validate_symbol_both_surfaces_fail_returns_invalid_symbol
  (Scenario C — full outage / both rate-limited, "yfinance unavailable"
  reason surfaces)

- test_validate_symbol_with_holding_user_facing_path
  (portfolio.add_holding integration: the user-reported repro now works
  because the same fix unblocks the portfolio add path too)
"""

import pytest

from app import earnings, market


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
    monkeypatch.setattr(earnings.market, "get_history", lambda sym, days=5: rows)


def _stub_info(monkeypatch, info_dict: dict | None, error: str | None = None):
    """Mock _yf_info to return the given (info, error) tuple."""
    monkeypatch.setattr(earnings, "_yf_info", lambda sym: (info_dict or {}, error))


def _bypass_cache(monkeypatch):
    """Run _validate_uncached directly (skip the 60s lru_cache)."""
    monkeypatch.setattr(earnings, "_validate_cached", lambda s, b: earnings._validate_uncached(s))


# ---------------------------------------------------------------------------
# Happy path — PRIMARY history check succeeds
# ---------------------------------------------------------------------------

def test_validate_symbol_primary_history_succeeds_when_ticker_info_empty(monkeypatch):
    """REGRESSION for the ROADMAP Phase 2 'invalid symbol' bug.

    Scenario B from docs/DECISIONS.md "Phase 2 audit — earnings
    validate_symbol path diff": Ticker.info is empty (rate-limited /
    sparse), yf.download returns real history. Under the pre-fix
    ordering (Ticker.info primary), this scenario returned valid=False
    unless the secondary history-fallback rescued it. Under the new
    PRIMARY=history / SECONDARY=Ticker.info ordering, validation
    succeeds immediately — the common rate-limit case is no longer
    dependent on the fallback rescuing it.
    """
    _stub_history(monkeypatch, [{"date": "2026-09-06", "close": 130.8}])
    _stub_info(monkeypatch, {})  # Ticker.info rate-limited / empty
    _bypass_cache(monkeypatch)

    result = earnings.validate_symbol("NVDA")
    assert result["valid"] is True
    # Ticker.info was empty so enrichment name falls back to sym.
    assert result["name"] == "NVDA"
    assert result["sector"] is None
    assert "reason" not in result  # success path doesn't carry reason


def test_validate_symbol_primary_history_enriches_with_ticker_info(monkeypatch):
    """Happy path: PRIMARY history succeeds AND Ticker.info enriches name+sector."""
    _stub_history(monkeypatch, [{"date": "2026-09-06", "close": 220.0}])
    _stub_info(monkeypatch, {"longName": "Apple Inc.", "sector": "Technology"})
    _bypass_cache(monkeypatch)

    result = earnings.validate_symbol("AAPL")
    assert result["valid"] is True
    assert result["name"] == "Apple Inc."
    assert result["sector"] == "Technology"


def test_validate_symbol_primary_history_enriches_with_confirmation_field(monkeypatch):
    """Ticker.info has exchange/currency/quoteType but no longName — still enriches."""
    _stub_history(monkeypatch, [{"date": "2026-09-06", "close": 50.0}])
    _stub_info(monkeypatch, {"exchange": "NMS", "quoteType": "EQUITY", "currency": "USD"})
    _bypass_cache(monkeypatch)

    result = earnings.validate_symbol("AAPL")
    assert result["valid"] is True
    # Name falls back to sym because no longName/shortName.
    assert result["name"] == "AAPL"
    assert result["sector"] is None


# ---------------------------------------------------------------------------
# SECONDARY fallback path — Ticker.info when history is empty
# ---------------------------------------------------------------------------

def test_validate_symbol_secondary_info_recognises_sparse_history(monkeypatch):
    """Scenario D: yf.download returns no history (sparse / new listing)
    but Ticker.info confirms the symbol. The validator's secondary
    fallback should still return valid=True with sector/longName.
    """
    _stub_history(monkeypatch, [])  # no OHLC history available
    _stub_info(monkeypatch, {"longName": "NewTech Inc.", "sector": "Technology"})
    _bypass_cache(monkeypatch)

    result = earnings.validate_symbol("NTCH")
    assert result["valid"] is True
    assert result["name"] == "NewTech Inc."
    assert result["sector"] == "Technology"


def test_validate_symbol_secondary_info_confirmation_field_only(monkeypatch):
    """Scenario D variant: Ticker.info has only confirmation fields
    (no longName/shortName). Should still return valid=True.
    """
    _stub_history(monkeypatch, [])
    _stub_info(monkeypatch, {"exchange": "NMS", "quoteType": "EQUITY"})
    _bypass_cache(monkeypatch)

    result = earnings.validate_symbol("SOMESYM")
    assert result["valid"] is True
    assert result["name"] == "SOMESYM"  # sym is the fallback name


# ---------------------------------------------------------------------------
# Failure path — both surfaces empty (the actual bug scenario)
# ---------------------------------------------------------------------------

def test_validate_symbol_both_surfaces_fail_returns_invalid_symbol(monkeypatch):
    """Scenario C — THE BUG from the ROADMAP.md Phase 2 audit.

    Both yf.download AND Ticker.info are empty. Validator must return
    valid=False with a reason that distinguishes 'yfinance unavailable'
    (network / rate-limit) from 'symbol genuinely not found'.
    """
    _stub_history(monkeypatch, [])
    _stub_info(monkeypatch, {}, error="network: ConnectionError: timed out")
    _bypass_cache(monkeypatch)

    result = earnings.validate_symbol("NVDA")
    assert result["valid"] is False
    assert "yfinance unavailable" in result["reason"]
    assert "NVDA" in result["reason"]
    # Must NOT use the misleading 'no yfinance profile' wording — that's
    # what the user was seeing pre-fix when Yahoo was rate-limiting.
    assert "no yfinance profile" not in result["reason"]


def test_validate_symbol_both_surfaces_empty_no_error(monkeypatch):
    """Both empty + no network error → 'symbol not found' reason."""
    _stub_history(monkeypatch, [])
    _stub_info(monkeypatch, {}, error=None)
    _bypass_cache(monkeypatch)

    result = earnings.validate_symbol("ZZZZZ")
    assert result["valid"] is False
    assert "no price history" in result["reason"]
    assert "ZZZZZ" in result["reason"]


def test_validate_symbol_rate_limit_error_distinguishable(monkeypatch):
    """Network-class / rate-limit error → reason mentions 'unavailable'."""
    _stub_history(monkeypatch, [])
    _stub_info(monkeypatch, {}, error="rate-limited: Too Many Requests")
    _bypass_cache(monkeypatch)

    result = earnings.validate_symbol("AAPL")
    assert result["valid"] is False
    assert "unavailable" in result["reason"]
    assert "rate-limit" in result["reason"]


# ---------------------------------------------------------------------------
# Input validation (no network involved)
# ---------------------------------------------------------------------------

def test_validate_symbol_empty_string():
    """Empty/whitespace input → valid:False, reason='empty symbol'."""
    assert earnings.validate_symbol("")["valid"] is False
    assert earnings.validate_symbol("")["reason"] == "empty symbol"
    assert earnings.validate_symbol("   ")["valid"] is False
    assert earnings.validate_symbol("   ")["reason"] == "empty symbol"
    assert earnings.validate_symbol(None)["valid"] is False
    assert earnings.validate_symbol(None)["reason"] == "empty symbol"


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


def test_validate_symbol_lowercase_normalised(monkeypatch):
    """Lowercase input is uppercased before lookup."""
    _stub_history(monkeypatch, [{"date": "2026-09-06", "close": 220.0}])
    _stub_info(monkeypatch, {"longName": "Apple Inc."})
    _bypass_cache(monkeypatch)

    result = earnings.validate_symbol("aapl")
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

    earnings._validate_cached.cache_clear()
    monkeypatch.setattr(earnings, "_validate_uncached", _fake_validate_uncached)
    monkeypatch.setattr(earnings, "_cache_bucket", lambda: 42)  # fixed bucket

    earnings.validate_symbol("AAPL")
    earnings.validate_symbol("AAPL")
    earnings.validate_symbol("AAPL")

    assert call_count == 1, f"Expected 1 yfinance call, got {call_count}"


def test_validate_symbol_cache_miss_across_buckets(monkeypatch):
    """Different cache buckets → underlying call made again."""
    call_count = 0

    def _fake_validate_uncached(sym):
        nonlocal call_count
        call_count += 1
        return {"valid": True, "symbol": sym, "name": "Test Co", "sector": None}

    earnings._validate_cached.cache_clear()
    monkeypatch.setattr(earnings, "_validate_uncached", _fake_validate_uncached)

    monkeypatch.setattr(earnings, "_cache_bucket", lambda: 42)
    earnings.validate_symbol("AAPL")
    monkeypatch.setattr(earnings, "_cache_bucket", lambda: 43)
    earnings.validate_symbol("AAPL")

    assert call_count == 2, f"Expected 2 yfinance calls, got {call_count}"


# ---------------------------------------------------------------------------
# User-facing path: add_ticker (earnings watchlist add)
# ---------------------------------------------------------------------------

def test_add_ticker_cache_miss_does_not_trigger_full_rebuild(monkeypatch):
    """When _cached_calendar() returns None (cache expired/missing),
    add_ticker must NOT call earnings_calendar() (which would trigger a
    30-60s full universe rebuild). It should instead build just the new
    ticker and return a minimal payload."""
    monkeypatch.setattr(earnings, "_validate_cached",
                        lambda s, b: {"valid": True, "symbol": s, "name": s, "sector": None})
    monkeypatch.setattr(earnings, "_cached_calendar", lambda: None)

    calendar_called = []
    original_earnings_calendar = earnings.earnings_calendar

    def tracking_earnings_calendar():
        calendar_called.append(True)
        return original_earnings_calendar()
    monkeypatch.setattr(earnings, "earnings_calendar", tracking_earnings_calendar)

    monkeypatch.setattr(earnings, "_enrich",
                        lambda sym, quotes: {"symbol": sym, "next_earnings": "2026-10-01", "price": 100.0})
    monkeypatch.setattr("app.market._quote_snapshot", lambda syms: {})
    monkeypatch.setattr(earnings, "load_watchlist", lambda: ["existing"])
    monkeypatch.setattr(earnings, "save_watchlist", lambda t: None)
    monkeypatch.setattr(earnings, "load_removed", lambda: [])
    monkeypatch.setattr(earnings, "save_removed", lambda t: None)
    monkeypatch.setattr(earnings.store, "save_json", lambda p, d: None)

    result = earnings.add_ticker("AAPL")

    assert not calendar_called, "earnings_calendar() should not be called on cache miss"
    assert "companies" in result
    symbols = {r["symbol"] for r in result.get("companies") or []}
    assert "AAPL" in symbols


def test_add_ticker_rate_limit_returns_friendly_error(monkeypatch):
    """User-facing add_ticker under the rate-limit scenario:
    Ticker.info empty + history empty → returns 'yfinance unavailable'
    message rather than the misleading 'invalid symbol'.
    """
    _stub_history(monkeypatch, [])
    _stub_info(monkeypatch, {}, error="network: ConnectionError: timed out")
    _bypass_cache(monkeypatch)

    monkeypatch.setattr(earnings, "load_watchlist", lambda: [])
    monkeypatch.setattr(earnings, "save_watchlist", lambda t: None)
    monkeypatch.setattr(earnings, "load_removed", lambda: [])
    monkeypatch.setattr(earnings, "save_removed", lambda t: None)

    result = earnings.add_ticker("NVDA")
    assert result["added"] is False
    # 'yfinance unavailable' wording is what tells the user it's a
    # transient/network issue rather than a typo'd ticker.
    assert "yfinance unavailable" in result["error"]
    assert result["symbol"] == "NVDA"


# ---------------------------------------------------------------------------
# User-facing path: portfolio.add_holding (the "adding to portfolio works"
# surface that motivated the fix)
# ---------------------------------------------------------------------------

def test_add_holding_validates_via_primary_history_path(monkeypatch):
    """portfolio.add_holding uses earnings.validate_symbol — when the
    Ticker.info surface is rate-limited but yf.download still works
    (the same scenario the user observed in the earnings add path),
    adding NVDA to a portfolio now succeeds instead of raising
    'invalid symbol'.
    """
    from app import portfolio
    _stub_history(monkeypatch, [{"date": "2026-09-06", "close": 130.8}])
    _stub_info(monkeypatch, {})  # Ticker.info rate-limited
    _bypass_cache(monkeypatch)

    # Make sure no stale data/cache gets in the way.
    pid = "diag-add-holding-pf"
    state = portfolio.load_portfolios()
    state["portfolios"][pid] = {"id": pid, "name": "Diag", "holdings": []}
    portfolio.save_portfolios(state)

    holding = portfolio.add_holding(pid, "NVDA", 1.0, 130.0)
    assert holding["symbol"] == "NVDA"
    assert holding["shares"] == 1.0
    assert holding["total_cost"] == 130.0


# ---------------------------------------------------------------------------
# Structural regression tests — verify the call order, not just the verdict
# ---------------------------------------------------------------------------

def test_validate_symbol_calls_history_before_ticker_info(monkeypatch):
    """STRUCTURAL regression for the ROADMAP Phase 2 'invalid symbol'
    fix.  Pre-fix (commit ``a2c793a``) ordering was
    PRIMARY=Ticker.info → FALLBACK=history.  Post-fix ordering is
    PRIMARY=history → SECONDARY=Ticker.info (enrichment only).  This
    test pins the call order so a future revert (someone re-introducing
    the old ordering as a "more natural" primary-first approach) fails
    the test instead of silently re-arming the bug.
    """
    call_log: list[str] = []

    def _tracking_history(sym, days=5):
        call_log.append("history")
        return [{"date": "2026-09-06", "close": 130.8}]

    def _tracking_info(sym):
        call_log.append("info")
        return ({"longName": "NVIDIA Corporation", "sector": "Technology"}, None)

    monkeypatch.setattr(earnings.market, "get_history", _tracking_history)
    monkeypatch.setattr(earnings, "_yf_info", _tracking_info)
    _bypass_cache(monkeypatch)

    result = earnings.validate_symbol("NVDA")
    assert result["valid"] is True
    # History MUST be called first.  Pre-fix code would have produced
    # call_log == ["info", "history"] (Ticker.info primary, history fallback).
    assert call_log == ["history", "info"], (
        f"Expected history first then info (primary=history), got {call_log}"
    )


def test_validate_symbol_history_primary_short_circuits(monkeypatch):
    """When the PRIMARY history check succeeds, Ticker.info is called
    at most once (for enrichment) and only on the success path.  Pre-fix
    code called Ticker.info FIRST (and retried it on rate-limit error,
    adding 1s of latency before the history fallback).  Post-fix code
    skips the retry entirely.
    """
    call_log: list[str] = []

    def _tracking_history(sym, days=5):
        call_log.append("history")
        return [{"date": "2026-09-06", "close": 130.8}]

    def _tracking_info(sym):
        call_log.append("info")
        # Simulate Ticker.info rate-limited (empty dict, no exception).
        return ({}, None)

    monkeypatch.setattr(earnings.market, "get_history", _tracking_history)
    monkeypatch.setattr(earnings, "_yf_info", _tracking_info)
    _bypass_cache(monkeypatch)

    result = earnings.validate_symbol("NVDA")
    assert result["valid"] is True
    # history called once (primary), info called once (enrichment).
    # Pre-fix code would have called info twice (initial + retry) then
    # history once (fallback), with 1s sleep between the info retries.
    assert call_log.count("history") == 1
    assert call_log.count("info") == 1


def test_validate_symbol_does_not_use_retry_helper(monkeypatch):
    """The pre-fix ``_yf_info_with_retry`` helper applied retry-with-
    1s-backoff around ``_yf_info``.  That helper masked the rate-limit
    bug (delayed the verdict by 1s instead of fixing it).  This test
    pins that the helper is GONE so a future re-introduction fails
    fast instead of re-arming the masking.
    """
    assert not hasattr(earnings, "_yf_info_with_retry"), (
        "_yf_info_with_retry was removed in the Phase 2 fix — retrying a "
        "fundamentally flaky call was masking the bug, not fixing it. "
        "If you need to re-add it, see docs/DECISIONS.md 'Phase 2 audit "
        "— earnings validate_symbol path diff' for the rationale."
    )


def test_validate_symbol_no_sleep_in_retry_path(monkeypatch):
    """The pre-fix code called ``time.sleep(1.0)`` between Ticker.info
    retries.  Post-fix code has no retry path at all, so no sleep.
    Pin ``time.sleep`` to a tracker and assert it's never called with
    a positive delay during validation.
    """
    import time as _time
    sleeps: list[float] = []
    monkeypatch.setattr(_time, "sleep", lambda s: sleeps.append(s))

    _stub_history(monkeypatch, [{"date": "2026-09-06", "close": 130.8}])
    _stub_info(monkeypatch, {}, error="rate-limited: Too Many Requests")
    _bypass_cache(monkeypatch)

    earnings.validate_symbol("NVDA")

    # No retry path → no sleep.  Pre-fix code would have slept 1.0s
    # between the two Ticker.info attempts.
    assert not any(s >= 0.5 for s in sleeps), (
        f"Found retry-style sleep in validate_symbol: {sleeps}"
    )
