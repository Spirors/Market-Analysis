"""FastAPI application: JSON API + static dashboard."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import (
    bottleneck,
    bottleneck_topics,
    config,
    market,
    portfolio as _portfolio,
    regime,
    service,
    store,
    topic_agent,
    validation,
)

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
    "ORCL": "Oracle",
    "NVDA": "NVIDIA", "AMD": "AMD", "AVGO": "Broadcom", "TSM": "TSMC",
    "INTC": "Intel", "MRVL": "Marvell", "QCOM": "Qualcomm", "ARM": "Arm Holdings",
    "CRDO": "Credo Tech", "ALAB": "Astera Labs",
    "MU": "Micron", "SNDK": "Sandisk", "WDC": "Western Digital", "STX": "Seagate",
    "000660.KS": "SK Hynix", "005930.KS": "Samsung Electronics",
    "CIEN": "Ciena", "LITE": "Lumentum", "COHR": "Coherent",
    "FN": "Fabrinet", "AAOI": "Applied Optoelectronics", "MTSI": "MACOM",
    "ASML": "ASML", "AMAT": "Applied Materials", "LRCX": "Lam Research",
    "KLAC": "KLA", "ONTO": "Onto Innovation", "FORM": "FormFactor",
    "DELL": "Dell", "ANET": "Arista Networks", "CRWV": "CoreWeave",
    "HPE": "HPE", "SMCI": "Super Micro", "NBIS": "Nebius", "APLD": "Applied Digital",
    "GEV": "GE Vernova", "ETN": "Eaton", "VRT": "Vertiv", "PWR": "Quanta Services",
    "CEG": "Constellation Energy", "VST": "Vistra", "BE": "Bloom Energy",
    "NVT": "nVent", "NRG": "NRG Energy", "TLN": "Talen Energy",
    "PLD": "Prologis", "DLR": "Digital Realty", "EQIX": "Equinix", "XLU": "Utilities",
    "PLTR": "Palantir", "CRM": "Salesforce", "NOW": "ServiceNow",
    "ADBE": "Adobe", "SHOP": "Shopify",
    "SNOW": "Snowflake", "CRWD": "CrowdStrike", "DDOG": "Datadog",
    "NET": "Cloudflare", "TEAM": "Atlassian", "ADSK": "Autodesk",
    "WDAY": "Workday", "MDB": "MongoDB", "HUBS": "HubSpot",
    "ZS": "Zscaler", "MNDY": "monday.com", "TWLO": "Twilio",
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
    The auto-tag "ai" is mutable like any other user tag — manual removal
    persists across subsequent RSS refreshes; the auto-tag is only
    re-applied when a brand-new row is inserted (see ``upsert_events``).
    Returns the updated event list so the client can re-render in one
    round trip. 404 if the link is unknown.

    The AI capex-cycle gauge does NOT recompute on tag edit — the user
    must click the global Refresh button to pick up the change. This
    keeps the gauge stable while the user is curating tags."""
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


@app.post("/api/events/dimensions")
def update_event_dimensions(payload: dict):
    """Override one or more heuristic-set fixed dimensions on one event.

    Body: ``{"link": "...", "category": "micro", "direction": "bearish"}``.
    Only the fields named in the body are changed; the rest of the row is
    untouched. Each field value must be one of the allowed values (or
    null/empty to clear it). The user_edited lock is armed on any change
    so the override survives the next RSS refresh.

    This is the manual-fix path for "heuristic was wrong" — e.g. the
    classifier put a bearish story under ``category: macro`` when it
    should be ``micro``, or a US-domestic story under ``region: global``
    when it should be ``region: us``. The change persists across both
    manual and scheduled refreshes.

    Returns the updated event payload + the full event list. 400 on
    unknown field name / invalid value; 404 if the link is unknown."""
    link = (payload or {}).get("link")
    if not link or not isinstance(link, str):
        raise HTTPException(status_code=400, detail="Body must include a non-empty 'link'.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object.")
    dimensions = {k: v for k, v in payload.items() if k != "link"}
    try:
        updated = store.update_event_dimensions(link, dimensions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"No event with link {link!r}.")
    return {"updated": updated, "events": store.list_events(limit=500)}


@app.post("/api/events/suppress")
def suppress_source(source: str = Query(...)):
    store.suppress_source(source)
    return store.list_events(limit=500)


@app.get("/api/portfolios")
def portfolios_get():
    state = _portfolio.load_portfolios()
    state = _portfolio.enrich_portfolios(state)
    return state


@app.post("/api/portfolios")
def portfolios_create(name: str = Query(...)):
    try:
        result = _portfolio.create_portfolio(name)
        # Enrich the new portfolio with live prices so the response matches
        # what GET /api/portfolios returns for a single portfolio.
        # The response shape from create_portfolio is {id, portfolio},
        # but we need to return the enriched portfolio dict directly to match
        # what the frontend's renderPortfolioInsert expects (a portfolio object).
        # Build a minimal state dict to pass through enrich_portfolios.
        pid = result["id"]
        p = result["portfolio"]
        mini_state = {"portfolios": {pid: p}, "column_order": {}, "column_visibility": {}}
        enriched = _portfolio.enrich_portfolios(mini_state)
        return {"id": pid, "portfolio": enriched["portfolios"][pid]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/portfolios/{pid}", status_code=204)
def portfolios_delete(pid: str):
    if not _portfolio.delete_portfolio(pid):
        raise HTTPException(status_code=404, detail="portfolio not found")
    return None


@app.put("/api/portfolios/{pid}")
def portfolios_rename(pid: str, name: str = Query(...)):
    """Rename a portfolio: ``PUT /api/portfolios/{pid}?name=...``.

    The inline pencil rename in ``static/js/portfolio.js`` commits
    (on blur / Enter) by sending the new name as a query param. Returns
    the renamed portfolio in the same ``{id, portfolio}`` shape as
    ``POST /api/portfolios``. No live-price enrichment: a rename touches
    only the name, so the holding price fields are unchanged and adding a
    yfinance round-trip would only stall the rename (see the "patch
    minimally" rationale in ``portfolio._patch_dashboard_cache``).
    """
    try:
        p = _portfolio.rename_portfolio(pid, name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if p is None:
        raise HTTPException(status_code=404, detail="portfolio not found")
    return {"id": pid, "portfolio": p}


@app.post("/api/portfolios/reorder")
def portfolios_reorder(body: dict):
    """Reorder the portfolios list.

    Body: ``{"order": ["pid-a", "pid-b", ...]}``. The new order must be
    a permutation of the existing portfolio ids — no adds, removes, or
    duplicates. Empty order is allowed only when there are zero
    portfolios. Returns the new order on success.
    """
    from fastapi import HTTPException as _exc
    order = body.get("order") if isinstance(body, dict) else None
    if not isinstance(order, list) or not all(isinstance(x, str) for x in order):
        raise _exc(status_code=400, detail="order must be a list of portfolio ids")
    try:
        state = _portfolio.reorder_portfolios(order)
    except ValueError as e:
        raise _exc(status_code=400, detail=str(e))
    return {"order": list(state["portfolios"].keys())}


@app.post("/api/portfolios/{pid}/holdings")
def holdings_add(pid: str, symbol: str = Query(...), shares: float = Query(...), total_cost: float = Query(...)):
    from fastapi import HTTPException as _exc
    try:
        h = _portfolio.add_holding(pid, symbol, shares, total_cost)
        # enrich with live price (via get_quotes for disk-cache benefit)
        from . import market
        if h.get("symbol"):
            q = market.get_quotes([h["symbol"]]).get(h["symbol"]) or {}
            h["last_price"] = q.get("price")
            h["pct_daily"] = q.get("pct_change")
        return h
    except KeyError as e:
        raise _exc(status_code=404, detail=str(e))
    except ValueError as e:
        raise _exc(status_code=400, detail=str(e))


@app.put("/api/portfolios/{pid}/holdings/{symbol}")
def holdings_edit(pid: str, symbol: str, shares: float | None = Query(None), total_cost: float | None = Query(None)):
    from fastapi import HTTPException as _exc
    try:
        h = _portfolio.edit_holding(pid, symbol, shares, total_cost)
        if h is None:
            raise _exc(status_code=404, detail="holding not found")
        from . import market
        if h.get("symbol"):
            q = market.get_quotes([h["symbol"]]).get(h["symbol"]) or {}
            h["last_price"] = q.get("price")
            h["pct_daily"] = q.get("pct_change")
        return h
    except KeyError as e:
        raise _exc(status_code=404, detail=str(e))
    except ValueError as e:
        raise _exc(status_code=400, detail=str(e))


@app.delete("/api/portfolios/{pid}/holdings/{symbol}", status_code=204)
def holdings_delete(pid: str, symbol: str):
    from fastapi import HTTPException as _exc
    if not _portfolio.remove_holding(pid, symbol):
        raise _exc(status_code=404, detail="holding not found")
    return None


@app.post("/api/portfolios/{pid}/holdings/reorder")
def holdings_reorder(pid: str, body: dict):
    """Reorder holdings within a portfolio.

    Body: {"order": ["NVDA", "AAPL", "MSFT"]}. The new order must be
    a permutation of the existing non-cash holding symbols -- no adds,
    removes, or duplicates. Cash rows always trail at the end.
    Returns {"order": [...symbols...]} on success.
    """
    from fastapi import HTTPException as _exc
    order = body.get("order") if isinstance(body, dict) else None
    if not isinstance(order, list) or not all(isinstance(x, str) for x in order):
        raise _exc(status_code=400, detail="order must be a list of symbol strings")
    try:
        p = _portfolio.reorder_holdings(pid, order)
    except KeyError as e:
        raise _exc(status_code=404, detail=str(e))
    except ValueError as e:
        raise _exc(status_code=400, detail=str(e))
    stock_syms = [h.get("symbol") for h in p.get("holdings", []) if h.get("kind") != "cash"]
    return {"order": stock_syms}


@app.post("/api/portfolios/{pid}/cash")
def cash_add(pid: str, label: str | None = Query(None), total_cost: float = Query(...), total_value: float = Query(...)):
    from fastapi import HTTPException as _exc
    try:
        return _portfolio.add_cash_row(pid, label, total_cost, total_value)
    except KeyError as e:
        raise _exc(status_code=404, detail=str(e))
    except ValueError as e:
        raise _exc(status_code=400, detail=str(e))


@app.put("/api/portfolios/{pid}/cash")
def cash_edit(pid: str, label: str | None = Query(None), total_cost: float | None = Query(None), total_value: float | None = Query(None)):
    from fastapi import HTTPException as _exc
    try:
        h = _portfolio.edit_cash_row(pid, label, total_cost, total_value)
        if h is None:
            raise _exc(status_code=404, detail="cash row not found")
        return h
    except KeyError as e:
        raise _exc(status_code=404, detail=str(e))
    except ValueError as e:
        raise _exc(status_code=400, detail=str(e))


@app.delete("/api/portfolios/{pid}/cash")
def cash_remove(pid: str):
    from fastapi import HTTPException as _exc
    if pid not in _portfolio.load_portfolios()["portfolios"]:
        raise _exc(status_code=404, detail=f"portfolio not found: {pid}")
    removed = _portfolio.remove_cash_row(pid)
    if not removed:
        raise _exc(status_code=404, detail="cash row not found")
    return {"removed": True}


@app.put("/api/portfolios/columns/{section}")
def columns_put(section: str, body: dict):
    """Persist column order + visibility for a section.

    Accepts either the default section key ("portfolio") or a per-portfolio
    override ("portfolio.<pid>"). The "portfolio" key is the fallback used
    for new portfolios that haven't been customized; each portfolio's own
    prefs are stored under "portfolio.<pid>" so different portfolios can
    show different columns. Per-portfolio section keys MUST point at an
    existing portfolio id - 404 otherwise. See "Per-portfolio column state"
    in docs/DECISIONS.md.
    """
    from fastapi import HTTPException as _exc
    from .portfolio import DEFAULT_COLUMN_ORDER
    if section not in DEFAULT_COLUMN_ORDER and not section.startswith("portfolio."):
        raise _exc(status_code=400, detail=f"unknown section: {section}")
    state = _portfolio.load_portfolios()
    if section.startswith("portfolio."):
        pid = section[len("portfolio."):]
        if pid not in state.get("portfolios", {}):
            raise _exc(status_code=404, detail=f"unknown portfolio: {pid}")
    order = body.get("order")
    visibility = body.get("visibility")
    if not isinstance(order, list) or not isinstance(visibility, dict):
        raise _exc(status_code=400, detail="order must be list, visibility must be object")
    state["column_order"][section] = list(order)
    state["column_visibility"][section] = dict(visibility)
    _portfolio.save_portfolios(state)
    return {"order": state["column_order"][section], "visibility": state["column_visibility"][section]}


@app.get("/api/portfolios/validate")
def portfolio_validate(symbol: str = Query(...)):
    return validation.validate_symbol(symbol)


@app.get("/api/regime")
def regime_endpoint():
    return regime.get_regime()


# ---- Bottleneck topics -----------------------------------------------------

_logger = logging.getLogger(__name__)

# Write paths (create / update / import / apply) warm the shared valuation
# cache so a freshly created topic can render its market cap and tier its
# underdogs. The warm is a multi-ticker ``.info`` walk, so it must never block
# the request: it runs on a daemon thread and every exception is swallowed and
# logged — a warming failure must not fail the user's write. The lock is
# process-local and non-blocking: while a walk is in flight, overlapping writes
# skip the warm rather than spawning a duplicate walk.
_bottleneck_warm_lock = threading.Lock()


def _warm_bottleneck_metrics() -> None:
    """Kick off a background warm for the current topic symbols.

    Warms two caches in one pass on one daemon thread: the shared valuation
    cache (market cap / PE) and the bulk history cache the render path reads
    for momentum.  A freshly created or edited topic changes the symbol
    universe, so its bulk history key is new and cold; warming it here keeps
    ``GET /api/bottleneck/topics`` from rendering ``—`` momentum until the next
    full market refresh.  ``history_universe_symbols`` is the same list the
    refresh uses, so this writes the very cache ``bottleneck_read_cached``
    reads.
    """
    if not _bottleneck_warm_lock.acquire(blocking=False):
        return  # a walk is already in flight; never stack another
    tickers = bottleneck.all_proxy_symbols()
    history_symbols = market.history_universe_symbols()

    def _run() -> None:
        try:
            bottleneck.ensure_metrics(tickers)
            market.get_histories_bulk(history_symbols, days=250)
        except Exception:  # noqa: BLE001 - warming must never fail a request
            _logger.warning("bottleneck warming failed", exc_info=True)
        finally:
            _bottleneck_warm_lock.release()

    threading.Thread(
        target=_run, name="bottleneck-warm", daemon=True
    ).start()


def _merge_imported_topics(imported: list[dict]) -> list[dict]:
    """Merge validated imported topics into the store, replacing same-id entries.

    Import persists the valid subset; the invalid ones are reported in the
    response's ``errors`` and never written.  A topic carrying an id that
    already exists replaces the stored one; a topic without an id is appended.
    """
    existing = bottleneck_topics.load_topics()
    index_by_id = {t.get("id"): i for i, t in enumerate(existing) if t.get("id")}
    merged = list(existing)
    for topic in imported:
        topic_id = topic.get("id")
        if topic_id and topic_id in index_by_id:
            merged[index_by_id[topic_id]] = topic
        else:
            merged.append(topic)
    return merged


@app.get("/api/bottleneck/topics")
def bottleneck_topics_list():
    """The front-end's single call to render the bottleneck section.

    Both halves in one response: the raw stored topics (for the edit forms) and
    the computed ``bottleneck_read`` payload (ranked layers + tiered
    underdogs).  The computed half is assembled from caches by
    ``service.bottleneck_read_cached`` — no full market refresh is needed for a
    freshly created topic to render.  ``generation`` names whether the drafting
    agent is available so the UI can disable Generate in the same round trip.
    """
    return store.json_safe({
        "topics": bottleneck_topics.load_topics(),
        "bottleneck": service.bottleneck_read_cached(),
        "generation": topic_agent.generation_availability(),
    })


@app.post("/api/bottleneck/topics", status_code=201)
def bottleneck_topic_create(body: dict):
    name = body.get("name") if isinstance(body, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(
            status_code=400,
            detail="'name' is required and must be a non-empty string.",
        )
    topic = bottleneck_topics.create_topic(name)
    _warm_bottleneck_metrics()
    return topic


@app.get("/api/bottleneck/topics/export")
def bottleneck_topics_export():
    return bottleneck_topics.export_topics()


@app.post("/api/bottleneck/topics/import")
def bottleneck_topics_import(body: Any = Body(...)):
    """Import topics from a bare list or a ``{"version", "topics"}`` document.

    Persists the **valid subset** (merged with the existing store) and reports
    the invalid topics in ``errors``; a payload that is neither shape is a 400.
    """
    if isinstance(body, list):
        pass
    elif isinstance(body, dict) and isinstance(body.get("topics"), list):
        pass
    else:
        raise HTTPException(
            status_code=400,
            detail='import payload must be a list of topics or a {"version", "topics"} document',
        )
    imported, errors = bottleneck_topics.import_topics(body)
    merged = _merge_imported_topics(imported)
    bottleneck_topics.save_topics(merged)
    _warm_bottleneck_metrics()
    return {"imported": len(imported), "errors": errors, "topics": merged}


@app.post("/api/bottleneck/topics/generate", status_code=201)
def bottleneck_topic_generate(body: dict):
    """Start a topic-drafting job.

    ``topic_agent.start_generation`` returns a failed, unpersisted job-shaped
    record on a precondition failure (missing key, missing skill, one already
    running).  That becomes a 409 carrying the exact message the UI should
    show; a started job is a 201 with the job record to poll.
    """
    payload = body if isinstance(body, dict) else {}
    job = topic_agent.start_generation(
        payload.get("theme"),
        model=payload.get("model"),
        topic_id=payload.get("topic_id"),
    )
    if job.get("status") == topic_agent.FAILED:
        raise HTTPException(status_code=409, detail=job.get("error"))
    return job


@app.put("/api/bottleneck/topics/{topic_id}")
def bottleneck_topic_update(topic_id: str, body: dict):
    existing = bottleneck_topics.get_topic(topic_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"unknown topic: {topic_id}")
    patch = body if isinstance(body, dict) else {}
    # Validate the merged result before persisting so an invalid patch is
    # rejected with the validator's own messages (identity is not editable).
    merged = {**existing, **patch}
    merged["id"] = existing["id"]
    errors = bottleneck_topics.validate_topic(merged)
    if errors:
        raise HTTPException(status_code=400, detail=errors)
    topic = bottleneck_topics.update_topic(topic_id, patch)
    _warm_bottleneck_metrics()
    return topic


@app.delete("/api/bottleneck/topics/{topic_id}", status_code=204)
def bottleneck_topic_delete(topic_id: str):
    if not bottleneck_topics.delete_topic(topic_id):
        raise HTTPException(status_code=404, detail=f"unknown topic: {topic_id}")
    # Deleting a topic changes the symbol universe (and therefore the bulk
    # history key); warm it so the remaining topics keep rendering momentum
    # instead of ``—`` until the next full refresh.
    _warm_bottleneck_metrics()
    return None


@app.get("/api/bottleneck/jobs")
def bottleneck_jobs_list():
    return topic_agent.list_jobs()


@app.get("/api/bottleneck/jobs/{job_id}")
def bottleneck_job_get(job_id: str):
    job = topic_agent.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")
    return job


@app.post("/api/bottleneck/jobs/{job_id}/cancel")
def bottleneck_job_cancel(job_id: str):
    job = topic_agent.cancel_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")
    return job


@app.post("/api/bottleneck/jobs/{job_id}/apply")
def bottleneck_job_apply(job_id: str, body: dict):
    payload = body if isinstance(body, dict) else {}
    topic = topic_agent.apply_draft(
        job_id, payload.get("topic_id"), payload.get("summary") or ""
    )
    if topic is None:
        raise HTTPException(
            status_code=404,
            detail="no succeeded draft for that job and topic",
        )
    _warm_bottleneck_metrics()
    return topic


@app.get("/api/bottleneck/skill/status")
def bottleneck_skill_status():
    """Skill inventory + generation availability in one call.

    Carrying ``generation`` here lets the UI disable the Generate button
    without discovering the failure only on click.
    """
    status = topic_agent.skill_status()
    status["generation"] = topic_agent.generation_availability()
    return status


@app.post("/api/bottleneck/skill/refresh")
def bottleneck_skill_refresh():
    """Install/update the skill. A CLI failure is a 200 with ``ok: false``."""
    return topic_agent.refresh_skill()


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
    # Best-effort cleanup of data/server.pid before we go — run.py writes
    # this on startup so an orchestrator can locate a stray server for
    # cleanup. Leaving it behind on graceful exit would let the next
    # session think an orphan still exists.
    try:
        from . import lifecycle
        lifecycle.remove_server_pid_file()
    except Exception:
        pass
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
