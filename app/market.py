"""Market data acquisition from free sources (yfinance; no secondary source).

Defines :class:`MarketDataAdapter` — a structural Protocol describing the
public surface consumed by callers (``service.py``, ``portfolio.py``,
``validation.py``). Today's yfinance implementation satisfies the protocol;
future paid sources can plug in by implementing the same shape without
touching call sites.

# Changelog:
# 2026-08-30 — market: Added MarketDataAdapter Protocol.  Behavior: none
#              (pure refactor).
"""

import hashlib
import logging
import re
import time
from datetime import date, datetime, timezone
from typing import Any, Optional

from typing import Protocol, runtime_checkable

import pandas as pd

from . import config, store


@runtime_checkable
class MarketDataAdapter(Protocol):
    """Structural Protocol for market-data providers.

    The yfinance implementation in this module satisfies it.  Future paid
    sources implement the same shape; call sites (``service.py``,
    ``portfolio.py``, ``validation.py``) never change.
    """

    def get_quotes(
        self, symbols: list[str], ttl: int = ...,
    ) -> dict[str, dict[str, Any]]: ...

    def get_history(
        self, symbol: str, days: int = ..., ttl: int = ...,
    ) -> list[dict[str, Any]]: ...

    def get_histories_bulk(
        self, symbols: list[str], days: int = ..., ttl: int = ...,
    ) -> dict[str, list[dict[str, Any]]]: ...

logger = logging.getLogger(__name__)

_yf = None

# Characters allowed in symbols that reach cache filenames (covers ^GSPC,
# BRK.B, BTC-USD, GC=F). Everything else is stripped so paths like ".."
# or "A/B" can never escape CACHE_DIR.
_SAFE_KEY_RE = re.compile(r"[^A-Z0-9.^=-]")


def _safe_key(symbol: str) -> str:
    """Sanitize a user-supplied symbol for use in a cache filename."""
    return _SAFE_KEY_RE.sub("", (symbol or "").upper())


def _get_yf():
    global _yf
    if _yf is None:
        import yfinance as yf
        _yf = yf
    return _yf


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_path(key: str) -> Any:
    return config.CACHE_DIR / f"{key}.json"


def _fresh(key: str, ttl: int) -> Optional[Any]:
    p = _cache_path(key)
    data = store.load_json(p)
    if not data:
        return None
    ts = data.get("cached_at", 0)
    if time.time() - ts < ttl:
        return data.get("payload")
    return None


def _put(key: str, payload: Any) -> None:
    store.save_json(_cache_path(key), {"cached_at": time.time(), "payload": payload})


def _close_series(close: Any, sym: str, symbols: list[str]) -> Optional[Any]:
    """Extract one symbol's Close series from a yfinance Close frame/Series."""
    if isinstance(close, pd.Series):
        # Single-symbol request with group_by="column" can still yield a
        # bare Series; it belongs to the one requested symbol.
        if len(symbols) != 1:
            return None
        return close
    if sym not in close.columns:
        return None
    return close[sym]


def _intraday_last(symbols: list[str]) -> dict[str, tuple[float, date]]:
    """Latest live 5m print + its session date, per symbol, in one download.

    5m/5d (not 1m/1d) is the only window verified to return bars for every
    asset class — including futures, whose 1d/1m requests come back empty.
    Failures degrade to an empty dict (never raise).
    """
    out: dict[str, tuple[float, Any]] = {}
    yf = _get_yf()
    try:
        df = yf.download(
            symbols, period="5d", interval="5m", prepost=False,
            auto_adjust=True, progress=False, group_by="column",
        )
        if df is None or df.empty or "Close" not in df.columns:
            return out
        close = df["Close"]
        for sym in symbols:
            try:
                s = _close_series(close, sym, symbols)
                if s is None:
                    continue
                s = s.dropna()
                if s.empty:
                    continue
                ts = s.index[-1]
                sess_date = ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()
                out[sym] = (float(s.iloc[-1]), sess_date)
            except Exception as e:
                logger.warning("intraday slice failed for %s: %s: %s",
                               sym, type(e).__name__, e)
    except Exception as e:
        logger.warning("intraday fetch failed for %s: %s: %s",
                       symbols, type(e).__name__, e)
    return out


def _daily_closes(symbols: list[str]) -> dict[str, list[tuple[Any, float]]]:
    """Ascending daily (date, close) pairs per symbol, in one download.

    Failures degrade to an empty dict (never raise).
    """
    out: dict[str, list[tuple[Any, float]]] = {}
    yf = _get_yf()
    try:
        df = yf.download(
            symbols, period="10d", interval="1d",
            auto_adjust=True, progress=False, group_by="column",
        )
        if df is None or df.empty or "Close" not in df.columns:
            return out
        close = df["Close"]
        for sym in symbols:
            try:
                s = _close_series(close, sym, symbols)
                if s is None:
                    continue
                s = s.dropna()
                rows: list[tuple[Any, float]] = []
                for idx, val in s.items():
                    d = idx.date() if hasattr(idx, "date") else pd.Timestamp(idx).date()
                    rows.append((d, float(val)))
                rows.sort(key=lambda r: r[0])
                if rows:
                    out[sym] = rows
            except Exception as e:
                logger.warning("daily slice failed for %s: %s: %s",
                               sym, type(e).__name__, e)
    except Exception as e:
        logger.warning("daily fetch failed for %s: %s: %s",
                       symbols, type(e).__name__, e)
    return out


def _fast_info_quote(sym: str) -> tuple[Optional[float], Optional[float]]:
    """(last_price, previous_close) from fast_info; (None, None) on failure.

    Used only as a fallback for symbols with no usable intraday print; note
    fast_info's previous_close is not the settled prior daily close, so it is
    never preferred over a date-anchored daily close.
    """
    try:
        fi = _get_yf().Ticker(sym).fast_info
        last = fi["last_price"]
        prev = fi["previous_close"]
        return (
            float(last) if last is not None else None,
            float(prev) if prev is not None else None,
        )
    except Exception as e:
        logger.warning("fast_info failed for %s: %s: %s", sym, type(e).__name__, e)
        return (None, None)


def _quote_snapshot(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Latest live intraday price + daily change for a list of symbols.

    Correctness comes from date-anchoring: the daily prior close is the most
    recent settled close *strictly before* the session date of the intraday
    print. This holds live, after close, on weekends and for 24/7 crypto.
    If a settled daily bar is newer than the intraday print, the print is
    stale and is discarded in favour of the daily last/prior. Falls back to
    fast_info (no intraday print) and then the latest daily close.
    Unavailable symbols are simply absent; never raises.

    Uses `fast_info` only as a fallback — the comment that it "returns None
    in current versions" is outdated for yfinance 1.6.0 — because its
    previous_close disagrees with the settled daily prior close.
    """
    out: dict[str, dict[str, Any]] = {}
    try:
        intra = _intraday_last(symbols)
        daily = _daily_closes(symbols)
        for sym in symbols:
            try:
                price: Optional[float] = None
                prior: Optional[float] = None
                ip = intra.get(sym)
                if ip is not None:
                    price, sess_date = ip
                    closes = daily.get(sym) or []
                    if closes and closes[-1][0] > sess_date:
                        # Stale-intraday guard: a settled daily bar is newer
                        # than this intraday print. Discard the older tick and
                        # serve the daily last/prior rather than a price the
                        # market has already moved past.
                        price = closes[-1][1]
                        prior = closes[-2][1] if len(closes) >= 2 else None
                    else:
                        priors = [c for (d, c) in closes if d < sess_date]
                        if priors:
                            prior = priors[-1]
                        else:
                            price = None  # no anchor -> fall through to fallback
                if price is None:
                    last, prev = _fast_info_quote(sym)
                    if last is not None:
                        price, prior = last, prev
                    else:
                        closes = daily.get(sym) or []
                        if not closes:
                            continue
                        price = closes[-1][1]
                        prior = closes[-2][1] if len(closes) >= 2 else None
                chg = (price - prior) if (price is not None and prior is not None) else None
                pct = (chg / prior * 100) if (chg is not None and prior not in (None, 0)) else None
                out[sym] = {
                    "price": round(price, 4) if price is not None else None,
                    "change": round(chg, 4) if chg is not None else None,
                    "pct_change": round(pct, 3) if pct is not None else None,
                }
            except Exception as e:
                logger.warning("quote build failed for %s: %s: %s",
                               sym, type(e).__name__, e)
    except Exception as e:
        logger.warning("quote snapshot failed for %s: %s: %s",
                       symbols, type(e).__name__, e)
    return out


def get_quotes(symbols: list[str], ttl: int = config.LIVE_QUOTE_TTL) -> dict[str, dict[str, Any]]:
    """Cached-or-fresh live quotes from yfinance (no secondary source).

    One cache entry per symbol (``quote_<sym>``), so callers asking for
    different symbol sets share overlap instead of each getting its own bulk
    key. Null/partial-null entries are never cached — a failed fetch stays a
    cache miss and the next call retries. Symbols without a usable price are
    omitted (callers already use ``.get(sym)``). Never raises.
    """
    out: dict[str, dict[str, Any]] = {}
    try:
        missing: list[str] = []
        for sym in symbols:
            entry = _fresh(f"quote_{_safe_key(sym)}", ttl)
            if entry is not None:
                out[sym] = entry
            else:
                missing.append(sym)
        if missing:
            snap = _quote_snapshot(missing)
            for sym in missing:
                entry = snap.get(sym)
                if not entry or entry.get("price") is None:
                    continue
                try:
                    _put(f"quote_{_safe_key(sym)}", entry)
                except Exception as e:
                    logger.warning("quote cache write failed for %s: %s: %s",
                                   sym, type(e).__name__, e)
                out[sym] = entry
    except Exception as e:
        logger.warning("get_quotes failed for %s: %s: %s",
                       symbols, type(e).__name__, e)
    return out


# The former Stooq CSV fallback (_stooq_quote/_stooq_quotes/_stooq_history)
# was removed 2026-08-23: Stooq now serves a JavaScript browser-verification
# wall to non-browser clients, so it returned nothing for every symbol
# (verified live). Restore from git history if Stooq reopens programmatic
# access; until then Yahoo failures surface as honest nulls and are never
# cached.


def get_history(symbol: str, days: int = 250, ttl: int = config.HISTORY_TTL) -> list[dict[str, Any]]:
    """Daily OHLC close history (list of {date, close}), cached."""
    # Sanitize: symbols can come from user-editable sources (portfolio
    # holdings, /api/portfolios/validate input), so the cache key must never
    # be able to escape CACHE_DIR.
    key = f"hist_{_safe_key(symbol)}_{days}"
    payload = _fresh(key, ttl)
    if payload is not None:
        return payload
    hist = _yf_history(symbol, days)
    # Never cache a failed fetch as an empty history: leave it uncached so
    # the next call retries.
    if hist:
        _put(key, hist)
    return hist


def _yf_history(symbol: str, days: int) -> list[dict[str, Any]]:
    yf = _get_yf()
    try:
        df = yf.download(
            symbol, period=f"{days}d", interval="1d",
            auto_adjust=True, progress=False,
        )
        if df is None or df.empty:
            return []
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.droplevel(1)
        out = []
        for idx, row in df.iterrows():
            close = row.get("Close")
            if close is None or pd.isna(close):
                continue
            out.append({"date": idx.strftime("%Y-%m-%d"), "close": float(close)})
        return out
    except Exception as e:
        logger.warning("history fetch failed for %s (%sd): %s: %s",
                       symbol, days, type(e).__name__, e)
        return []


def _bulk_histories_key(symbols: list[str], days: int) -> str:
    """The single cache key for a bulk history set.

    Shared by :func:`get_histories_bulk` (the writer) and
    :func:`get_histories_bulk_cached` (the cache-only reader) so the two can
    never drift onto different keys for the same request.
    """
    sym_hash = hashlib.sha1("|".join(sorted(symbols)).encode()).hexdigest()[:16]
    return f"bulkhist_{sym_hash}_{days}"


def get_histories_bulk(symbols: list[str], days: int = 250, ttl: int = config.HISTORY_TTL) -> dict[str, list[dict[str, Any]]]:
    """Fetch histories for many symbols in one yfinance download (cached)."""
    key = _bulk_histories_key(symbols, days)
    payload = _fresh(key, ttl)
    if payload is not None:
        return payload
    out = _yf_histories_bulk(symbols, days)
    # Never cache a failed fetch as an empty dict: leave it uncached so the
    # next call retries.
    if out:
        _put(key, out)
    return out


def get_histories_bulk_cached(symbols: list[str], days: int = 250, ttl: int = config.HISTORY_TTL) -> dict[str, list[dict[str, Any]]]:
    """Bulk histories from the on-disk cache only. Never fetches; {} on a miss.

    Probes the exact key :func:`get_histories_bulk` writes (via the shared
    :func:`_bulk_histories_key`), so a refresh and a cache-only reader address
    one dataset.  A miss or an expired entry returns an empty dict — the caller
    renders absence, never a stale or invented value.
    """
    key = _bulk_histories_key(symbols, days)
    payload = _fresh(key, ttl)
    return payload if isinstance(payload, dict) else {}


def _yf_histories_bulk(symbols: list[str], days: int) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    yf = _get_yf()
    try:
        df = yf.download(
            symbols, period=f"{days}d", interval="1d",
            auto_adjust=True, progress=False, group_by="column",
        )
        if df is None or df.empty:
            return out
        close_cols = df["Close"] if "Close" in df.columns else None
        if close_cols is None:
            return out
        for sym in symbols:
            if sym not in close_cols.columns:
                continue
            series = close_cols[sym].dropna()
            rows = []
            for idx, val in series.items():
                rows.append({"date": idx.strftime("%Y-%m-%d"), "close": float(val)})
            if rows:
                out[sym] = rows
    except Exception as e:
        logger.warning("bulk history fetch failed for %s (%sd): %s: %s",
                       symbols, days, type(e).__name__, e)
    # Per-symbol fallback for anything missing.
    for sym in symbols:
        if sym not in out:
            h = _yf_history(sym, days)
            if h:
                out[sym] = h
    return out


def history_universe_symbols() -> list[str]:
    """The exact symbol list the market snapshot bulk-downloads histories for.

    One source of truth: :func:`build_market_snapshot` (the refresh writer) and
    the cache-only render reader (``service.bottleneck_read_cached``) both build
    the bulk cache key from this list, so a number shown in two views reads the
    same cached dataset instead of two independently-expiring downloads.
    Deferred import: ``bottleneck`` imports this module at load time.
    """
    from . import bottleneck

    ai_tickers = list({t for tickers in config.AI_CAPEX_COHORTS.values() for t in tickers})
    return list(dict.fromkeys(
        config.HISTORY_CORE_SYMBOLS
        + list(config.SECTORS)
        + list(config.INDICES)
        + ai_tickers
        + bottleneck.all_proxy_symbols()
    ))


def build_market_snapshot() -> dict[str, Any]:
    """Aggregate quotes + histories into a single market snapshot dict."""
    all_symbols = (
        list(config.INDICES)
        + list(config.VOLATILITY)
        + list(config.RATES)
        + list(config.COMMODITIES)
        + list(config.SECTORS)
        + list(config.CROSS_ASSET)
    )
    quotes = get_quotes(all_symbols)

    snapshot: dict[str, Any] = {
        "as_of": _now_iso(),
        "indices": {s: quotes.get(s) for s in config.INDICES},
        "volatility": {s: quotes.get(s) for s in config.VOLATILITY},
        "rates": {s: quotes.get(s) for s in config.RATES},
        "commodities": {s: quotes.get(s) for s in config.COMMODITIES},
        "sectors": {s: quotes.get(s) for s in config.SECTORS},
    }

    # Bottleneck proxy tickers ride along in the same bulk download so layer
    # ranking reads warm snapshot data instead of falling back to ~50
    # sequential per-symbol fetches on a cold cache. The symbol list is shared
    # with the cache-only render reader (``history_universe_symbols``) so both
    # address the identical bulk cache key.
    history_symbols = history_universe_symbols()
    bulk = get_histories_bulk(history_symbols, days=250)

    hist: dict[str, Any] = {}
    for sym in config.HISTORY_CORE_SYMBOLS:
        hist[sym] = bulk.get(sym, [])
    extra: dict[str, Any] = {}
    # Everything fetched lands in "extra" (bottleneck ranking reads it);
    # consumers look symbols up individually, so extra keys are additive.
    for sym in history_symbols:
        extra[sym] = bulk.get(sym, [])
    hist["extra"] = extra
    snapshot["histories"] = hist

    return snapshot


def build_futures_snapshot() -> dict[str, Any]:
    """Quote snapshot for index/commodity futures.

    Items are {symbol, name, last, chg, chg_pct, prior_close}; values are
    null when no source is available (never fabricated).
    """
    symbols = list(config.INDEX_FUTURES) + list(config.COMMODITY_FUTURES)
    # Shared per-symbol live-quote cache (same path as portfolios/dashboard),
    # so futures never fetch a parallel copy that could disagree.
    # The Stooq fallback that once covered futures is gone: Stooq serves a
    # bot-challenge page and has no futures codes, so failures stay null.
    quotes = get_quotes(symbols, config.LIVE_QUOTE_TTL)

    def _items(group: dict[str, str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for sym, name in group.items():
            q = quotes.get(sym)
            if not q:
                out.append({
                    "symbol": sym, "name": name, "last": None,
                    "chg": None, "chg_pct": None, "prior_close": None,
                })
                continue
            last = q.get("price")
            chg = q.get("change")
            prior = round(last - chg, 4) if (last is not None and chg is not None) else None
            out.append({
                "symbol": sym, "name": name, "last": last, "chg": chg,
                "chg_pct": q.get("pct_change"), "prior_close": prior,
            })
        return out

    return {
        "as_of": _now_iso(),
        "index_futures": _items(config.INDEX_FUTURES),
        "commodities": _items(config.COMMODITY_FUTURES),
    }
