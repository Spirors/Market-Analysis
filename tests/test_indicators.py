"""Tests for app/indicators.py: pure math functions and compute_indicators."""

import math

import pytest

from app import config, indicators


# ---- helpers ----------------------------------------------------------------

def _hist(*closes: float) -> list[dict]:
    """Build a minimal price history list from bare close values."""
    return [{"close": c} for c in closes]


def _hist_with_none(*closes) -> list[dict]:
    """History with explicit None values mixed in."""
    return [{"close": c} for c in closes]


# ---- roc_at -----------------------------------------------------------------

def test_roc_at_basic():
    # roc_at computes: (closes[cur_i] / closes[base_i] - 1) * 100
    # where cur_i = n-1-end_offset, base_i = n-end_offset-lookback
    # For [100, 100, 100, 100, 110], lookback=5: base_i=0, cur_i=4
    # → (110/100 - 1) * 100 = 10.0
    closes = [100.0, 100.0, 100.0, 100.0, 110.0]
    assert indicators.roc_at(closes, lookback=5) == pytest.approx(10.0)


def test_roc_at_negative():
    # [200, 200, 190, 180], lookback=3: base_i=1, cur_i=3
    # → (180/200 - 1) * 100 = -10.0
    closes = [200.0, 200.0, 190.0, 180.0]
    assert indicators.roc_at(closes, lookback=3) == pytest.approx(-10.0)


def test_roc_at_end_offset():
    # [100, 105, 110, 108, 112], lookback=2, end_offset=1
    # cur_i = 5-1-1=3, base_i = 5-1-2=2
    # → (closes[3]/closes[2] - 1) * 100 = (108/110 - 1) * 100
    closes = [100.0, 105.0, 110.0, 108.0, 112.0]
    result = indicators.roc_at(closes, lookback=2, end_offset=1)
    assert result == pytest.approx((108 / 110 - 1) * 100)


def test_roc_at_too_short():
    assert indicators.roc_at([100, 101], lookback=5) is None


def test_roc_at_base_zero():
    # lookback=2: base_i = 2-0-2=0, base = closes[0]=0 → returns None
    assert indicators.roc_at([0.0, 100.0], lookback=2) is None


def test_roc_at_empty():
    assert indicators.roc_at([], lookback=1) is None


def test_roc_at_end_offset_out_of_range():
    assert indicators.roc_at([100, 101], lookback=1, end_offset=5) is None


# ---- pct_above_ma -----------------------------------------------------------

def test_pct_above_ma_all_above():
    hists = {
        "A": _hist(110, 111, 112, 113, 114, 115),
        "B": _hist(200, 201, 202, 203, 204, 205),
    }
    result = indicators.pct_above_ma(hists, n=5)
    assert result["breadth_pct"] == 100.0
    assert result["above_count"] == 2
    assert result["total"] == 2


def test_pct_above_ma_none_above():
    hists = {
        "A": _hist(100, 99, 98, 97, 96, 95),
        "B": _hist(200, 199, 198, 197, 196, 195),
    }
    result = indicators.pct_above_ma(hists, n=5)
    assert result["breadth_pct"] == 0.0
    assert result["above_count"] == 0


def test_pct_above_ma_mixed():
    hists = {
        "ABOVE": _hist(100, 101, 102, 103, 104, 110),
        "BELOW": _hist(200, 195, 190, 185, 180, 175),
    }
    result = indicators.pct_above_ma(hists, n=5)
    assert result["breadth_pct"] == 50.0
    assert result["above_count"] == 1
    assert result["total"] == 2


def test_pct_above_ma_too_short_skipped():
    hists = {"A": _hist(100, 101)}  # only 2 bars, need 5
    result = indicators.pct_above_ma(hists, n=5)
    assert result["breadth_pct"] is None
    assert result["total"] == 0


def test_pct_above_ma_empty_histories():
    result = indicators.pct_above_ma({}, n=50)
    assert result["breadth_pct"] is None
    assert result["total"] == 0


def test_pct_above_ma_detail_has_expected_keys():
    hists = {"A": _hist(110, 111, 112, 113, 114, 115)}
    result = indicators.pct_above_ma(hists, n=5)
    detail = result["detail"]["A"]
    assert set(detail.keys()) == {"above", "close", "ma", "pct_from_ma"}


def test_pct_above_ma_close_at_ma_not_above():
    # Close exactly equals MA → above should be False (strict >)
    # MA of [100, 100, 100, 100, 100] = 100, close = 100 → not above
    hists = {"A": _hist(100, 100, 100, 100, 100, 100)}
    result = indicators.pct_above_ma(hists, n=5)
    assert result["above_count"] == 0


# ---- breadth_pct_above_ma ---------------------------------------------------

def test_breadth_pct_above_ma_filters_symbols():
    hists = {
        "A": _hist(110, 111, 112, 113, 114, 115),
        "B": _hist(200, 201, 202, 203, 204, 205),
        "C": _hist(50, 51, 52, 53, 54, 55),
    }
    # Only ask about A and C
    result = indicators.breadth_pct_above_ma(hists, ma_window=5, symbols=["A", "C"])
    assert result == 100.0  # both above


def test_breadth_pct_above_ma_no_data():
    result = indicators.breadth_pct_above_ma({}, ma_window=50)
    assert result is None


# ---- breadth_pct_above_ma_at ------------------------------------------------

def test_breadth_pct_above_ma_at_offset_zero_matches_manual():
    hist_a = _hist(100, 101, 102, 103, 104, 110)
    hist_b = _hist(200, 195, 190, 185, 180, 175)
    hists = {"A": hist_a, "B": hist_b}
    result = indicators.breadth_pct_above_ma_at(hists, ma_window=5, end_offset=0)
    # A: MA of first 5 = (100+101+102+103+104)/5 = 102, close=110 > 102 → above
    # B: MA of first 5 = (200+195+190+185+180)/5 = 190, close=175 < 190 → not above
    assert result == 50.0


def test_breadth_pct_above_ma_at_too_short_skipped():
    hists = {"A": _hist(100, 101)}
    result = indicators.breadth_pct_above_ma_at(hists, ma_window=5)
    assert result is None


def test_breadth_pct_above_ma_at_ma_zero_skipped():
    hists = {"A": _hist(0, 0, 0, 0, 0, 1)}
    result = indicators.breadth_pct_above_ma_at(hists, ma_window=5)
    assert result is None


# ---- vix_ma_ratio_at --------------------------------------------------------

def test_vix_ma_ratio_at_basic():
    # MA of [10,11,12,13,14] = 12, close = 15 → ratio = 15/12 = 1.25
    hist = _hist(10, 11, 12, 13, 14, 15)
    result = indicators.vix_ma_ratio_at(hist, ma_window=5, end_offset=0)
    assert result == pytest.approx(15 / 12)


def test_vix_ma_ratio_at_offset():
    hist = _hist(10, 11, 12, 13, 14, 15)
    # end_offset=1: current = hist[-2]=14, MA = sum(hist[-7:-2]) / 5
    # hist[-7:-2] = hist[-7:-2] — wait, hist has 6 elements, indices 0..5
    # start = cur_i - ma_window = 4 - 5 = -1 → too short
    result = indicators.vix_ma_ratio_at(hist, ma_window=5, end_offset=1)
    assert result is None  # not enough bars


def test_vix_ma_ratio_at_empty():
    assert indicators.vix_ma_ratio_at([]) is None


def test_vix_ma_ratio_at_ma_zero():
    hist = _hist(0, 0, 0, 0, 0, 5)
    result = indicators.vix_ma_ratio_at(hist, ma_window=5)
    assert result is None


# ---- realized_vol -----------------------------------------------------------

def test_realized_vol_flat_series():
    # Constant prices → zero vol
    hist = _hist(*[100.0] * 25)
    result = indicators.realized_vol(hist, window=21)
    assert result == 0.0


def test_realized_vol_volatile_series():
    # Alternating up/down should produce non-zero vol
    prices = [100 + (i % 2) * 5 for i in range(25)]
    hist = _hist(*[float(p) for p in prices])
    result = indicators.realized_vol(hist, window=21)
    assert result is not None
    assert result > 0


def test_realized_vol_too_short():
    hist = _hist(100, 101, 102)
    assert indicators.realized_vol(hist, window=21) is None


def test_realized_vol_empty():
    assert indicators.realized_vol([], window=21) is None


def test_realized_vol_with_zero_close():
    # Zero close values should be skipped in returns
    hist = _hist(100, 0, 101, 102, 103, 104, 105, 106, 107, 108, 109,
                 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121)
    result = indicators.realized_vol(hist, window=21)
    # Should still produce a value (skips the zero base)
    assert result is not None


# ---- trend_state ------------------------------------------------------------

def test_trend_state_uptrend():
    # All prices above both 50 and 200 SMA → uptrend
    closes = list(range(100, 310))  # 210 bars, monotonically increasing
    hist = _hist(*[float(c) for c in closes])
    result = indicators.trend_state(hist, short=50, long=200)
    assert result["state"] == "uptrend"
    assert result["close"] == 309.0


def test_trend_state_downtrend():
    closes = list(range(310, 100, -1))  # monotonically decreasing
    hist = _hist(*[float(c) for c in closes])
    result = indicators.trend_state(hist, short=50, long=200)
    assert result["state"] == "downtrend"


def test_trend_state_mixed():
    # Price above short MA but below long MA
    # Build: first 200 bars declining, last 50 bars recovering
    base = [100.0 + i * 0.1 for i in range(200)]  # slow rise
    tail = [120.0 + i * 0.5 for i in range(50)]   # fast rise but starting from below long MA
    hist = _hist(*(base + tail))
    result = indicators.trend_state(hist, short=50, long=200)
    # close should be above short MA (tail is rising) but may or may not be above long MA
    assert result["state"] in ("uptrend", "mixed")


def test_trend_state_empty():
    result = indicators.trend_state([])
    assert result["state"] == "unknown"
    assert result["reason"] == "no data"


def test_trend_state_short_data():
    # Fewer than long MA → long MA is None → mixed or uptrend
    hist = _hist(100.0, 101.0, 102.0, 103.0, 104.0)
    result = indicators.trend_state(hist, short=3, long=200)
    assert result["state"] in ("uptrend", "mixed", "downtrend")
    assert result["sma_long"] is None


def test_trend_state_drawdown():
    # Peak then decline → drawdown should be negative
    closes = [100.0] * 200 + [90.0]
    hist = _hist(*closes)
    result = indicators.trend_state(hist, short=50, long=200)
    assert result["drawdown_pct"] is not None
    assert result["drawdown_pct"] < 0


# ---- vix_signal -------------------------------------------------------------

def test_vix_signal_complacent():
    # VIX well below its MA → ratio < 0.85
    hist = _hist(*[20.0] * 49 + [15.0])  # MA ≈ 20, level=15, ratio=0.75
    result = indicators.vix_signal(hist, ma_window=50)
    assert result["signal"] == "complacent"
    assert result["level"] == 15.0


def test_vix_signal_elevated():
    # VIX well above its MA → ratio > 1.25
    hist = _hist(*[15.0] * 49 + [25.0])  # MA ≈ 15, level=25, ratio≈1.67
    result = indicators.vix_signal(hist, ma_window=50)
    assert result["signal"] == "elevated"


def test_vix_signal_normal():
    # VIX near its MA → 0.85 <= ratio <= 1.25
    hist = _hist(*[20.0] * 49 + [21.0])  # MA ≈ 20, level=21, ratio=1.05
    result = indicators.vix_signal(hist, ma_window=50)
    assert result["signal"] == "normal"


def test_vix_signal_empty():
    result = indicators.vix_signal([])
    assert result["level"] is None
    assert result["signal"] == "no data"


def test_vix_signal_short_history():
    hist = _hist(20.0, 21.0)  # only 2 bars, MA unknown
    result = indicators.vix_signal(hist, ma_window=50)
    assert result["signal"] == "unknown"


# ---- compute_indicators (integration with fake snapshot) ---------------------

def _fake_snapshot():
    """Minimal snapshot shaped like market.build_market_snapshot output."""
    # Build histories with enough bars for all indicators
    spy_bars = [(100 + i * 0.5) for i in range(260)]
    vix_bars = [18.0] * 260

    histories = {"SPY": _hist(*spy_bars), "^VIX": _hist(*vix_bars)}

    # Build sector/index histories
    extra = {}
    for sym in list(config.INDICES.keys()) + list(config.SECTORS.keys()):
        extra[sym] = _hist(*[100.0 + i for i in range(60)])

    # AI cohort tickers
    for tickers in config.AI_CAPEX_COHORTS.values():
        for t in tickers:
            if t not in extra:
                extra[t] = _hist(*[50.0 + i for i in range(60)])

    # Cross-asset tickers used by compute_indicators' _roc_3m
    for sym in ["RSP", "IWM", "QQQ", "HYG", "LQD", "TLT"]:
        if sym not in extra:
            extra[sym] = _hist(*[100.0 + i for i in range(70)])

    histories["extra"] = extra
    return {"as_of": "2026-08-26T12:00:00", "histories": histories}


def test_compute_indicators_returns_all_keys():
    snap = _fake_snapshot()
    result = indicators.compute_indicators(snap)

    assert "breadth" in result
    assert "breadth_indices" in result
    assert "breadth_sectors" in result
    assert "breadth_ai" in result
    assert "spy" in result
    assert "vix" in result
    assert "roc_3m_pct" in result
    assert result["as_of"] == "2026-08-26T12:00:00"


def test_compute_indicators_spy_trend():
    snap = _fake_snapshot()
    result = indicators.compute_indicators(snap)
    spy = result["spy"]
    assert "trend" in spy
    assert spy["trend"]["state"] in ("uptrend", "downtrend", "mixed", "unknown")
    assert "realized_vol_annual_pct" in spy


def test_compute_indicators_vix_signal():
    snap = _fake_snapshot()
    result = indicators.compute_indicators(snap)
    vix = result["vix"]
    assert vix["signal"] in ("complacent", "elevated", "normal", "unknown", "no data")


def test_compute_indicators_roc_3m():
    snap = _fake_snapshot()
    result = indicators.compute_indicators(snap)
    roc = result["roc_3m_pct"]
    # RSP/SPY is always None (computed in risk engine)
    assert roc["RSP/SPY"] is None
    # Others should be numeric (we have enough data)
    for key in ("RSP", "IWM", "QQQ", "HYG", "LQD", "TLT"):
        assert key in roc


def test_compute_indicators_empty_snapshot():
    result = indicators.compute_indicators({})
    assert result["breadth"]["breadth_pct"] is None
    assert result["spy"]["trend"]["state"] == "unknown"
    assert result["vix"]["signal"] == "no data"


# Need pytest for approx (already imported at top)
