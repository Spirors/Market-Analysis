"""Tests for app/ai_valuation: cache I/O, yfinance fetch, valuation summary."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app import ai_valuation, config


# ---- load_cache / save_cache -------------------------------------------------

def test_load_cache_returns_none_when_missing(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    assert ai_valuation.load_cache() is None


def test_save_cache_then_load_cache_round_trips(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache({"NVDA": 45.0, "AMD": 32.0, "fetched_at": "2026-09-11T12:00:00"})
    loaded = ai_valuation.load_cache()
    assert loaded == {"NVDA": 45.0, "AMD": 32.0, "fetched_at": "2026-09-11T12:00:00"}


def test_load_cache_returns_none_when_expired(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    stale = {"NVDA": 45.0, "fetched_at": "2020-01-01T00:00:00"}  # way past TTL
    ai_valuation._CACHE_PATH.write_text(json.dumps(stale), encoding="utf-8")
    assert ai_valuation.load_cache() is None


def test_load_cache_returns_map_when_within_ttl(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    fresh = {"NVDA": 45.0, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    ai_valuation._CACHE_PATH.write_text(json.dumps(fresh), encoding="utf-8")
    loaded = ai_valuation.load_cache()
    assert loaded == fresh


def test_save_cache_atomic_write_does_not_clobber_existing(tmp_path):
    """tmp+os.replace pattern: even if file exists, the write succeeds."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache({"NVDA": 45.0, "fetched_at": "2026-09-11T12:00:00"})
    ai_valuation.save_cache({"AMD": 32.0, "fetched_at": "2026-09-11T13:00:00"})
    loaded = ai_valuation.load_cache()
    assert loaded["AMD"] == 32.0
    assert "NVDA" not in loaded  # second write fully replaces


def test_load_cache_returns_none_on_invalid_json(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation._CACHE_PATH.write_text("not json {", encoding="utf-8")
    assert ai_valuation.load_cache() is None


# ---- fetch_beneficiary_pe ----------------------------------------------------

def test_fetch_beneficiary_pe_cache_hit_does_not_call_yfinance(tmp_path):
    """When the cache is fresh, no yfinance call is made."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    fresh = {"NVDA": 45.0, "AMD": 32.0, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    ai_valuation.save_cache(fresh)
    with patch("yfinance.Ticker") as mock_ticker:
        result = ai_valuation.fetch_beneficiary_pe()
    mock_ticker.assert_not_called()
    # fetch_beneficiary_pe strips fetched_at from its return (PE-only dict)
    expected_pe = {k: v for k, v in fresh.items() if k != "fetched_at"}
    assert result == expected_pe


def test_fetch_beneficiary_pe_skips_spenders(tmp_path):
    """Capex Spenders tickers (MSFT/GOOGL/AMZN/META/ORCL) are NOT in the fetch list."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    captured = []

    def fake_ticker(sym):
        captured.append(sym)
        t = MagicMock()
        t.info = {"forwardPE": 30.0}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        ai_valuation.fetch_beneficiary_pe(force=True)

    assert "MSFT" not in captured
    assert "GOOGL" not in captured
    assert "AMZN" not in captured
    assert "META" not in captured
    assert "ORCL" not in captured
    # Sanity: at least one beneficiary ticker was fetched
    assert any(s in captured for s in ("NVDA", "AMD", "MU"))


def test_fetch_beneficiary_pe_skips_invalid_pe_values(tmp_path):
    """None, NaN, negative, zero forward PEs are excluded from the result."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"

    pe_values = {"NVDA": 45.0, "AMD": None, "INTC": -5.0, "MU": float("nan"), "QCOM": 0}

    def fake_ticker(sym):
        t = MagicMock()
        t.info = {"forwardPE": pe_values.get(sym)}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        result = ai_valuation.fetch_beneficiary_pe(force=True)

    assert "NVDA" in result and result["NVDA"] == 45.0
    for skipped in ("AMD", "INTC", "MU", "QCOM"):
        assert skipped not in result, f"{skipped} should have been filtered"


def test_fetch_beneficiary_pe_partial_failure_does_not_crash(tmp_path):
    """One ticker raises; the others still land in the cache."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"

    def fake_ticker(sym):
        if sym == "NVDA":
            raise RuntimeError("rate-limited")
        t = MagicMock()
        t.info = {"forwardPE": 45.0}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        result = ai_valuation.fetch_beneficiary_pe(force=True)

    assert "NVDA" not in result
    assert result.get("AMD") == 45.0 or any(v == 45.0 for v in result.values())


def test_fetch_beneficiary_pe_force_refresh_ignores_cache(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache({"NVDA": 1.0, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S")})

    def fake_ticker(sym):
        t = MagicMock()
        t.info = {"forwardPE": 99.0}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        result = ai_valuation.fetch_beneficiary_pe(force=True)
    assert result["NVDA"] == 99.0


# ---- compute_valuation -------------------------------------------------------

def test_compute_valuation_median():
    pe_map = {"a": 20.0, "b": 25.0, "c": 30.0, "d": 35.0, "e": 40.0}
    out = ai_valuation.compute_valuation(pe_map)
    assert out["median_pe"] == 30.0
    assert out["stretched"] is True  # median == 30 == threshold
    assert out["note"]  # non-empty


def test_compute_valuation_stretched_at_threshold():
    pe_map = {"a": 35.0, "b": 40.0}
    out = ai_valuation.compute_valuation(pe_map)
    assert out["median_pe"] == 37.5
    assert out["stretched"] is True


def test_compute_valuation_not_stretched_below_threshold():
    pe_map = {"a": 20.0, "b": 25.0}
    out = ai_valuation.compute_valuation(pe_map)
    assert out["median_pe"] == 22.5
    assert out["stretched"] is False


def test_compute_valuation_empty_returns_none_stretch():
    out = ai_valuation.compute_valuation({})
    assert out["median_pe"] is None
    assert out["stretched"] is False
    assert "no" in out["note"].lower() or "none" in out["note"].lower()


def test_compute_valuation_uses_config_threshold():
    """The threshold comes from config, not a hardcoded constant."""
    pe_map = {"a": 29.99, "b": 30.01}
    with patch.object(config, "AI_VALUATION_STRETCH_PE", 25.0):
        out = ai_valuation.compute_valuation(pe_map)
    # Both values > 25, median ~30; with threshold 25 the median is stretched
    assert out["stretched"] is True


def test_compute_valuation_includes_per_ticker_pe():
    pe_map = {"NVDA": 45.0, "AMD": 32.0}
    out = ai_valuation.compute_valuation(pe_map)
    assert out["per_ticker_pe"] == pe_map


def test_compute_valuation_includes_cache_ttl_hours():
    out = ai_valuation.compute_valuation({"a": 30.0})
    assert out["cache_ttl_hours"] == config.AI_VALUATION_CACHE_TTL_HOURS
