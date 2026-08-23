"""Golden tests for app/analysis.py (deterministic weighted-vote synthesis).

The expected scores below are hand-computed from the weight table in the
module docstring (weights: risk 3, regime 2, breadth 2, and seven inputs at
weight 1 => total 14). Any change to weights or mappings that shifts these
golden values must be a conscious decision.
"""

import pytest

from app import analysis


# ---- Payload builders -------------------------------------------------------

def _full_payload(bullish: bool = True) -> dict:
    """A dashboard payload where every scored input is populated.

    `bullish=True` maps every input to its most bullish tone; False maps every
    input to its most bearish tone.
    """
    sign = 1 if bullish else -1
    return {
        "as_of": "2026-08-22T12:00:00+00:00",
        "risk": {
            "risk_level": "GREEN" if bullish else "RED",
            "verdict": "Divided sentiment" if bullish else "Washout",
            "counts": {"bullish": 4 if bullish else 1,
                       "bearish": 4 if bullish else 6,
                       "neutral": 1},
            "consensus_optimism": False,
            "fragility_flags": [],
            "flip_conditions": [],
            "signals": [],
        },
        "regime": {
            "regime": {"regime_label": "Broadening" if bullish else "Contraction",
                       "confidence": 72},
            "composite": {"composite_score": 66 if bullish else 31,
                          "zone": "Expansion" if bullish else "Contraction"},
        },
        "indicators": {
            "breadth": {"breadth_pct": 70 if bullish else 30},
            "vix": {"level": 12.0 if bullish else 28.0,
                    "signal": "complacent" if bullish else "elevated",
                    "ma": 16.0},
            "spy": {"trend": {"state": "uptrend" if bullish else "downtrend",
                              "drawdown_pct": -2.0 if bullish else -14.0}},
        },
        "futures": {
            "index_futures": [
                {"symbol": "ES=F", "chg_pct": 0.5 * sign},
                {"symbol": "NQ=F", "chg_pct": 0.6 * sign},
            ]
        },
        "bottleneck": {
            "categories": [
                {"proxy_40d_roc_pct": 8.0 * sign},
                {"proxy_40d_roc_pct": 9.0 * sign},
            ],
            "strongest_signal": {"layer": "HBM", "proxy_40d_roc_pct": 9.0 * sign},
        },
        "earnings": {
            "companies": (
                [{"symbol": "NVDA", "rec_signal": "Bullish"},
                 {"symbol": "MSFT", "rec_signal": "Bullish"},
                 {"symbol": "AAPL", "rec_signal": "Bullish"},
                 {"symbol": "KO", "rec_signal": "Neutral"}]
                if bullish else
                [{"symbol": "NVDA", "rec_signal": "Cautious"},
                 {"symbol": "MSFT", "rec_signal": "Cautious"},
                 {"symbol": "AAPL", "rec_signal": "Neutral"}]
            )
        },
        "events": [
            {"published": "2026-08-20T09:00:00Z",
             "tags": ["bullish" if bullish else "bearish"]},
        ],
        "thirteenf": {
            "quarter": "2026-Q2",
            "funds": [
                # Non-AI top holding -> no AI-overlap penalty when bullish;
                # NVDA in top-3 -> overlap >= 50% -> penalty when bearish.
                {"name": "Fund A", "top": [{"ticker": "XOM" if bullish else "NVDA",
                                            "weight_pct": 21.0}]},
            ],
        },
    }


# ---- Golden cases -----------------------------------------------------------

def test_golden_fully_bullish_payload():
    """Every input bullish: num = 3+2+2+0.5+1+1+0.5+0.5+0.5+0 = 11, den = 14."""
    result = analysis.build_analysis(_full_payload(bullish=True))

    assert result["score"] == pytest.approx(78.6)          # 11 / 14 * 100
    assert result["stance"] == "Risk-On"                   # score >= 25
    assert result["confidence"] == 94                      # |78.6| * 1.2 = 94.32, no cap
    assert result["divergences"] == []
    # All ten inputs scored; nothing excluded.
    assert "unavailable" not in result["inputs_used"]
    expected_inputs = set(analysis._WEIGHTS)
    assert set(result["inputs_used"]) == expected_inputs


def test_golden_fully_bearish_payload():
    """Every input bearish: num = -12, den = 14."""
    result = analysis.build_analysis(_full_payload(bullish=False))

    assert result["score"] == pytest.approx(-85.7)         # -12 / 14 * 100
    assert result["stance"] == "Risk-Off"                  # score <= -35
    assert result["confidence"] == 100                     # |-85.7| * 1.2 clamps to 100
    assert result["divergences"] == []


def test_golden_stance_boundaries():
    """Stance thresholds: >=25 Risk-On, >-10 Neutral, >-35 Cautious, else Risk-Off."""
    assert analysis._stance_from_score(25.0) == "Risk-On"
    assert analysis._stance_from_score(24.9) == "Neutral"
    assert analysis._stance_from_score(-9.9) == "Neutral"
    assert analysis._stance_from_score(-10.0) == "Cautious"
    assert analysis._stance_from_score(-35.0) == "Risk-Off"
    assert analysis._stance_from_score(-34.9) == "Cautious"


# ---- Weight-table regression guard ------------------------------------------

def test_total_weight_matches_weight_table():
    """Regression guard: the denominator must be derived from the table.

    An older revision hardcoded a stale total (15) while the table summed to
    14, silently deflating every score. If this fails, someone reintroduced a
    hardcoded total or changed the table without updating the total.
    """
    assert analysis._TOTAL_WEIGHT == sum(analysis._WEIGHTS.values())
    # Documented totals: risk 3 + regime 2 + breadth 2 + seven inputs at 1.
    assert sum(analysis._WEIGHTS.values()) == 14.0
    assert len(analysis._WEIGHTS) == 10


# ---- Partial payloads engage confidence caps --------------------------------

def test_partial_payload_low_coverage_scores_and_exclusions():
    """Only the risk engine scored: score -100, Risk-Off, six sections excluded."""
    payload = {"as_of": "2026-08-22T12:00:00+00:00",
               "risk": {"risk_level": "RED", "counts": {}, "signals": []}}
    result = analysis.build_analysis(payload)

    assert result["score"] == pytest.approx(-100.0)  # -3 / 3
    assert result["stance"] == "Risk-Off"
    assert result["inputs_used"]["unavailable"] == [
        "regime", "indicators/breadth", "futures", "bottleneck",
        "earnings recs", "superinvestor 13F",
    ]


def test_partial_payload_low_coverage_caps_confidence_at_35():
    """Only the risk engine (weight 3 of 14 => coverage ~0.21 < 0.4) -> cap 35."""
    payload = {"as_of": "2026-08-22T12:00:00+00:00",
               "risk": {"risk_level": "RED", "counts": {}, "signals": []}}
    result = analysis.build_analysis(payload)

    assert result["confidence"] == 35


def test_partial_payload_mid_coverage_caps_confidence_at_55():
    """risk + regime + breadth (7 of 14 => coverage 0.5, i.e. < 0.7) -> cap 55."""
    payload = {
        "as_of": "2026-08-22T12:00:00+00:00",
        "risk": {"risk_level": "RED", "counts": {}, "signals": []},
        "regime": {"regime": {"regime_label": "Contraction"}},
        "indicators": {"breadth": {"breadth_pct": 30}},
    }
    result = analysis.build_analysis(payload)

    assert result["score"] == pytest.approx(-100.0)  # -7 / 7
    assert result["stance"] == "Risk-Off"
    assert result["confidence"] == 55


def test_full_coverage_leaves_confidence_uncapped():
    """Coverage 1.0 must not trip either cap even for a modest score."""
    conf = analysis._confidence_from_score(30.0, analysis._TOTAL_WEIGHT)
    assert conf == int(round(30.0 * 1.2))


# ---- Robustness -------------------------------------------------------------

def test_unknown_regime_label_does_not_crash_and_scores_neutral():
    payload = {
        "as_of": "2026-08-22T12:00:00+00:00",
        "regime": {"regime": {"regime_label": "Hyperinflationary Spiral"},
                   "composite": {"composite_score": 50}},
    }
    result = analysis.build_analysis(payload)

    # Unknown labels map to tone 0.0 but still consume their weight.
    assert result["score"] == 0.0
    assert result["stance"] == "Neutral"
    assert result["confidence"] == 0
    assert "Hyperinflationary Spiral" in result["inputs_used"]["regime"]


def test_empty_payload_degrades_to_neutral_without_crashing():
    result = analysis.build_analysis({})

    assert result["score"] == 0.0
    assert result["stance"] == "Neutral"
    assert result["confidence"] == 0
    assert result["inputs_used"]["unavailable"] == [
        "risk engine", "regime", "indicators/breadth", "futures",
        "bottleneck", "earnings recs", "superinvestor 13F",
    ]


def test_events_outside_seven_day_window_are_ignored():
    payload = _full_payload(bullish=True)
    payload["events"] = [{"published": "2026-07-01T09:00:00Z", "tags": ["bullish"]}]

    result = analysis.build_analysis(payload)

    # Events drop out of scoring entirely (no unavailable entry for them).
    assert "events_last_7d" not in result["inputs_used"]
    # Without the +0.5 event tone: num = 10.5, den = 13.
    assert result["score"] == pytest.approx(round(10.5 / 13 * 100, 1))
