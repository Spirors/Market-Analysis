"""Refresh orchestration and dashboard aggregation."""

import time
from datetime import datetime, timezone
from typing import Any

from . import ai_sentiment, analysis, bottleneck, config, earnings, indicators, market, news, regime, risk, store, thirteenf


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def refresh_market() -> dict[str, Any]:
    """Pull market data and compute indicators + risk + bottleneck (fast path)."""
    snapshot = market.build_market_snapshot()
    inds = indicators.compute_indicators(snapshot)
    earn = earnings.earnings_calendar()
    risk_read = risk.compute_risk(snapshot, earn)
    bn = bottleneck.bottleneck_read(snapshot)
    ai = ai_sentiment.compute_ai_sentiment(snapshot, store.list_events(limit=500), earn)

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
        "futures": market.build_futures_snapshot(),
        "thirteenf": thirteenf.build_thirteenf(),
        "earnings": earn,
        "ai_sentiment": ai,
    }
    store.save_json(config.DATA_DIR / "dashboard.json", result)
    return result


def refresh_news() -> dict[str, Any]:
    """Fast news-only refresh: ingest the live feed and store High/Critical
    events (no market pulls, no regime detection). Runs in seconds.

    Returns a small summary dict: feeds_checked / per_feed / collected /
    inserted counts."""
    return news.fetch_and_store()


def backfill_news() -> dict[str, Any]:
    """Load the curated event timeline (deterministic, idempotent)."""
    return news.seed_events()


def refresh_earnings() -> dict[str, Any]:
    return earnings.earnings_force_refresh()


def refresh_regime() -> dict[str, Any]:
    return regime.run_regime_detection()


def refresh_all(full: bool = False) -> dict[str, Any]:
    """Full refresh. `full=True` also runs the (slower) regime detection."""
    result = refresh_market()
    result["news"] = news.fetch_and_store()
    result["earnings"] = earnings.earnings_calendar()
    if full:
        result["regime"] = regime.run_regime_detection()
    # The synthesis runs last so every input (incl. regime) exists; cached
    # regime costs nothing here (_enrich already fetches it on light serves).
    result.setdefault("regime", regime.get_regime())
    result["ai_analysis"] = analysis.build_analysis(result)
    store.log_analysis_run(result["ai_analysis"])
    store.save_json(config.DATA_DIR / "dashboard.json", result)
    return result


def get_dashboard() -> dict[str, Any]:
    """Return cached dashboard if fresh enough, else refresh (fast path)."""
    data = store.load_json(config.DATA_DIR / "dashboard.json")
    if data and time.time() - _fresh_timestamp(data) < config.QUOTE_TTL:
        return _enrich(data)
    refreshed = refresh_all(full=False)
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
    return data
