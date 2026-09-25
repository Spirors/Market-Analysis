"""Tests for app/ai_valuation: cache I/O, yfinance fetch, valuation summary."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
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
    # Fresh timestamp: a hardcoded date rots past the 12h TTL and breaks
    # load_cache() (as happened when 2026-09-11 aged out).
    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    ai_valuation.save_cache({"NVDA": 45.0, "AMD": 32.0, "fetched_at": fetched_at})
    loaded = ai_valuation.load_cache()
    assert loaded == {"NVDA": 45.0, "AMD": 32.0, "fetched_at": fetched_at}


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
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    ai_valuation.save_cache({"NVDA": 45.0, "fetched_at": now})
    ai_valuation.save_cache({"AMD": 32.0, "fetched_at": now})
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


# ---- read-modify-write: the two key sets never clobber each other ------------

def _fresh_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


_METRIC_ENTRY = {
    "market_cap": 1.2e12,
    "revenue_growth": 0.18,
    "forward_pe": 33.4,
    "as_of": "2026-09-25T12:00:00Z",
}


def test_save_cache_preserves_sibling_metrics_on_pe_replace(tmp_path):
    """Explicit pe_map replaces the cohort set but keeps per_ticker_metrics."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache(
        {"OLD": 10.0, "fetched_at": _fresh_stamp()},
        metrics={"AVGO": dict(_METRIC_ENTRY)},
    )
    ai_valuation.save_cache(pe_map={"NVDA": 48.2}, fetched_at=_fresh_stamp())

    doc = json.loads(ai_valuation._CACHE_PATH.read_text(encoding="utf-8"))
    assert doc["NVDA"] == 48.2
    assert "OLD" not in doc  # cohort set replaced wholesale
    assert doc["per_ticker_metrics"]["AVGO"] == _METRIC_ENTRY


def test_fetch_beneficiary_force_refresh_preserves_metrics_on_disk(tmp_path):
    """(a) The data-loss bug: force-refreshing PE must not delete metrics."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache(
        {"NVDA": 48.2, "fetched_at": _fresh_stamp()},
        metrics={"AVGO": dict(_METRIC_ENTRY)},
    )

    def fake_ticker(sym):
        t = MagicMock()
        t.info = {"forwardPE": 40.0}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        ai_valuation.fetch_beneficiary_pe(force=True)

    # Assert on the reloaded document, not the return value.
    doc = json.loads(ai_valuation._CACHE_PATH.read_text(encoding="utf-8"))
    assert doc["per_ticker_metrics"]["AVGO"] == _METRIC_ENTRY
    assert doc["NVDA"] == 40.0  # PE set refreshed


def test_fetch_ticker_metrics_preserves_cohort_pe_and_wires_breadth_ai(tmp_path):
    """(b) A metrics refresh must not blank the cohort PE / breadth_ai view."""
    from app import indicators  # imported here to keep the module hermetic

    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache({"NVDA": 48.2, "fetched_at": _fresh_stamp()})

    def fake_ticker(sym):
        t = MagicMock()
        t.info = {"marketCap": 5.0e11, "revenueGrowth": 0.2, "forwardPE": 33.0}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        ai_valuation.fetch_ticker_metrics(["AVGO"], force=True)

    doc = json.loads(ai_valuation._CACHE_PATH.read_text(encoding="utf-8"))
    assert doc["NVDA"] == 48.2  # cohort PE survived the metrics write
    assert "AVGO" not in {k for k in doc if k not in ai_valuation._META_KEYS}

    breadth_ai = {"detail": {"NVDA": {}}}
    indicators.wire_forward_pe(breadth_ai)
    assert breadth_ai["detail"]["NVDA"]["forward_pe"] == 48.2


def test_compute_valuation_ignores_per_ticker_metrics(tmp_path):
    """(c) Display metrics never leak into the cohort median."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    pe_map = {"a": 20.0, "b": 25.0, "c": 30.0}
    doc = {
        **pe_map,
        "fetched_at": _fresh_stamp(),
        "per_ticker_metrics": {"XYZ": dict(_METRIC_ENTRY)},
    }

    with_metrics = ai_valuation.compute_valuation(doc)
    without_metrics = ai_valuation.compute_valuation(pe_map)

    assert with_metrics["per_ticker_pe"] == pe_map
    assert all(isinstance(v, (int, float)) for v in with_metrics["per_ticker_pe"].values())
    assert "per_ticker_metrics" not in with_metrics["per_ticker_pe"]
    assert with_metrics["median_pe"] == without_metrics["median_pe"] == 25.0


def test_fetch_ticker_metrics_shared_symbol_copies_cohort_pe_exactly(tmp_path):
    """(d) A symbol in both universes shows the cohort PE exactly, not a refetch."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache({"NVDA": 48.2, "fetched_at": _fresh_stamp()})

    def fake_ticker(sym):
        t = MagicMock()
        # Deliberately different from the cohort PE; the card must NOT use it.
        t.info = {"marketCap": 3.0e12, "revenueGrowth": 0.9, "forwardPE": 99.9}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        out = ai_valuation.fetch_ticker_metrics(["NVDA", "AVGO"], force=True)

    assert out["NVDA"]["forward_pe"] == 48.2  # exact equality, not approx
    assert out["AVGO"]["forward_pe"] == 99.9  # non-cohort keeps its own fetched value

    doc = json.loads(ai_valuation._CACHE_PATH.read_text(encoding="utf-8"))
    assert doc["NVDA"] == 48.2  # cohort PE lives flat at the top level
    assert doc["per_ticker_metrics"]["NVDA"]["forward_pe"] == 48.2
    assert out["NVDA"]["forward_pe"] == ai_valuation.compute_valuation(doc)["per_ticker_pe"]["NVDA"]


# ---- fetch_ticker_metrics: signed values, honesty, provenance ---------------

def test_fetch_ticker_metrics_stores_signed_pe_unfiltered(tmp_path):
    """A negative forward PE is real fetched data for the card, but never in the median."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"

    def fake_ticker(sym):
        t = MagicMock()
        t.info = {"marketCap": 1.0e9, "revenueGrowth": -0.4, "forwardPE": -7.4}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        out = ai_valuation.fetch_ticker_metrics(["LOSS"], force=True)

    assert out["LOSS"]["forward_pe"] == -7.4

    doc = json.loads(ai_valuation._CACHE_PATH.read_text(encoding="utf-8"))
    assert "LOSS" not in ai_valuation.compute_valuation(doc)["per_ticker_pe"]


def test_fetch_ticker_metrics_raise_absent_and_absent_field_null(tmp_path):
    """Fetch raised -> absent; fetched-but-missing field -> None with an as_of."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"

    def fake_ticker(sym):
        if sym == "BAD":
            raise RuntimeError("rate-limited")
        t = MagicMock()
        t.info = {"forwardPE": 12.5}  # no marketCap / revenueGrowth
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        out = ai_valuation.fetch_ticker_metrics(["BAD", "PARTIAL"], force=True)

    assert "BAD" not in out
    assert out["PARTIAL"]["market_cap"] is None
    assert out["PARTIAL"]["revenue_growth"] is None
    assert out["PARTIAL"]["forward_pe"] == 12.5
    assert out["PARTIAL"]["as_of"]


def test_fetch_ticker_metrics_as_of_is_iso8601_utc(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"

    def fake_ticker(sym):
        t = MagicMock()
        t.info = {"marketCap": 1.0, "revenueGrowth": 0.1, "forwardPE": 5.0}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        out = ai_valuation.fetch_ticker_metrics(["X"], force=True)

    as_of = out["X"]["as_of"]
    assert as_of.endswith("Z")
    parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(None)


def test_fetch_ticker_metrics_cache_first_and_force(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache(
        metrics={"AVGO": dict(_METRIC_ENTRY)},
        fetched_at=_fresh_stamp(),
    )

    with patch("yfinance.Ticker") as mock_ticker:
        out = ai_valuation.fetch_ticker_metrics(["AVGO"])
    mock_ticker.assert_not_called()
    assert out["AVGO"]["forward_pe"] == 33.4

    def fake_ticker(sym):
        t = MagicMock()
        t.info = {"marketCap": 9.0e9, "revenueGrowth": 0.5, "forwardPE": 21.0}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker) as mock_ticker:
        forced = ai_valuation.fetch_ticker_metrics(["AVGO"], force=True)
    assert mock_ticker.call_count == 1
    assert forced["AVGO"]["forward_pe"] == 21.0


# ---- load_ticker_metrics degradation + round-trip ---------------------------

@pytest.mark.parametrize(
    "payload",
    [
        None,  # missing file handled separately below
        "not json {",
        json.dumps({"per_ticker_metrics": {"X": dict(_METRIC_ENTRY)},
                    "fetched_at": "2020-01-01T00:00:00"}),  # expired
        json.dumps({"per_ticker_metrics": {"X": dict(_METRIC_ENTRY)}}),  # no fetched_at
    ],
)
def test_load_ticker_metrics_degrades_to_empty(tmp_path, payload):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    if payload is None:
        if ai_valuation._CACHE_PATH.exists():
            ai_valuation._CACHE_PATH.unlink()
    else:
        ai_valuation._CACHE_PATH.write_text(payload, encoding="utf-8")
    assert ai_valuation.load_ticker_metrics() == {}


def test_fetch_ticker_metrics_round_trips(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"

    def fake_ticker(sym):
        t = MagicMock()
        t.info = {"marketCap": 4.0e10, "revenueGrowth": 0.25, "forwardPE": 17.5}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        written = ai_valuation.fetch_ticker_metrics(["RT"], force=True)

    reloaded = ai_valuation.load_ticker_metrics()
    assert reloaded["RT"] == written["RT"]


# ---- cross-view consistency: the reader is the authority ---------------------

def test_load_ticker_metrics_overlays_live_cohort_pe(tmp_path):
    """A shared symbol must report the live cohort PE, not a frozen copy.

    Otherwise refreshing the cohort set would leave the card serving a stale PE
    while breadth_ai served the new one -- two views disagreeing about one
    number.
    """
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache(
        {"NVDA": 48.2, "fetched_at": _fresh_stamp()},
        metrics={"NVDA": dict(_METRIC_ENTRY)},  # entry froze forward_pe at 33.4
    )
    # The cohort set moves on; the frozen metrics entry does not.
    ai_valuation.save_cache(pe_map={"NVDA": 55.0}, fetched_at=_fresh_stamp())

    reloaded = ai_valuation.load_ticker_metrics()
    assert reloaded["NVDA"]["forward_pe"] == 55.0
    # And it equals exactly what breadth_ai's source reports.
    breadth_pe = ai_valuation.compute_valuation(ai_valuation.load_cache())["per_ticker_pe"]
    assert reloaded["NVDA"]["forward_pe"] == breadth_pe["NVDA"]
    # A non-cohort symbol keeps its own signed value untouched.
    assert reloaded["NVDA"]["market_cap"] == _METRIC_ENTRY["market_cap"]


def test_load_ticker_metrics_leaves_non_cohort_symbols_alone(tmp_path):
    """The overlay must not invent a cohort entry for a display-only ticker."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache(
        {"NVDA": 48.2, "fetched_at": _fresh_stamp()},
        metrics={"AXTI": {**_METRIC_ENTRY, "forward_pe": -7.4}},
    )
    reloaded = ai_valuation.load_ticker_metrics()
    assert reloaded["AXTI"]["forward_pe"] == -7.4
    # The cohort set must not have gained the display ticker.
    assert set(ai_valuation._cohort_pe_map(ai_valuation.load_cache())) == {"NVDA"}


def test_fetch_beneficiary_pe_fresh_empty_cache_does_not_refetch(tmp_path):
    """A fresh cache with no valid PE must not trigger a network walk.

    Regression guard: an ``if pe_map:`` guard here would put the whole cohort
    fetch on every serve whenever the last fetch found nothing valid.
    """
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache(
        {"fetched_at": _fresh_stamp()},
        metrics={"AXTI": dict(_METRIC_ENTRY)},
    )

    with patch("yfinance.Ticker") as ticker:
        out = ai_valuation.fetch_beneficiary_pe()
        ticker.assert_not_called()

    assert out == {}


def test_cache_path_is_isolated_under_tmp_path(tmp_path):
    """Autouse fixture redirects the module-level path off the real data dir."""
    assert ai_valuation._CACHE_PATH == tmp_path / "ai_valuation.json"
