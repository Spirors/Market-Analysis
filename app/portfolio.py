"""Portfolio data layer: CRUD on data/portfolios.json.

Persistence: single file holding all portfolios plus per-section column
prefs (visibility + order). Atomic writes via store.save_json. Live
price enrichment is done at serve time by the API layer.
"""

from __future__ import annotations

import re
from typing import Any

from . import config, earnings, store

PORTFOLIOS_PATH = config.DATA_DIR / "portfolios.json"

DEFAULT_COLUMN_ORDER: dict[str, list[str]] = {
    "earnings":  ["symbol", "date", "price", "pct_daily", "pct_7d", "high_52w", "forward_pe", "forward_peg", "market_cap_fmt", "sector", "rec"],
    "portfolio": ["symbol", "shares", "total_cost", "last_price", "total_value", "gain_loss", "pct_daily"],
}

DEFAULT_COLUMN_VISIBILITY: dict[str, dict[str, bool]] = {
    "earnings":  {"symbol": True, "date": True, "price": True, "pct_daily": True, "pct_7d": True, "high_52w": True, "forward_pe": True, "forward_peg": False, "market_cap_fmt": False, "sector": False, "rec": True},
    "portfolio": {"symbol": True, "shares": True, "total_cost": True, "last_price": True, "total_value": True, "gain_loss": True, "pct_daily": True},
}


def _default_state() -> dict[str, Any]:
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
    return {"id": pid, "portfolio": state["portfolios"][pid]}


def delete_portfolio(pid: str) -> bool:
    state = load_portfolios()
    if pid not in state["portfolios"]:
        return False
    del state["portfolios"][pid]
    save_portfolios(state)
    return True


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
    validation = earnings.validate_symbol(symbol)
    if not validation.get("valid"):
        raise ValueError(validation.get("reason") or "invalid symbol")
    state = load_portfolios()
    p = _get_portfolio(state, pid)
    if any(h.get("symbol") == symbol for h in p["holdings"]):
        raise ValueError(f"{symbol} already in portfolio")
    holding = {"symbol": symbol, "shares": float(shares), "total_cost": float(total_cost)}
    p["holdings"].append(holding)
    save_portfolios(state)
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
            return h
    return None


def enrich_portfolios(state: dict[str, Any]) -> dict[str, Any]:
    """Merge live yfinance quotes into each ticker holding. Pure function.

    Adds `last_price` and `pct_daily` to each non-cash holding. Cash rows
    pass through unchanged. Missing quotes stay None (no exception).
    """
    from . import market
    symbols: list[str] = []
    for p in state.get("portfolios", {}).values():
        for h in p.get("holdings", []):
            sym = h.get("symbol")
            if sym and h.get("kind") != "cash" and sym not in symbols:
                symbols.append(sym)
    quotes = market._quote_snapshot(symbols) if symbols else {}
    for p in state.get("portfolios", {}).values():
        for h in p.get("holdings", []):
            sym = h.get("symbol")
            if not sym or h.get("kind") == "cash":
                continue
            q = quotes.get(sym) or {}
            h["last_price"] = q.get("price")
            h["pct_daily"] = q.get("pct_change")
    return state
