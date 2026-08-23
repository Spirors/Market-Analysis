"""FastAPI application: JSON API + static dashboard."""

from fastapi import FastAPI, Query
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


@app.get("/api/events")
def events(limit: int = Query(default=500)):
    return store.list_events(limit=limit)


@app.delete("/api/events")
def delete_event(link: str | None = Query(default=None), source: str | None = Query(default=None)):
    if link:
        store.delete_event(link)
    elif source:
        store.delete_events_by_source(source)
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
    return earnings.add_ticker(symbol)


@app.delete("/api/earnings/watchlist")
def earnings_remove(symbol: str = Query(...)):
    return earnings.remove_ticker(symbol)


@app.get("/api/regime")
def regime_endpoint():
    return regime.get_regime()
