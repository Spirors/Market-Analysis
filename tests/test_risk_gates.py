"""Reachability tests for app/risk.py gates on synthetic histories.

No network: every scenario feeds hand-built OHLC-close lists shaped so each
signal's tone is unambiguous (slopes far beyond the config bands). The point
is that the RED gates actually FIRE when their evidence is present -- including
when only a few signals have data -- and that the valuation-stretch signal is
alive on both sides of its threshold.
"""

import math
from datetime import date, timedelta

from app import config, risk

N_BARS = 210  # >= 200 so SPY trend sees its long MA; >= 127 for correlations


# ---- Synthetic series helpers ------------------------------------------------

def _hist(closes) -> list[dict]:
    start = date(2026, 1, 1)
    return [
        {"date": (start + timedelta(days=i)).isoformat(), "close": float(v)}
        for i, v in enumerate(closes)
    ]


def _ramp(start: float, end: float, n: int = N_BARS) -> list[float]:
    step = (end - start) / (n - 1)
    return [start + i * step for i in range(n)]


def _gramp(start: float, end: float, n: int = N_BARS) -> list[float]:
    """Geometric ramp: constant *percentage* steps, i.e. constant log returns.

    Linear ramps make daily-return magnitudes drift, which flips the sign of
    the stock-bond correlation signal; geometric series keep it unambiguous.
    """
    g = (end / start) ** (1 / (n - 1))
    return [start * g ** i for i in range(n)]


def _wobble(vals: list[float], sign: int = 1, amp: float = 0.01) -> list[float]:
    """Deterministic sinusoidal perturbation giving returns real variance.

    Pure constant-return series leave Pearson correlation at the mercy of
    float noise; a shared sine wave with equal (`sign=1`) or opposite
    (`sign=-1`) phase pins the stock-bond correlation near +/-1.
    """
    return [v * (1 + sign * amp * math.sin(i)) for i, v in enumerate(vals)]


def _accelerating_qqq() -> list[dict]:
    """Geometric growth whose rate steps up mid-series: 3m ROC is high AND
    higher than it was 9 bars ago (extended + accelerating)."""
    vals = []
    c = 300.0
    for i in range(N_BARS):
        vals.append(c)
        c *= 1.01 if i >= 149 else 1.002
    return _hist(vals)


def _breadth_extra(shape_fn) -> dict[str, list[dict]]:
    """Histories for every INDICES+SECTORS symbol (the breadth universe)."""
    symbols = list(config.INDICES) + list(config.SECTORS)
    return {s: _hist(shape_fn()) for s in symbols}


def _consensus_optimism_snapshot() -> dict:
    """Everything bullish: broad breadth (rising), broadening leadership,
    suppressed vol (falling), credit risk-on, small-caps leading, negative
    stock-bond correlation, SPY uptrend, and an extending AI theme."""
    spy = _wobble(_gramp(400, 520), sign=1)
    histories = {
        "SPY": _hist(spy),
        "RSP": _hist([110.0] * 140 + _ramp(110, 150, 70)),   # RSP/SPY strongly up
        "^VIX": _hist([20.0] * 150 + _ramp(20, 10, 60)),     # complacent + falling
        "HYG": _hist([80.0] * 140 + _ramp(80, 88, 70)),      # HYG/LQD up
        "LQD": _hist([100.0] * N_BARS),
        "IWM": _hist([180.0] * 140 + _ramp(180, 220, 70)),   # IWM/SPY up
        "TLT": _hist(_wobble(_gramp(150, 100), sign=-1)),    # bonds hedge (corr < 0)
        "QQQ": _accelerating_qqq(),                          # AI theme flag
        "extra": {},
    }
    # Breadth universe rises everywhere except one laggard that only pops
    # above its 50DMA in the last 5 bars => breadth is high AND rising.
    laggard = list(config.SECTORS)[0]
    extra = {}
    for s in list(config.INDICES) + list(config.SECTORS):
        if s == laggard:
            extra[s] = _hist([100.0] * (N_BARS - 5) + [106.0] * 5)
        else:
            extra[s] = _hist(_ramp(100, 130))
    histories["extra"] = extra
    return {"as_of": "2026-08-01T12:00:00+00:00", "histories": histories}


def _capitulation_snapshot() -> dict:
    """Everything bearish: washed-out breadth, narrowing leadership, elevated
    vol, credit risk-off, small-caps lagging, positive correlation, downtrend
    with a deep drawdown."""
    spy = _wobble(_gramp(520, 400), sign=1)
    histories = {
        "SPY": _hist(spy),
        "RSP": _hist(_ramp(140, 85)),                        # falls faster than SPY
        "^VIX": _hist([12.0] * 150 + _ramp(12, 45, 60)),     # elevated
        "HYG": _hist([80.0] * N_BARS),
        "LQD": _hist(_ramp(100, 112)),                       # HYG/LQD down
        "IWM": _hist(_ramp(260, 150)),                       # falls faster than SPY
        "TLT": _hist(_wobble(_gramp(140, 100), sign=1)),     # bonds sell off too (corr > 0)
        "extra": {},
    }
    histories["extra"] = _breadth_extra(lambda: _ramp(130, 100))
    return {"as_of": "2026-08-01T12:00:00+00:00", "histories": histories}


def _sparse_snapshot(vix_hist: list[dict], include_qqq: bool = False) -> dict:
    """Only three tone-bearing signals have data: Concentration, VIX, SPY trend."""
    histories = {
        "SPY": _hist(_gramp(400, 520)),
        "RSP": _hist([110.0] * 140 + _ramp(110, 150, 70)),
        "^VIX": vix_hist,
        "extra": {},
    }
    if include_qqq:
        histories["QQQ"] = _accelerating_qqq()
    return {"as_of": "2026-08-01T12:00:00+00:00", "histories": histories}


_VIX_COMPLACENT = [20.0] * 150 + _ramp(20, 10, 60)
_VIX_ELEVATED = [12.0] * 150 + _ramp(12, 45, 60)


# ---- Gate reachability -------------------------------------------------------

def test_consensus_optimism_red_fires_when_bullish_signals_dominate():
    res = risk.compute_risk(_consensus_optimism_snapshot())

    assert res["risk_level"] == "RED"
    assert res["consensus_optimism"] is True
    assert res["verdict"].startswith("Consensus optimism")
    # All seven data-backed signals are bullish; gate = max(3, ceil(.6*7)) = 5.
    assert res["counts"]["bullish"] == 7
    assert res["counts"]["bearish"] == 0
    assert len(res["signals"]) == 7
    # Fragility evidence backs the call: overheating breadth + deepening VIX
    # complacency (+ the extending-AI-theme flag).
    flags = " | ".join(f["flag"] for f in res["fragility_flags"])
    assert "breadth overheating" in flags
    assert "VIX complacency deepening" in flags
    assert len(res["fragility_flags"]) >= 2


def test_capitulation_red_fires_on_bearish_signals_plus_drawdown():
    res = risk.compute_risk(_capitulation_snapshot())

    assert res["risk_level"] == "RED"
    assert res["verdict"].startswith("Washout")
    assert res["counts"]["bearish"] == 7
    assert res["counts"]["bullish"] == 0
    flags = " | ".join(f["flag"] for f in res["fragility_flags"])
    assert "washed out" in flags          # breadth washout flag
    assert "drawdown" in flags            # SPY ~-23% from highs


def test_sparse_data_scales_gate_so_consensus_red_still_reachable():
    """Only 3 signals have data; gate scales to max(3, ceil(.6*3)) = 3.

    With the old absolute '>= 5 bullish' gate this RED was unreachable at
    this coverage; the scaled gate plus two fragility flags must fire it.
    """
    snap = _sparse_snapshot(_hist(_VIX_COMPLACENT), include_qqq=True)
    res = risk.compute_risk(snap)

    assert len(res["signals"]) == 3            # Concentration, VIX, SPY trend
    assert res["counts"]["bullish"] == 3
    assert res["counts"]["bearish"] == 0
    assert res["consensus_optimism"] is True   # 3 bullish >= scaled gate of 3
    assert res["risk_level"] == "RED"
    assert len(res["fragility_flags"]) >= 2    # VIX deepening + AI extension


def test_sparse_data_divided_signals_stay_green():
    """Thin data with genuinely divided tones must NOT trip any RED gate."""
    snap = _sparse_snapshot(_hist(_VIX_ELEVATED), include_qqq=False)
    res = risk.compute_risk(snap)

    assert res["counts"] == {"bullish": 2, "bearish": 1, "neutral": 0}
    assert res["consensus_optimism"] is False
    assert res["fragility_flags"] == []
    assert res["risk_level"] == "GREEN"
    assert res["verdict"].startswith("Divided sentiment")


# ---- Valuation stretch (regression guard for the dead-signal bug) ------------

def _earnings(pes: list[tuple[str, float]]) -> dict:
    return {"companies": [{"symbol": s, "forward_pe": pe} for s, pe in pes]}


def test_valuation_stretch_fires_at_threshold():
    """Median PE exactly at config.VALUATION_STRETCH_PE must fire (>= band)."""
    earnings = _earnings([("NVDA", 40.0), ("MSFT", 30.0), ("AMD", 25.0)])
    median_pe, threshold = risk._valuation_stretched(earnings)

    assert threshold == config.VALUATION_STRETCH_PE
    assert median_pe == config.VALUATION_STRETCH_PE  # median of 40/30/25

    res = risk.compute_risk({"histories": {}}, earnings)
    assert any("stretched" in f["flag"] for f in res["fragility_flags"])


def test_valuation_stretch_silent_below_threshold():
    earnings = _earnings([("NVDA", 28.0), ("MSFT", 25.0), ("AMD", 22.0)])
    median_pe, _ = risk._valuation_stretched(earnings)
    assert median_pe is not None
    assert median_pe < config.VALUATION_STRETCH_PE

    res = risk.compute_risk({"histories": {}}, earnings)
    assert not any("stretched" in f["flag"] for f in res["fragility_flags"])


def test_valuation_stretch_needs_three_ai_names():
    """Fewer than 3 AI-cohort names with a forward PE => insufficient data."""
    earnings = _earnings([("NVDA", 90.0), ("MSFT", 85.0)])
    median_pe, threshold = risk._valuation_stretched(earnings)
    assert median_pe is None and threshold is None

    res = risk.compute_risk({"histories": {}}, earnings)
    assert res["fragility_flags"] == []


def test_valuation_stretch_ignores_non_ai_names():
    earnings = _earnings([("XOM", 100.0), ("JPM", 95.0), ("KO", 90.0)])
    median_pe, _ = risk._valuation_stretched(earnings)
    assert median_pe is None

    res = risk.compute_risk({"histories": {}}, earnings)
    assert res["fragility_flags"] == []


# ---- Degenerate inputs -------------------------------------------------------

def test_empty_and_zero_inputs_do_not_crash():
    for snap in (
        {},
        {"histories": {}},
        {"histories": {"SPY": [], "^VIX": [], "extra": {}}},
    ):
        res = risk.compute_risk(snap)
        # No tone-bearing data => neither RED gate may fire; unanimity of an
        # empty signal set reads as divided (GREEN).
        assert res["signals"] == []
        assert res["counts"] == {"bullish": 0, "bearish": 0, "neutral": 0}
        assert res["division_score"] == 1.0
        assert res["risk_level"] == "GREEN"


def test_null_closes_are_ignored_not_fatal():
    snap = {"histories": {
        "SPY": [{"date": "2026-01-01", "close": None},
                {"date": "2026-01-02", "close": 500.0}],
        "^VIX": [],
        "extra": {},
    }}
    res = risk.compute_risk(snap)  # must not raise
    assert isinstance(res["risk_level"], str)


def test_correlation_window_too_short_returns_none():
    """Signal 6's helper must abstain (None) when the window does not fit."""
    a = _hist(_ramp(100, 200))
    b = _hist(_ramp(200, 100))
    assert risk._correlation(a[:10], b[:10]) is None
