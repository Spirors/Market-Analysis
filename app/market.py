"""Market data acquisition from free sources (yfinance primary, Stooq fallback)."""

import hashlib
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from . import config, store

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


def _quote_snapshot(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Latest price + change for a list of symbols via one bulk download.

    Uses daily close history (reliable in yfinance 1.6.0) instead of the
    `fast_info` quote scraper, which returns None in current versions.
    """
    out: dict[str, dict[str, Any]] = {}
    yf = _get_yf()
    try:
        df = yf.download(
            symbols, period="7d", interval="1d",
            auto_adjust=True, progress=False, group_by="column",
        )
        if df is None or df.empty:
            return out
        close = df["Close"] if "Close" in df.columns else None
        if close is None:
            return out
        for sym in symbols:
            if sym not in close.columns:
                continue
            s = close[sym].dropna()
            if s.empty:
                continue
            price = float(s.iloc[-1])
            prev = float(s.iloc[-2]) if len(s) >= 2 else None
            chg = (price - prev) if prev else None
            pct = (chg / prev * 100) if (chg is not None and prev) else None
            out[sym] = {
                "price": round(price, 4),
                "change": round(chg, 4) if chg is not None else None,
                "pct_change": round(pct, 3) if pct is not None else None,
            }
    except Exception:
        pass
    return out


def get_quotes(symbols: list[str], ttl: int = config.QUOTE_TTL) -> dict[str, dict[str, Any]]:
    """Return cached-or-fresh quotes. Falls back to Stooq per-symbol on failure."""
    payload = _fresh("quotes", ttl)
    if payload is None:
        payload = _quote_snapshot(symbols)
        if not payload:
            payload = _stooq_quotes(symbols)
        _put("quotes", payload)
    # Ensure all requested symbols are represented (fill missing with stooq).
    missing = [s for s in symbols if s not in payload]
    if missing:
        for s in missing:
            q = _stooq_quote(s)
            if q:
                payload[s] = q
    return payload


def _stooq_quote(sym: str) -> Optional[dict[str, Any]]:
    """Stooq CSV fallback for a single symbol (works without keys)."""
    import urllib.request

    code = sym.replace("^", "").replace("=", "").replace("-", "")
    url = f"https://stooq.com/q/l/?s={code}&f=sd2t2ohlcv&h&e=csv"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            text = r.read().decode("utf-8").strip()
        lines = text.splitlines()
        if len(lines) < 2:
            return None
        header = lines[0].split(",")
        vals = lines[1].split(",")
        row = dict(zip(header, vals))
        price = float(row.get("Close") or 0)
        if not price:
            return None
        return {
            "price": price,
            "change": None,
            "pct_change": None,
        }
    except Exception:
        return None


def _stooq_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for s in symbols:
        q = _stooq_quote(s)
        if q:
            out[s] = q
    return out


def get_history(symbol: str, days: int = 250, ttl: int = config.HISTORY_TTL) -> list[dict[str, Any]]:
    """Daily OHLC close history (list of {date, close}), cached."""
    # Sanitize: symbols can come from the user-editable earnings watchlist,
    # so the cache key must never be able to escape CACHE_DIR.
    key = f"hist_{_safe_key(symbol)}_{days}"
    payload = _fresh(key, ttl)
    if payload is not None:
        return payload
    hist = _yf_history(symbol, days)
    if not hist:
        hist = _stooq_history(symbol, days)
    # Never cache a failed fetch as an empty history: leave it uncached so
    # the next call retries both sources.
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
    except Exception:
        return []


def _stooq_history(symbol: str, days: int) -> list[dict[str, Any]]:
    import urllib.request

    code = symbol.replace("^", "").replace("=", "").replace("-", "")
    url = f"https://stooq.com/q/d/l/?s={code}&i=d"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            text = r.read().decode("utf-8").strip()
        lines = text.splitlines()
        if len(lines) < 2:
            return []
        header = lines[0].split(",")
        out = []
        for line in lines[1:][-days:]:
            vals = line.split(",")
            row = dict(zip(header, vals))
            close = row.get("Close")
            if not close:
                continue
            out.append({"date": row["Date"], "close": float(close)})
        return out
    except Exception:
        return []


def get_histories_bulk(symbols: list[str], days: int = 250, ttl: int = config.HISTORY_TTL) -> dict[str, list[dict[str, Any]]]:
    """Fetch histories for many symbols in one yfinance download (cached)."""
    sym_hash = hashlib.sha1("|".join(sorted(symbols)).encode()).hexdigest()[:16]
    key = f"bulkhist_{sym_hash}_{days}"
    payload = _fresh(key, ttl)
    if payload is not None:
        return payload
    out = _yf_histories_bulk(symbols, days)
    # Never cache a failed fetch as an empty dict: leave it uncached so the
    # next call retries.
    if out:
        _put(key, out)
    return out


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
    except Exception:
        pass
    # Per-symbol fallback for anything missing.
    for sym in symbols:
        if sym not in out:
            h = _yf_history(sym, days)
            if h:
                out[sym] = h
    return out


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

    ai_tickers = list({t for tickers in config.AI_CAPEX_COHORTS.values() for t in tickers})
    history_symbols = config.HISTORY_CORE_SYMBOLS + list(config.SECTORS) + list(config.INDICES) + ai_tickers
    bulk = get_histories_bulk(history_symbols, days=250)

    hist: dict[str, Any] = {}
    for sym in config.HISTORY_CORE_SYMBOLS:
        hist[sym] = bulk.get(sym, [])
    extra: dict[str, Any] = {}
    for sym in list(config.SECTORS) + list(config.INDICES):
        extra[sym] = bulk.get(sym, [])
    for sym in ai_tickers:
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
    # Separate cache key from the main snapshot's "quotes" payload so a
    # futures-only fetch can never shadow the full universe there.
    quotes = _fresh("quotes_futures", config.QUOTE_TTL)
    if quotes is None:
        quotes = _quote_snapshot(symbols)
        # No Stooq fallback for futures: Stooq currently serves a bot-challenge
        # page and has no futures codes, so failures stay null.
        # Never cache an all-null snapshot: leave it uncached so the next
        # call retries instead of serving nulls for the whole TTL.
        if any(quotes.values()):
            _put("quotes_futures", quotes)

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
