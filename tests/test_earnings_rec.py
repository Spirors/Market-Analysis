"""Tests for app/earnings.py pure helpers (no network)."""

import math

import pytest

from app import earnings


# ---- _to_float --------------------------------------------------------------

def test_to_float_none():
    assert earnings._to_float(None) is None


def test_to_float_valid():
    assert earnings._to_float(42) == 42.0
    assert earnings._to_float("3.14") == pytest.approx(3.14)


def test_to_float_nan_filtered():
    assert earnings._to_float(float("nan")) is None


def test_to_float_rounds_to_3dp():
    assert earnings._to_float(1.23456) == 1.235
    assert earnings._to_float(1.23444) == 1.234


def test_to_float_non_numeric():
    assert earnings._to_float("abc") is None
    assert earnings._to_float([]) is None


def test_to_float_zero():
    assert earnings._to_float(0) == 0.0


# ---- _fmt_billions ----------------------------------------------------------

def test_fmt_billions_trillions():
    assert earnings._fmt_billions(1_500_000_000_000) == "1.50T"
    assert earnings._fmt_billions(2_300_000_000_000) == "2.30T"


def test_fmt_billions_billions():
    assert earnings._fmt_billions(50_000_000_000) == "50.00B"
    assert earnings._fmt_billions(1_200_000_000) == "1.20B"


def test_fmt_billions_millions():
    assert earnings._fmt_billions(500_000_000) == "500.00M"
    assert earnings._fmt_billions(1_500_000) == "1.50M"


def test_fmt_billions_small():
    assert earnings._fmt_billions(999) == "999"
    assert earnings._fmt_billions(0) == "0"
    # 42.5 with :.0f uses banker's rounding → "42"
    assert earnings._fmt_billions(42.5) == "42"
    assert earnings._fmt_billions(43.5) == "44"


def test_fmt_billions_none():
    assert earnings._fmt_billions(None) is None


def test_fmt_billions_non_numeric():
    assert earnings._fmt_billions("abc") is None
    assert earnings._fmt_billions([]) is None


def test_fmt_billions_string_numeric():
    assert earnings._fmt_billions("1500000000") == "1.50B"


# ---- _52w_high --------------------------------------------------------------

def test_52w_high_basic():
    series = [{"close": 100}, {"close": 150}, {"close": 120}]
    assert earnings._52w_high(series) == 150.0


def test_52w_high_rounds_to_4dp():
    series = [{"close": 100.12345}]
    assert earnings._52w_high(series) == 100.1235  # rounded to 4dp


def test_52w_high_empty():
    assert earnings._52w_high([]) is None


def test_52w_high_all_none():
    series = [{"close": None}, {"close": None}]
    assert earnings._52w_high(series) is None


def test_52w_high_skips_none():
    series = [{"close": None}, {"close": 100}, {"close": None}, {"close": 150}]
    assert earnings._52w_high(series) == 150.0


# ---- _pct_change ------------------------------------------------------------

def test_pct_change_basic():
    series = [{"close": 100}, {"close": 110}]
    # 7-day change: need 8 elements; only 2 → None
    assert earnings._pct_change(series, 7) is None


def test_pct_change_valid():
    series = [{"close": 100 + i} for i in range(10)]
    # 5-day change: cur=series[-1]=109, prev=series[-6]=104
    result = earnings._pct_change(series, 5)
    assert result == pytest.approx((109 / 104 - 1) * 100, abs=0.001)


def test_pct_change_insufficient_history():
    series = [{"close": 100}, {"close": 105}]
    assert earnings._pct_change(series, 7) is None


def test_pct_change_zero_base():
    # For days_back=7, prev = series[-8]. In a 9-element series, series[-8] = series[1].
    series = [{"close": 100}, {"close": 0}, {"close": 10}, {"close": 20},
              {"close": 30}, {"close": 40}, {"close": 50},
              {"close": 60}, {"close": 80}]
    assert earnings._pct_change(series, 7) is None  # prev=0


def test_pct_change_none_close():
    # series[-8] = series[1] must have close=None for prev to be None
    series = [{"close": 100}, {"close": None}, {"close": 10}, {"close": 20},
              {"close": 30}, {"close": 40}, {"close": 50},
              {"close": 60}, {"close": 80}]
    assert earnings._pct_change(series, 7) is None


def test_pct_change_one_day():
    series = [{"close": 100}, {"close": 105}]
    result = earnings._pct_change(series, 1)
    assert result == pytest.approx(5.0, abs=0.001)


# ---- _ai_rec ----------------------------------------------------------------

def test_ai_rec_bullish():
    row = {"forward_pe": 25, "pct_7d": 2.0, "dist_52w_high_pct": -10}
    rec = earnings._ai_rec(row)
    assert rec["signal"] == "Bullish"
    assert rec["color"] == "#3B6D11"


def test_ai_rec_cautious_expensive():
    row = {"forward_pe": 60, "pct_7d": 2.0, "dist_52w_high_pct": -10}
    rec = earnings._ai_rec(row)
    assert rec["signal"] == "Cautious"
    assert rec["color"] == "#A32D2D"


def test_ai_rec_cautious_momentum_breakdown():
    row = {"forward_pe": 25, "pct_7d": -10.0, "dist_52w_high_pct": -10}
    rec = earnings._ai_rec(row)
    assert rec["signal"] == "Cautious"


def test_ai_rec_cautious_far_below_high():
    row = {"forward_pe": 25, "pct_7d": 2.0, "dist_52w_high_pct": -30}
    rec = earnings._ai_rec(row)
    assert rec["signal"] == "Cautious"


def test_ai_rec_neutral_mixed():
    # PE is fine, but momentum is between -3 and -8, dist is between -20 and -25
    row = {"forward_pe": 40, "pct_7d": -5.0, "dist_52w_high_pct": -22}
    rec = earnings._ai_rec(row)
    assert rec["signal"] == "Neutral"
    assert rec["color"] == "#B9860B"


def test_ai_rec_neutral_defaults():
    # All fields missing → Neutral with "mixed signals"
    rec = earnings._ai_rec({})
    assert rec["signal"] == "Neutral"
    assert "mixed signals" in rec["reason"]


def test_ai_rec_bullish_boundary_pe():
    # PE=34, mom7=-3, dist_52w=-20 → all boundaries met for Bullish
    row = {"forward_pe": 34, "pct_7d": -3.0, "dist_52w_high_pct": -20}
    rec = earnings._ai_rec(row)
    assert rec["signal"] == "Bullish"


def test_ai_rec_bullish_just_outside_pe():
    # PE=35 → not <35, so not Bullish
    row = {"forward_pe": 35, "pct_7d": 2.0, "dist_52w_high_pct": -10}
    rec = earnings._ai_rec(row)
    assert rec["signal"] == "Neutral"


def test_ai_rec_cautious_boundary_pe():
    # PE=51 → >50 → Cautious
    row = {"forward_pe": 51, "pct_7d": 2.0, "dist_52w_high_pct": -10}
    rec = earnings._ai_rec(row)
    assert rec["signal"] == "Cautious"


def test_ai_rec_cautious_boundary_momentum():
    # mom7=-8.1 → < -8 → Cautious
    row = {"forward_pe": 30, "pct_7d": -8.1, "dist_52w_high_pct": -10}
    rec = earnings._ai_rec(row)
    assert rec["signal"] == "Cautious"


def test_ai_rec_cautious_boundary_dist():
    # dist=-25.1 → < -25 → Cautious
    row = {"forward_pe": 30, "pct_7d": 2.0, "dist_52w_high_pct": -25.1}
    rec = earnings._ai_rec(row)
    assert rec["signal"] == "Cautious"
