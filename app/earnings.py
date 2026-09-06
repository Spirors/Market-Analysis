"""Earnings calendar for the tracked mega-cap universe (macro concentration lens).

Supports a user-maintained wishlist persisted to data/watchlist.json, merged
with the default EARNINGS_UNIVERSE. Users may remove any ticker, including
defaults; removed defaults are tracked so they do not reappear.
"""

import functools
import logging
import re
import time
from datetime import datetime
from typing import Any

from . import config, market, store

logger = logging.getLogger(__name__)

# Valid ticker pattern: 1-10 uppercase alphanumeric chars (with optional dot/dash/caret/equals for things like BRK.B, BTC-USD, ^GSPC, GC=F).
_TICKER_RE = re.compile(r"^[A-Z0-9.^=-]{1,10}$")

WATCHLIST_PATH = config.DATA_DIR / "watchlist.json"
REMOVED_PATH = config.DATA_DIR / "earnings_removed.json"
EARNINGS_CACHE_PATH = config.CACHE_DIR / "earnings.json"


def _load_json(path: Any, default: Any) -> Any:
    data = store.load_json(path, default=default)
    return data if isinstance(data, dict) else default


def load_watchlist() -> list[str]:
    data = _load_json(WATCHLIST_PATH, {"tickers": []})
    tickers = data.get("tickers", [])
    return [str(s).upper() for s in tickers if s]


def save_watchlist(tickers: list[str]) -> None:
    store.save_json(WATCHLIST_PATH, {"tickers": tickers})


def load_removed() -> list[str]:
    data = _load_json(REMOVED_PATH, {"tickers": []})
    tickers = data.get("tickers", [])
    return [str(s).upper() for s in tickers if s]


def save_removed(tickers: list[str]) -> None:
    store.save_json(REMOVED_PATH, {"tickers": tickers})


def _invalidate_cache() -> None:
    EARNINGS_CACHE_PATH.unlink(missing_ok=True)


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


def _yf_info_with_retry(sym: str, retries: int = 1, backoff: float = 1.0) -> tuple[dict[str, Any], str | None]:
    """Like _yf_info but retries once on network/rate-limit errors."""
    info, err = _yf_info(sym)
    if err and retries > 0:
        logger.info("validate_symbol: first attempt for %s failed (%s), retrying after %.1fs", sym, err, backoff)
        time.sleep(backoff)
        info, err = _yf_info(sym)
    return info, err


def _validate_by_history(sym: str) -> dict[str, Any] | None:
    """Fallback validation via yfinance history quote."""
    hist = market.get_history(sym, days=5)
    if hist:
        return {"symbol": sym, "name": sym, "sector": None}
    return None


# Fields that, if present in the yfinance info dict, confirm the symbol is
# real even when longName/shortName are missing (some tickers have sparse
# info dicts).
_CONFIRMATION_FIELDS = {"symbol", "exchange", "currency", "quoteType", "regularMarketPrice"}


def _validate_uncached(sym: str) -> dict[str, Any]:
    """Core validation logic without caching."""
    # 1. Primary lookup via yfinance Ticker.info (with one retry on failure)
    info, err = _yf_info_with_retry(sym)
    name = info.get("longName") or info.get("shortName")
    sector = info.get("sector")
    if name:
        return {"valid": True, "symbol": sym, "name": str(name), "sector": sector}
    # Even without a name, any confirmation field means Yahoo recognises it.
    if info and _CONFIRMATION_FIELDS & info.keys():
        return {"valid": True, "symbol": sym, "name": sym, "sector": sector}

    # 2. Fallback: price-history check (one more network call).
    fallback = _validate_by_history(sym)
    if fallback:
        return {"valid": True, "symbol": sym, "name": sym, "sector": None}

    # 3. Both lookups returned empty.  Distinguish network failure from
    #    genuine "symbol not found" so the caller can show a helpful message.
    if err:
        reason = (
            f"yfinance unavailable ({err}); try again in a minute"
        )
    else:
        reason = f"no yfinance profile and no price history found for {sym}"
    return {"valid": False, "symbol": sym, "name": None, "sector": None, "reason": reason}


# ---- Validation cache (60 s TTL, keyed on upper-cased symbol + time bucket) --

def _cache_bucket() -> int:
    """Current 60-second bucket index (used as cache-busting parameter)."""
    return int(time.time() // 60)


@functools.lru_cache(maxsize=128)
def _validate_cached(sym_upper: str, ts_bucket: int) -> dict[str, Any]:
    return _validate_uncached(sym_upper)


def validate_symbol(sym: str) -> dict[str, Any]:
    """Return {valid, symbol, name, sector[, reason]} for a candidate ticker.

    Failed lookups carry a human-readable ``reason`` so callers (API 400s,
    add_ticker) can explain the rejection.

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


def _ticker_calendar(sym: str) -> dict[str, Any]:
    import yfinance as yf

    try:
        t = yf.Ticker(sym)
        cal = t.calendar if hasattr(t, "calendar") else None
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if isinstance(ed, (list, tuple)) and ed:
                ed = ed[0]
            if isinstance(ed, datetime):
                return {"symbol": sym, "next_earnings": ed.date().isoformat()}
            if isinstance(ed, str):
                return {"symbol": sym, "next_earnings": ed[:10]}
        edates = t.get_earnings_dates(limit=1)
        if edates is not None and not edates.empty:
            return {"symbol": sym, "last_earnings": edates.index[0].strftime("%Y-%m-%d")}
    except Exception:
        pass
    return {"symbol": sym, "next_earnings": None}


def _pct_change(series: list[dict[str, Any]], days_back: int) -> float | None:
    if len(series) < days_back + 1:
        return None
    cur = series[-1].get("close")
    prev = series[-(days_back + 1)].get("close")
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur / prev - 1) * 100, 3)


def _52w_high(series: list[dict[str, Any]]) -> float | None:
    highs = [r.get("close") for r in series if r.get("close") is not None]
    if not highs:
        return None
    return round(max(highs), 4)


def _fmt_billions(v: Any) -> str | None:
    if v is None:
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    if n >= 1_000_000_000_000:
        return f"{n / 1_000_000_000_000:.2f}T"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    return f"{n:.0f}"


def _ai_rec(row: dict[str, Any]) -> dict[str, Any]:
    """Local heuristic 'AI-style' recommendation for the earnings setup."""
    pe = row.get("forward_pe")
    dist_52w = row.get("dist_52w_high_pct")
    mom7 = row.get("pct_7d")

    reasons: list[str] = []
    if pe is not None and pe > 0:
        if pe < 30:
            reasons.append("reasonable valuation")
        elif pe > 50:
            reasons.append("expensive valuation")
    if mom7 is not None:
        if mom7 >= 0:
            reasons.append("positive 7d momentum")
        elif mom7 < -8:
            reasons.append("negative 7d momentum")
    if dist_52w is not None:
        if dist_52w >= -15:
            reasons.append("near 52W high")
        elif dist_52w < -25:
            reasons.append("far below 52W high")

    # Green = reasonable valuation + not breaking down + reasonably near highs.
    if pe is not None and pe < 35 and mom7 is not None and mom7 >= -3 and dist_52w is not None and dist_52w >= -20:
        return {"signal": "Bullish", "color": "#3B6D11", "reason": "; ".join(reasons) or "setup looks constructive"}
    # Red = expensive OR breaking down OR far below highs.
    if (pe is not None and pe > 50) or (mom7 is not None and mom7 < -8) or (dist_52w is not None and dist_52w < -25):
        return {"signal": "Cautious", "color": "#A32D2D", "reason": "; ".join(reasons) or "setup looks fragile"}
    return {"signal": "Neutral", "color": "#B9860B", "reason": "; ".join(reasons) or "mixed signals"}


def _enrich(sym: str, quotes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build a fully enriched earnings row for one symbol."""
    row = _ticker_calendar(sym)

    # Price + daily change from pre-fetched quotes (no shared cache pollution).
    q = quotes.get(sym) or {}
    row["price"] = q.get("price")
    row["pct_daily"] = q.get("pct_change")

    # 7-day change + 52-week high from ~1 year history.
    hist = market.get_history(sym, days=260)
    row["pct_7d"] = _pct_change(hist, 7)
    row["high_52w"] = _52w_high(hist)
    if row["price"] is not None and row["high_52w"]:
        row["dist_52w_high_pct"] = round((row["price"] / row["high_52w"] - 1) * 100, 2)
    else:
        row["dist_52w_high_pct"] = None

    # Fundamentals from yfinance info.
    info, _err = _yf_info(sym)
    row["name"] = info.get("longName") or info.get("shortName") or sym
    row["sector"] = info.get("sector") or None
    row["market_cap"] = info.get("marketCap")
    row["market_cap_fmt"] = _fmt_billions(info.get("marketCap"))
    row["forward_pe"] = _to_float(info.get("forwardPE"))
    row["forward_peg"] = _to_float(info.get("pegRatio"))

    # Keep data provenance timestamp.
    row["as_of"] = datetime.now().isoformat()

    # Local AI-style recommendation.
    rec = _ai_rec(row)
    row["rec_signal"] = rec["signal"]
    row["rec_color"] = rec["color"]
    row["rec_reason"] = rec["reason"]

    return row


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return None if f != f else round(f, 3)  # filter NaN
    except (TypeError, ValueError):
        return None


def add_ticker(sym: str) -> dict[str, Any]:
    sym = (sym or "").strip().upper()
    if not sym:
        return {"symbol": None}

    # Enforce the same validation as the API path before persisting: an
    # unvalidated symbol must never reach the watchlist (it flows into
    # market.py cache filenames).
    validation = validate_symbol(sym)
    if not validation.get("valid"):
        return {
            "symbol": sym,
            "added": False,
            "error": validation.get("reason") or "invalid symbol",
        }

    tickers = load_watchlist()
    removed = load_removed()

    if sym in removed:
        removed.remove(sym)
        save_removed(removed)
    if sym not in tickers:
        tickers.append(sym)
        save_watchlist(tickers)

    # Fast path: patch the existing cache instead of rebuilding everything.
    cached = _cached_calendar()
    if cached:
        companies = cached.get("companies", [])
        symbols = {r["symbol"] for r in companies}
        if sym not in symbols:
            quotes = market._quote_snapshot([sym])
            companies.append(_enrich(sym, quotes))
        cached["companies"] = sorted(companies, key=lambda r: r.get("next_earnings") or r.get("last_earnings") or "")
        cached["watchlist"] = tickers
        cached["as_of"] = datetime.now().isoformat()
        store.save_json(EARNINGS_CACHE_PATH, {"cached_at": time.time(), "payload": cached})
        return cached

    _invalidate_cache()
    return earnings_calendar()


def remove_ticker(sym: str) -> dict[str, Any]:
    sym = (sym or "").strip().upper()
    tickers = [s for s in load_watchlist() if s != sym]
    save_watchlist(tickers)

    if sym in config.EARNINGS_UNIVERSE and sym not in tickers:
        removed = load_removed()
        if sym not in removed:
            removed.append(sym)
            save_removed(removed)

    # Fast path: patch the existing cache instead of rebuilding everything.
    cached = _cached_calendar()
    if cached:
        companies = [r for r in cached.get("companies", []) if r["symbol"] != sym]
        cached["companies"] = companies
        cached["watchlist"] = tickers
        cached["as_of"] = datetime.now().isoformat()
        store.save_json(EARNINGS_CACHE_PATH, {"cached_at": time.time(), "payload": cached})
        return cached

    _invalidate_cache()
    return earnings_calendar()


def lookup_ticker(sym: str) -> dict[str, Any]:
    return validate_symbol(sym)


def _universe() -> list[str]:
    """Default universe minus user-removed defaults, plus user watchlist."""
    seen: set[str] = set()
    out: list[str] = []
    removed = set(load_removed())
    for s in list(config.EARNINGS_UNIVERSE) + load_watchlist():
        if s and s not in seen and s not in removed:
            seen.add(s)
            out.append(s)
    return out


def _cached_calendar() -> dict[str, Any] | None:
    data = store.load_json(EARNINGS_CACHE_PATH)
    if not data:
        return None
    ts = data.get("cached_at", 0)
    if time.time() - ts < config.EARNINGS_TTL:
        payload = data.get("payload")
        # A cache full of null prices was almost certainly built during a
        # yfinance outage — serving it for 30 minutes would render the
        # earnings section as 12 rows of "—" until the TTL expires, even
        # after yfinance recovers. Treat it as corrupt and rebuild.
        if _has_usable_prices(payload):
            return payload
    return None


def cached_payload() -> dict[str, Any] | None:
    """Return the on-disk earnings-cache payload regardless of TTL.

    Unlike ``_cached_calendar()`` which enforces ``EARNINGS_TTL`` and would
    cause ``earnings_calendar()`` to fall through to a full yfinance rebuild
    when stale, this returns whatever is on disk (or None if missing/corrupt).
    Used by dashboard-load paths that MUST stay fast even when the cache is
    past its TTL — the earnings section owns its own refresh lifecycle via
    the user-initiated Refresh button + scheduled task.
    """
    cache = store.load_json(EARNINGS_CACHE_PATH, default=None)
    if not isinstance(cache, dict):
        return None
    payload = cache.get("payload")
    if not _has_usable_prices(payload):
        # Same all-null guard as _cached_calendar: never serve a cache full
        # of null prices — callers (service._enrich) rebuild via
        # earnings_calendar() when this returns None.
        return None
    return payload if isinstance(payload, dict) else None


def _has_usable_prices(payload: Any) -> bool:
    """True if the cached payload has at least one row with a live price.

    The earnings cache can end up full of null prices when yfinance fails
    partway through enrichment (rate limit, transient outage). Detecting
    that state lets callers treat the cache as corrupt and rebuild instead
    of serving a half-dead payload for the rest of the TTL window.
    """
    if not isinstance(payload, dict):
        return False
    companies = payload.get("companies")
    if not isinstance(companies, list) or not companies:
        return False
    return any(
        isinstance(row, dict) and row.get("price") is not None
        for row in companies
    )


def earnings_calendar() -> dict[str, Any]:
    """Return enriched earnings rows for the tracked universe, cached."""
    cached = _cached_calendar()
    if cached:
        return cached

    universe = _universe()
    quotes = market._quote_snapshot(universe)
    rows = [_enrich(s, quotes) for s in universe]
    out = {
        "as_of": datetime.now().isoformat(),
        "companies": rows,
        "watchlist": load_watchlist(),
    }
    # Only persist when the rebuild actually produced live prices. Saving an
    # all-null result would re-arm the cache-corruption cycle: next call
    # would happily serve 30 minutes of "—" until yfinance comes back.
    if _has_usable_prices(out):
        store.save_json(EARNINGS_CACHE_PATH, {"cached_at": time.time(), "payload": out})
    return out


def earnings_force_refresh() -> dict[str, Any]:
    EARNINGS_CACHE_PATH.unlink(missing_ok=True)
    return earnings_calendar()
