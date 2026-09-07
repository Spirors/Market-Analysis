"""Symbol validation: check whether a candidate ticker exists on Yahoo.

Used by ``app.portfolio.add_holding`` to reject invalid/garbage symbols
before they reach the watchlist / cache filenames.

PRIMARY existence check is the bulk-download surface
(``market.get_history`` → ``yf.download``) — the same yfinance surface
that ``portfolio.enrich_portfolios`` uses successfully for NVDA / AAPL /
etc. The per-symbol ``Ticker.info`` endpoint is the rate-limited one;
using it as the SECONDARY fallback (not the primary gate) keeps the
false-positive "invalid symbol" verdicts from firing during Yahoo
rate-limit incidents. See ``docs/DECISIONS.md`` "Phase 2 audit —
earnings validate_symbol path diff" for the full reproduction matrix.

This module was extracted from ``app.earnings`` after the Earnings
watchlist section was removed; validate_symbol is still needed by
``portfolio.add_holding`` to validate user-entered tickers.
"""

from __future__ import annotations

import functools
import re
import time
from typing import Any

from . import market

# Valid ticker pattern: 1-10 uppercase alphanumeric chars (with optional
# dot/dash/caret/equals for things like BRK.B, BTC-USD, ^GSPC, GC=F).
_TICKER_RE = re.compile(r"^[A-Z0-9.^=-]{1,10}$")

# Fields that, if present in the yfinance info dict, confirm the symbol is
# real even when longName/shortName are missing (some tickers have sparse
# info dicts).
_CONFIRMATION_FIELDS = {"symbol", "exchange", "currency", "quoteType", "regularMarketPrice"}


def _yf_info(sym: str) -> tuple[dict[str, Any], str | None]:
    """Fetch ticker info via yfinance; return (info_dict, error_string).

    Returns (info, None) on success, or ({}, error_message) on failure.
    The error_message is human-readable and distinguishes network failures
    from "symbol genuinely not found" when possible.
    """
    import yfinance as yf

    try:
        t = yf.Ticker(sym)
        info = t.info if hasattr(t, "info") and t.info else {}
        return (info if isinstance(info, dict) else {}, None)
    except Exception as exc:
        exc_name = type(exc).__name__
        # Network-class exceptions: requests.ConnectionError, requests.Timeout,
        # yfinance exceptions wrapping them, etc.
        if any(k in exc_name.lower() for k in ("connection", "timeout", "request", "http", "ssl")):
            return ({}, f"network: {exc_name}: {exc}")
        # Rate-limit often surfaces as HTTP 429 or TooManyRequests
        msg = str(exc).lower()
        if "429" in msg or "too many" in msg or "rate" in msg:
            return ({}, f"rate-limited: {exc}")
        return ({}, f"yfinance: {exc_name}: {exc}")


def _validate_uncached(sym: str) -> dict[str, Any]:
    """Core validation logic without caching.

    See module docstring for the path-diff rationale.
    """
    # 1. PRIMARY: bulk-download existence check (same surface as the
    #    portfolio display/enrich path — reliable in yfinance 1.6.0,
    #    documented at app/market.py:97-98).
    hist = market.get_history(sym, days=5)
    if hist:
        # Best-effort enrichment via Ticker.info.  Failure here is OK —
        # we already confirmed the symbol exists via the primary path.
        name = sym
        sector: Any = None
        try:
            info, _ = _yf_info(sym)
            if info:
                name = info.get("longName") or info.get("shortName") or sym
                sector = info.get("sector")
        except Exception:
            # Enrichment failure is non-fatal; primary already confirmed.
            pass
        return {"valid": True, "symbol": sym, "name": str(name), "sector": sector}

    # 2. SECONDARY: Ticker.info (rate-limited).  Some symbols have sparse
    #    price history but still confirmable via the info dict.
    info, err = _yf_info(sym)
    if info:
        name = info.get("longName") or info.get("shortName")
        if name:
            return {"valid": True, "symbol": sym, "name": str(name),
                    "sector": info.get("sector")}
        # Even without a name, any confirmation field means Yahoo
        # recognises it (some tickers have sparse info dicts).
        if _CONFIRMATION_FIELDS & info.keys():
            return {"valid": True, "symbol": sym, "name": sym,
                    "sector": info.get("sector")}

    # 3. Both surfaces empty/failed.  Distinguish network failure from
    #    genuine "symbol not found" so the caller can show a helpful
    #    message instead of the flat "invalid symbol".
    if err:
        reason = f"yfinance unavailable ({err}) for {sym}; try again in a minute"
    else:
        reason = f"no price history and no yfinance profile for {sym}"
    return {"valid": False, "symbol": sym, "name": None, "sector": None,
            "reason": reason}


def _cache_bucket() -> int:
    """Current 60-second bucket index (used as cache-busting parameter)."""
    return int(time.time() // 60)


@functools.lru_cache(maxsize=128)
def _validate_cached(sym_upper: str, ts_bucket: int) -> dict[str, Any]:
    return _validate_uncached(sym_upper)


def validate_symbol(sym: str) -> dict[str, Any]:
    """Return {valid, symbol, name, sector[, reason]} for a candidate ticker.

    Failed lookups carry a human-readable ``reason`` so callers (API 400s,
    add_holding) can explain the rejection.

    Results are cached for ~60 s per symbol to avoid hammering yfinance when
    the user adds several tickers in quick succession.
    """
    sym = (sym or "").strip().upper()
    if not sym:
        return {"valid": False, "symbol": sym, "name": None, "sector": None,
                "reason": "empty symbol"}

    # Reject obvious garbage before hitting the network.
    if not _TICKER_RE.match(sym):
        return {"valid": False, "symbol": sym, "name": None, "sector": None,
                "reason": f"invalid ticker format for {sym}"}

    return _validate_cached(sym, _cache_bucket())
