"""Property-based tests for app/indicators.py using Hypothesis.

Verifies mathematical invariants that hold for all valid inputs:
- pct_above_ma is always in [0, 100]
- vix_signal monotonicity: higher ratio → same or higher signal severity
- realized_vol is non-negative
- roc_at sign symmetry over mirrored series
"""

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from app import indicators


# ---- Helpers for building valid histories ------------------------------------

def _valid_close():
    """Strategy: positive float close price (guards against log-of-zero)."""
    return st.floats(min_value=0.01, max_value=1_000_000, allow_nan=False, allow_infinity=False)


def _history(n: int = 60):
    """Strategy: list of n price-history dicts with positive closes."""
    return st.lists(
        _valid_close(),
        min_size=n,
        max_size=n,
    ).map(lambda closes: [{"close": c} for c in closes])


# ---- pct_above_ma in [0, 100] ------------------------------------------------

@given(
    closes_a=st.lists(_valid_close(), min_size=5, max_size=200),
    closes_b=st.lists(_valid_close(), min_size=5, max_size=200),
)
@settings(max_examples=200)
def test_pct_above_ma_always_in_range(closes_a, closes_b):
    """Breadth % must always be between 0 and 100."""
    hists = {
        "A": [{"close": c} for c in closes_a],
        "B": [{"close": c} for c in closes_b],
    }
    result = indicators.pct_above_ma(hists, n=5)
    pct = result["breadth_pct"]
    if pct is not None:
        assert 0 <= pct <= 100, f"breadth_pct={pct} out of range"


@given(closes=st.lists(_valid_close(), min_size=5, max_size=100))
@settings(max_examples=200)
def test_single_symbol_pct_above_ma_binary(closes):
    """With one symbol, breadth is either 0 or 100."""
    hists = {"X": [{"close": c} for c in closes]}
    result = indicators.pct_above_ma(hists, n=5)
    pct = result["breadth_pct"]
    if pct is not None:
        assert pct in (0.0, 100.0), f"single-symbol breadth should be 0 or 100, got {pct}"


# ---- realized_vol non-negative ------------------------------------------------

@given(closes=st.lists(_valid_close(), min_size=3, max_size=300))
@settings(max_examples=200)
def test_realized_vol_non_negative(closes):
    """Annualized volatility must never be negative."""
    hist = [{"close": c} for c in closes]
    result = indicators.realized_vol(hist, window=21)
    if result is not None:
        assert result >= 0, f"realized_vol={result} is negative"


# ---- roc_at sign symmetry over mirrored series --------------------------------

@given(base=_valid_close(), factor=st.floats(min_value=0.5, max_value=2.0))
@settings(max_examples=200)
def test_roc_at_sign_symmetry(base, factor):
    """roc_at on [base, base*factor] should be positive when factor>1 and
    negative when factor<1 (for lookback=2)."""
    series = [base, base * factor]
    result = indicators.roc_at(series, lookback=2)
    if result is not None:
        if factor > 1:
            assert result > 0, f"expected positive ROC for factor={factor}, got {result}"
        elif factor < 1:
            assert result < 0, f"expected negative ROC for factor={factor}, got {result}"
        else:
            assert result == 0, f"expected zero ROC for factor=1.0, got {result}"


# ---- vix_signal monotonicity --------------------------------------------------

@given(ratio=st.floats(min_value=0.01, max_value=5.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=200)
def test_vix_signal_level_monotonic(ratio):
    """A synthetic series where level/ma ≈ ratio produces the expected
    signal bucket.  Higher ratios never produce a 'lower' signal.

    Uses 500 bars so the single-level bar has negligible impact on the
    50-day SMA (MA ≈ ma_val, and the actual ratio ≈ level / ma_val).

    The MA includes the last bar, so the *actual* ratio seen by vix_signal
    is ``50 * ratio / (49 + ratio)``.  Test boundaries are derived from
    that formula against vix_signal's thresholds (0.85 / 1.25):
      - complacent boundary: ratio < 0.847  (actual < 0.85)
      - elevated boundary:   ratio > 1.257  (actual > 1.25)
    """
    ma_val = 20.0
    level = ma_val * ratio
    # Build 500-bar history: first 499 bars = ma_val, last bar = level.
    hist = [{"close": ma_val}] * 499 + [{"close": level}]
    result = indicators.vix_signal(hist, ma_window=50)

    if ratio < 0.847:
        assert result["signal"] == "complacent"
    elif ratio > 1.26:
        assert result["signal"] == "elevated"
    else:
        assert result["signal"] == "normal"
