"""Tests for app/service.py coverage helpers (no network, no real data)."""

import pytest

from app import config, service, store


# ---- _quote_ok --------------------------------------------------------------

def test_quote_ok_with_price():
    assert service._quote_ok({"price": 100.0}) is True


def test_quote_ok_without_price():
    assert service._quote_ok({"price": None}) is False
    assert service._quote_ok({}) is False


def test_quote_ok_non_dict():
    assert service._quote_ok(None) is False
    assert service._quote_ok(42) is False
    assert service._quote_ok("string") is False


# ---- _count_quotes ----------------------------------------------------------

def test_count_quotes_all_present():
    group = {"^GSPC": {"price": 5000}, "^NDX": {"price": 18000}}
    ok, total = service._count_quotes(group, ["^GSPC", "^NDX"])
    assert ok == 2
    assert total == 2


def test_count_quotes_partial():
    group = {"^GSPC": {"price": 5000}}
    ok, total = service._count_quotes(group, ["^GSPC", "^NDX"])
    assert ok == 1
    assert total == 2


def test_count_quotes_none_group():
    ok, total = service._count_quotes(None, ["^GSPC"])
    assert ok == 0
    assert total == 1


def test_count_quotes_empty_symbols():
    ok, total = service._count_quotes({}, [])
    assert ok == 0
    assert total == 0


def test_count_quotes_missing_price():
    group = {"^GSPC": {"change": 10}}
    ok, total = service._count_quotes(group, ["^GSPC"])
    assert ok == 0
    assert total == 1


# ---- _presence --------------------------------------------------------------

def test_presence_truthy():
    assert service._presence({"data": True}) == {"ok": 1, "total": 1}


def test_presence_falsy():
    assert service._presence(None) == {"ok": 0, "total": 1}
    assert service._presence({}) == {"ok": 0, "total": 1}
    assert service._presence(0) == {"ok": 0, "total": 1}
    assert service._presence("") == {"ok": 0, "total": 1}


# ---- _fresh_timestamp -------------------------------------------------------

def test_fresh_timestamp_valid_iso():
    data = {"as_of": "2026-08-26T12:00:00+00:00"}
    ts = service._fresh_timestamp(data)
    assert ts > 0


def test_fresh_timestamp_invalid():
    data = {"as_of": "not-a-date"}
    ts = service._fresh_timestamp(data)
    assert ts == 0.0


def test_fresh_timestamp_missing():
    data = {}
    ts = service._fresh_timestamp(data)
    assert ts == 0.0


def test_fresh_timestamp_empty_string():
    data = {"as_of": ""}
    ts = service._fresh_timestamp(data)
    assert ts == 0.0


# ---- _coverage_counts (complete payload) ------------------------------------

def _complete_payload():
    """A fully populated dashboard payload with all sections present."""
    # Build enough quote data for all tracked symbols
    indices = {s: {"price": 5000.0} for s in config.INDICES}
    volatility = {s: {"price": 20.0} for s in config.VOLATILITY}
    rates = {s: {"price": 4.0} for s in config.RATES}
    commodities = {s: {"price": 100.0} for s in config.COMMODITIES}
    sectors = {s: {"price": 50.0} for s in config.SECTORS}

    # Indicators
    ai_syms = sorted({t for tickers in config.AI_CAPEX_COHORTS.values() for t in tickers})
    breadth_detail = {s: {"above": True} for s in list(config.INDICES) + list(config.SECTORS)}
    breadth_ai_detail = {s: {"above": True} for s in ai_syms}

    indicators = {
        "breadth": {"breadth_pct": 75.0, "detail": breadth_detail},
        "breadth_ai": {"detail": breadth_ai_detail},
        "spy": {
            "trend": {"state": "uptrend"},
            "realized_vol_annual_pct": 15.0,
        },
        "vix": {"level": 18.0, "signal": "normal"},
    }

    # Risk: 9 signals (RISK_SIGNAL_TOTAL)
    signals = [{"name": f"signal_{i}"} for i in range(9)]

    # Bottleneck: some layers with ROC
    bn = {
        "categories": [{
            "streams": {
                "upstream": {
                    "layers": [
                        {"proxy_40d_roc_pct": 5.0},
                        {"proxy_40d_roc_pct": -3.0},
                    ]
                }
            }
        }]
    }

    # Futures
    fut = {
        "index_futures": [{"last": 5000.0}, {"last": None}],
        "commodities": [{"last": 80.0}],
    }

    # 13F
    tf = {"funds": [{"name": "Berkshire"}, {"name": "Pershing"}]}

    # Earnings
    earn = {"companies": [{"price": 100}, {"price": 200}]}

    # AI sentiment
    ai = {"cohorts": [{"roc_3m_pct": 5.0}, {"roc_3m_pct": None}]}

    return {
        "market": {
            "indices": indices,
            "volatility": volatility,
            "rates": rates,
            "commodities": commodities,
            "sectors": sectors,
        },
        "indicators": indicators,
        "risk": {"signals": signals},
        "bottleneck": bn,
        "futures": fut,
        "thirteenf": tf,
        "earnings": earn,
        "ai_sentiment": ai,
        "news": {"feeds_checked": 4},
        "regime": {"regime": {"regime_label": "Broadening"}},
        "ai_analysis": {"stance": "Risk-On"},
        "events": [{"link": "https://x/1"}],
    }


def test_coverage_counts_complete_payload():
    cov = service._coverage_counts(_complete_payload())

    # Market: all symbols present
    assert cov["indices"]["ok"] == len(config.INDICES)
    assert cov["indices"]["total"] == len(config.INDICES)
    assert cov["volatility"]["ok"] == len(config.VOLATILITY)
    assert cov["rates"]["ok"] == len(config.RATES)
    assert cov["commodities"]["ok"] == len(config.COMMODITIES)
    assert cov["sectors"]["ok"] == len(config.SECTORS)

    # Total market
    expected_market_total = (len(config.INDICES) + len(config.VOLATILITY)
                             + len(config.RATES) + len(config.COMMODITIES)
                             + len(config.SECTORS))
    assert cov["market"]["total"] == expected_market_total
    assert cov["market"]["ok"] == expected_market_total

    # Indicators
    assert cov["indicators"]["total"] == 5
    assert cov["indicators"]["ok"] == 5

    # Risk
    assert cov["risk"]["ok"] == 9
    assert cov["risk"]["total"] == config.RISK_SIGNAL_TOTAL

    # Bottleneck
    assert cov["bottleneck"]["ok"] == 2
    assert cov["bottleneck"]["total"] == 2

    # Futures: 3 items total, 2 with live last
    assert cov["futures"]["total"] == 3
    assert cov["futures"]["ok"] == 2

    # 13F
    assert cov["thirteenf"]["ok"] == 2
    assert cov["thirteenf"]["total"] == len(config.SUPERINVESTORS)

    # Earnings
    assert cov["earnings"]["ok"] == 2
    assert cov["earnings"]["total"] == 2

    # AI sentiment
    assert cov["ai_sentiment"]["ok"] == 1
    assert cov["ai_sentiment"]["total"] == 2

    # Presence sections
    assert cov["news"] == {"ok": 1, "total": 1}
    assert cov["regime"] == {"ok": 1, "total": 1}
    assert cov["ai_analysis"] == {"ok": 1, "total": 1}
    assert cov["events"] == {"ok": 1, "total": 1}


def test_coverage_counts_empty_payload():
    cov = service._coverage_counts({})
    for section in ("indices", "volatility", "rates", "commodities", "sectors"):
        assert cov[section] == {"ok": 0, "total": len(getattr(config, section.upper(), []))}
    assert cov["indicators"]["ok"] == 0
    assert cov["risk"]["ok"] == 0
    assert cov["news"] == {"ok": 0, "total": 1}
    assert cov["regime"] == {"ok": 0, "total": 1}
    assert cov["ai_analysis"] == {"ok": 0, "total": 1}
    assert cov["events"] == {"ok": 0, "total": 1}


def test_coverage_counts_partial_payload():
    """Only indices and risk present; other sections missing."""
    payload = {
        "market": {
            "indices": {"^GSPC": {"price": 5000.0}},
            "volatility": {},
            "rates": {},
            "commodities": {},
            "sectors": {},
        },
        "risk": {"signals": [{"name": "s1"}, {"name": "s2"}]},
    }
    cov = service._coverage_counts(payload)
    assert cov["indices"]["ok"] == 1
    assert cov["indices"]["total"] == len(config.INDICES)
    assert cov["risk"]["ok"] == 2
    assert cov["risk"]["total"] == config.RISK_SIGNAL_TOTAL
    assert cov["indicators"]["ok"] == 0
    assert cov["news"] == {"ok": 0, "total": 1}


def test_coverage_counts_regime_error_not_ok():
    payload = {"regime": {"error": "detector not installed"}}
    cov = service._coverage_counts(payload)
    assert cov["regime"] == {"ok": 0, "total": 1}


def test_coverage_counts_regime_empty_dict_not_ok():
    cov = service._coverage_counts({"regime": {}})
    assert cov["regime"] == {"ok": 0, "total": 1}


# ---- _attach_coverage -------------------------------------------------------

def test_attach_coverage_adds_key():
    result = {}
    out = service._attach_coverage(result)
    assert "coverage" in out
    assert out is result  # mutates in place


def test_attach_coverage_does_not_remove_existing_keys():
    result = {"market": {"indices": {}, "volatility": {}, "rates": {},
                         "commodities": {}, "sectors": {}}}
    service._attach_coverage(result)
    assert "market" in result


# ---- get_dashboard (with stubbed store + refresh) ----------------------------

def test_get_dashboard_returns_enriched_data(monkeypatch, tmp_path):
    """Stub store.load_json to return a cached dashboard and verify _enrich runs."""
    cached_dashboard = {
        "as_of": "2026-08-26T12:00:00+00:00",
        "market": {
            "indices": {"^GSPC": {"price": 5000.0}},
            "volatility": {},
            "rates": {},
            "commodities": {},
            "sectors": {},
        },
    }

    # Make load_json always return our cached dashboard
    monkeypatch.setattr(store, "load_json", lambda *a, **kw: cached_dashboard)
    # Make list_events return empty list
    monkeypatch.setattr(store, "list_events", lambda **kw: [])
    # Stub earnings_calendar to avoid network
    from app import earnings as earnings_mod
    monkeypatch.setattr(earnings_mod, "earnings_calendar", lambda: {"companies": []})
    # Stub regime.get_regime
    from app import regime as regime_mod
    monkeypatch.setattr(regime_mod, "get_regime", lambda: {"regime": {"regime_label": "test"}})
    # Stub store.get_analysis_history
    monkeypatch.setattr(store, "get_analysis_history", lambda **kw: [])

    result = service.get_dashboard()
    assert "events" in result
    assert "earnings" in result
    assert "regime" in result
    assert "coverage" in result


def test_get_dashboard_recomputes_ai_sentiment_from_current_events(monkeypatch):
    """Cached ``ai_sentiment`` was computed at refresh time and would show
    stale "no AI-relevant events" / "insufficient data" until the user clicked
    Refresh. ``_enrich`` must overwrite it from the live event list + earnings
    cache so the gauge always reflects the latest ingest."""
    cached_dashboard = {
        "as_of": "2026-08-26T12:00:00+00:00",
        "market": {
            "indices": {"^GSPC": {"price": 5000.0}},
            "volatility": {}, "rates": {}, "commodities": {}, "sectors": {},
        },
        # Stale gauge — would be shown if _enrich did not recompute.
        "ai_sentiment": {
            "score": 0.0, "verdict": "Balanced / mixed",
            "news": {"tone": "neutral", "note": "no AI-relevant events"},
            "valuation": {"note": "insufficient data", "forward_pe": None},
            "cohorts": [],
        },
    }

    monkeypatch.setattr(store, "load_json", lambda *a, **kw: cached_dashboard)

    # AI-tagged events arrived AFTER the cache was written. With the fix,
    # _enrich should pick them up and the news tone should reflect them.
    ai_events = [
        {"title": "Nvidia AI chip demand soars", "summary": "AI capex boom",
         "tags": ["ai"], "impact": "High", "direction": "bullish",
         "published": "2026-08-26T11:00:00+00:00"},
    ]
    monkeypatch.setattr(store, "list_events",
                        lambda **kw: ai_events if not kw.get("ai_only") else ai_events)
    from app import earnings as earnings_mod
    # Earnings with >=3 forward_pe entries so PE is computed (not "insufficient").
    earnings_payload = {
        "companies": [
            {"symbol": "NVDA", "forward_pe": 35.0, "forward_peg": 1.5},
            {"symbol": "AMD", "forward_pe": 28.0, "forward_peg": 1.2},
            {"symbol": "AVGO", "forward_pe": 22.0, "forward_peg": 1.0},
        ],
    }
    monkeypatch.setattr(earnings_mod, "earnings_calendar", lambda: earnings_payload)

    from app import regime as regime_mod, ai_sentiment as ai_mod, market as market_mod
    monkeypatch.setattr(regime_mod, "get_regime", lambda: {"regime": {}})
    # Stub the history fetch so the test never hits the network/disk cache.
    monkeypatch.setattr(market_mod, "get_histories_bulk",
                        lambda symbols, days=250: {})
    # Force the gauge computation path so the test is deterministic.
    from app import config as cfg
    monkeypatch.setattr(cfg, "NEWS_LOOKBACK_DAYS", 60)
    monkeypatch.setattr(ai_mod, "compute_ai_sentiment",
                        lambda snap, ev, earn: {
                            "score": 42.0,
                            "verdict": "Healthy expansion",
                            "news": {"tone": "bullish",
                                     "note": f"{len(ev)} AI-relevant events"},
                            "valuation": {"forward_pe": 28.0, "forward_peg": 1.2,
                                          "stretched": False,
                                          "note": "median forward PE 28.0"},
                            "cohorts": [],
                            "spread_pct": None,
                            "flip_conditions": [],
                            "as_of": "2026-08-26T12:00:00+00:00",
                        })

    result = service.get_dashboard()

    # The stale "no AI-relevant events" / "insufficient data" must be gone.
    ai = result["ai_sentiment"]
    assert ai["news"]["tone"] == "bullish"
    assert ai["news"]["note"] == "1 AI-relevant events"
    assert ai["valuation"]["forward_pe"] == 28.0
    assert "insufficient" not in ai["valuation"]["note"]


def test_recompute_ai_sentiment_filters_ai_only(monkeypatch):
    """_recompute_ai_sentiment must call list_events with ai_only=True and
    the 60-day cutoff so non-AI events and old events do not leak into the
    gauge (matching refresh_market's call site)."""
    from app import service
    from app import config as cfg

    captured = {}

    def fake_list_events(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(service, "ai_sentiment", type("M", (), {
        "compute_ai_sentiment": lambda *a, **kw: {"score": 0.0, "news": {}, "valuation": {}, "cohorts": []},
    })())
    monkeypatch.setattr(service, "market", type("M", (), {
        "get_histories_bulk": lambda symbols, days=250: {},
    })())
    monkeypatch.setattr(service.store, "list_events", fake_list_events)

    service._recompute_ai_sentiment([], {"companies": []})

    assert captured.get("ai_only") is True
    assert captured.get("limit") == 5000
    assert "since_iso" in captured
    # The cutoff must be ~60 days back from now (NEWS_LOOKBACK_DAYS). Use
    # a small tolerance because the cutoff is computed at call time
    # (microseconds after `expected` here, or microseconds before — the
    # race is what matters, not the order).
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.fromisoformat(captured["since_iso"])
    expected = datetime.now(timezone.utc) - timedelta(days=cfg.NEWS_LOOKBACK_DAYS)
    assert abs((cutoff - expected).total_seconds()) < 5.0
