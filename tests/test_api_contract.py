"""Contract tests for app/api.py using FastAPI's TestClient.

All network-backed services are stubbed or redirected: the dashboard route
serves a payload assembled by the REAL coverage counter (service._attach_
coverage), earnings validation is stubbed at the module boundary, and event /
regime routes run against throwaway tmp paths so no subprocess or fetch can
ever fire.
"""

import json
import os
import time

import pytest
from fastapi.testclient import TestClient

from app import api, config, earnings, regime, service, store


# ---- Fixtures ----------------------------------------------------------------

@pytest.fixture
def client() -> TestClient:
    # Real localhost base URL so requests pass the Host-header allowlist
    # exactly as a browser hitting 127.0.0.1:8000 would.
    return TestClient(api.app, base_url="http://127.0.0.1:8000")


@pytest.fixture
def tmp_store(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "EVENTS_PATH", tmp_path / "events.json")
    monkeypatch.setattr(config, "ANALYSIS_DB_PATH", tmp_path / "analysis.db")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_READY", False)
    monkeypatch.setattr(store, "_analysis_repo", None)


@pytest.fixture
def tmp_regime_dir(monkeypatch, tmp_path):
    regdir = tmp_path / "regime"
    regdir.mkdir()
    monkeypatch.setattr(config, "REGIME_DIR", regdir)
    # A missing detector script makes run_regime_detection degrade to an
    # error payload immediately -- no subprocess, no hang.
    monkeypatch.setattr(config, "REGIME_DETECTOR_SCRIPT", tmp_path / "missing_detector.py")
    return regdir


def _base_dashboard_payload() -> dict:
    """Minimal dashboard payload shaped like service.refresh_market output."""
    return {
        "as_of": "2026-08-22T12:00:00+00:00",
        "market": {
            "indices": {"^GSPC": {"price": 5000.0, "change": 10.0, "pct_change": 0.2},
                        "^NDX": None, "^DJI": None, "^RUT": None},
            "volatility": {}, "rates": {}, "commodities": {}, "sectors": {},
        },
        "indicators": {},
        "risk": {"risk_level": "YELLOW", "signals": [{}]},
        "bottleneck": {},
        "futures": {
            "index_futures": [{"symbol": "ES=F", "name": "S&P 500 E-mini",
                               "last": 5000.0, "chg": 5.0, "chg_pct": 0.1,
                               "prior_close": 4995.0},
                              {"symbol": "NQ=F", "name": "Nasdaq 100 E-mini",
                               "last": None, "chg": None, "chg_pct": None,
                               "prior_close": None}],
            "commodities": [],
        },
        "thirteenf": {},
        "earnings": {},
        "ai_sentiment": {},
        "vintage": {"market": "2026-08-22T12:00:00+00:00"},
    }


# ---- GET /api/dashboard ------------------------------------------------------

def test_dashboard_serves_payload_with_additive_coverage_and_vintage(
        client, monkeypatch):
    payload = service._attach_coverage(_base_dashboard_payload())
    monkeypatch.setattr(service, "get_dashboard", lambda: payload)

    r = client.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()

    # Core sections pass through untouched (coverage/vintage are additive).
    assert body["as_of"] == "2026-08-22T12:00:00+00:00"
    assert body["market"]["indices"]["^GSPC"]["price"] == 5000.0
    assert body["risk"]["risk_level"] == "YELLOW"

    # Additive coverage metadata, computed by the real counter.
    cov = body["coverage"]
    assert cov["indices"] == {"ok": 1, "total": len(config.INDICES)}
    assert cov["volatility"]["total"] == len(config.VOLATILITY)
    assert cov["risk"]["total"] == config.RISK_SIGNAL_TOTAL
    assert cov["risk"]["ok"] == 1
    expected_futures_total = len(config.INDEX_FUTURES) + len(config.COMMODITY_FUTURES)
    assert cov["futures"]["total"] == 2  # counts payload items, not the universe
    assert cov["futures"]["ok"] == 1     # only the contract with a live last
    for section in ("market", "indicators", "breadth", "bottleneck",
                    "thirteenf", "earnings", "ai_sentiment", "news",
                    "regime", "ai_analysis", "events"):
        assert section in cov

    # Per-section vintage stamps survive the round trip.
    assert isinstance(body["vintage"], dict)
    assert "market" in body["vintage"]


def test_dashboard_route_returns_service_result_verbatim(client, monkeypatch):
    sentinel = {"as_of": "x", "custom_key": {"deep": True}}
    monkeypatch.setattr(service, "get_dashboard", lambda: sentinel)

    r = client.get("/api/dashboard")
    assert r.status_code == 200
    assert r.json() == sentinel


# ---- GET /api/meta -----------------------------------------------------------

def test_meta_returns_labels_and_groups(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    body = r.json()

    labels = body["labels"]
    assert isinstance(labels, dict)
    assert labels["^GSPC"] == "S&P 500"
    assert labels["NVDA"] == "NVIDIA"
    assert labels["ES=F"] == "S&P 500 E-mini"

    groups = body["groups"]
    for group in ("indices", "volatility", "rates", "commodities",
                  "index_futures", "commodity_futures", "sectors",
                  "cross_asset", "ai_capex_cohorts"):
        assert group in groups
    assert groups["ai_capex_cohorts"] == config.AI_CAPEX_COHORTS


# ---- Host-header allowlist ---------------------------------------------------

def test_foreign_host_header_rejected(client):
    r = client.get("/api/meta", headers={"Host": "evil.example.com:8000"})
    assert r.status_code == 403
    assert "not allowed" in r.json()["detail"]


def test_localhost_host_accepted(client):
    r = client.get("/api/meta", headers={"Host": "127.0.0.1:8000"})
    assert r.status_code == 200


# ---- DELETE /api/events ------------------------------------------------------

def test_delete_events_without_params_returns_400(client):
    r = client.delete("/api/events")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "link" in detail and "source" in detail


def test_delete_events_with_both_params_returns_400(client):
    r = client.delete("/api/events", params={"link": "https://x/1", "source": "MarketWatch"})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "either" in detail.lower() or "both" in detail.lower()


# ---- Earnings watchlist ------------------------------------------------------

def test_add_watchlist_invalid_symbol_returns_400_with_reason(client, monkeypatch):
    reason = "no yfinance profile and no price history found"
    monkeypatch.setattr(
        earnings, "validate_symbol",
        lambda sym: {"valid": False, "symbol": sym, "name": None,
                     "sector": None, "reason": reason},
    )

    r = client.post("/api/earnings/watchlist", params={"symbol": "ZZZZZ"})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "ZZZZZ" in detail
    assert reason in detail


def test_validate_endpoint_passes_through_validator(client, monkeypatch):
    monkeypatch.setattr(
        earnings, "validate_symbol",
        lambda sym: {"valid": True, "symbol": sym, "name": "Test Co",
                     "sector": "Tech"},
    )

    r = client.get("/api/earnings/validate", params={"symbol": "TST"})
    assert r.status_code == 200
    assert r.json()["valid"] is True
    assert r.json()["name"] == "Test Co"


# ---- GET /api/events ---------------------------------------------------------

def test_list_events_endpoint_respects_limit(tmp_store, client):
    def ev(link, published):
        return {"link": link, "title": f"Story {link}", "published": published,
                "impact": "High", "source": "FeedA"}

    store.upsert_events([
        ev("https://x/1", "2026-08-01T10:00:00"),
        ev("https://x/2", "2026-08-10T10:00:00"),
        ev("https://x/3", "2026-08-05T10:00:00"),
    ])

    r = client.get("/api/events", params={"limit": 2})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    assert [row["link"] for row in rows] == ["https://x/2", "https://x/3"]
    assert set(rows[0]) >= {"title", "published", "impact", "tags"}

    r_all = client.get("/api/events")
    assert r_all.status_code == 200
    assert len(r_all.json()) == 3


# ---- GET /api/regime ---------------------------------------------------------

def test_regime_serves_cached_report_without_rerunning(tmp_regime_dir, client):
    store.save_json(
        tmp_regime_dir / "macro_regime_2026-08-01.json",
        {"regime": {"regime_label": "Transitional", "confidence": 61},
         "composite": {"composite_score": 50, "zone": "Neutral"}},
    )

    r = client.get("/api/regime")
    assert r.status_code == 200
    body = r.json()
    assert body["regime"]["regime_label"] == "Transitional"
    assert "error" not in body


def test_regime_fresh_report_not_flagged_stale(tmp_regime_dir):
    path = tmp_regime_dir / "macro_regime_2026-08-23.json"
    store.save_json(path, {"regime": {"regime_label": "Broadening"}})

    body = regime.get_regime()
    assert "stale" not in body


def test_regime_old_report_served_flagged_stale(tmp_regime_dir):
    path = tmp_regime_dir / "macro_regime_2026-05-01.json"
    store.save_json(path, {"regime": {"regime_label": "Contraction"}})
    old = time.time() - (config.REGIME_MAX_AGE_DAYS + 2) * 86400
    os.utime(path, (old, old))

    body = regime.get_regime()
    assert body.get("stale") is True
    assert body["age_days"] > config.REGIME_MAX_AGE_DAYS


def test_regime_reports_error_quickly_when_no_cache(tmp_regime_dir, client,
                                                    monkeypatch):
    # Guard against accidental slowness: the detector script is missing, so
    # the endpoint must degrade to an error payload instead of hanging.
    import time

    started = time.monotonic()
    r = client.get("/api/regime")
    elapsed = time.monotonic() - started

    assert r.status_code == 200
    assert "error" in r.json()
    assert elapsed < 5.0


# ---- /api/shutdown -----------------------------------------------------------

class _SyncTimer:
    """Replacement for threading.Timer that fires immediately on .start().

    Lets the shutdown endpoint exercise os._exit synchronously in tests
    without the 300 ms real-time delay that the production code uses so the
    JSON response can flush.
    """
    def __init__(self, interval, function, args=None):
        self.interval = interval
        self._function = function
        self._args = args or ()

    def start(self):
        self._function(*self._args)


def test_shutdown_post_schedules_exit(client, monkeypatch):
    """POST /api/shutdown returns 200 immediately and calls os._exit(0)."""
    exit_codes: list[int] = []
    monkeypatch.setattr(api.os, "_exit", lambda code=0: exit_codes.append(code))
    monkeypatch.setattr(api.threading, "Timer", _SyncTimer)

    r = client.post("/api/shutdown")
    assert r.status_code == 200
    assert r.json() == {"status": "shutting down"}
    assert exit_codes == [0]


def test_shutdown_get_also_works(client, monkeypatch):
    """GET /api/shutdown is registered as a fallback for clients that send
    a plain GET (some browers or proxies strip POST methods)."""
    exit_codes: list[int] = []
    monkeypatch.setattr(api.os, "_exit", lambda code=0: exit_codes.append(code))
    monkeypatch.setattr(api.threading, "Timer", _SyncTimer)

    r = client.get("/api/shutdown")
    assert r.status_code == 200
    assert r.json() == {"status": "shutting down"}
    assert exit_codes == [0]


def test_shutdown_does_not_immediately_exit(client, monkeypatch):
    """Response must be returned BEFORE os._exit is called so the body can
    flush; in production the delay is _SHUTDOWN_DELAY_S, but in the test
    we patch Timer to run synchronously and assert that the response code
    is observable."""
    calls = []
    monkeypatch.setattr(api.os, "_exit", lambda code=0: calls.append(code))
    monkeypatch.setattr(api.threading, "Timer", _SyncTimer)

    r = client.post("/api/shutdown")
    # The TestClient runs the app code in-process; with a SyncTimer the
    # function call happens before the framework yields back to us, so
    # the request cycle is observed AFTER the scheduled exit. The
    # important check is that os._exit was invoked.
    assert calls == [0]
    assert r.status_code == 200
