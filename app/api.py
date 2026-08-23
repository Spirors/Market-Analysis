"""FastAPI application: JSON API + static dashboard."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, earnings, regime, service, store

app = FastAPI(title="Market Analysis Tool")

app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(config.STATIC_DIR / "index.html"))


@app.get("/api/dashboard")
def dashboard():
    return service.get_dashboard()


@app.post("/api/refresh")
def refresh(full: bool = False):
    return service.refresh_all(full=full)


# Display names for AI-capex-cohort tickers. config.AI_CAPEX_COHORTS lists
# symbols only; these are the names the dashboard has always shown for them.
_COHORT_TICKER_NAMES = {
    "AMZN": "Amazon", "MSFT": "Microsoft", "GOOGL": "Alphabet", "META": "Meta Platforms",
    "ORCL": "Oracle", "CRM": "Salesforce", "NOW": "ServiceNow",
    "NVDA": "NVIDIA", "AMD": "AMD", "AVGO": "Broadcom", "TSM": "TSMC",
    "QCOM": "Qualcomm", "ARM": "Arm Holdings", "CRDO": "Credo Tech", "ALAB": "Astera Labs",
    "MU": "Micron", "WDC": "Western Digital", "STX": "Seagate",
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
