"""AI valuation: forward-PE cache + cohort median + stretched flag.

Replaces the deleted ``compute_valuation_flag`` from the 2026-09-06
earnings-watchlist cleanup. The new shape is narrower (PE only -- no PEG,
no earnings-date) and is scoped to the beneficiary cohorts (the AI trade),
not the full AI_CAPEX_COHORTS universe (which includes Capex Spenders,
demand-side hyperscalers whose PE reflects the broader market).

Cache: on-disk JSON at ``config.AI_VALUATION_CACHE_PATH`` with a 12-hour
TTL (mirrors the deleted EARNINGS_CACHE pattern). Atomic write via
``tmp + os.replace`` so concurrent writers can't corrupt the file.

Document shape::

    {
        "NVDA": 48.2,                     # cohort PE keys, flat, at top level
        "AMD": 32.1,                      #   -> the "per_ticker_pe" set that
        ...                               #      feeds the cohort median
        "fetched_at": "<stamp>",
        "per_ticker_metrics": {           # sibling key: arbitrary DISPLAY
            "AVGO": {                     #   tickers (a bottleneck topic's
                "market_cap": 1.2e12,     #   names), NOT the beneficiary
                "revenue_growth": 0.18,   #   cohort. Never mixed into the
                "forward_pe": 33.4,       #   median.
                "as_of": "2026-09-25T12:00:00Z",
            },
        },
    }

The two key sets are written through a single reader/writer
(``save_cache``) that read-modify-writes the on-disk document, so a
beneficiary refresh can never delete ``per_ticker_metrics`` and a metrics
refresh can never blank the cohort PE keys (``breadth_ai``).

Fetch strategy -- beneficiary PE: yfinance ``Ticker.info["forwardPE"]`` per
ticker, skipping ``None`` / NaN / negative / zero (a PE <= 0 can't enter a
median). Fetch strategy -- display metrics: one ``.info`` read per symbol
per pass, converting ``marketCap`` / ``revenueGrowth`` / ``forwardPE``.
The card's ``forward_pe`` is stored **signed and unfiltered** (a loss-making
company's negative PE is real fetched data), and is copied from the cohort
PE map whenever the symbol is also a beneficiary, so the two views cannot
disagree. Network errors per-ticker are swallowed -- one bad ticker doesn't
fail the batch.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

# Path is bound at import time -- tests/conftest.py patches this name
# directly on the module (NOT config.AI_VALUATION_CACHE_PATH).
_CACHE_PATH: Path = config.AI_VALUATION_CACHE_PATH

# Doc-level metadata keys. Everything else at the top level is a cohort PE
# key ("per_ticker_pe"); ``per_ticker_metrics`` is a dict, so it is excluded
# from the median by the numeric filter regardless -- but naming it here keeps
# the writer's intent explicit.
_META_KEYS = frozenset({"fetched_at", "per_ticker_metrics"})
_STAMP_FMT = "%Y-%m-%dT%H:%M:%S"

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


def _finite_or_none(v: Any) -> float | None:
    """Coerce a fetched value to a finite float, else None.

    None / NaN / inf / unparseable all collapse to None. This is a
    *representation* guard only -- it does not filter sign, so a loss-making
    company's negative ``forwardPE`` survives intact.
    """
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _stamp_now() -> str:
    """Doc-level ``fetched_at`` stamp (matches the legacy parse format)."""
    return time.strftime(_STAMP_FMT)


def _now_iso() -> str:
    """Per-entry ``as_of``: ISO-8601 UTC, second precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_raw_doc() -> dict | None:
    """Read the cache document without applying the TTL. None if absent/corrupt."""
    if not _CACHE_PATH.exists():
        return None
    try:
        raw = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return raw if isinstance(raw, dict) else None


def _cohort_pe_map(doc: dict | None) -> dict[str, float]:
    """The cohort PE set: the flat numeric top-level keys of the cache doc.

    Identical to ``compute_valuation(doc)["per_ticker_pe"]``. This is the set
    whose median feeds the AI gauge, so an arbitrary display ticker must never
    land here -- that would contaminate the cohort median and could flip the
    ``stretched`` flag.
    """
    if not isinstance(doc, dict):
        return {}
    return {
        k: v
        for k, v in doc.items()
        if k not in _META_KEYS and isinstance(v, (int, float))
    }


def load_cache() -> dict | None:
    """Return the cached doc if it exists AND is within TTL. Otherwise None."""
    raw = _read_raw_doc()
    if raw is None:
        return None
    fetched_at = raw.get("fetched_at")
    if not fetched_at:
        return None
    try:
        cached_time = time.strptime(fetched_at, _STAMP_FMT)
    except ValueError:
        return None
    age_s = time.time() - time.mktime(cached_time)
    if age_s > config.AI_VALUATION_CACHE_TTL_HOURS * 3600:
        return None
    return raw


def save_cache(
    doc: dict | None = None,
    *,
    pe_map: dict | None = None,
    metrics: dict | None = None,
    fetched_at: str | None = None,
) -> None:
    """THE single cache writer. Atomic read-modify-write, not a full-file swap.

    Every write merges into the current on-disk document and preserves the
    key set it is not updating, so the sibling key sets can never clobber one
    another. ``doc`` is a legacy/back-compat mapping whose non-metadata keys
    are treated as the cohort PE set. New callers should be explicit:

    - ``pe_map``     replaces the cohort-PE key set (never pass display tickers)
    - ``metrics``    deep-merges into ``per_ticker_metrics`` per symbol
    - ``fetched_at`` stamps the doc-level cohort-PE vintage

    Atomic tmpfile + ``os.replace`` so a crash can't leave a half-written
    cache.
    """
    if doc is not None:
        if pe_map is None:
            pe_map = {k: v for k, v in doc.items() if k not in _META_KEYS}
        if metrics is None and isinstance(doc.get("per_ticker_metrics"), dict):
            metrics = doc["per_ticker_metrics"]
        if fetched_at is None:
            fetched_at = doc.get("fetched_at")

    current = _read_raw_doc()
    if not isinstance(current, dict):
        current = {}

    if pe_map is not None:
        # Replace the cohort-PE key set wholesale; keep metadata siblings.
        current = {k: v for k, v in current.items() if k in _META_KEYS}
        current.update(pe_map)

    if metrics is not None:
        existing = current.get("per_ticker_metrics")
        existing = existing if isinstance(existing, dict) else {}
        current["per_ticker_metrics"] = {**existing, **metrics}

    if fetched_at is not None:
        current["fetched_at"] = fetched_at

    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(_CACHE_PATH.parent),
        prefix=f"{_CACHE_PATH.name}-",
        suffix=".tmp",
    )
    try:
        os.close(fd)
        Path(tmp_path).write_text(json.dumps(current, indent=2), encoding="utf-8")
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
    values, and writes through ``save_cache`` (the single writer) so the
    sibling ``per_ticker_metrics`` key set survives. Network errors
    per-ticker are swallowed -- one rate-limited ticker doesn't fail the
    whole batch.
    """
    if not force:
        cached = load_cache()
        if cached is not None:
            # A fresh cache is authoritative even when it holds no valid PE.
            # Falling through on an empty map would put a network walk over the
            # whole beneficiary cohort on every single serve.
            return _cohort_pe_map(cached)

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

    # Single writer: replaces the cohort-PE key set, preserves metrics.
    save_cache(pe_map=out, fetched_at=_stamp_now())
    return dict(out)


def load_ticker_metrics() -> dict[str, dict]:
    """Return the ``per_ticker_metrics`` map, or ``{}`` if the doc is absent,
    corrupt, expired, missing ``fetched_at``, or has no metrics.

    This reader owns cross-view consistency, because the two key sets share one
    document and one doc-level ``fetched_at`` but are refreshed independently.
    For a symbol that is *also* a beneficiary cohort member the **live cohort PE
    wins**, so a card built from this map can never disagree with ``breadth_ai``,
    which reads that same cohort set. Without this overlay a card would serve a
    frozen PE copy that drifts every time the cohort set is refreshed.

    Each entry keeps its own ``as_of``, which is what makes the metrics vintage
    honest: the doc-level stamp describes the cohort set, not this one.

    Consumers never touch the raw document.
    """
    doc = load_cache()
    if not isinstance(doc, dict):
        return {}
    metrics = doc.get("per_ticker_metrics")
    if not isinstance(metrics, dict):
        return {}
    cohort = _cohort_pe_map(doc)
    out: dict[str, dict] = {}
    for sym, entry in metrics.items():
        if not isinstance(entry, dict):
            continue
        if sym in cohort:
            entry = {**entry, "forward_pe": cohort[sym]}
        out[sym] = entry
    return out


def fetch_ticker_metrics(
    symbols: list[str],
    *,
    force: bool = False,
) -> dict[str, dict]:
    """Fetch per-ticker display metrics for arbitrary (display) symbols.

    Returns ``{symbol: {"market_cap", "revenue_growth", "forward_pe", "as_of"}}``.

    Cache-first per symbol: a symbol already in ``per_ticker_metrics`` within
    TTL is reused; ``force=True`` refetches every requested symbol. Each
    symbol is fetched with exactly one ``Ticker.info`` read, from which
    ``marketCap`` / ``revenueGrowth`` / ``forwardPE`` are taken.

    ``forward_pe`` is stored **signed and unfiltered** (unlike the cohort
    ``per_ticker_pe`` set, which excludes ``<= 0`` because negatives cannot
    enter a median). When a requested symbol is also a beneficiary cohort
    member, its ``forward_pe`` is copied from the cohort PE map rather than
    the freshly-read ``info`` value -- so the card and ``breadth_ai`` are
    identical by construction, never merely by coincidence.

    A field yfinance genuinely lacks is stored as ``None`` (with the
    ``as_of`` stamp); a symbol whose fetch raises is simply absent from the
    result. Nothing is ever fabricated, and no field ever lands in the cohort
    PE set.
    """
    import yfinance as yf  # imported lazily so test environments without yfinance still work

    cached = {} if force else load_ticker_metrics()
    # Cohort PE map read from the same TTL-gated doc that breadth_ai reads, so
    # a shared symbol can never show two different numbers.
    pe_map = compute_valuation(load_cache() or {}).get("per_ticker_pe", {})

    out: dict[str, dict] = {}
    fetched: dict[str, dict] = {}
    seen: set[str] = set()
    for sym in symbols:
        if not isinstance(sym, str) or not sym or sym in seen:
            continue
        seen.add(sym)
        if not force and sym in cached:
            out[sym] = dict(cached[sym])
            continue
        try:
            info = yf.Ticker(sym).info or {}
        except Exception:
            continue  # fetch raised -> symbol absent from the map
        entry = {
            "market_cap": _finite_or_none(info.get("marketCap")),
            "revenue_growth": _finite_or_none(info.get("revenueGrowth")),
            "forward_pe": _finite_or_none(info.get("forwardPE")),
            "as_of": _now_iso(),
        }
        if sym in pe_map:
            # Shared with the beneficiary cohort: copy, don't refetch.
            entry["forward_pe"] = pe_map[sym]
        fetched[sym] = entry
        out[sym] = entry

    if fetched:
        raw = _read_raw_doc() or {}
        stamp = raw.get("fetched_at") or _stamp_now()
        # Metrics write preserves the cohort-PE key set; fetched_at is only
        # (re)stamped when the doc has none, so it keeps describing the PE set.
        save_cache(metrics=fetched, fetched_at=stamp)

    # Cached entries too: always surface the current cohort PE for a shared
    # symbol, so the returned card cannot drift from breadth_ai.
    for sym, entry in out.items():
        if sym in pe_map:
            out[sym] = {**entry, "forward_pe": pe_map[sym]}
    return out


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
    # The numeric filter also drops ``per_ticker_metrics`` (a dict), so the
    # display metrics can never contaminate the cohort median.
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
