"""Portfolio data layer: CRUD on data/portfolios.json.

Persistence: single file holding all portfolios.  Column prefs (visibility +
order) live in this file under ``column_order`` / ``column_visibility`` —
each portfolio has its own entry keyed by ``portfolio.<pid>`` so column
customization is independent per portfolio (the
``portfolio`` key is the default for new portfolios).  See
``docs/DECISIONS.md`` "Per-portfolio column state" for the rationale.

Atomic writes via store.save_json.  Live price + fundamentals enrichment
is done at serve time by the API layer.
"""

from __future__ import annotations

import functools
import re
import time
from datetime import date, datetime, timezone
from typing import Any

from . import config, store, validation


def _patch_dashboard_cache(state: dict[str, Any]) -> None:
    """Patch the cached dashboard payload's portfolios field after a mutation.

    Per the audit-2026-09-07 P0 fix: the pre-fix implementation re-enriched
    ALL holdings via enrich_portfolios(state) on every 1-symbol mutation,
    paying ~3s of yfinance HTTP calls per click. We now patch the structural
    state only and bump the vintage; live prices for newly-added holdings
    stay None until the next full enrichment pass (Refresh button, QUOTE_TTL
    expiry, or follow-up GET /api/portfolios → enrich_portfolios). The UI
    renders None as "—". Per the "Earnings cache-miss path must not trigger
    a full universe rebuild" decision (80d0fef), a cache-patching helper
    must NOT fall through to a full rebuild — either patch minimally or
    invalidate and return. This is the "patch minimally" path (the
    earnings-derived cache pattern was the model; the same rule applies
    here).

    The cache is best-effort: missing/malformed cache is silently skipped
    (a fresh refresh will rebuild it). No exception escapes.
    """
    cache_path = config.DATA_DIR / "dashboard.json"
    try:
        cached = store.load_json(cache_path)
    except Exception:
        return
    if not isinstance(cached, dict):
        return
    try:
        # Structural patch only: the state's holdings already carry
        # symbol/shares/total_cost (and any user-edited values). Live prices
        # (last_price, pct_daily, sector, etc.) for newly-added holdings
        # stay None until the next full enrichment pass; the UI shows "—"
        # in the meantime. Skipping enrich_portfolios here is the entire
        # point of the P0 fix.
        cached["portfolios"] = state.get("portfolios", {})
        # Bump the portfolios section's vintage stamp so the per-card "As of"
        # footer reflects the mutation time instead of the last full refresh.
        vintage = cached.setdefault("vintage", {})
        vintage["portfolios"] = datetime.now(timezone.utc).isoformat()
        store.save_json(cache_path, cached)
    except Exception:
        # Cache patching is best-effort. A failed patch means the user
        # sees stale data until QUOTE_TTL expires — same as before this
        # fix — not a hard error.
        pass

# Column order / visibility defaults for the Portfolio section. Each
# portfolio can override via column_order["portfolio.<pid>"] /
# column_visibility["portfolio.<pid>"] - see "Per-portfolio column
# state" in docs/DECISIONS.md. The "portfolio" key is the default that
# new portfolios inherit on first save. The user-requested column order
# (7-day %, 30-day %, Earnings date, Marketcap, Forward PE, Forward PEG,
# 52W high, Sector) is preserved here.
DEFAULT_COLUMN_ORDER: dict[str, list[str]] = {
    "portfolio": [
        "_star", "symbol", "shares", "total_cost", "last_price",
        "total_value", "gain_loss", "pct_daily",
        "pct_7d", "pct_30d", "next_earnings", "marketcap",
        "forward_pe", "forward_peg", "high_52w", "sector",
    ],
}

DEFAULT_COLUMN_VISIBILITY: dict[str, dict[str, bool]] = {
    "portfolio": {k: True for k in DEFAULT_COLUMN_ORDER["portfolio"]},
}

DEFAULT_COLUMN_VISIBILITY: dict[str, dict[str, bool]] = {
    "portfolio": {k: True for k in DEFAULT_COLUMN_ORDER["portfolio"]},
}


PORTFOLIOS_PATH = config.DATA_DIR / "portfolios.json"


def _default_state() -> dict[str, Any]:
    # Column prefs live here only because the PUT /api/portfolios/columns/{section}
    # route (app/api.py) reads/writes them.  The portfolio frontend ignores
    # server-stored prefs entirely — it uses localStorage.  These fields are
    # effectively write-only dead data for the portfolio section.
    return {
        "version": 1,
        "portfolios": {},
        "column_order": {k: list(v) for k, v in DEFAULT_COLUMN_ORDER.items()},
        "column_visibility": {k: dict(v) for k, v in DEFAULT_COLUMN_VISIBILITY.items()},
    }


def load_portfolios() -> dict[str, Any]:
    """Return the full portfolios state, or a default if the file is missing/corrupt."""
    data = store.load_json(PORTFOLIOS_PATH)
    if not isinstance(data, dict) or data.get("version") != 1:
        return _default_state()
    for section in DEFAULT_COLUMN_ORDER:
        data.setdefault("column_order", {}).setdefault(section, list(DEFAULT_COLUMN_ORDER[section]))
        data.setdefault("column_visibility", {}).setdefault(section, dict(DEFAULT_COLUMN_VISIBILITY[section]))
    data.setdefault("portfolios", {})
    return data


def save_portfolios(state: dict[str, Any]) -> None:
    store.save_json(PORTFOLIOS_PATH, state)


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    s = (name or "").strip().lower()
    s = _SLUG_RE.sub("-", s).strip("-")
    if not s:
        raise ValueError("portfolio name is required")
    return s


def _next_unique_id(state: dict[str, Any], base: str) -> str:
    existing = set(state["portfolios"].keys())
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


def create_portfolio(name: str) -> dict[str, Any]:
    state = load_portfolios()
    base = _slugify(name)
    pid = _next_unique_id(state, base)
    state["portfolios"][pid] = {
        "id": pid,
        "name": name.strip(),
        "holdings": [],
    }
    save_portfolios(state)
    _patch_dashboard_cache(state)
    return {"id": pid, "portfolio": state["portfolios"][pid]}


def delete_portfolio(pid: str) -> bool:
    state = load_portfolios()
    if pid not in state["portfolios"]:
        return False
    del state["portfolios"][pid]
    save_portfolios(state)
    _patch_dashboard_cache(state)
    return True


def reorder_portfolios(order: list[str]) -> dict[str, Any]:
    """Reorder the portfolios dict according to ``order``.

    ``order`` must be a permutation of the current portfolio ids (no
    additions, removals, or duplicates). The persisted state is
    rewritten as a new dict whose key order matches ``order``; Python's
    ``json`` preserves dict insertion order, and JS's ``JSON.parse``
    reads it back as an object whose iteration order matches the same
    sequence, so the frontend's ``Object.values(portfolios)`` walks the
    new order without any extra plumbing.

    No data on individual portfolios is touched. The dashboard cache is
    patched (just the portfolios field + a bumped vintage stamp) so the
    next ``GET /api/dashboard`` returns the new order without a full
    refresh.

    Returns the updated state dict.

    Raises ``ValueError`` if ``order`` is not a permutation of the
    current pid set; the caller (``/api/portfolios/reorder``) maps that
    to HTTP 400. Empty ``order`` is rejected unless there are zero
    portfolios (the trivial "no-op" case).
    """
    state = load_portfolios()
    current = list(state["portfolios"].keys())
    if not isinstance(order, list) or set(order) != set(current) or len(order) != len(current):
        raise ValueError("order must be a permutation of existing portfolio ids")
    # Build a new dict so the on-disk order reflects `order` exactly.
    state["portfolios"] = {pid: state["portfolios"][pid] for pid in order}
    save_portfolios(state)
    _patch_dashboard_cache(state)
    return state


def rename_portfolio(pid: str, name: str) -> dict[str, Any] | None:
    name = (name or "").strip()
    if not name:
        raise ValueError("portfolio name is required")
    state = load_portfolios()
    p = state["portfolios"].get(pid)
    if not p:
        return None
    p["name"] = name
    save_portfolios(state)
    _patch_dashboard_cache(state)
    return p


def _get_portfolio(state: dict[str, Any], pid: str) -> dict[str, Any]:
    p = state["portfolios"].get(pid)
    if not p:
        raise KeyError(f"unknown portfolio: {pid}")
    return p


def add_holding(pid: str, symbol: str, shares: float, total_cost: float) -> dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        raise ValueError("symbol is required")
    if shares is None or shares < 0:
        raise ValueError("shares must be >= 0")
    if total_cost is None or total_cost < 0:
        raise ValueError("total_cost must be >= 0")
    validation_result = validation.validate_symbol(symbol)
    if not validation_result.get("valid"):
        raise ValueError(validation_result.get("reason") or "invalid symbol")
    state = load_portfolios()
    p = _get_portfolio(state, pid)
    if any(h.get("symbol") == symbol for h in p["holdings"]):
        raise ValueError(f"{symbol} already in portfolio")
    holding = {"symbol": symbol, "shares": float(shares), "total_cost": float(total_cost)}
    p["holdings"].append(holding)
    save_portfolios(state)
    _patch_dashboard_cache(state)
    return holding


def edit_holding(pid: str, symbol: str, shares: float | None, total_cost: float | None) -> dict[str, Any] | None:
    state = load_portfolios()
    p = _get_portfolio(state, pid)
    for h in p["holdings"]:
        if h.get("symbol") == symbol and h.get("kind") != "cash":
            if shares is not None:
                if shares < 0:
                    raise ValueError("shares must be >= 0")
                h["shares"] = float(shares)
            if total_cost is not None:
                if total_cost < 0:
                    raise ValueError("total_cost must be >= 0")
                h["total_cost"] = float(total_cost)
            save_portfolios(state)
            _patch_dashboard_cache(state)
            return h
    return None


def remove_holding(pid: str, symbol: str) -> bool:
    state = load_portfolios()
    p = _get_portfolio(state, pid)
    new_holdings = [h for h in p["holdings"] if not (h.get("symbol") == symbol and h.get("kind") != "cash")]
    if len(new_holdings) == len(p["holdings"]):
        return False
    p["holdings"] = new_holdings
    save_portfolios(state)
    _patch_dashboard_cache(state)
    return True


def add_cash_row(pid: str, label: str | None, total_cost: float, total_value: float) -> dict[str, Any]:
    if total_cost is None or total_cost < 0:
        raise ValueError("total_cost must be >= 0")
    if total_value is None or total_value < 0:
        raise ValueError("total_value must be >= 0")
    state = load_portfolios()
    p = _get_portfolio(state, pid)
    if any(h.get("kind") == "cash" for h in p["holdings"]):
        raise ValueError("cash row already exists")
    holding = {"kind": "cash", "label": label or "Cash", "total_cost": float(total_cost), "total_value": float(total_value)}
    p["holdings"].append(holding)
    save_portfolios(state)
    _patch_dashboard_cache(state)
    return holding


def edit_cash_row(pid: str, label: str | None, total_cost: float | None, total_value: float | None) -> dict[str, Any] | None:
    state = load_portfolios()
    p = _get_portfolio(state, pid)
    for h in p["holdings"]:
        if h.get("kind") == "cash":
            if label is not None and label.strip():
                h["label"] = label.strip()
            if total_cost is not None:
                if total_cost < 0:
                    raise ValueError("total_cost must be >= 0")
                h["total_cost"] = float(total_cost)
            if total_value is not None:
                if total_value < 0:
                    raise ValueError("total_value must be >= 0")
                h["total_value"] = float(total_value)
            save_portfolios(state)
            _patch_dashboard_cache(state)
            return h
    return None


def remove_cash_row(pid: str) -> bool:
    """Delete the single cash row from a portfolio. Returns False if no cash row exists."""
    state = load_portfolios()
    p = state["portfolios"].get(pid)
    if not p:
        return False
    new_holdings = [h for h in p["holdings"] if h.get("kind") != "cash"]
    if len(new_holdings) == len(p["holdings"]):
        return False
    p["holdings"] = new_holdings
    save_portfolios(state)
    _patch_dashboard_cache(state)
    return True


# ---- Portfolio enrichment (live price + fundamentals + history) --------------
#
# These helpers add 7 fields beyond price + pct_daily:
#   pct_7d, pct_30d, high_52w         (from 260-day bulk history)
#   sector, marketcap, forward_pe,
#     forward_peg, next_earnings        (from per-symbol Ticker.info / calendar)
#
# The Ticker.info fetch is cached 5 minutes via lru_cache so repeated portfolio
# loads don't hammer yfinance; cold-cache loads are slower (one HTTP per
# unique symbol) but acceptable. See "Per-portfolio column state" in
# docs/DECISIONS.md for the data-source rationale.

_INFO_CACHE_BUCKET_S = 300  # 5 minutes - fundamentals don't change fast enough to justify more fetches


def _to_float(v: Any) -> float | None:
    """Coerce to float; round to 3dp; treat None and NaN as None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return round(f, 3)


def _pct_change(series: list[dict[str, Any]], days_back: int) -> float | None:
    """Percent change of the last close vs the close N trading days ago."""
    if len(series) < days_back + 1:
        return None
    cur = series[-1].get("close")
    prev = series[-(days_back + 1)].get("close")
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur / prev - 1) * 100, 3)


def _52w_high(series: list[dict[str, Any]]) -> float | None:
    """Highest close in the supplied series (260 trading days = ~1 year)."""
    if not series:
        return None
    highs: list[float] = []
    for r in series:
        c = r.get("close")
        if c is not None:
            highs.append(c)
    if not highs:
        return None
    return round(max(highs), 4)


def _extract_next_earnings(cal: Any) -> str | None:
    """Best-effort next earnings date from a Ticker.calendar payload.

    yfinance's ``calendar`` property returns a dict whose ``Earnings Date``
    key is sometimes a list of 1-2 dates (confirmed + tentative) and
    sometimes a single date. In yfinance 1.6.0 the list elements are
    ``datetime.date`` instances (not ``datetime.datetime``); older
    versions returned ``datetime.datetime``. ``datetime`` is a subclass
    of ``date``, so checking ``isinstance(ed, date)`` covers both.
    Returns None on any failure so the caller never raises - per the
    project's "never fabricate" rule, missing values stay None and the
    UI shows "-".
    """
    if not isinstance(cal, dict):
        return None
    ed = cal.get("Earnings Date")
    if isinstance(ed, (list, tuple)) and ed:
        ed = ed[0]
    # datetime.datetime is a subclass of datetime.date, so the broader
    # `date` check covers both the yfinance 1.6.0 datetime.date shape
    # and older versions' datetime.datetime shape. Both have
    # .isoformat(); strip time portion if present.
    if isinstance(ed, date):
        return ed.isoformat()[:10]
    if isinstance(ed, str):
        return ed[:10]
    return None


@functools.lru_cache(maxsize=128)
def _info_cached(sym_upper: str, ts_bucket: int) -> tuple[Any, Any, Any, Any, Any]:
    """Cached per-symbol Ticker.info + calendar fetch (5-min buckets).

    Returns (sector, marketcap, forward_pe, forward_peg, next_earnings).
    All failures resolve to None so the caller never has to handle
    exceptions.  lru_cache(maxsize=128) bounds memory; ts_bucket key
    invalidates the cache every _INFO_CACHE_BUCKET_S seconds.  Uses a
    single Ticker instance per fetch so the cached entry represents one
    round-trip to yfinance (was two before - separate info + calendar
    Tickers, even when called from the same cache entry).
    """
    sector: Any = None
    marketcap: Any = None
    forward_pe: Any = None
    forward_peg: Any = None
    next_earnings: Any = None
    try:
        import yfinance as yf
        t = yf.Ticker(sym_upper)
        info = t.info if hasattr(t, "info") and t.info else {}
        if isinstance(info, dict):
            sector = info.get("sector")
            marketcap = _to_float(info.get("marketCap"))
            forward_pe = _to_float(info.get("forwardPE"))
            # pegRatio vs "forwardPegRatio" varies by yfinance version - prefer
            # the explicit forward-peg field, fall back to generic pegRatio.
            forward_peg = _to_float(info.get("forwardPegRatio")) or _to_float(info.get("pegRatio"))
        cal = t.calendar if hasattr(t, "calendar") else None
        next_earnings = _extract_next_earnings(cal)
    except Exception:
        pass
    return (sector, marketcap, forward_pe, forward_peg, next_earnings)


def get_info_snapshot(sym: str) -> dict[str, Any]:
    """Return fundamentals dict for one symbol, cached for 5 minutes.

    Empty/garbage symbols short-circuit to all-None without hitting the
    cache key (lru_cache requires hashable inputs).
    """
    sym = (sym or "").strip().upper()
    if not sym:
        return {"sector": None, "marketcap": None, "forward_pe": None,
                "forward_peg": None, "next_earnings": None}
    bucket = int(time.time() // _INFO_CACHE_BUCKET_S)
    sector, marketcap, forward_pe, forward_peg, next_earnings = _info_cached(sym, bucket)
    return {"sector": sector, "marketcap": marketcap, "forward_pe": forward_pe,
            "forward_peg": forward_peg, "next_earnings": next_earnings}


def reorder_holdings(pid: str, order: list[str]) -> dict[str, Any]:
    """Reorder the holdings list for portfolio ``pid`` according to ``order``.

    ``order`` must be a permutation of the current non-cash holdings' symbols
    (no additions, removals, or duplicates). Cash rows (``kind == "cash"``)
    are NOT included in ``order`` — they always trail at the end.

    Returns the updated portfolio dict.

    Raises ``ValueError`` if ``order`` is not a permutation of the current
    non-cash symbol set; the caller maps that to HTTP 400.
    Raises ``KeyError`` if ``pid`` is unknown.
    """
    state = load_portfolios()
    p = _get_portfolio(state, pid)

    non_cash = [h for h in p["holdings"] if h.get("kind") != "cash"]
    cash_rows = [h for h in p["holdings"] if h.get("kind") == "cash"]

    current_syms = [h.get("symbol") for h in non_cash]

    if not isinstance(order, list) or set(order) != set(current_syms) or len(order) != len(current_syms):
        raise ValueError("order must be a permutation of existing holding symbols")

    # Build a symbol → holding map for fast lookup.
    sym_map = {h.get("symbol"): h for h in non_cash}
    p["holdings"] = [sym_map[s] for s in order] + cash_rows

    save_portfolios(state)
    _patch_dashboard_cache(state)
    return p


def enrich_portfolios(state: dict[str, Any]) -> dict[str, Any]:
    """Merge live yfinance quotes + fundamentals + history into each holding.

    Adds the following to each non-cash holding:
        last_price      - latest close (from 7-day bulk history)
        pct_daily       - % change vs prior close (from 7-day bulk history)
        pct_7d          - % change 7 trading days ago
        pct_30d         - % change 30 trading days ago
        high_52w        - highest close in the past ~260 trading days
        sector          - company sector (Ticker.info)
        marketcap       - market capitalization (Ticker.info)
        forward_pe      - forward PE ratio (Ticker.info)
        forward_peg     - forward PEG ratio (Ticker.info)
        next_earnings   - next earnings date YYYY-MM-DD (Ticker.calendar)

    Cash rows pass through unchanged. Missing values stay None (no
    exception) - per the project "never fabricate" rule. Pure function:
    mutates the holdings dicts in-place and returns the same state object.
    """
    from . import market
    symbols: list[str] = []
    for p in state.get("portfolios", {}).values():
        for h in p.get("holdings", []):
            sym = h.get("symbol")
            if sym and h.get("kind") != "cash" and sym not in symbols:
                symbols.append(sym)
    if not symbols:
        return state
    quotes = market._quote_snapshot(symbols)
    # 260-day bulk history covers pct_7d, pct_30d, and 52w high in one download.
    histories = market.get_histories_bulk(symbols, days=260)
    # Per-symbol fundamentals (sector, marketcap, valuation, earnings date).
    # Cached 5 min via lru_cache so a portfolio re-render within the bucket
    # is instant; cold-cache cost is one HTTP per unique symbol.
    info_map = {s: get_info_snapshot(s) for s in symbols}
    for p in state.get("portfolios", {}).values():
        for h in p.get("holdings", []):
            sym = h.get("symbol")
            if not sym or h.get("kind") == "cash":
                continue
            q = quotes.get(sym) or {}
            h["last_price"] = q.get("price")
            h["pct_daily"] = q.get("pct_change")
            hist = histories.get(sym) or []
            h["pct_7d"] = _pct_change(hist, 7)
            h["pct_30d"] = _pct_change(hist, 30)
            h["high_52w"] = _52w_high(hist)
            info = info_map.get(sym) or {}
            h["sector"] = info.get("sector")
            h["marketcap"] = info.get("marketcap")
            h["forward_pe"] = info.get("forward_pe")
            h["forward_peg"] = info.get("forward_peg")
            h["next_earnings"] = info.get("next_earnings")
    return state
