"""FastAPI application: JSON API + static dashboard."""

from __future__ import annotations

import os
import threading

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, earnings, regime, service, store

app = FastAPI(title="Market Analysis Tool")

# Delay (seconds) between responding to /api/shutdown and calling os._exit.
# Long enough for FastAPI to flush the JSON response to the client (the
# browser's sendBeacon waits for the response to be queued, not delivered).
_SHUTDOWN_DELAY_S = 0.3


@app.middleware("http")
async def _host_allowlist(request: Request, call_next):
    """Reject requests whose Host header is not an allowed hostname.

    The server binds 127.0.0.1, but a DNS-rebinding page can still reach it
    from a browser by re-resolving its own hostname to 127.0.0.1 — those
    requests carry the attacker's hostname in Host. Comparing the hostname
    (port stripped, IPv6 brackets handled) against config.ALLOWED_HOSTS
    defeats that; direct local browsing always sends a matching host.
    """
    host = (request.headers.get("host") or "").lower().strip()
    if host.startswith("["):
        hostname = host[1:host.index("]")] if "]" in host else host
    else:
        hostname = host.rsplit(":", 1)[0]
    if hostname not in config.ALLOWED_HOSTS:
        return JSONResponse(
            status_code=403,
            content={"detail": f"host '{hostname or 'missing'}' not allowed"},
        )
    return await call_next(request)


app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(config.STATIC_DIR / "index.html"))


@app.get("/api/dashboard")
def dashboard():
    return service.get_dashboard()


@app.post("/api/refresh")
def refresh(full: bool = False):
    try:
        return service.refresh_all(full=full)
    except service.RefreshBusy:
        return {"error": "another refresh is already running (scheduled task or other process)"}


# Display names for AI-capex-cohort tickers. config.AI_CAPEX_COHORTS lists
# symbols only; these are the names the dashboard has always shown for them.
_COHORT_TICKER_NAMES = {
    "AMZN": "Amazon", "MSFT": "Microsoft", "GOOGL": "Alphabet", "META": "Meta Platforms",
    "ORCL": "Oracle", "CRM": "Salesforce", "NOW": "ServiceNow",
    "NVDA": "NVIDIA", "AMD": "AMD", "AVGO": "Broadcom", "TSM": "TSMC",
    "QCOM": "Qualcomm", "ARM": "Arm Holdings", "CRDO": "Credo Tech", "ALAB": "Astera Labs",
    "MU": "Micron", "WDC": "Western Digital", "STX": "Seagate",
    "000660.KS": "SK Hynix", "005930.KS": "Samsung Electronics",
    "LITE": "Lumentum", "COHR": "Coherent", "AAOI": "Applied Optoelectronics",
    "AMAT": "Applied Materials", "LRCX": "Lam Research", "KLAC": "KLA",
    "DELL": "Dell", "SMCI": "Super Micro", "ANET": "Arista Networks", "NBIS": "Nebius",
    "VST": "Vistra", "CEG": "Constellation Energy", "NRG": "NRG Energy",
    "PLD": "Prologis", "DLR": "Digital Realty", "EQIX": "Equinix",
    "PLTR": "Palantir", "SHOP": "Shopify", "ADBE": "Adobe",
}


@app.get("/api/meta")
def meta():
    """Frontend label metadata derived from app/config.py (read-only)."""
    labels: dict[str, str] = dict(_COHORT_TICKER_NAMES)
    # Later groups win on overlap; only benign duplicates exist today
    # (e.g. CL=F appears in both COMMODITIES and COMMODITY_FUTURES).
    for group in (
        config.CROSS_ASSET,
        config.SECTORS,
        config.COMMODITY_FUTURES,
        config.COMMODITIES,
        config.INDEX_FUTURES,
        config.RATES,
        config.VOLATILITY,
        config.INDICES,
    ):
        labels.update(group)
    return {
        "labels": labels,
        "groups": {
            "indices": config.INDICES,
            "volatility": config.VOLATILITY,
            "rates": config.RATES,
            "commodities": config.COMMODITIES,
            "index_futures": config.INDEX_FUTURES,
            "commodity_futures": config.COMMODITY_FUTURES,
            "sectors": config.SECTORS,
            "cross_asset": config.CROSS_ASSET,
            "ai_capex_cohorts": config.AI_CAPEX_COHORTS,
        },
    }


@app.get("/api/events")
def events(limit: int = Query(default=500)):
    return store.list_events(limit=limit)


@app.delete("/api/events")
def delete_event(link: str | None = Query(default=None), source: str | None = Query(default=None)):
    if link and source:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'link' or 'source', not both — compound deletes must be separate calls.",
        )
    if link:
        store.delete_event(link)
    elif source:
        store.delete_events_by_source(source)
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide a 'link' or 'source' query parameter to delete events.",
        )
    return store.list_events(limit=500)


@app.post("/api/events/tags")
def update_event_tags(payload: dict):
    """Add and/or remove user tags on one event.

    Body: ``{"link": "...", "add": ["my-tag"], "remove": ["old-tag"]}``.
    The auto-tag "ai" cannot be removed manually — it is always re-applied
    on insert/refresh whenever the title or summary still matches the AI
    keywords, so a manual removal would be silently undone next ingest.
    Returns the updated event list so the client can re-render in one round
    trip. 404 if the link is unknown."""
    link = (payload or {}).get("link")
    add = (payload or {}).get("add") or []
    remove = (payload or {}).get("remove") or []
    if not link or not isinstance(link, str):
        raise HTTPException(status_code=400, detail="Body must include a non-empty 'link'.")
    if not isinstance(add, list) or not isinstance(remove, list):
        raise HTTPException(status_code=400, detail="'add' and 'remove' must be arrays of strings.")
    updated = store.update_event_tags(link, add=add, remove=remove)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"No event with link {link!r}.")
    return {"updated": updated, "events": store.list_events(limit=500)}


@app.post("/api/events/suppress")
def suppress_source(source: str = Query(...)):
    store.suppress_source(source)
    return store.list_events(limit=500)


@app.get("/api/analysis/history")
def analysis_history(limit: int = Query(default=20)):
    return store.get_analysis_history(limit=limit)


@app.get("/api/earnings")
def earnings_endpoint():
    return earnings.earnings_calendar()


@app.get("/api/earnings/validate")
def earnings_validate(symbol: str = Query(...)):
    return earnings.validate_symbol(symbol)


@app.post("/api/earnings/watchlist")
def earnings_add(symbol: str = Query(...)):
    result = earnings.validate_symbol(symbol)
    if not result.get("valid"):
        reason = result.get("reason") or "unknown ticker"
        raise HTTPException(status_code=400, detail=f"Invalid symbol {symbol!r}: {reason}")
    return earnings.add_ticker(symbol)


@app.delete("/api/earnings/watchlist")
def earnings_remove(symbol: str = Query(...)):
    return earnings.remove_ticker(symbol)


@app.get("/api/regime")
def regime_endpoint():
    return regime.get_regime()


# Pending shutdown timer — module-level so /api/cancel-shutdown can cancel
# it. ``pagehide`` schedules the exit, ``pageshow`` (sent by the new page
# after an F5 reload) cancels it. Only a true tab/window close — no
# pageshow follows — actually reaches ``os._exit``.
_shutdown_timer: threading.Timer | None = None
_shutdown_lock = threading.Lock()


@app.post("/api/shutdown")
@app.get("/api/shutdown")
def shutdown():
    """Tear down the server when the dashboard tab is truly closed.

    The frontend fires ``navigator.sendBeacon('/api/shutdown')`` on
    ``pagehide`` (with ``beforeunload`` as a backup) AND immediately
    dispatches ``/api/cancel-shutdown`` on the *next* page's ``pageshow``.
    An F5 / browser reload therefore cancels the timer before it fires and
    the server stays alive across the reload. Only when the tab/window is
    actually closing — and no follow-up page loads — does the timer reach
    ``os._exit`` and reap the cmd window the desktop launcher spawned.

    We ``os._exit`` rather than ``sys.exit`` because uvicorn's asyncio
    shutdown can hang on a closing socket; a hard exit is appropriate for a
    local-only single-user process.
    """
    global _shutdown_timer
    with _shutdown_lock:
        if _shutdown_timer is not None:
            _shutdown_timer.cancel()
        _shutdown_timer = threading.Timer(_SHUTDOWN_DELAY_S, os._exit, args=(0,))
        _shutdown_timer.start()
    return {"status": "shutting down"}


@app.post("/api/cancel-shutdown")
@app.get("/api/cancel-shutdown")
def cancel_shutdown():
    """Cancel a pending ``/api/shutdown`` exit.

    Sent by the frontend on ``pageshow`` so a page reload (F5, link nav,
    bfcache restore) does not kill the server while the user is still
    using it. Idempotent: a no-op when no shutdown is scheduled.
    """
    global _shutdown_timer
    with _shutdown_lock:
        if _shutdown_timer is not None:
            _shutdown_timer.cancel()
            _shutdown_timer = None
    return {"status": "ok"}
