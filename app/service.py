"""Refresh orchestration and dashboard aggregation."""

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from . import ai_sentiment, analysis, bottleneck, config, earnings, indicators, market, news, regime, risk, store, thirteenf
from .lockfile import RefreshBusy, refresh_lock

# Single-flight guard: N concurrent dashboard requests must not trigger N
# parallel full refreshes. Blocking is fine for this local single-user tool.
_refresh_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- Coverage reporting -----------------------------------------------------
# A source outage should look different from genuine calm. Each dashboard
# section maps to a small declarative counter of its key fields; the frontend
# renders a muted "n/m" badge only when a section is incomplete. Purely
# additive metadata: nothing here removes or renames payload keys.

def _quote_ok(q: Any) -> bool:
    return isinstance(q, dict) and q.get("price") is not None


def _count_quotes(group: Any, symbols: list[str]) -> tuple[int, int]:
    vals = [(group or {}).get(s) for s in symbols]
    return sum(1 for q in vals if _quote_ok(q)), len(vals)


def _presence(value: Any) -> dict[str, int]:
    return {"ok": 1, "total": 1} if value else {"ok": 0, "total": 1}


def _coverage_counts(result: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Compute {section: {ok, total}} from a fully-built dashboard result."""
    mkt = result.get("market") or {}
    ind = result.get("indicators") or {}
    risk_read = result.get("risk") or {}
    bn = result.get("bottleneck") or {}
    fut = result.get("futures") or {}
    tf = result.get("thirteenf") or {}
    earn = result.get("earnings") or {}
    ai = result.get("ai_sentiment") or {}

    cov: dict[str, dict[str, int]] = {}

    # Quote groups: one entry per tracked symbol with a non-null price.
    quote_groups = {
        "indices": (mkt.get("indices"), list(config.INDICES)),
        "volatility": (mkt.get("volatility"), list(config.VOLATILITY)),
        "rates": (mkt.get("rates"), list(config.RATES)),
        "commodities": (mkt.get("commodities"), list(config.COMMODITIES)),
        "sectors": (mkt.get("sectors"), list(config.SECTORS)),
    }
    market_ok = market_total = 0
    for name, (group, symbols) in quote_groups.items():
        ok, total = _count_quotes(group, symbols)
        cov[name] = {"ok": ok, "total": total}
        market_ok += ok
        market_total += total
    cov["market"] = {"ok": market_ok, "total": market_total}

    # Indicators: the headline fields the Indicators card renders.
    spy = ind.get("spy") or {}
    trend = spy.get("trend") or {}
    vix = ind.get("vix") or {}
    indicator_fields = [
        (ind.get("breadth") or {}).get("breadth_pct"),
        trend.get("state") if trend.get("state") not in (None, "", "unknown") else None,
        spy.get("realized_vol_annual_pct"),
        vix.get("level"),
        vix.get("signal") if vix.get("signal") not in (None, "", "no data", "unknown") else None,
    ]
    cov["indicators"] = {
        "ok": sum(1 for f in indicator_fields if f is not None),
        "total": len(indicator_fields),
    }

    # Breadth cards: symbols that produced a 50DMA reading vs. tracked count.
    ai_syms = sorted({t for tickers in config.AI_CAPEX_COHORTS.values() for t in tickers})
    breadth_detail = (ind.get("breadth") or {}).get("detail") or {}
    cov["breadth"] = {
        "ok": len(breadth_detail),
        "total": len(config.INDICES) + len(config.SECTORS),
    }
    breadth_ai_detail = (ind.get("breadth_ai") or {}).get("detail") or {}
    cov["breadth_ai"] = {"ok": len(breadth_ai_detail), "total": len(ai_syms)}

    # Risk: how many of the engine's signals actually produced evidence.
    signals = [s for s in (risk_read.get("signals") or []) if isinstance(s, dict)]
    cov["risk"] = {"ok": len(signals), "total": config.RISK_SIGNAL_TOTAL}

    # Bottleneck: layers that got a momentum score vs. all defined layers.
    layers = [
        layer
        for cat in (bn.get("categories") or [])
        for stream in (cat.get("streams") or {}).values()
        for layer in (stream.get("layers") or [])
    ]
    cov["bottleneck"] = {
        "ok": sum(1 for l in layers if l.get("proxy_40d_roc_pct") is not None),
        "total": len(layers),
    }

    # Futures: contracts with a live last price.
    items = list(fut.get("index_futures") or []) + list(fut.get("commodities") or [])
    cov["futures"] = {
        "ok": sum(1 for i in items if isinstance(i, dict) and i.get("last") is not None),
        "total": len(items),
    }

    # 13F: funds loaded vs. tracked superinvestors.
    cov["thirteenf"] = {
        "ok": len(tf.get("funds") or []),
        "total": len(config.SUPERINVESTORS),
    }

    # Earnings: watchlist rows carrying a live price.
    companies = earn.get("companies") or []
    cov["earnings"] = {
        "ok": sum(1 for c in companies if isinstance(c, dict) and c.get("price") is not None),
        "total": len(companies),
    }

    # AI gauge: cohorts with a computable 3m momentum.
    cohorts = ai.get("cohorts") or []
    cov["ai_sentiment"] = {
        "ok": sum(1 for c in cohorts if isinstance(c, dict) and c.get("roc_3m_pct") is not None),
        "total": len(cohorts),
    }

    # Sections without a natural count degrade to presence checks.
    cov["news"] = _presence(result.get("news"))
    regime = result.get("regime")
    cov["regime"] = (
        {"ok": 1, "total": 1}
        if isinstance(regime, dict) and regime and not regime.get("error")
        else {"ok": 0, "total": 1}
    )
    cov["ai_analysis"] = _presence(result.get("ai_analysis"))
    cov["events"] = _presence(result.get("events"))
    return cov


def _attach_coverage(result: dict[str, Any]) -> dict[str, Any]:
    result["coverage"] = _coverage_counts(result)
    return result


def refresh_market() -> dict[str, Any]:
    """Pull market data and compute indicators + risk + bottleneck (fast path)."""
    # Per-section completion stamps: each card shows its own data age instead
    # of implying everything shares the global as_of.
    vintage: dict[str, str] = {}

    def _stamp(section: str) -> None:
        vintage[section] = _now_iso()

    snapshot = market.build_market_snapshot()
    _stamp("market")
    inds = indicators.compute_indicators(snapshot)
    _stamp("indicators")
    earn = earnings.earnings_calendar()
    risk_read = risk.compute_risk(snapshot, earn)
    _stamp("risk")
    bn = bottleneck.bottleneck_read(snapshot)
    _stamp("bottleneck")
    # The AI capex-cycle gauge weighs recent AI news flow (~last 30 days) plus
    # the AI-tagged events the user has curated, so the gauge sees more than
    # the 48h ingest window that drives the timeline card. Bumping the cap to
    # 5000 keeps the window wide even when AI news is dense.
    ai_news_since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    ai_events = store.list_events(limit=5000, since_iso=ai_news_since, ai_only=True)
    ai = ai_sentiment.compute_ai_sentiment(snapshot, ai_events, earn)
    _stamp("ai_sentiment")
    fut = market.build_futures_snapshot()
    _stamp("futures")
    tf = thirteenf.build_thirteenf()
    _stamp("thirteenf")

    result = {
        "as_of": _now_iso(),
        "market": {
            "indices": snapshot["indices"],
            "volatility": snapshot["volatility"],
            "rates": snapshot["rates"],
            "commodities": snapshot["commodities"],
            "sectors": snapshot["sectors"],
        },
        "indicators": inds,
        "risk": risk_read,
        "bottleneck": bn,
        "futures": fut,
        "thirteenf": tf,
        "earnings": earn,
        "ai_sentiment": ai,
        "vintage": vintage,
    }
    _attach_coverage(result)
    store.save_json(config.DATA_DIR / "dashboard.json", result)
    return result


def refresh_news() -> dict[str, Any]:
    """Fast news-only refresh: ingest the live feed and store High/Critical
    events (no market pulls, no regime detection). Runs in seconds.

    Returns a small summary dict: feeds_checked / per_feed / collected /
    inserted counts. If another process holds the cross-process refresh lock
    (e.g. the 09:00 full refresh), this run is skipped and reported."""
    try:
        with refresh_lock():
            return news.fetch_and_store()
    except RefreshBusy:
        return {"skipped": True, "reason": "another refresh is already running"}


def backfill_news() -> dict[str, Any]:
    """Load the curated event timeline (deterministic, idempotent)."""
    return news.seed_events()


def refresh_earnings() -> dict[str, Any]:
    return earnings.earnings_force_refresh()


def refresh_regime() -> dict[str, Any]:
    return regime.run_regime_detection()


def refresh_all(full: bool = False) -> dict[str, Any]:
    """Full refresh. `full=True` also runs the (slower) regime detection.

    Raises RefreshBusy when another *process* (scheduled task) is already
    refreshing; callers decide whether to serve cache or skip."""
    with refresh_lock():
        result = refresh_market()
        vintage = result.setdefault("vintage", {})
        result["news"] = news.fetch_and_store()
        vintage["news"] = _now_iso()
        result["earnings"] = earnings.earnings_calendar()
        vintage["earnings"] = _now_iso()
        if full:
            result["regime"] = regime.run_regime_detection()
        # The synthesis runs last so every input (incl. regime) exists; cached
        # regime costs nothing here (_enrich already fetches it on light serves).
        result.setdefault("regime", regime.get_regime())
        vintage["regime"] = _now_iso()
        result["ai_analysis"] = analysis.build_analysis(result)
        vintage["ai_analysis"] = _now_iso()
        store.log_analysis_run(result["ai_analysis"])
        _attach_coverage(result)
        store.save_json(config.DATA_DIR / "dashboard.json", result)
        return result


def get_dashboard() -> dict[str, Any]:
    """Return cached dashboard if fresh enough, else refresh (fast path).

    Refreshes are single-flight: concurrent callers block on _refresh_lock,
    and each re-checks freshness after acquiring it, so the second caller
    serves the result the first just wrote instead of refreshing again.
    If a *separate process* (scheduled task) holds the cross-process lock,
    we serve whatever cache exists rather than stacking a second refresh.
    """
    data = store.load_json(config.DATA_DIR / "dashboard.json")
    if data and time.time() - _fresh_timestamp(data) < config.QUOTE_TTL:
        return _enrich(data)
    try:
        with _refresh_lock:
            # Double-checked staleness: another thread may have refreshed while
            # we waited for the lock.
            data = store.load_json(config.DATA_DIR / "dashboard.json")
            if data and time.time() - _fresh_timestamp(data) < config.QUOTE_TTL:
                return _enrich(data)
            refreshed = refresh_all(full=False)
    except RefreshBusy:
        # Scheduled task is refreshing right now; serve current cache — it
        # will be fresh again once that run finishes writing atomically.
        data = data or {}
        return _enrich(data)
    return _enrich(refreshed)


def _fresh_timestamp(data: dict[str, Any]) -> float:
    try:
        as_of = data.get("as_of", "")
        dt = datetime.fromisoformat(as_of)
        return dt.timestamp()
    except Exception:
        return 0.0


def _enrich(data: dict[str, Any]) -> dict[str, Any]:
    """Attach stored events, earnings, and latest regime to a dashboard dict."""
    data["events"] = store.list_events(limit=500)
    # Events are re-read from the store on every serve, so their vintage is
    # stamped here rather than at refresh time.
    data.setdefault("vintage", {})["events"] = _now_iso()
    data["earnings"] = earnings.earnings_calendar()
    if "regime" not in data:
        data["regime"] = regime.get_regime()
    if not data.get("ai_analysis"):
        # Between refreshes: serve the latest logged run, stamped with its ts.
        history = store.get_analysis_history(limit=1)
        if history:
            latest = history[0]
            data["ai_analysis"] = {
                "generated_at": latest["ts"],
                "stance": latest["stance"],
                "confidence": latest["confidence"],
                "headline": latest["headline"],
                "from_history": True,
            }
    # Recompute on every serve: events/earnings/regime may have just changed
    # above, and the counts are cheap to derive from the in-memory payload.
    _attach_coverage(data)
    return data
