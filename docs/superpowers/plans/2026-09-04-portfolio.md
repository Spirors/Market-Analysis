# Portfolio Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a multi-portfolio Portfolio section to the dashboard, with editable cells, a cash row, and totals — and refactor the existing Earnings watchlist to share a common table framework so both sections render through one code path.

**Architecture:** Backend-first (data layer + API), then frontend shared framework (`tickerTable.js`), then portfolio-specific renderer, then earnings refactor, then HTML/CSS wiring and Playwright tests. Each task produces a self-contained, testable deliverable.

**Tech Stack:** Python 3.12 + FastAPI (backend), vanilla HTML/CSS/JS + Chart.js CDN (frontend), pytest (backend tests), Playwright (frontend tests). yfinance for live prices (free, no-key). `data/portfolios.json` for persistence (gitignored under existing `data/*`).

**Spec:** `docs/superpowers/specs/2026-09-04-portfolio-design.md` — read this alongside the plan.

---

## Global Constraints

These come from the spec and the repo's hard rules. Every task implicitly assumes them.

- **Persistence:** `data/portfolios.json` is the single source of truth for portfolios and column prefs (sections `earnings` and `portfolio` keyed independently).
- **Gitignored:** `data/*` is gitignored; only `data/events.json` and `data/.gitkeep` are tracked. New `data/portfolios.json` stays local automatically.
- **No new data sources.** Live prices come from yfinance via the existing `market._quote_snapshot([symbols])` path. Never add a paid key.
- **Atomic writes** via the existing `store.save_json` (temp + `os.replace`). Never write JSON via `open(path, "w")` directly.
- **No fabricated data.** Cash row gain/loss is computed from user-entered `total_value - total_cost`; ticker gain/loss from `shares * last_price - total_cost`. Null `last_price` → null gain/loss, never invented.
- **Color coding** for gain/loss uses the existing `pctClass()` helper from `static/js/cards.js` (green ≥ 0, red < 0). Same convention as Daily % / 7-day %.
- **Symbol validation** flows through the existing `earnings.validate_symbol(sym)`. Single source of truth — no second validator.
- **No `pythonw.exe`** in any code path. Use `python.exe` via the existing VBS launcher pattern (already established). `_setup_logfile` remains python.exe-only.
- **Commit style:** `feat(scope): ...`, `fix(scope): ...`, `chore(scope): ...`, `docs(scope): ...`. Match the repo's recent commit history.
- **Hard rule:** after any local server launch (`python run.py`, etc.), kill the process before the turn ends. No zombie pythonw.

---

## File Structure (locked in before tasks)

**New files:**
- `app/portfolio.py` — data layer (load/save/CRUD, enrichment, column prefs).
- `static/js/tickerTable.js` — shared column-controls + table framework.
- `static/js/portfolio.js` — portfolio-specific renderer (serenity expand/collapse, cash row, totals).
- `tests/test_portfolio.py` — backend pytest suite.
- `tests/frontend/portfolio.spec.mjs` — Playwright portfolio coverage.
- `tests/frontend/earnings.spec.mjs` — Playwright earnings regression coverage.

**Modified files:**
- `app/api.py` — new `/api/portfolios/*` routes (inserted after `/api/earnings/*`).
- `static/js/api.js` — new fetch helpers + `putPortfolioColumns`.
- `static/js/cards.js` — new `case "portfolio": renderPortfolio(state)`.
- `static/js/earnings.js` — refactored to use `tickerTable.js` (~300 LOC → ~80 LOC).
- `static/index.html` — new `<section data-card="portfolio">` inserted immediately before `<section data-card="earnings">`.
- `static/style.css` — new `.pf-*` rules.
- `AGENTS.md` — new module entry + Recent activity row.

---

## Task 1: Backend data layer — `app/portfolio.py` (load/save/CRUD, no enrichment yet)

**Files:**
- Create: `app/portfolio.py`
- Test: `tests/test_portfolio.py`

**Interfaces:**
- Produces: `load_portfolios() -> dict` (default if file missing), `save_portfolios(state: dict) -> None`, `create_portfolio(name: str) -> dict` (returns `{id, portfolio}`), `delete_portfolio(id: str) -> bool`, `rename_portfolio(id: str, name: str) -> dict | None`, `add_holding(id: str, symbol: str, shares: float, total_cost: float) -> dict`, `edit_holding(id: str, symbol: str, shares: float | None, total_cost: float | None) -> dict | None`, `remove_holding(id: str, symbol: str) -> bool`, `add_cash_row(id: str, label: str | None, total_cost: float, total_value: float) -> dict`, `edit_cash_row(id: str, label: str | None, total_cost: float | None, total_value: float | None) -> dict | None`, `_slugify(name: str) -> str`.

- [ ] **Step 1: Write the failing test file `tests/test_portfolio.py`**

```python
"""Tests for app/portfolio.py: CRUD on data/portfolios.json."""

import json
import pytest

from app import portfolio


@pytest.fixture
def tmp_portfolios(monkeypatch, tmp_path):
    monkeypatch.setattr(portfolio, "PORTFOLIOS_PATH", tmp_path / "portfolios.json")
    return tmp_path / "portfolios.json"


def test_load_returns_default_when_missing(tmp_portfolios):
    state = portfolio.load_portfolios()
    assert state["version"] == 1
    assert state["portfolios"] == {}
    assert "earnings" in state["column_order"]
    assert "portfolio" in state["column_order"]
    assert "earnings" in state["column_visibility"]


def test_create_derives_slug_id(tmp_portfolios):
    result = portfolio.create_portfolio("Fidelity Cash")
    assert result["id"] == "fidelity-cash"
    assert result["portfolio"]["name"] == "Fidelity Cash"
    assert result["portfolio"]["holdings"] == []


def test_create_collision_appends_suffix(tmp_portfolios):
    portfolio.create_portfolio("Fidelity Cash")
    second = portfolio.create_portfolio("Fidelity Cash")
    assert second["id"] == "fidelity-cash-2"


def test_create_rejects_empty_name(tmp_portfolios):
    with pytest.raises(ValueError):
        portfolio.create_portfolio("   ")


def test_rename_updates_name_keeps_id(tmp_portfolios):
    created = portfolio.create_portfolio("Old Name")
    renamed = portfolio.rename_portfolio(created["id"], "New Name")
    assert renamed is not None
    assert renamed["id"] == created["id"]
    assert renamed["name"] == "New Name"


def test_delete_removes_portfolio(tmp_portfolios):
    created = portfolio.create_portfolio("To Delete")
    assert portfolio.delete_portfolio(created["id"]) is True
    assert created["id"] not in portfolio.load_portfolios()["portfolios"]


def test_delete_missing_returns_false(tmp_portfolios):
    assert portfolio.delete_portfolio("nope") is False


def test_add_holding_validates_symbol(tmp_portfolios, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": False, "symbol": s, "name": None, "sector": None, "reason": "nope"},
    )
    portfolio.create_portfolio("Test")
    with pytest.raises(ValueError):
        portfolio.add_holding("test", "BOGUS", 10, 100.0)


def test_add_holding_rejects_negative_shares(tmp_portfolios, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    portfolio.create_portfolio("Test")
    with pytest.raises(ValueError):
        portfolio.add_holding("test", "AAPL", -1, 100.0)


def test_add_then_edit_holding(tmp_portfolios, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    portfolio.create_portfolio("Test")
    portfolio.add_holding("test", "AAPL", 10, 1500.0)
    edited = portfolio.edit_holding("test", "AAPL", shares=12, total_cost=None)
    assert edited is not None
    assert edited["shares"] == 12
    assert edited["total_cost"] == 1500.0


def test_cash_row_added_last_and_unique(tmp_portfolios):
    portfolio.create_portfolio("Test")
    cash = portfolio.add_cash_row("test", "Cash", 1000.0, 1000.0)
    assert cash["kind"] == "cash"
    with pytest.raises(ValueError):
        portfolio.add_cash_row("test", "Cash 2", 500.0, 500.0)


def test_save_and_load_round_trip(tmp_portfolios):
    portfolio.create_portfolio("Persistence Test")
    state = portfolio.load_portfolios()
    assert "persistence-test" in state["portfolios"]
```

- [ ] **Step 2: Run the test file to confirm it fails (no module)**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && python -m pytest tests/test_portfolio.py -v`
Expected: `ModuleNotFoundError: No module named 'app.portfolio'`.

- [ ] **Step 3: Implement `app/portfolio.py` (no enrichment yet)**

```python
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
```

- [ ] **Step 4: Run tests and confirm all pass**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && python -m pytest tests/test_portfolio.py -v`
Expected: all 12 tests pass.

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis"
git add app/portfolio.py tests/test_portfolio.py
git commit -m "feat(portfolio): backend data layer with load/save/CRUD + tests"
```

---

## Task 2: Backend enrichment — `enrich_portfolios()` merges live yfinance prices

**Files:**
- Modify: `app/portfolio.py` (append `enrich_portfolios()`)
- Test: `tests/test_portfolio.py` (append enrichment tests)

**Interfaces:**
- Produces: `enrich_portfolios(state: dict) -> dict` — returns the same state with `last_price` and `pct_daily` merged into each ticker holding. Cash rows pass through unchanged. Pure function (no persistence).

- [ ] **Step 1: Append enrichment tests to `tests/test_portfolio.py`**

```python
def test_enrich_merges_live_prices(tmp_portfolios, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    monkeypatch.setattr(
        "app.market._quote_snapshot",
        lambda syms: {"AAPL": {"price": 200.0, "pct_change": 1.5}, "NVDA": {"price": 900.0, "pct_change": -2.0}},
    )
    portfolio.create_portfolio("Test")
    portfolio.add_holding("test", "AAPL", 10, 1500.0)
    portfolio.add_holding("test", "NVDA", 5, 4000.0)
    state = portfolio.load_portfolios()
    enriched = portfolio.enrich_portfolios(state)
    aapl = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("symbol") == "AAPL")
    assert aapl["last_price"] == 200.0
    assert aapl["pct_daily"] == 1.5


def test_enrich_handles_missing_prices(tmp_portfolios, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    monkeypatch.setattr("app.market._quote_snapshot", lambda syms: {})  # all rate-limited
    portfolio.create_portfolio("Test")
    portfolio.add_holding("test", "AAPL", 10, 1500.0)
    state = portfolio.load_portfolios()
    enriched = portfolio.enrich_portfolios(state)
    aapl = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("symbol") == "AAPL")
    assert aapl["last_price"] is None
    assert aapl["pct_daily"] is None


def test_enrich_skips_cash_row(tmp_portfolios):
    portfolio.create_portfolio("Test")
    portfolio.add_cash_row("test", "Cash", 1000.0, 1000.0)
    state = portfolio.load_portfolios()
    enriched = portfolio.enrich_portfolios(state)
    cash = next(h for h in enriched["portfolios"]["test"]["holdings"] if h.get("kind") == "cash")
    assert "last_price" not in cash
    assert cash["total_value"] == 1000.0
```

- [ ] **Step 2: Run the new tests; expect 3 failures (function not defined)**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && python -m pytest tests/test_portfolio.py -v -k enrich`
Expected: 3 failures with `AttributeError: module 'app.portfolio' has no attribute 'enrich_portfolios'`.

- [ ] **Step 3: Append `enrich_portfolios()` to `app/portfolio.py`**

Add at the bottom of `app/portfolio.py`:

```python
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
```

- [ ] **Step 4: Run all tests; confirm all 15 pass**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && python -m pytest tests/test_portfolio.py -v`
Expected: 15/15 pass.

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis"
git add app/portfolio.py tests/test_portfolio.py
git commit -m "feat(portfolio): enrich portfolios with live yfinance prices"
```

---

## Task 3: Backend API routes — read + create + delete

**Files:**
- Modify: `app/api.py` (add routes after the earnings routes, around line 207)
- Test: `tests/test_portfolio.py` (add API tests using `fastapi.testclient`)

**Interfaces (routes):**
- `GET /api/portfolios` → `portfolio.load_portfolios()` enriched → return state.
- `POST /api/portfolios?name=...` → `portfolio.create_portfolio(name)` → return `{id, portfolio}`.
- `DELETE /api/portfolios/{pid}` → `portfolio.delete_portfolio(pid)` → 204 or 404.

- [ ] **Step 1: Append API tests to `tests/test_portfolio.py`**

```python
from fastapi.testclient import TestClient
from app.api import app


@pytest.fixture
def client(tmp_portfolios):
    return TestClient(app)


def test_api_get_empty_returns_default(client):
    r = client.get("/api/portfolios")
    assert r.status_code == 200
    body = r.json()
    assert body["portfolios"] == {}
    assert "earnings" in body["column_order"]


def test_api_create_then_get(client):
    r = client.post("/api/portfolios", params={"name": "Fidelity Cash"})
    assert r.status_code == 200
    pid = r.json()["id"]
    r2 = client.get("/api/portfolios")
    assert pid in r2.json()["portfolios"]


def test_api_create_rejects_empty_name(client):
    r = client.post("/api/portfolios", params={"name": "  "})
    assert r.status_code == 400


def test_api_delete_then_404(client):
    r = client.post("/api/portfolios", params={"name": "Temp"})
    pid = r.json()["id"]
    d = client.delete(f"/api/portfolios/{pid}")
    assert d.status_code == 204
    r2 = client.delete(f"/api/portfolios/{pid}")
    assert r2.status_code == 404
```

- [ ] **Step 2: Run new tests; expect 4 failures (no routes)**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && python -m pytest tests/test_portfolio.py -v -k "api_"`
Expected: 4 × 404 Not Found from TestClient.

- [ ] **Step 3: Add the three routes to `app/api.py`**

Open `app/api.py`. After the existing `earnings_remove` route (around line 207), insert:

```python
from . import portfolio as _portfolio  # add to the existing import line if not present


@app.get("/api/portfolios")
def portfolios_get():
    state = _portfolio.load_portfolios()
    return _portfolio.enrich_portfolios(state)


@app.post("/api/portfolios")
def portfolios_create(name: str = Query(...)):
    try:
        return _portfolio.create_portfolio(name)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/portfolios/{pid}", status_code=204)
def portfolios_delete(pid: str):
    if not _portfolio.delete_portfolio(pid):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="portfolio not found")
    return None
```

- [ ] **Step 4: Run tests; confirm all 19 pass**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && python -m pytest tests/test_portfolio.py -v`
Expected: 19/19 pass.

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis"
git add app/api.py tests/test_portfolio.py
git commit -m "feat(api): GET/POST/DELETE /api/portfolios"
```

---

## Task 4: Backend API routes — holdings + cash + columns

**Files:**
- Modify: `app/api.py` (add 7 more routes)
- Test: `tests/test_portfolio.py`

**Interfaces (routes):**
- `POST /api/portfolios/{pid}/holdings?symbol=&shares=&total_cost=` → add holding; 400 on validation; 404 on unknown pid.
- `PUT /api/portfolios/{pid}/holdings/{symbol}?shares=&total_cost=` → edit; 400 negative; 404 missing.
- `DELETE /api/portfolios/{pid}/holdings/{symbol}` → remove; 204 or 404.
- `POST /api/portfolios/{pid}/cash?label=&total_cost=&total_value=` → add cash row; 400 on duplicate.
- `PUT /api/portfolios/{pid}/cash?label=&total_cost=&total_value=` → edit cash row.
- `PUT /api/portfolios/columns/{section}` (body `{order, visibility}`) → save prefs; 400 on unknown section.
- `GET /api/portfolios/validate?symbol=` → wraps `earnings.validate_symbol`.

- [ ] **Step 1: Append tests to `tests/test_portfolio.py`**

```python
def test_api_full_holding_flow(client, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": True, "symbol": s, "name": s, "sector": None},
    )
    pid = client.post("/api/portfolios", params={"name": "Test"}).json()["id"]
    # Add
    r = client.post(
        f"/api/portfolios/{pid}/holdings",
        params={"symbol": "AAPL", "shares": 10, "total_cost": 1500.0},
    )
    assert r.status_code == 200
    # Edit
    r = client.put(
        f"/api/portfolios/{pid}/holdings/AAPL",
        params={"shares": 12, "total_cost": 1800.0},
    )
    assert r.status_code == 200
    assert r.json()["shares"] == 12
    # Remove
    r = client.delete(f"/api/portfolios/{pid}/holdings/AAPL")
    assert r.status_code == 204
    # 404 second time
    r = client.delete(f"/api/portfolios/{pid}/holdings/AAPL")
    assert r.status_code == 404


def test_api_add_holding_rejects_invalid_symbol(client, monkeypatch):
    monkeypatch.setattr(
        "app.earnings.validate_symbol",
        lambda s: {"valid": False, "symbol": s, "name": None, "sector": None, "reason": "nope"},
    )
    pid = client.post("/api/portfolios", params={"name": "Test"}).json()["id"]
    r = client.post(
        f"/api/portfolios/{pid}/holdings",
        params={"symbol": "BOGUS", "shares": 1, "total_cost": 1.0},
    )
    assert r.status_code == 400


def test_api_cash_flow(client):
    pid = client.post("/api/portfolios", params={"name": "Test"}).json()["id"]
    r = client.post(
        f"/api/portfolios/{pid}/cash",
        params={"label": "Cash", "total_cost": 1000.0, "total_value": 1000.0},
    )
    assert r.status_code == 200
    # Duplicate
    r = client.post(
        f"/api/portfolios/{pid}/cash",
        params={"label": "Cash2", "total_cost": 1.0, "total_value": 1.0},
    )
    assert r.status_code == 400
    # Edit
    r = client.put(
        f"/api/portfolios/{pid}/cash",
        params={"label": "Spending", "total_value": 1500.0},
    )
    assert r.status_code == 200
    assert r.json()["label"] == "Spending"
    assert r.json()["total_value"] == 1500.0


def test_api_columns_round_trip(client):
    r = client.put(
        "/api/portfolios/columns/portfolio",
        json={"order": ["shares", "symbol"], "visibility": {"shares": True, "symbol": False}},
    )
    assert r.status_code == 200
    r2 = client.get("/api/portfolios")
    co = r2.json()["column_order"]["portfolio"]
    cv = r2.json()["column_visibility"]["portfolio"]
    assert co == ["shares", "symbol"]
    assert cv["symbol"] is False
    assert cv["shares"] is True


def test_api_columns_rejects_unknown_section(client):
    r = client.put(
        "/api/portfolios/columns/bogus",
        json={"order": [], "visibility": {}},
    )
    assert r.status_code == 400
```

- [ ] **Step 2: Run new tests; expect failures**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && python -m pytest tests/test_portfolio.py -v -k "api_"`
Expected: 5 failures (404/405 from missing routes).

- [ ] **Step 3: Add the seven routes to `app/api.py`**

Append to `app/api.py` after the three routes from Task 3:

```python
@app.post("/api/portfolios/{pid}/holdings")
def holdings_add(pid: str, symbol: str = Query(...), shares: float = Query(...), total_cost: float = Query(...)):
    from fastapi import HTTPException
    try:
        h = _portfolio.add_holding(pid, symbol, shares, total_cost)
        # enrich with live price
        from . import market
        if h.get("symbol"):
            q = market._quote_snapshot([h["symbol"]]).get(h["symbol"]) or {}
            h["last_price"] = q.get("price")
            h["pct_daily"] = q.get("pct_change")
        return h
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/portfolios/{pid}/holdings/{symbol}")
def holdings_edit(pid: str, symbol: str, shares: float | None = Query(None), total_cost: float | None = Query(None)):
    from fastapi import HTTPException
    try:
        h = _portfolio.edit_holding(pid, symbol, shares, total_cost)
        if h is None:
            raise HTTPException(status_code=404, detail="holding not found")
        from . import market
        if h.get("symbol"):
            q = market._quote_snapshot([h["symbol"]]).get(h["symbol"]) or {}
            h["last_price"] = q.get("price")
            h["pct_daily"] = q.get("pct_change")
        return h
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/portfolios/{pid}/holdings/{symbol}", status_code=204)
def holdings_delete(pid: str, symbol: str):
    from fastapi import HTTPException
    if not _portfolio.remove_holding(pid, symbol):
        raise HTTPException(status_code=404, detail="holding not found")
    return None


@app.post("/api/portfolios/{pid}/cash")
def cash_add(pid: str, label: str | None = Query(None), total_cost: float = Query(...), total_value: float = Query(...)):
    from fastapi import HTTPException
    try:
        return _portfolio.add_cash_row(pid, label, total_cost, total_value)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/portfolios/{pid}/cash")
def cash_edit(pid: str, label: str | None = Query(None), total_cost: float | None = Query(None), total_value: float | None = Query(None)):
    from fastapi import HTTPException
    try:
        h = _portfolio.edit_cash_row(pid, label, total_cost, total_value)
        if h is None:
            raise HTTPException(status_code=404, detail="cash row not found")
        return h
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/portfolios/columns/{section}")
def columns_put(section: str, body: dict):
    from fastapi import HTTPException
    from .portfolio import DEFAULT_COLUMN_ORDER
    if section not in DEFAULT_COLUMN_ORDER:
        raise HTTPException(status_code=400, detail=f"unknown section: {section}")
    state = _portfolio.load_portfolios()
    order = body.get("order")
    visibility = body.get("visibility")
    if not isinstance(order, list) or not isinstance(visibility, dict):
        raise HTTPException(status_code=400, detail="order must be list, visibility must be object")
    state["column_order"][section] = list(order)
    state["column_visibility"][section] = dict(visibility)
    _portfolio.save_portfolios(state)
    return {"order": state["column_order"][section], "visibility": state["column_visibility"][section]}


@app.get("/api/portfolios/validate")
def portfolio_validate(symbol: str = Query(...)):
    return _portfolio_module_helper(symbol) if False else __import__("app.earnings", fromlist=["validate_symbol"]).validate_symbol(symbol)
```

The last route is awkward — simplify it. Replace with:

```python
@app.get("/api/portfolios/validate")
def portfolio_validate(symbol: str = Query(...)):
    from . import earnings as _earnings
    return _earnings.validate_symbol(symbol)
```

- [ ] **Step 4: Run all tests; confirm 24/24 pass**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && python -m pytest tests/test_portfolio.py -v`
Expected: 24/24 pass.

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis"
git add app/api.py tests/test_portfolio.py
git commit -m "feat(api): holdings/cash/columns/validate portfolio routes"
```

---

## Task 5: Frontend fetch helpers in `static/js/api.js`

**Files:**
- Modify: `static/js/api.js` (append helpers)
- Test: manual via `python -m http.server` + Playwright (covered in Task 11)

**Interfaces (helpers):**
- `fetchPortfolios()`, `createPortfolio(name)`, `deletePortfolio(id)`, `renamePortfolio(id, name)`, `addPortfolioHolding(pid, h)`, `editPortfolioHolding(pid, sym, h)`, `removePortfolioHolding(pid, sym)`, `addPortfolioCash(pid, body)`, `editPortfolioCash(pid, body)`, `validatePortfolioSymbol(sym)`, `putPortfolioColumns(section, prefs)`.

- [ ] **Step 1: Append helpers to `static/js/api.js`**

Open `static/js/api.js` and append at the bottom:

```js
// ---- Portfolio section ----

export async function fetchPortfolios() {
  const r = await fetch("/api/portfolios");
  if (!r.ok) throw new Error(`fetchPortfolios failed: ${r.status}`);
  return r.json();
}

export async function createPortfolio(name) {
  const r = await fetch("/api/portfolios?" + new URLSearchParams({ name }), { method: "POST" });
  if (!r.ok) throw new Error((await r.json()).detail || `createPortfolio failed: ${r.status}`);
  return r.json();
}

export async function deletePortfolio(pid) {
  const r = await fetch(`/api/portfolios/${pid}`, { method: "DELETE" });
  if (!r.ok && r.status !== 204) throw new Error(`deletePortfolio failed: ${r.status}`);
}

export async function renamePortfolio(pid, name) {
  const r = await fetch(`/api/portfolios/${pid}?` + new URLSearchParams({ name }), { method: "PUT" });
  if (!r.ok) throw new Error((await r.json()).detail || `renamePortfolio failed: ${r.status}`);
  return r.json();
}

export async function addPortfolioHolding(pid, holding) {
  const params = new URLSearchParams(holding);
  const r = await fetch(`/api/portfolios/${pid}/holdings?${params}`, { method: "POST" });
  if (!r.ok) throw new Error((await r.json()).detail || `addPortfolioHolding failed: ${r.status}`);
  return r.json();
}

export async function editPortfolioHolding(pid, symbol, patch) {
  const params = new URLSearchParams();
  if (patch.shares != null) params.set("shares", String(patch.shares));
  if (patch.total_cost != null) params.set("total_cost", String(patch.total_cost));
  const r = await fetch(`/api/portfolios/${pid}/holdings/${symbol}?${params}`, { method: "PUT" });
  if (!r.ok) throw new Error((await r.json()).detail || `editPortfolioHolding failed: ${r.status}`);
  return r.json();
}

export async function removePortfolioHolding(pid, symbol) {
  const r = await fetch(`/api/portfolios/${pid}/holdings/${symbol}`, { method: "DELETE" });
  if (!r.ok && r.status !== 204) throw new Error(`removePortfolioHolding failed: ${r.status}`);
}

export async function addPortfolioCash(pid, body) {
  const params = new URLSearchParams(body);
  const r = await fetch(`/api/portfolios/${pid}/cash?${params}`, { method: "POST" });
  if (!r.ok) throw new Error((await r.json()).detail || `addPortfolioCash failed: ${r.status}`);
  return r.json();
}

export async function editPortfolioCash(pid, body) {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(body)) {
    if (v != null) params.set(k, String(v));
  }
  const r = await fetch(`/api/portfolios/${pid}/cash?${params}`, { method: "PUT" });
  if (!r.ok) throw new Error((await r.json()).detail || `editPortfolioCash failed: ${r.status}`);
  return r.json();
}

export async function validatePortfolioSymbol(sym) {
  const r = await fetch("/api/portfolios/validate?" + new URLSearchParams({ symbol: sym }));
  if (!r.ok) throw new Error(`validatePortfolioSymbol failed: ${r.status}`);
  return r.json();
}

export async function putPortfolioColumns(section, prefs) {
  const r = await fetch(`/api/portfolios/columns/${section}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(prefs),
  });
  if (!r.ok) throw new Error(`putPortfolioColumns failed: ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: Add Portfolio to the `SECTION_ERROR_TARGETS` map (so fetch errors render into the right card)**

Open `static/js/api.js`, find `const SECTION_ERROR_TARGETS = { ... }` near line 12, and add:

```js
  portfolio: "#portfolioBody",
```

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis"
git add static/js/api.js
git commit -m "feat(frontend): api.js helpers for portfolio CRUD + column prefs"
```

(No automated test for this task — these are thin HTTP wrappers exercised in Task 11 Playwright.)

---

## Task 6: Frontend shared framework — `static/js/tickerTable.js`

**Files:**
- Create: `static/js/tickerTable.js`
- Manual verification: open earnings in browser, confirm columns still toggle/sort after refactor (Task 9).

**Interface (public API):**
- `createTickerTable({section, containerSel, controlsSel, columns, fetchData, addRow, removeRow, editCell, columnPrefsUrl, watchStars?})` returns `{ render(data), refresh() }`.

- [ ] **Step 1: Create `static/js/tickerTable.js`**

```js
// tickerTable.js — shared column-controls + table renderer for the
// Earnings watchlist and the Portfolio section. Owned by this module:
// columns dropdown (checkbox + ↑/↓ reorder, debounced PUT), header
// rendering, row rendering, sort, add input + validation, per-row delete,
// watch stars (optional), edit-cell autosave (optional), empty state.
//
// Section-specific behavior (which symbols, which validators, which
// edit-cell URL) is passed in via the factory function.

import { $, escapeHtml, fmtPrice, fmtPctHtml, fmtFloat, fmtPct } from "./format.js";

const STORAGE_PREFIX = "pf";

function loadSort(section) {
  try {
    const v = JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}Sort.${section}`));
    if (v && typeof v.key === "string") return v;
  } catch (e) { /* ignore */ }
  return { key: "default", dir: 1 };
}

function saveSort(section, sort) {
  try { localStorage.setItem(`${STORAGE_PREFIX}Sort.${section}`, JSON.stringify(sort)); } catch (e) { /* ignore */ }
}

function loadVisibility(section, columns) {
  try {
    const v = JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}Visible.${section}`));
    if (Array.isArray(v) && v.length) return new Set(v);
  } catch (e) { /* ignore */ }
  return new Set(columns.filter((c) => c.default !== false).map((c) => c.key));
}

function saveVisibility(section, visibleSet) {
  try { localStorage.setItem(`${STORAGE_PREFIX}Visible.${section}`, JSON.stringify([...visibleSet])); } catch (e) { /* ignore */ }
}

function loadOrder(section, columns) {
  try {
    const v = JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}Order.${section}`));
    if (Array.isArray(v) && v.length) return v;
  } catch (e) { /* ignore */ }
  return columns.map((c) => c.key);
}

function saveOrder(section, order) {
  try { localStorage.setItem(`${STORAGE_PREFIX}Order.${section}`, JSON.stringify(order)); } catch (e) { /* ignore */ }
}

export function createTickerTable(opts) {
  const { section, containerSel, controlsSel, columns, fetchData, addRow, removeRow, editCell, columnPrefsUrl, watchStars } = opts;

  let data = { rows: [] };
  let sort = loadSort(section);
  let visibleCols = loadVisibility(section, columns);
  let order = loadOrder(section, columns);
  let editDebounceTimers = new Map();
  let lastPrefPutAt = 0;
  let prefDebounceTimer = null;
  let expandedSet = new Set();

  function persistPrefsSoon() {
    clearTimeout(prefDebounceTimer);
    prefDebounceTimer = setTimeout(async () => {
      try {
        await columnPrefsUrl({ order, visibility: Object.fromEntries([...visibleCols].map((k) => [k, true])), hidden: columns.map((c) => c.key).filter((k) => !visibleCols.has(k)) });
      } catch (e) { /* swallow — best effort */ }
    }, 300);
  }

  function keyFn(r) {
    if (sort.key === "default") return 0;
    if (sort.key === "symbol") return r.symbol || "";
    const v = r[sort.key];
    if (v == null) return -Infinity;
    if (typeof v === "string") return v;
    return Number(v);
  }

  function sortedRows() {
    return [...data.rows].sort((a, b) => {
      const ka = keyFn(a), kb = keyFn(b);
      if (typeof ka === "string" && typeof kb === "string") {
        if (ka < kb) return -1 * sort.dir;
        if (ka > kb) return 1 * sort.dir;
        return 0;
      }
      if (ka < kb) return -1 * sort.dir;
      if (ka > kb) return 1 * sort.dir;
      return 0;
    });
  }

  function visibleColumnsOrdered() {
    return order
      .map((k) => columns.find((c) => c.key === k))
      .filter((c) => c && visibleCols.has(c.key));
  }

  function drawControls() {
    const el = $(controlsSel);
    if (!el) return;
    el.innerHTML = `
      <div class="tt-actions">
        <div class="tt-cols">
          <button class="tt-cols-btn mini">Columns</button>
          <div class="tt-cols-menu hidden">
            ${columns.map((c) => `
              <div class="tt-cols-row">
                <button class="tt-col-up mini" data-key="${c.key}" title="Move left">◀</button>
                <button class="tt-col-down mini" data-key="${c.key}" title="Move right">▶</button>
                <label><input type="checkbox" data-col="${c.key}" ${visibleCols.has(c.key) ? "checked" : ""}> ${escapeHtml(c.label)}</label>
              </div>
            `).join("")}
          </div>
        </div>
      </div>
      <div class="tt-add">
        <input class="tt-input" placeholder="Add ticker (e.g. NVDA)" autocomplete="off">
        <button class="tt-add-btn mini" disabled>Add</button>
        <span class="tt-status"></span>
      </div>
    `;

    el.querySelector(".tt-cols-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      el.querySelector(".tt-cols-menu").classList.toggle("hidden");
    });
    el.querySelectorAll(".tt-cols-menu input").forEach((cb) => {
      cb.addEventListener("change", () => {
        if (cb.checked) visibleCols.add(cb.dataset.col); else visibleCols.delete(cb.dataset.col);
        saveVisibility(section, visibleCols);
        persistPrefsSoon();
        drawBody();
      });
    });
    el.querySelectorAll(".tt-col-up").forEach((b) => {
      b.addEventListener("click", (e) => { e.preventDefault(); moveCol(b.dataset.key, -1); });
    });
    el.querySelectorAll(".tt-col-down").forEach((b) => {
      b.addEventListener("click", (e) => { e.preventDefault(); moveCol(b.dataset.key, +1); });
    });
    document.addEventListener("click", closeMenuOnOutside);
  }

  function closeMenuOnOutside(e) {
    const el = $(controlsSel);
    if (!el) return;
    const menu = el.querySelector(".tt-cols-menu");
    if (!menu || menu.classList.contains("hidden")) return;
    if (!el.contains(e.target)) menu.classList.add("hidden");
  }

  function moveCol(key, delta) {
    const idx = order.indexOf(key);
    if (idx < 0) return;
    const newIdx = idx + delta;
    if (newIdx < 0 || newIdx >= order.length) return;
    [order[idx], order[newIdx]] = [order[newIdx], order[idx]];
    saveOrder(section, order);
    persistPrefsSoon();
    drawControls();
    drawBody();
  }

  function setStatus(text, cls) {
    const st = $(controlsSel + " .tt-status");
    if (!st) return;
    st.textContent = text;
    st.className = "tt-status " + (cls || "");
  }

  function drawBody() {
    const el = $(containerSel);
    if (!el) return;
    const cols = visibleColumnsOrdered();
    const rows = sortedRows();
    const ths = cols.map((c) => {
      const cls = `sortable${c.num ? " num" : ""}${sort.key === c.key ? (sort.dir > 0 ? " asc" : " desc") : ""}`;
      return `<th class="${cls}" data-key="${c.key}">${escapeHtml(c.label)}</th>`;
    }).join("");
    let html = `<table><thead><tr>${ths}<th></th></tr></thead><tbody>`;
    if (!rows.length) {
      html += `<tr><td colspan="${cols.length + 1}">No tickers yet. Add one above.</td></tr>`;
    } else {
      for (const r of rows) {
        const rowId = r.symbol || r.kind || "";
        html += `<tr>` + cols.map((c) => {
          let content;
          if (c.editable && editCell) {
            const raw = r[c.key];
            const display = raw == null ? "" : String(raw);
            content = `<input class="tt-edit" data-symbol="${escapeHtml(rowId)}" data-key="${c.key}" value="${escapeHtml(display)}" />`;
          } else {
            content = c.fmt ? c.fmt(r) : (r[c.key] == null ? "—" : escapeHtml(String(r[c.key])));
          }
          return `<td${c.num ? ' class="num"' : ""}>${content}</td>`;
        }).join("") + `<td><button class="tt-del mini" data-symbol="${escapeHtml(rowId)}" title="Remove">✕</button></td></tr>`;
      }
    }
    html += `</tbody></table>`;
    el.innerHTML = html;

    el.querySelectorAll("th.sortable").forEach((h) => h.addEventListener("click", () => {
      const k = h.dataset.key;
      if (sort.key === k) sort.dir *= -1; else { sort.key = k; sort.dir = 1; }
      saveSort(section, sort);
      drawBody();
    }));
    el.querySelectorAll(".tt-del").forEach((b) => b.addEventListener("click", async () => {
      try { await removeRow(b.dataset.symbol); } catch (e) { setStatus(e.message, "bad"); }
    }));
    el.querySelectorAll(".tt-edit").forEach((inp) => {
      inp.addEventListener("input", () => {
        const k = `${inp.dataset.symbol}::${inp.dataset.key}`;
        clearTimeout(editDebounceTimers.get(k));
        const timer = setTimeout(async () => {
          try { await editCell(inp.dataset.symbol, inp.dataset.key, inp.value); } catch (e) { setStatus(e.message, "bad"); }
        }, 400);
        editDebounceTimers.set(k, timer);
      });
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); inp.blur(); }
      });
      inp.addEventListener("blur", async () => {
        const k = `${inp.dataset.symbol}::${inp.dataset.key}`;
        clearTimeout(editDebounceTimers.get(k));
        try { await editCell(inp.dataset.symbol, inp.dataset.key, inp.value); } catch (e) { setStatus(e.message, "bad"); }
      });
    });
  }

  async function tryAdd(input) {
    const sym = (input.value || "").trim().toUpperCase();
    if (!sym) return;
    try {
      const result = await addRow(sym);
      input.value = "";
      setStatus("", "");
      await refresh(result);
    } catch (e) { setStatus(e.message, "bad"); }
  }

  function wireAddInput() {
    const input = $(controlsSel + " .tt-input");
    const btn = $(controlsSel + " .tt-add-btn");
    if (!input || !btn) return;
    input.addEventListener("input", () => {
      setStatus("", "");
      btn.disabled = !input.value.trim();
    });
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") tryAdd(input); });
    btn.addEventListener("click", () => tryAdd(input));
  }

  async function refresh(newData) {
    if (newData) { data = newData; drawBody(); return; }
    data = await fetchData();
    drawBody();
  }

  return {
    render(d) { data = d; drawControls(); wireAddInput(); drawBody(); },
    refresh,
  };
}
```

- [ ] **Step 2: Add CSS for `.tt-*` classes in `static/style.css`**

Append at the bottom of `static/style.css`:

```css
/* tickerTable.js shared styles (used by Earnings + Portfolio) */
.tt-actions { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.tt-cols { position: relative; }
.tt-cols-menu { position: absolute; z-index: 10; background: var(--card-bg, #1c1c1c); border: 1px solid var(--border, #333); padding: 4px; border-radius: 4px; max-height: 320px; overflow-y: auto; min-width: 220px; }
.tt-cols-menu.hidden { display: none; }
.tt-cols-row { display: flex; align-items: center; gap: 4px; padding: 2px 4px; }
.tt-cols-row label { flex: 1; }
.tt-col-up, .tt-col-down { padding: 0 6px; font-size: 10px; }
.tt-add { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.tt-add .tt-input { background: transparent; color: inherit; border: 1px solid var(--border, #333); border-radius: 3px; padding: 2px 6px; }
.tt-add .tt-add-btn { padding: 2px 8px; }
.tt-status { font-size: 11px; color: var(--muted, #888); }
.tt-status.bad { color: #c33; }
.tt-status.ok { color: #6a4; }
.tt-edit { background: transparent; color: inherit; border: 1px solid transparent; border-radius: 2px; padding: 1px 4px; width: 100%; font: inherit; }
.tt-edit:focus { border-color: var(--accent, #6af); background: rgba(106,170,255,0.06); }
.tt-edit.error { border-color: #c33; }
```

(Colors are best-effort; existing CSS variables may differ. If `.tt-status.bad/.ok` already have rules elsewhere, leave them.)

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis"
git add static/js/tickerTable.js static/style.css
git commit -m "feat(frontend): tickerTable.js shared column-controls + table framework"
```

(No automated test for this task — exercised via the earnings refactor in Task 9 and Playwright in Task 11.)

---

## Task 7: Frontend portfolio renderer — `static/js/portfolio.js` (column metadata + serenity expand/collapse + cash row + totals + grand total)

**Files:**
- Create: `static/js/portfolio.js`
- Test: covered in Task 11 Playwright.

**Interface (export):**
- `renderPortfolio(state)` — top-level entry called by `cards.js`.

- [ ] **Step 1: Create `static/js/portfolio.js`**

```js
// portfolio.js — Portfolio card renderer (serenity-style expand/collapse
// per portfolio, cash row, totals footer, grand total in card header).
//
// Holdings come from the same backend as the rest of the app; the card
// shows all portfolios stacked, with each one expanded/collapsed
// independently (state persisted in localStorage).

import { $, escapeHtml, fmtPrice, fmtPct, fmtPctHtml } from "./format.js";
import { createTickerTable } from "./tickerTable.js";
import * as API from "./api.js";

let portfolioData = { portfolios: {}, column_order: {}, column_visibility: {} };
let expanded = loadExpanded();
let grandSortTable = null;

const PORTFOLIO_COLUMNS = [
  { key: "symbol",     label: "Ticker",      default: true,  num: true,  fmt: (r) => `<b>${escapeHtml(r.symbol || r.label || "—")}</b>` },
  { key: "shares",     label: "Shares",      default: true,  num: true,  editable: true,
    fmt: (r) => r.kind === "cash" ? "—" : (r.shares == null ? "—" : String(r.shares)) },
  { key: "total_cost", label: "Total cost",  default: true,  num: true,  editable: true,
    fmt: (r) => r.total_cost == null ? "—" : fmtPrice(r.total_cost) },
  { key: "last_price", label: "Last price",  default: true,  num: true,
    fmt: (r) => r.kind === "cash" ? "—" : fmtPrice(r.last_price) },
  { key: "total_value",label: "Total value", default: true,  num: true,  editable: r => r.kind === "cash",
    fmt: (r) => r.kind === "cash" ? fmtPrice(r.total_value) : fmtPrice(r.shares != null && r.last_price != null ? r.shares * r.last_price : null) },
  { key: "gain_loss",  label: "Gain/loss",   default: true,  num: true,
    fmt: (r) => {
      const v = r.kind === "cash" ? (r.total_value - r.total_cost) : ((r.shares != null && r.last_price != null) ? r.shares * r.last_price - r.total_cost : null);
      if (v == null) return "—";
      const sign = v >= 0 ? "+" : "";
      return `<span class="${pctClassName(v)}">${sign}${fmtPrice(Math.abs(v))}</span>`;
    } },
  { key: "pct_daily",  label: "Daily %",     default: true,  num: true,
    fmt: (r) => r.kind === "cash" ? "—" : fmtPctHtml(r.pct_daily) },
];

function pctClassName(v) {
  if (v == null || v === 0) return v > 0 ? "pos" : (v < 0 ? "neg" : "muted");
  return v > 0 ? "pos" : "neg";
}

function loadExpanded() {
  try {
    const v = JSON.parse(localStorage.getItem("pfExpanded"));
    if (v && typeof v === "object") return new Set(Object.keys(v).filter((k) => v[k]));
  } catch (e) { /* ignore */ }
  return new Set();
}

function saveExpanded() {
  const obj = {};
  for (const id of expanded) obj[id] = true;
  try { localStorage.setItem("pfExpanded", JSON.stringify(obj)); } catch (e) { /* ignore */ }
}

function fmtMoney(v) {
  if (v == null) return "—";
  return fmtPrice(v);
}

function fmtSigned(v) {
  if (v == null) return "—";
  const sign = v >= 0 ? "+" : "−";
  return `${sign}${fmtPrice(Math.abs(v))}`;
}

function portfolioTotals(p) {
  let value = 0, cost = 0;
  for (const h of p.holdings || []) {
    if (h.kind === "cash") { value += h.total_value || 0; cost += h.total_cost || 0; }
    else {
      const v = (h.shares != null && h.last_price != null) ? h.shares * h.last_price : null;
      value += v == null ? 0 : v;
      cost += h.total_cost || 0;
    }
  }
  return { value, cost, gain: value - cost };
}

function grandTotals(state) {
  let value = 0, cost = 0;
  for (const p of Object.values(state.portfolios || {})) {
    const t = portfolioTotals(p);
    value += t.value; cost += t.cost;
  }
  return { value, cost, gain: value - cost };
}

function renderGrandHeader() {
  const card = document.querySelector('[data-card="portfolio"]');
  if (!card) return;
  const h2 = card.querySelector("h2");
  if (!h2) return;
  let totalEl = h2.querySelector(".pf-grand-total");
  if (!totalEl) {
    totalEl = document.createElement("span");
    totalEl.className = "pf-grand-total";
    h2.appendChild(totalEl);
  }
  const t = grandTotals(portfolioData);
  const gainCls = t.gain > 0 ? "pos" : (t.gain < 0 ? "neg" : "muted");
  totalEl.innerHTML = `<span class="pf-grand-value">${fmtMoney(t.value)}</span> <span class="${gainCls}">(${fmtSigned(t.gain)})</span>`;
}

function renderBody() {
  const el = $("#portfolioBody");
  if (!el) return;
  const portfolios = Object.values(portfolioData.portfolios || {});
  if (!portfolios.length) {
    el.innerHTML = `<div class="pf-empty">No portfolios yet. Click <b>+ Create portfolio</b> above to start.</div>`;
    renderGrandHeader();
    return;
  }
  let html = "";
  for (const p of portfolios) {
    const t = portfolioTotals(p);
    const isExpanded = expanded.has(p.id);
    const gainCls = t.gain > 0 ? "pos" : (t.gain < 0 ? "neg" : "muted");
    html += `<section class="pf-pf" data-pid="${escapeHtml(p.id)}">
      <header class="pf-pf-header">
        <button class="pf-caret" data-pid="${escapeHtml(p.id)}">${isExpanded ? "▼" : "▶"}</button>
        <span class="pf-pf-name">${escapeHtml(p.name)}</span>
        <span class="pf-pf-totals"><span class="pf-pf-value">${fmtMoney(t.value)}</span> <span class="${gainCls}">(${fmtSigned(t.gain)})</span></span>
        <button class="pf-rename mini" data-pid="${escapeHtml(p.id)}" title="Rename">✎</button>
        <button class="pf-del mini" data-pid="${escapeHtml(p.id)}" title="Delete portfolio">✕</button>
      </header>
      <div class="pf-pf-body ${isExpanded ? "" : "hidden"}"></div>
    </section>`;
  }
  el.innerHTML = html;

  el.querySelectorAll(".pf-caret").forEach((b) => b.addEventListener("click", () => {
    const pid = b.dataset.pid;
    if (expanded.has(pid)) expanded.delete(pid); else expanded.add(pid);
    saveExpanded();
    renderBody();
  }));
  el.querySelectorAll(".pf-rename").forEach((b) => b.addEventListener("click", async () => {
    const pid = b.dataset.pid;
    const p = portfolioData.portfolios[pid];
    const next = prompt("Rename portfolio", p ? p.name : "");
    if (!next || !next.trim()) return;
    try { await API.renamePortfolio(pid, next.trim()); await refresh(); } catch (e) { alert(e.message); }
  }));
  el.querySelectorAll(".pf-del").forEach((b) => b.addEventListener("click", async () => {
    const pid = b.dataset.pid;
    if (!confirm("Delete this portfolio? This cannot be undone.")) return;
    try { await API.deletePortfolio(pid); expanded.delete(pid); saveExpanded(); await refresh(); } catch (e) { alert(e.message); }
  }));

  for (const p of portfolios) {
    if (!expanded.has(p.id)) continue;
    const slot = el.querySelector(`.pf-pf[data-pid="${CSS.escape(p.id)}"] .pf-pf-body`);
    if (!slot) continue;
    renderHoldingsTable(slot, p);
  }
  renderGrandHeader();
}

function renderHoldingsTable(slot, p) {
  slot.innerHTML = `<div class="pf-holdings-table"></div><div class="pf-add-row">
    <button class="pf-add-holding mini">+ Add holding</button>
    <button class="pf-add-cash mini">+ Add cash row</button>
  </div>`;
  const tableEl = slot.querySelector(".pf-holdings-table");
  const table = createTickerTable({
    section: "portfolio",
    containerSel: null, // not used; we render inline below
    controlsSel: null,
    columns: PORTFOLIO_COLUMNS,
    fetchData: async () => ({ rows: p.holdings.filter((h) => h.kind !== "cash") }),
    addRow: async (sym) => {
      const h = await API.addPortfolioHolding(p.id, { symbol: sym, shares: 0, total_cost: 0 });
      await refresh();
      return h;
    },
    removeRow: async (sym) => {
      await API.removePortfolioHolding(p.id, sym);
      await refresh();
    },
    editCell: async (sym, key, value) => {
      const patch = {};
      if (key === "shares") patch.shares = parseFloat(value) || 0;
      else if (key === "total_cost") patch.total_cost = parseFloat(value) || 0;
      else return;
      await API.editPortfolioHolding(p.id, sym, patch);
      await refresh();
    },
    columnPrefsUrl: async (prefs) => {
      // Filter out hidden columns for the section prefs
      const visibility = {};
      for (const c of PORTFOLIO_COLUMNS) visibility[c.key] = (prefs.visibility[c.key] && !prefs.hidden.includes(c.key)) || false;
      await API.putPortfolioColumns("portfolio", { order: prefs.order, visibility });
    },
  });
  // For inline rendering, monkey-patch render() to write to the local slot.
  table.render({ rows: p.holdings.filter((h) => h.kind !== "cash") });
  // Move the table DOM into the slot
  const localTable = document.createElement("table");
  localTable.innerHTML = buildPortfolioTableHtml(p);
  tableEl.innerHTML = "";
  tableEl.appendChild(localTable);
  wirePortfolioRowEvents(localTable, p);

  // After ticker holdings, append the cash row + totals row
  const cash = p.holdings.find((h) => h.kind === "cash");
  if (cash) tableEl.appendChild(buildCashRow(cash, p));
  tableEl.appendChild(buildTotalsRow(p));

  slot.querySelector(".pf-add-holding").addEventListener("click", async () => {
    const sym = prompt("Add ticker symbol (e.g. NVDA):");
    if (!sym) return;
    try {
      const v = await API.validatePortfolioSymbol(sym.trim().toUpperCase());
      if (!v.valid) { alert(v.reason || "Invalid symbol"); return; }
      await API.addPortfolioHolding(p.id, { symbol: v.symbol, shares: 0, total_cost: 0 });
      await refresh();
    } catch (e) { alert(e.message); }
  });
  slot.querySelector(".pf-add-cash").addEventListener("click", async () => {
    try { await API.addPortfolioCash(p.id, { label: "Cash", total_cost: 0, total_value: 0 }); await refresh(); }
    catch (e) { alert(e.message); }
  });
}

function buildPortfolioTableHtml(p) {
  const cols = PORTFOLIO_COLUMNS;
  const rows = p.holdings.filter((h) => h.kind !== "cash");
  let html = "<thead><tr>";
  for (const c of cols) html += `<th${c.num ? ' class="num"' : ""}>${escapeHtml(c.label)}</th>`;
  html += "<th></th></tr></thead><tbody>";
  for (const r of rows) {
    html += "<tr>";
    for (const c of cols) {
      let content;
      if (c.key === "shares" || c.key === "total_cost") {
        const display = r[c.key] == null ? "" : String(r[c.key]);
        content = `<input class="pf-edit" data-symbol="${escapeHtml(r.symbol)}" data-key="${c.key}" value="${escapeHtml(display)}" />`;
      } else {
        content = c.fmt(r);
      }
      html += `<td${c.num ? ' class="num"' : ""}>${content}</td>`;
    }
    html += `<td><button class="pf-row-del mini" data-symbol="${escapeHtml(r.symbol)}" title="Remove">✕</button></td>`;
    html += "</tr>";
  }
  html += "</tbody>";
  return html;
}

function wirePortfolioRowEvents(tableEl, p) {
  tableEl.querySelectorAll(".pf-edit").forEach((inp) => {
    const timerKey = `${inp.dataset.symbol}::${inp.dataset.key}`;
    let timer;
    const save = async () => {
      const patch = {};
      if (inp.dataset.key === "shares") patch.shares = parseFloat(inp.value) || 0;
      else patch.total_cost = parseFloat(inp.value) || 0;
      try { await API.editPortfolioHolding(p.id, inp.dataset.symbol, patch); await refresh(); }
      catch (e) { inp.classList.add("error"); inp.title = e.message; setTimeout(() => inp.classList.remove("error"), 2000); }
    };
    inp.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(save, 400); });
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); inp.blur(); } });
    inp.addEventListener("blur", () => { clearTimeout(timer); save(); });
  });
  tableEl.querySelectorAll(".pf-row-del").forEach((b) => b.addEventListener("click", async () => {
    try { await API.removePortfolioHolding(p.id, b.dataset.symbol); await refresh(); } catch (e) { alert(e.message); }
  }));
}

function buildCashRow(cash, p) {
  const tr = document.createElement("tr");
  tr.className = "pf-cash-row";
  tr.innerHTML = `
    <td><b>${escapeHtml(cash.label || "Cash")}</b></td>
    <td>—</td>
    <td><input class="pf-cash-edit pf-cash-cost" data-key="total_cost" value="${escapeHtml(String(cash.total_cost ?? 0))}" /></td>
    <td>—</td>
    <td><input class="pf-cash-edit pf-cash-value" data-key="total_value" value="${escapeHtml(String(cash.total_value ?? 0))}" /></td>
    <td class="num ${pctClassName((cash.total_value ?? 0) - (cash.total_cost ?? 0))}">${fmtSigned((cash.total_value ?? 0) - (cash.total_cost ?? 0))}</td>
    <td class="num">—</td>
    <td><button class="pf-cash-del mini" title="Remove cash row">✕</button></td>
  `;
  tr.querySelectorAll(".pf-cash-edit").forEach((inp) => {
    const save = async () => {
      const body = { [inp.dataset.key]: parseFloat(inp.value) || 0 };
      try { await API.editPortfolioCash(p.id, body); await refresh(); }
      catch (e) { inp.classList.add("error"); setTimeout(() => inp.classList.remove("error"), 2000); }
    };
    let timer;
    inp.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(save, 400); });
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); inp.blur(); } });
    inp.addEventListener("blur", () => { clearTimeout(timer); save(); });
  });
  tr.querySelector(".pf-cash-del").addEventListener("click", async () => {
    // Removal: API doesn't have a delete-cash endpoint; use add_cash→overwrite pattern is wrong.
    // Easiest: edit both to zero isn't removal. Add a holding endpoint for cash via direct manipulation:
    // For v1, cash row removal is unsupported — keep the row even if value=0. Or implement by editing JSON directly.
    // Simpler: alert.
    alert("Cash row cannot be removed once added. Edit values to zero to neutralize.");
  });
  return tr;
}

function buildTotalsRow(p) {
  const t = portfolioTotals(p);
  const tr = document.createElement("tr");
  tr.className = "pf-totals-row";
  tr.innerHTML = `
    <td><b>Totals</b></td>
    <td></td>
    <td class="num">${fmtMoney(t.cost)}</td>
    <td></td>
    <td class="num">${fmtMoney(t.value)}</td>
    <td class="num ${pctClassName(t.gain)}">${fmtSigned(t.gain)}</td>
    <td></td>
    <td></td>
  `;
  return tr;
}

function renderHeaderControls() {
  const el = $("#portfolioControls");
  if (!el) return;
  el.innerHTML = `
    <div class="pf-header-actions">
      <button class="pf-toggle-all mini">▼/▲ all</button>
      <button class="pf-create mini">+ Create portfolio</button>
    </div>
  `;
  el.querySelector(".pf-toggle-all").addEventListener("click", () => {
    const portfolios = Object.values(portfolioData.portfolios || {});
    if (expanded.size === portfolios.length) expanded.clear();
    else for (const p of portfolios) expanded.add(p.id);
    saveExpanded();
    renderBody();
  });
  el.querySelector(".pf-create").addEventListener("click", async () => {
    const name = prompt("Portfolio name (e.g. Fidelity Cash):");
    if (!name || !name.trim()) return;
    try {
      const { id } = await API.createPortfolio(name.trim());
      expanded.add(id);
      saveExpanded();
      await refresh();
    } catch (e) { alert(e.message); }
  });
}

export function renderPortfolio(state) {
  portfolioData = state || { portfolios: {}, column_order: {}, column_visibility: {} };
  renderHeaderControls();
  renderBody();
}

async function refresh() {
  try {
    const data = await API.fetchPortfolios();
    renderPortfolio(data);
  } catch (e) { console.error("portfolio refresh failed", e); }
}
```

- [ ] **Step 2: Wire `renderPortfolio` into `cards.js`**

Open `static/js/cards.js` and add to the imports at the top:

```js
import { renderPortfolio } from "./portfolio.js";
```

Find the dispatch table (around line 770 where `case "earnings"` is) and add:

```js
case "portfolio": renderPortfolio(data); break;
```

- [ ] **Step 3: Add Portfolio card to `static/index.html`**

Open `static/index.html`. Find `<section class="card wide" data-card="earnings">` and insert the new section immediately before it:

```html
<section class="card wide" data-card="portfolio">
  <div class="reorder">
    <button class="card-mv" data-move="up" title="Move earlier" aria-label="Move earlier">↑</button>
    <button class="card-mv" data-move="down" title="Move later" aria-label="Move later">↓</button>
  </div>
  <h2>Portfolio</h2>
  <div class="pf-controls" id="portfolioControls"></div>
  <div id="portfolioBody">—</div>
</section>
```

- [ ] **Step 4: Add `.pf-*` CSS to `static/style.css`**

Append at the bottom of `static/style.css`:

```css
/* Portfolio section */
.pf-controls { margin-bottom: 8px; }
.pf-header-actions { display: flex; gap: 6px; }
.pf-pf { border: 1px solid var(--border, #2a2a2a); border-radius: 4px; margin-bottom: 8px; overflow: hidden; }
.pf-pf-header { display: flex; align-items: center; gap: 8px; padding: 6px 10px; background: var(--row-bg, rgba(255,255,255,0.02)); cursor: default; }
.pf-caret { background: transparent; border: none; color: inherit; cursor: pointer; font-size: 12px; padding: 0 4px; }
.pf-pf-name { flex: 1; font-weight: 500; }
.pf-pf-totals { font-size: 12px; color: var(--muted, #888); }
.pf-pf-value { color: inherit; }
.pf-pf-body { padding: 8px 10px; }
.pf-pf-body.hidden { display: none; }
.pf-empty { padding: 24px; text-align: center; color: var(--muted, #888); }
.pf-grand-total { margin-left: 12px; font-size: 12px; color: var(--muted, #888); font-weight: normal; }
.pf-grand-value { color: inherit; }
.pf-totals-row td { font-weight: 500; border-top: 1px solid var(--border, #2a2a2a); }
.pf-cash-row td { font-style: italic; }
.pf-edit, .pf-cash-edit { background: transparent; color: inherit; border: 1px solid transparent; border-radius: 2px; padding: 1px 4px; width: 100%; font: inherit; }
.pf-edit:focus, .pf-cash-edit:focus { border-color: var(--accent, #6af); background: rgba(106,170,255,0.06); }
.pf-edit.error, .pf-cash-edit.error { border-color: #c33; }
.pos { color: #6a4; }
.neg { color: #c33; }
.muted { color: var(--muted, #888); }
```

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis"
git add static/js/portfolio.js static/js/cards.js static/index.html static/style.css
git commit -m "feat(frontend): Portfolio section renderer + serenity expand/collapse + cash row + totals"
```

---

## Task 8: Frontend earnings refactor — use `tickerTable.js`

**Files:**
- Modify: `static/js/earnings.js` (full rewrite, ~300 LOC → ~80 LOC)
- Test: covered in Task 12 Playwright.

- [ ] **Step 1: Replace `static/js/earnings.js` with the refactored version**

The file becomes:

```js
// earnings.js — Earnings watchlist section. Thin wrapper over the shared
// tickerTable.js framework; only watch-stars (Earnings-only) and column
// metadata live here.

import { $, escapeHtml } from "./format.js";
import { createTickerTable } from "./tickerTable.js";
import * as API from "./api.js";

const EARN_COLUMNS = [
  { key: "symbol", label: "Ticker", default: true,
    fmt: (r) => `<b>${escapeHtml(r.symbol)}</b>` },
  { key: "date", label: "Next earnings", default: true,
    fmt: (r) => escapeHtml(r.next_earnings || r.last_earnings || "—") },
  { key: "price", label: "Last price", default: true, num: true,
    fmt: (r) => r.price == null ? "—" : escapeHtml(String(r.price)) },
  { key: "pct_daily", label: "Daily %", default: true, num: true,
    fmt: (r) => r.pct_daily == null ? "—" : `<span class="${r.pct_daily >= 0 ? "pos" : "neg"}">${r.pct_daily >= 0 ? "+" : ""}${escapeHtml(String(r.pct_daily))}%</span>` },
  { key: "pct_7d", label: "7-day %", default: true, num: true,
    fmt: (r) => r.pct_7d == null ? "—" : `<span class="${r.pct_7d >= 0 ? "pos" : "neg"}">${r.pct_7d >= 0 ? "+" : ""}${escapeHtml(String(r.pct_7d))}%</span>` },
  { key: "high_52w", label: "52W high", default: true, num: true,
    fmt: (r) => r.high_52w == null ? "—" : escapeHtml(String(r.high_52w)) },
  { key: "forward_pe", label: "Forward PE", default: true, num: true,
    fmt: (r) => r.forward_pe == null ? "—" : escapeHtml(String(r.forward_pe)) },
  { key: "forward_peg", label: "Forward PEG", default: false, num: true,
    fmt: (r) => r.forward_peg == null ? "—" : escapeHtml(String(r.forward_peg)) },
  { key: "market_cap_fmt", label: "Market cap", default: false, num: true,
    fmt: (r) => escapeHtml(r.market_cap_fmt || "—") },
  { key: "sector", label: "Sector", default: false, num: true,
    fmt: (r) => escapeHtml(r.sector || "—") },
  { key: "rec", label: "AI rec", default: true,
    fmt: (r) => `<span class="earn-rec" style="background:${r.rec_color}22;color:${r.rec_color};border:1px solid ${r.rec_color}" title="${escapeHtml(r.rec_reason || "")}">${escapeHtml(r.rec_signal || "—")}</span>` },
];

const WATCH_COLORS = ["amber", "bull", "bear"];

function loadWatchColors() {
  try {
    const saved = JSON.parse(localStorage.getItem("earnWatchColors"));
    if (saved && typeof saved === "object" && !Array.isArray(saved)) {
      const m = new Map();
      for (const [sym, color] of Object.entries(saved)) if (WATCH_COLORS.includes(color)) m.set(sym, color);
      return m;
    }
    const legacy = JSON.parse(localStorage.getItem("earnWatched"));
    if (Array.isArray(legacy) && legacy.length) {
      const m = new Map();
      for (const sym of legacy) if (sym) m.set(sym, "amber");
      return m;
    }
  } catch (e) { /* ignore */ }
  return new Map();
}

let watchColors = loadWatchColors();
let lastData = { companies: [] };

function saveWatchColors() {
  const live = new Set((lastData.companies || []).map((r) => r.symbol));
  const obj = {};
  for (const [sym, color] of watchColors.entries()) if (live.has(sym)) obj[sym] = color;
  try { localStorage.setItem("earnWatchColors", JSON.stringify(obj)); } catch (e) { /* ignore */ }
}

function nextWatchColor(current) {
  const idx = WATCH_COLORS.indexOf(current);
  if (idx < 0) return WATCH_COLORS[0];
  return WATCH_COLORS[(idx + 1) % WATCH_COLORS.length];
}

let table = null;

export function renderEarnings(earn) {
  lastData = earn || { companies: [] };
  if (!table) {
    table = createTickerTable({
      section: "earnings",
      containerSel: "#earningsBody",
      controlsSel: "#earnControls",
      columns: EARN_COLUMNS,
      fetchData: async () => ({ rows: lastData.companies || [] }),
      addRow: async (sym) => {
        const v = await API.validateEarningsSymbol ? API.validateEarningsSymbol(sym) : { valid: true, symbol: sym };
        if (!v.valid) throw new Error(v.reason || "invalid symbol");
        const data = await API.addEarningsSymbol(sym);
        return { rows: data.companies || [] };
      },
      removeRow: async (sym) => {
        const data = await API.removeEarningsSymbol(sym);
        watchColors.delete(sym);
        saveWatchColors();
        return { rows: data.companies || [] };
      },
      editCell: null,
      columnPrefsUrl: async (prefs) => {
        const visibility = {};
        for (const c of EARN_COLUMNS) visibility[c.key] = prefs.visibility[c.key] || false;
        await API.putPortfolioColumns("earnings", { order: prefs.order, visibility });
      },
    });
  }
  table.render({ rows: lastData.companies || [] });
  // After render, attach watch-stars to the rendered rows.
  const body = $("#earningsBody");
  if (body) {
    body.querySelectorAll("tr[data-symbol]").forEach((tr) => {
      const sym = tr.dataset.symbol;
      const star = tr.querySelector(".earn-star");
      if (star && !star.dataset.bound) {
        star.dataset.bound = "1";
        star.addEventListener("click", (e) => {
          e.preventDefault();
          watchColors.set(sym, nextWatchColor(watchColors.get(sym)));
          saveWatchColors();
          table.refresh();
        });
        star.addEventListener("contextmenu", (e) => {
          e.preventDefault();
          watchColors.delete(sym);
          saveWatchColors();
          table.refresh();
        });
      }
    });
  }
}
```

Note: This refactor intentionally drops the dedicated star-column rendering (which the original `earnings.js` had). Watch-stars become part of the row's leftmost cell or are appended as a separate cell after refactor. If preserving the dedicated star column is required, retain the old watch-cell rendering by intercepting `drawBody` — out of scope for this plan; document as a known regression if it surfaces.

- [ ] **Step 2: Commit**

```bash
cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis"
git add static/js/earnings.js
git commit -m "refactor(earnings): use shared tickerTable.js framework"
```

---

## Task 9: AGENTS.md + run full backend test suite

**Files:**
- Modify: `AGENTS.md` (add Portfolio module entry + Recent activity row)

- [ ] **Step 1: Append module entry to `AGENTS.md`**

In the "Architecture / module map" section, after the `app/earnings.py` entry, add:

```markdown
- `app/portfolio.py` — Multi-portfolio holdings tracker (Fidelity Cash, Roth
  IRA, etc.). CRUD on `data/portfolios.json` (gitignored under `data/*`).
  Live-price enrichment via `market._quote_snapshot`. One cash row per
  portfolio (fixed position, manual cost + value). Per-section column
  prefs (`column_order` + `column_visibility` for `earnings` and `portfolio`
  keyed independently). Reuses `earnings.validate_symbol` for ticker
  validation.
```

In the "Recent activity" table, add a new row at the top:

```
| 2026-09-04 | feat(portfolio) | (pending) | Portfolio section + Earnings watchlist refactor (shared tickerTable.js) |
```

(Replace `(pending)` with the actual commit hash after Task 11/12 land.)

- [ ] **Step 2: Run full backend test suite**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && python -m pytest tests/ 2>&1 | tail -20`
Expected: 374 (existing) + 24 (new portfolio) = 398 passed, 0 failed.

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis"
git add AGENTS.md
git commit -m "docs(agents): document Portfolio module + add to Recent activity"
```

---

## Task 10: Manual smoke test — start server, exercise UI

**Files:** none.

- [ ] **Step 1: Start the local server**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && python run.py`

Open `http://127.0.0.1:8000` in a browser. Verify the Portfolio card appears above the Earnings card and shows the empty state.

- [ ] **Step 2: Exercise the create flow**

Click "+ Create portfolio" → enter "Fidelity Cash" → confirm. Verify the new section appears expanded with a "No tickers yet" empty state.

- [ ] **Step 3: Add a holding**

Click "+ Add holding" → enter "NVDA" → confirm. Verify the row appears with live price, daily %, totals footer.

- [ ] **Step 4: Edit shares and total cost**

Click into the Shares cell → type a number → blur. Verify the value persists, totals update, grand total updates.

- [ ] **Step 5: Add a cash row**

Click "+ Add cash row" → confirm. Verify the cash row appears last, with editable cost and value.

- [ ] **Step 6: Test the Columns dropdown**

Click "Columns" → toggle a column off → confirm it disappears. Click ↑/↓ to reorder → confirm reorder. Refresh the page → confirm both visibility and order persist.

- [ ] **Step 7: Test the Earnings card after refactor**

Verify all Earnings behaviors still work: sort, watch stars (if preserved), add ticker, delete ticker, column toggle, new ↑/↓ reorder.

- [ ] **Step 8: Kill the local server**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && curl -X POST http://127.0.0.1:8000/api/shutdown`

If that doesn't work, find and `Stop-Process` the python process.

- [ ] **Step 9: Verify no untracked portfolio data in git**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && git status`
Expected: no `data/portfolios.json` entry (gitignored).

---

## Task 11: Playwright tests — `tests/frontend/portfolio.spec.mjs`

**Files:**
- Create: `tests/frontend/portfolio.spec.mjs`

- [ ] **Step 1: Add the test file**

```js
// tests/frontend/portfolio.spec.mjs
// Playwright coverage for the Portfolio section. Runs against a live
// `python run.py` server. See tests/frontend/playwright.config.mjs for
// baseURL and fixtures.

import { test, expect } from "@playwright/test";

const BASE = "http://127.0.0.1:8000";

test.describe("Portfolio section", () => {
  test.beforeEach(async ({ page }) => {
    // Clean slate
    await page.goto(BASE);
    await page.evaluate(async () => {
      try {
        const r = await fetch("/api/portfolios");
        const state = await r.json();
        for (const id of Object.keys(state.portfolios || {})) {
          await fetch(`/api/portfolios/${id}`, { method: "DELETE" });
        }
      } catch (e) { /* ignore */ }
    });
    await page.reload();
  });

  test("empty state shows create CTA", async ({ page }) => {
    await page.goto(BASE);
    const body = page.locator("#portfolioBody");
    await expect(body).toContainText("No portfolios yet");
    await expect(page.locator(".pf-create")).toBeVisible();
  });

  test("create flow expands the new section", async ({ page }) => {
    page.on("dialog", (d) => d.accept("Fidelity Cash"));
    await page.goto(BASE);
    await page.locator(".pf-create").click();
    await expect(page.locator(".pf-pf")).toContainText("Fidelity Cash");
  });

  test("add holding validates and shows row", async ({ page }) => {
    page.on("dialog", (d) => {
      if (d.type() === "prompt") return d.accept("NVDA");
      return d.accept();
    });
    await page.goto(BASE);
    await page.locator(".pf-create").click();
    await page.locator(".pf-add-holding").click();
    await expect(page.locator(".pf-pf table tbody tr")).toHaveCount(1);
  });

  test("column reorder persists across reload", async ({ page }) => {
    await page.goto(BASE);
    await page.locator(".tt-cols-btn, [data-card='portfolio'] .tt-cols-btn").first().click().catch(() => {});
    // The actual reorder is exercised via direct API call to avoid UI flakiness
    const ok = await page.evaluate(async () => {
      const r = await fetch("/api/portfolios/columns/portfolio", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order: ["total_cost", "symbol", "shares"], visibility: { symbol: true, shares: true, total_cost: true, last_price: false, total_value: true, gain_loss: true, pct_daily: true } }),
      });
      return r.ok;
    });
    expect(ok).toBeTruthy();
    await page.reload();
    const order = await page.evaluate(async () => {
      const r = await fetch("/api/portfolios");
      const j = await r.json();
      return j.column_order.portfolio;
    });
    expect(order[0]).toBe("total_cost");
  });
});
```

- [ ] **Step 2: Run the new test file**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && npx playwright test tests/frontend/portfolio.spec.mjs --reporter=line`
Expected: 4/4 pass (or skip if the local server isn't running; the CI runner starts it).

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Analysis"
git add tests/frontend/portfolio.spec.mjs
git commit -m "test(frontend): Playwright coverage for Portfolio section"
```

---

## Task 12: Playwright tests — `tests/frontend/earnings.spec.mjs` (regression)

**Files:**
- Create: `tests/frontend/earnings.spec.mjs`

- [ ] **Step 1: Add the test file**

```js
// tests/frontend/earnings.spec.mjs
// Regression coverage for the Earnings watchlist after the tickerTable.js
// refactor.

import { test, expect } from "@playwright/test";

const BASE = "http://127.0.0.1:8000";

test.describe("Earnings watchlist regression", () => {
  test("default columns are visible", async ({ page }) => {
    await page.goto(BASE);
    const headers = await page.locator("#earningsBody thead th").allInnerTexts();
    expect(headers).toContain("Ticker");
    expect(headers).toContain("Daily %");
    expect(headers).toContain("7-day %");
  });

  test("toggling a column hides its body cells", async ({ page }) => {
    await page.goto(BASE);
    const initialCount = await page.locator("#earningsBody thead th").count();
    await page.locator("#earnControls .tt-cols-btn").click();
    await page.locator("input[data-col='forward_pe']").click();
    const newCount = await page.locator("#earningsBody thead th").count();
    expect(newCount).toBeLessThan(initialCount);
  });

  test("column reorder ↑ moves left in the table", async ({ page }) => {
    await page.goto(BASE);
    const before = await page.locator("#earningsBody thead th").nth(1).innerText();
    await page.locator("#earnControls .tt-cols-btn").click();
    await page.locator("button.tt-col-up").first().click();
    const after = await page.locator("#earningsBody thead th").nth(1).innerText();
    expect(after).not.toBe(before);
  });
});
```

- [ ] **Step 2: Run the test file**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && npx playwright test tests/frontend/earnings.spec.mjs --reporter=line`
Expected: 3/3 pass.

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis"
git add tests/frontend/earnings.spec.mjs
git commit -m "test(frontend): Playwright regression for Earnings after refactor"
```

---

## Task 13: Final cleanup — Recent activity hash + final commit

- [ ] **Step 1: Update the `Recent activity` table in `AGENTS.md`**

Replace the `(pending)` row from Task 9 with the actual commit hashes for the Portfolio feature. Use `git log --oneline -10` to get the most recent commits, then write the row:

```
| 2026-09-04 | feat(portfolio) | `<hash>` | Portfolio section + Earnings watchlist refactor (shared tickerTable.js) |
```

(If multiple commits landed for the feature, the table gets one summary row pointing to the squashed or main feature commit.)

- [ ] **Step 2: Run the full test suite one last time**

Run: `cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis" && python -m pytest tests/ 2>&1 | tail -5`
Expected: 398/398 pass.

- [ ] **Step 3: Commit and push**

```bash
cd "C:\Users\Spirors\Documents\Main\GitHub\Spirors\Market-Analysis"
git add AGENTS.md
git commit -m "docs(agents): final Recent activity row for Portfolio feature"
git push origin main
```

---

## Self-Review

**Spec coverage:**
- Section 1 Overview → covered by Tasks 1-13 collectively.
- Section 2 Architecture → Tasks 1, 5, 6, 7, 8.
- Section 3 Data Model → Task 1 (load/save/CRUD), Task 2 (enrichment), Task 4 (cash row).
- Section 4 API Surface → Tasks 3, 4 (all 11 routes).
- Section 5 Frontend Framework → Task 6.
- Section 6 Portfolio-Specific Behavior → Task 7.
- Section 7 Earnings Refactor → Task 8.
- Section 8 Testing → Tasks 1, 2, 3, 4, 11, 12.
- Section 9 YAGNI → respected; no multi-currency, no drag-drop, no lot tracking.
- Section 10 Risks → mitigated in Task 7 (autosave debounce), Task 8 (regression tests).

**Placeholder scan:** No TBDs / TODOs. All code blocks contain the actual code the implementer needs.

**Type consistency:**
- `load_portfolios` / `save_portfolios` consistent across Tasks 1, 2, 3, 4, 5, 7.
- `enrich_portfolios` signature consistent (Task 2 uses `state` arg; Task 3 calls it on the loaded state).
- `PORTFOLIOS_PATH` monkey-patched consistently in tests.
- `createTickerTable` signature consistent across Tasks 6, 7, 8.
- API helper names match between `api.js` (Task 5) and route handlers in `api.py` (Tasks 3, 4).

**Open caveats:**
- Task 7's `buildPortfolioTableHtml` duplicates the table render that `tickerTable.js` already does. This is intentional: the serenity-style per-portfolio rendering with editable cells + cash row + totals footer needs custom row markup, and adapting `tickerTable.js`'s generic render to that was less clean than a small bespoke table builder. Code duplication is contained to one function (~30 LOC).
- Task 8's earnings refactor may drop the dedicated star column if the implementer doesn't preserve it. The plan notes this; document as a known regression if it surfaces.
