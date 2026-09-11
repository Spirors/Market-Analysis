"""Tests for per-section refresh cooldowns in app/service.py.

Each dashboard section (portfolios, indicators/breadth-ai) has a cooldown
window during which refresh_market() reuses the cached payload instead of
recomputing.  Tests seed dashboard.json with a fresh vintage stamp, then
run refresh_market() and assert the cooldown_skip list and whether the
skipped section was actually reused.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app import config, service, store


# ---- Helpers ----------------------------------------------------------------

def _seed_dashboard_cache(
    tmp_path,
    *,
    vintage: dict[str, str] | None = None,
    portfolios: dict[str, Any] | None = None,
    indicators: dict[str, Any] | None = None,
) -> None:
    """Write a minimal dashboard.json with the given vintage + section data."""
    payload: dict[str, Any] = {
        "as_of": "2026-09-01T00:00:00+00:00",
        "market": {
            "indices": {}, "volatility": {}, "rates": {},
            "commodities": {}, "sectors": {},
        },
        "indicators": indicators or {"breadth": {"breadth_pct": 75.0}},
        "risk": {"risk_level": "YELLOW", "signals": [{}]},
        "bottleneck": {},
        "futures": {"index_futures": [], "commodities": []},
        "thirteenf": {},
        "ai_sentiment": {},
        "portfolios": portfolios or {},
        "vintage": vintage or {},
    }
    store.save_json(tmp_path / "dashboard.json", payload)


def _fresh_vintage_ts() -> str:
    """ISO timestamp representing 'just now'."""
    return datetime.now(timezone.utc).isoformat()


def _stale_vintage_ts(minutes_ago: int) -> str:
    """ISO timestamp representing N minutes ago."""
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


# ---- Config constants -------------------------------------------------------

def test_config_reports_cooldown_constants():
    assert config.PORTFOLIO_REFRESH_COOLDOWN_S == 900
    assert config.BREADTH_AI_REFRESH_COOLDOWN_S == 1800
    assert config.REFRESH_SECTION_COOLDOWNS == {"portfolios": 900, "indicators": 1800}


# ---- Portfolio always enriches (cooldown removed for portfolios) -------------

def test_refresh_market_always_enriches_portfolios_regardless_of_cooldown(tmp_path, monkeypatch):
    """Portfolio enrichment always runs — even when vintage['portfolios'] is fresh."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    now_ts = _fresh_vintage_ts()
    # Seed a cache with a fresh vintage so _in_cooldown("portfolios") would
    # return True if it were called.
    _seed_dashboard_cache(tmp_path, vintage={"portfolios": now_ts})

    # Mock enrich_portfolios to return enriched holdings with live prices.
    enriched_portfolios = {
        "pid1": {
            "id": "pid1",
            "name": "Test",
            "holdings": [
                {"symbol": "NVDA", "shares": 10, "total_cost": 1000, "last_price": 150.0, "pct_daily": 2.0},
            ],
        }
    }

    def mock_enrich(state):
        return {"portfolios": enriched_portfolios}

    monkeypatch.setattr("app.service._portfolio.enrich_portfolios", mock_enrich)
    # Stub heavy external calls
    monkeypatch.setattr("app.market.build_market_snapshot", lambda: {
        "indices": {}, "volatility": {}, "rates": {}, "commodities": {}, "sectors": {},
    })
    monkeypatch.setattr("app.indicators.compute_indicators", lambda s: {})
    monkeypatch.setattr("app.risk.compute_risk", lambda s: {"risk_level": "YELLOW", "signals": [{}]})
    monkeypatch.setattr("app.bottleneck.bottleneck_read", lambda s: {})
    monkeypatch.setattr("app.market.build_futures_snapshot", lambda: {"index_futures": [], "commodities": []})
    monkeypatch.setattr("app.spot.build_spot_snapshot", lambda: {})
    monkeypatch.setattr("app.thirteenf.build_thirteenf", lambda: {})
    monkeypatch.setattr("app.ai_sentiment.compute_ai_sentiment", lambda s, e: {})

    result = service.refresh_market()

    # enrich_portfolios must have been called (cooldown no longer gates it)
    assert result["portfolios"] == enriched_portfolios
    # Live prices are present — not blanked by cooldown
    holdings = result["portfolios"]["pid1"]["holdings"]
    assert holdings[0]["last_price"] == 150.0
    # "portfolio" must NOT appear in cooldown_skip
    assert "portfolio" not in result.get("cooldown_skip", [])


# ---- Breadth-AI / Indicators cooldown ----------------------------------------

def test_refresh_market_respects_breadth_ai_cooldown(tmp_path, monkeypatch):
    """When vintage['indicators'] is fresh, skip indicators computation."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    now_ts = _fresh_vintage_ts()
    cached_indicators = {"breadth": {"breadth_pct": 70.0}, "spy": {"trend": {"state": "uptrend"}}}
    _seed_dashboard_cache(tmp_path, vintage={"indicators": now_ts}, indicators=cached_indicators)

    indicators_called = {"n": 0}

    def spy_indicators(s):
        indicators_called["n"] += 1
        return {}

    monkeypatch.setattr("app.service.indicators.compute_indicators", spy_indicators)
    monkeypatch.setattr("app.market.build_market_snapshot", lambda: {
        "indices": {}, "volatility": {}, "rates": {}, "commodities": {}, "sectors": {},
    })
    monkeypatch.setattr("app.risk.compute_risk", lambda s: {"risk_level": "YELLOW", "signals": [{}]})
    monkeypatch.setattr("app.bottleneck.bottleneck_read", lambda s: {})
    monkeypatch.setattr("app.market.build_futures_snapshot", lambda: {"index_futures": [], "commodities": []})
    monkeypatch.setattr("app.spot.build_spot_snapshot", lambda: {})
    monkeypatch.setattr("app.thirteenf.build_thirteenf", lambda: {})
    monkeypatch.setattr("app.ai_sentiment.compute_ai_sentiment", lambda s, e: {})

    result = service.refresh_market()

    assert "breadth_ai" in result.get("cooldown_skip", [])
    # The cached indicators payload must be reused
    assert result["indicators"] == cached_indicators
    # compute_indicators should NOT have been called
    assert indicators_called["n"] == 0


# ---- Outside cooldown -------------------------------------------------------

def test_refresh_market_refreshes_outside_cooldown(tmp_path, monkeypatch):
    """When vintage['portfolios'] is stale (20 min ago), recompute."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    stale_ts = _stale_vintage_ts(minutes_ago=20)
    _seed_dashboard_cache(tmp_path, vintage={"portfolios": stale_ts})

    enrich_called = {"n": 0}
    real_enrich = service._portfolio.enrich_portfolios

    def spy_enrich(state):
        enrich_called["n"] += 1
        return real_enrich(state)

    monkeypatch.setattr("app.service._portfolio.enrich_portfolios", spy_enrich)
    monkeypatch.setattr("app.market.build_market_snapshot", lambda: {
        "indices": {}, "volatility": {}, "rates": {}, "commodities": {}, "sectors": {},
    })
    monkeypatch.setattr("app.indicators.compute_indicators", lambda s: {})
    monkeypatch.setattr("app.risk.compute_risk", lambda s: {"risk_level": "YELLOW", "signals": [{}]})
    monkeypatch.setattr("app.bottleneck.bottleneck_read", lambda s: {})
    monkeypatch.setattr("app.market.build_futures_snapshot", lambda: {"index_futures": [], "commodities": []})
    monkeypatch.setattr("app.spot.build_spot_snapshot", lambda: {})
    monkeypatch.setattr("app.thirteenf.build_thirteenf", lambda: {})
    monkeypatch.setattr("app.ai_sentiment.compute_ai_sentiment", lambda s, e: {})

    result = service.refresh_market()

    assert "portfolio" not in result.get("cooldown_skip", [])
    # enrich_portfolios should have been called
    assert enrich_called["n"] >= 1


# ---- Unrelated sections still run when indicators in cooldown ----------------

def test_refresh_market_runs_unrelated_sections_even_when_indicators_in_cooldown(tmp_path, monkeypatch):
    """risk, bottleneck, ai_sentiment must still run when indicators are in cooldown."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    now_ts = _fresh_vintage_ts()
    cached_indicators = {"breadth": {"breadth_pct": 75.0}}
    _seed_dashboard_cache(tmp_path, vintage={"indicators": now_ts}, indicators=cached_indicators)

    risk_called = {"n": 0}
    bottleneck_called = {"n": 0}
    ai_sentiment_called = {"n": 0}

    def spy_risk(s):
        risk_called["n"] += 1
        return {"risk_level": "YELLOW", "signals": [{}]}

    def spy_bottleneck(s):
        bottleneck_called["n"] += 1
        return {}

    def spy_ai_sentiment(s, e):
        ai_sentiment_called["n"] += 1
        return {}

    monkeypatch.setattr("app.service.risk.compute_risk", spy_risk)
    monkeypatch.setattr("app.service.bottleneck.bottleneck_read", spy_bottleneck)
    monkeypatch.setattr("app.service.ai_sentiment.compute_ai_sentiment", spy_ai_sentiment)
    monkeypatch.setattr("app.market.build_market_snapshot", lambda: {
        "indices": {}, "volatility": {}, "rates": {}, "commodities": {}, "sectors": {},
    })
    monkeypatch.setattr("app.service.indicators.compute_indicators", lambda s: {})
    monkeypatch.setattr("app.market.build_futures_snapshot", lambda: {"index_futures": [], "commodities": []})
    monkeypatch.setattr("app.spot.build_spot_snapshot", lambda: {})
    monkeypatch.setattr("app.thirteenf.build_thirteenf", lambda: {})

    result = service.refresh_market()

    # indicators were in cooldown, but these must still run
    assert risk_called["n"] == 1
    assert bottleneck_called["n"] == 1
    assert ai_sentiment_called["n"] == 1
    # And breadth_ai should be in cooldown_skip
    assert "breadth_ai" in result.get("cooldown_skip", [])


# ---- Cold cache (no dashboard.json) -----------------------------------------

def test_cooldown_skip_empty_on_cold_cache(tmp_path, monkeypatch):
    """No cached dashboard -> cooldown_skip is []."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    monkeypatch.setattr("app.market.build_market_snapshot", lambda: {
        "indices": {}, "volatility": {}, "rates": {}, "commodities": {}, "sectors": {},
    })
    monkeypatch.setattr("app.indicators.compute_indicators", lambda s: {})
    monkeypatch.setattr("app.risk.compute_risk", lambda s: {"risk_level": "YELLOW", "signals": [{}]})
    monkeypatch.setattr("app.bottleneck.bottleneck_read", lambda s: {})
    monkeypatch.setattr("app.market.build_futures_snapshot", lambda: {"index_futures": [], "commodities": []})
    monkeypatch.setattr("app.spot.build_spot_snapshot", lambda: {})
    monkeypatch.setattr("app.thirteenf.build_thirteenf", lambda: {})
    monkeypatch.setattr("app.ai_sentiment.compute_ai_sentiment", lambda s, e: {})

    result = service.refresh_market()

    assert result.get("cooldown_skip") == []
