"""True cash-market spot prices for the Spot card.

The dashboard's Commodities card shows Yahoo tickers like ``CL=F`` /
``GC=F`` / ``NG=F`` that are *front-month futures contracts*, not spot.
This module pulls actual cash/spot benchmarks from free, no-key public
feeds so the Spot card can show genuine spot prices distinct from the
paper futures.

Two source families are supported:

1. **FRED (St. Louis Fed)** — public CSV endpoints, daily, no key.
   Energy benchmarks (WTI Cushing, Brent BFOE, Henry Hub NG).
2. **Minted Metal** — public JSON, twice-daily after LBMA fixes, no key,
   CC BY 4.0 (attribution required). Precious metals (gold, silver).

Each series is fetched independently — one source failure does not break
others. Items that return no data surface as ``last=None`` so the renderer
shows "—" without poisoning the rest of the card.

Coverage is intentionally narrower than the Commodities card universe:
copper / wheat / corn have only monthly free series, and bitcoin's only
free source is the Yahoo ticker already in the Commodities card. See
``config.SPOT_SERIES`` / ``config.SPOT_METALS`` for the live list.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

from . import config, market

logger = logging.getLogger(__name__)

_FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
_CACHE_KEY = "spot_quotes"
_REQUEST_TIMEOUT = 15  # seconds — both endpoints respond well under 1s


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- Source 1: FRED (CSV) ----------------------------------------------------

def _fetch_fred_series(series_id: str) -> list[tuple[str, Optional[float]]]:
    """Return ``[(date_iso, value_or_None), ...]`` for one FRED series, newest first."""
    url = _FRED_CSV_URL.format(series_id=series_id)
    req = urllib.request.Request(url, headers={"User-Agent": "market-analysis-tool/1.0"})
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
        text = resp.read().decode("utf-8", errors="replace")

    rows: list[tuple[str, Optional[float]]] = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2:
            continue
        date_str, val_str = row[0].strip(), row[1].strip()
        # Skip FRED's 3-line observation-metadata header; meta rows have a
        # non-parseable first cell ("DATE", ".", etc.).
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if val_str in ("", "."):
            rows.append((date_str, None))
            continue
        try:
            rows.append((date_str, float(val_str)))
        except ValueError:
            rows.append((date_str, None))
    rows.reverse()  # newest-first
    return rows


def _item_from_fred(series_id: str, name: str) -> dict[str, Any]:
    """One spot item sourced from a FRED daily series."""
    last: Optional[float] = None
    prior: Optional[float] = None
    source_date: Optional[str] = None
    error: Optional[str] = None
    try:
        rows = _fetch_fred_series(series_id)
    except Exception as e:
        logger.warning("FRED spot fetch failed for %s: %s: %s",
                       series_id, type(e).__name__, e)
        error = f"{type(e).__name__}: {e}"
    else:
        # Latest two non-null observations; FRED occasionally emits a
        # placeholder "." row, so filter nulls rather than trusting index 0.
        non_null = [(d, v) for d, v in rows if v is not None]
        if non_null:
            source_date = non_null[0][0]
            last = non_null[0][1]
            if len(non_null) >= 2:
                prior = non_null[1][1]

    return _build_item(
        sid=series_id, name=name,
        last=last, prior=prior,
        source_date=source_date,
        source_label="FRED (St. Louis Fed)",
        source_url=f"https://fred.stlouisfed.org/series/{series_id}",
        error=error,
    )


# ---- Source 2: Minted Metal (JSON) -------------------------------------------

def _fetch_minted_metal_payload() -> dict[str, Any]:
    """Single network call for the whole precious-metals payload."""
    req = urllib.request.Request(
        config.MINTED_METAL_URL,
        headers={"User-Agent": "market-analysis-tool/1.0"},
    )
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _item_from_minted_metal(
    symbol: str, name: str, metal_key: str,
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """One spot item sourced from a Minted Metal precious-metal entry."""
    last: Optional[float] = None
    prior: Optional[float] = None
    source_date: Optional[str] = None
    source_label = "Minted Metal (LBMA proxy)"
    source_url = config.MINTED_METAL_URL
    error: Optional[str] = None
    try:
        if payload is None:
            payload = _fetch_minted_metal_payload()
        metal = (payload.get("metals") or {}).get(metal_key)
        if not isinstance(metal, dict):
            raise ValueError(f"missing '{metal_key}' in Minted Metal payload")
        last_raw = metal.get("price")
        prior_raw = metal.get("previousPrice")
        last = float(last_raw) if last_raw is not None else None
        prior = float(prior_raw) if prior_raw is not None else None
        fixed_at = metal.get("fixedAt")
        if isinstance(fixed_at, str):
            source_date = fixed_at[:10]  # YYYY-MM-DD
        sl = metal.get("sourceLabel")
        su = metal.get("sourceUrl")
        src = metal.get("source")
        # Compose a label that always names the upstream benchmark
        # (e.g. "LBMA London PM Fix via Minted Metal") — Minted Metal's own
        # `sourceLabel` (e.g. "London PM Fix") doesn't mention LBMA.
        if sl and src:
            source_label = f"{src} {sl} via Minted Metal"
        elif sl:
            source_label = f"{sl} via Minted Metal"
        if su:
            source_url = su
    except Exception as e:
        logger.warning("Minted Metal fetch failed for %s: %s: %s",
                       symbol, type(e).__name__, e)
        error = f"{type(e).__name__}: {e}"

    return _build_item(
        sid=symbol, name=name,
        last=last, prior=prior,
        source_date=source_date,
        source_label=source_label,
        source_url=source_url,
        error=error,
    )


# ---- Shared item builder ----------------------------------------------------

def _build_item(
    sid: str, name: str,
    last: Optional[float], prior: Optional[float],
    source_date: Optional[str],
    source_label: str, source_url: str,
    error: Optional[str],
) -> dict[str, Any]:
    chg: Optional[float] = None
    pct: Optional[float] = None
    if last is not None and prior not in (None, 0):
        chg = round(last - prior, 4)
        pct = round((last - prior) / prior * 100, 3)
    out: dict[str, Any] = {
        "id": sid,
        "name": name,
        "last": last,
        "prior_close": prior,
        "chg": chg,
        "pct_change": pct,
        "source_date": source_date,
        "source_label": source_label,
        "source_url": source_url,
    }
    if error is not None:
        out["error"] = error
    return out


# ---- Public entry point -----------------------------------------------------

def build_spot_snapshot() -> dict[str, Any]:
    """Return ``{as_of, items, attribution}`` for the Spot card.

    Items are cached as a unit under :data:`_CACHE_KEY` with
    ``config.SPOT_TTL``. A snapshot where every item is null is NOT cached
    (same failure-aware rule the futures snapshot follows).
    """
    payload = market._fresh(_CACHE_KEY, config.SPOT_TTL)
    if payload is not None:
        return payload

    items: list[dict[str, Any]] = []

    # FRED energy benchmarks — one HTTP call each.
    for sid, name in config.SPOT_SERIES.items():
        items.append(_item_from_fred(sid, name))

    # Minted Metal precious metals — share ONE HTTP call across all rows.
    metal_payload: Optional[dict[str, Any]] = None
    metal_failure: Optional[str] = None
    try:
        metal_payload = _fetch_minted_metal_payload()
    except Exception as e:
        logger.warning("Minted Metal shared fetch failed: %s: %s",
                       type(e).__name__, e)
        metal_failure = f"{type(e).__name__}: {e}"

    for symbol, (name, metal_key) in config.SPOT_METALS.items():
        if metal_payload is None:
            items.append(_build_item(
                sid=symbol, name=name,
                last=None, prior=None,
                source_date=None,
                source_label="Minted Metal (LBMA proxy)",
                source_url=config.MINTED_METAL_URL,
                error=metal_failure,
            ))
        else:
            items.append(_item_from_minted_metal(
                symbol, name, metal_key, payload=metal_payload,
            ))

    snap: dict[str, Any] = {
        "as_of": _now_iso(),
        "items": items,
        # Keyed by the matching Yahoo futures ticker (GC=F, CL=F, …) so the
        # Commodities renderer can display real spot beside each paper
        # contract without knowing about FRED / Minted Metal internals.
        "commodities_map": {
            config.SPOT_TO_FUTURES_SYMBOL[item["id"]]: item
            for item in items
            if item.get("id") in config.SPOT_TO_FUTURES_SYMBOL
        },
        # CC BY 4.0 attribution; renderer surfaces it when any Minted Metal
        # row is present.
        "attribution": config.MINTED_METAL_ATTRIBUTION,
    }

    if any(i.get("last") is not None for i in items):
        market._put(_CACHE_KEY, snap)
    else:
        logger.warning("Spot snapshot has no live items; not caching.")
    return snap


def _cache_file_path():
    """Cache-file path for the spot snapshot (used by tests)."""
    return config.CACHE_DIR / f"{_CACHE_KEY}.json"