"""AI valuation: forward-PE cache + cohort median + stretched flag.

Replaces the deleted ``compute_valuation_flag`` from the 2026-09-06
earnings-watchlist cleanup. The new shape is narrower (PE only -- no PEG,
no earnings-date) and is scoped to the beneficiary cohorts (the AI trade),
not the full AI_CAPEX_COHORTS universe (which includes Capex Spenders,
demand-side hyperscalers whose PE reflects the broader market).

Cache: on-disk JSON at ``config.AI_VALUATION_CACHE_PATH`` with a 12-hour
TTL (mirrors the deleted EARNINGS_CACHE pattern). Atomic write via
``tmp + os.replace`` so concurrent writers can't corrupt the file.

Fetch strategy: yfinance ``Ticker.info["forwardPE"]`` per ticker. Skip
tickers where the value is ``None`` / NaN / negative / zero (forward PE
< 0 means losses; PE = 0 means no estimate; both are unusable). Network
errors per-ticker are swallowed -- one bad ticker doesn't fail the batch.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from . import config

# Path is bound at import time -- tests/conftest.py patches this name
# directly on the module (NOT config.AI_VALUATION_CACHE_PATH).
_CACHE_PATH: Path = config.AI_VALUATION_CACHE_PATH

# Beneficiary cohorts = AI_CAPEX_COHORTS minus Capex Spenders. Computed once
# at import time so the hot path doesn't iterate the constant dict.
_BENEFICIARY_COHORTS: dict[str, list[str]] = {
    name: tickers
    for name, tickers in config.AI_CAPEX_COHORTS.items()
    if name != "Capex Spenders"
}
_BENEFICIARY_TICKERS: list[str] = sorted({
    t for tickers in _BENEFICIARY_COHORTS.values() for t in tickers
})


def _is_valid_pe(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, float):
        return not (math.isnan(v) or math.isinf(v)) and v > 0
    try:
        return float(v) > 0
    except (TypeError, ValueError):
        return False


def load_cache() -> dict | None:
    """Return the cached PE map if it exists AND is within TTL. Otherwise None."""
    if not _CACHE_PATH.exists():
        return None
    try:
        raw = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    fetched_at = raw.get("fetched_at")
    if not fetched_at:
        return None
    try:
        cached_time = time.strptime(fetched_at, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    age_s = time.time() - time.mktime(cached_time)
    if age_s > config.AI_VALUATION_CACHE_TTL_HOURS * 3600:
        return None
    return raw


def save_cache(pe_map: dict) -> None:
    """Atomic write to disk. Last full-file rewrite wins (acceptable for a
    developer cache)."""
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(_CACHE_PATH.parent),
        prefix=f"{_CACHE_PATH.name}-",
        suffix=".tmp",
    )
    try:
        os.close(fd)
        Path(tmp_path).write_text(json.dumps(pe_map, indent=2), encoding="utf-8")
        os.replace(tmp_path, _CACHE_PATH)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def fetch_beneficiary_pe(
    tickers: list[str] | None = None,
    *,
    force: bool = False,
) -> dict[str, float]:
    """Return {ticker: forward_pe} across beneficiary cohorts.

    Cache-first. On miss/expiry (or when force=True): walks the ticker
    list, calls ``yf.Ticker(sym).info["forwardPE"]``, filters invalid
    values, atomic-saves the partial map. Network errors per-ticker are
    swallowed -- one rate-limited ticker doesn't fail the whole batch.
    """
    if not force:
        cached = load_cache()
        if cached is not None:
            # Strip the metadata keys; return only {ticker: pe}
            return {k: v for k, v in cached.items() if k != "fetched_at" and isinstance(v, (int, float))}

    import yfinance as yf  # imported lazily so test environments without yfinance still work

    symbols = tickers if tickers is not None else _BENEFICIARY_TICKERS
    out: dict[str, float] = {}
    for sym in symbols:
        try:
            info = yf.Ticker(sym).info or {}
        except Exception:
            continue
        pe = info.get("forwardPE")
        if _is_valid_pe(pe):
            out[sym] = float(pe)

    out["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_cache(out)
    # Return the per-ticker map only (caller doesn't see the metadata key)
    return {k: v for k, v in out.items() if k != "fetched_at"}


def compute_valuation(pe_map: dict[str, float]) -> dict:
    """Return the valuation summary the AI gauge consumes.

    Shape::

        {
            "median_pe": float | None,
            "stretched": bool,           # median_pe >= AI_VALUATION_STRETCH_PE
            "note": str,                 # human-readable
            "per_ticker_pe": dict,       # the input map (passthrough for hover)
            "fetched_at": str | None,    # ISO timestamp or None if pe_map empty
            "cache_ttl_hours": int,      # mirror of config.AI_VALUATION_CACHE_TTL_HOURS
        }
    """
    # Strip metadata key from pe_map (caller may pass a cache-shaped dict).
    per_ticker = {k: v for k, v in pe_map.items() if k != "fetched_at" and isinstance(v, (int, float))}
    cache_ttl = config.AI_VALUATION_CACHE_TTL_HOURS
    if not per_ticker:
        return {
            "median_pe": None,
            "stretched": False,
            "note": "no beneficiary PE data",
            "per_ticker_pe": {},
            "fetched_at": pe_map.get("fetched_at") if isinstance(pe_map, dict) else None,
            "cache_ttl_hours": cache_ttl,
        }
    vals = sorted(per_ticker.values())
    mid = len(vals) // 2
    if len(vals) % 2 == 0:
        median = (vals[mid - 1] + vals[mid]) / 2
    else:
        median = vals[mid]
    stretched = median >= config.AI_VALUATION_STRETCH_PE
    if stretched:
        note = f"median {median:.1f}x >= {config.AI_VALUATION_STRETCH_PE:g}x (stretched)"
    else:
        note = f"median {median:.1f}x < {config.AI_VALUATION_STRETCH_PE:g}x"
    return {
        "median_pe": round(median, 2),
        "stretched": stretched,
        "note": note,
        "per_ticker_pe": per_ticker,
        "fetched_at": pe_map.get("fetched_at") if isinstance(pe_map, dict) else None,
        "cache_ttl_hours": cache_ttl,
    }
