"""Risk-divergence engine — the crown jewel.

Core thesis: a healthy bull market has DIVIDED sentiment. When sentiment stops
being divided — pure optimism, risk dismissed, everyone in the same trade — that
is a fragility setup, a structure for disaster, not a good sign.

This engine computes divergence signals from free market data and outputs a
GREEN / YELLOW / RED risk read with the specific evidence and the conditions
that would flip the call.
"""

import math
from typing import Any, Optional

from . import config, indicators
from .indicators import _closes, _sma

# Absolute forward-PE band for the AI mega-cap stretch flag; replaces the broken
# same-sample quartile comparison (median vs Q3 of the same sorted sample).
VALUATION_STRETCH_PE = 30.0


def _aligned_series(a_hist: list[dict], b_hist: list[dict]) -> tuple[list[float], list[float]]:
    a = {h["date"]: h["close"] for h in a_hist if h.get("close") is not None}
    b = {h["date"]: h["close"] for h in b_hist if h.get("close") is not None}
    dates = sorted(set(a) & set(b))
    return [a[d] for d in dates], [b[d] for d in dates]


def _correlation_window(ra: list[float], rb: list[float], window: int = 126) -> Optional[float]:
    ra, rb = ra[-window:], rb[-window:]
    n = len(ra)
    if n < 20:
        return None
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    if va == 0 or vb == 0:
        return None
    return round(cov / math.sqrt(va * vb), 2)


def _correlation(a_hist: list[dict], b_hist: list[dict], window: int = 126) -> Optional[float]:
    """Pearson correlation of daily returns over the last `window` bars."""
    a, b = _aligned_series(a_hist, b_hist)
    if len(a) < window + 1:
        return None
    ra = [math.log(a[i] / a[i - 1]) for i in range(1, len(a))]
    rb = [math.log(b[i] / b[i - 1]) for i in range(1, len(b))]
    return _correlation_window(ra, rb, window)


def _correlation_at(a_hist: list[dict], b_hist: list[dict], end_idx: int, window: int = 126) -> Optional[float]:
    """Correlation ending at a specific historical index (negative = from end)."""
    a, b = _aligned_series(a_hist, b_hist)
    if not a:
        return None
    idx = end_idx if end_idx >= 0 else len(a) + end_idx + 1
    if idx < window + 1 or idx > len(a):
        return None
    ra = [math.log(a[i] / a[i - 1]) for i in range(1, idx)]
    rb = [math.log(b[i] / b[i - 1]) for i in range(1, idx)]
    return _correlation_window(ra, rb, window)


def _ratio_roc_3m(a_hist: list[dict], b_hist: list[dict]) -> Optional[float]:
    """3-month rate of change of the a/b ratio."""
    a, b = _aligned_series(a_hist, b_hist)
    if len(a) < 63:
        return None
    cur = a[-1] / b[-1]
    base = a[-63] / b[-63]
    if base == 0:
        return None
    return round((cur / base - 1) * 100, 2)


def _ratio_roc_at(a_hist: list[dict], b_hist: list[dict], end_idx: int, lookback: int = 63) -> Optional[float]:
    """Ratio ROC ending at a specific historical index."""
    a, b = _aligned_series(a_hist, b_hist)
    if not a:
        return None
    idx = end_idx if end_idx >= 0 else len(a) + end_idx + 1
    if idx < lookback + 1 or idx > len(a):
        return None
    cur = a[idx - 1] / b[idx - 1]
    base = a[idx - lookback - 1] / b[idx - lookback - 1]
    if base == 0:
        return None
    return round((cur / base - 1) * 100, 2)


def _roc_3m(hist: list[dict]) -> Optional[float]:
    closes = _closes(hist)
    if len(closes) < 63:
        return None
    base = closes[-63]
    if base == 0:
        return None
    return round((closes[-1] / base - 1) * 100, 2)


def _roc_at(hist: list[dict], end_idx: int, lookback: int = 63) -> Optional[float]:
    closes = _closes(hist)
    if not closes:
        return None
    idx = end_idx if end_idx >= 0 else len(closes) + end_idx + 1
    if idx < lookback + 1 or idx > len(closes):
        return None
    cur = closes[idx - 1]
    base = closes[idx - lookback - 1]
    if base == 0:
        return None
    return round((cur / base - 1) * 100, 2)


def _vix_ratio_at(hist: list[dict], end_idx: int, ma_window: int = 50) -> Optional[float]:
    closes = _closes(hist)
    if not closes:
        return None
    idx = end_idx if end_idx >= 0 else len(closes) + end_idx + 1
    if idx < ma_window + 1 or idx > len(closes):
        return None
    level = closes[idx - 1]
    ma = sum(closes[idx - ma_window - 1:idx - 1]) / ma_window
    if ma == 0:
        return None
    return level / ma


def _breadth_pct_at(extra: dict[str, list[dict]], end_idx: int, n: int = 50) -> Optional[float]:
    """Breadth % above n-day MA as of a historical end index."""
    above = total = 0
    for sym, hist in extra.items():
        closes = _closes(hist)
        if not closes:
            continue
        idx = end_idx if end_idx >= 0 else len(closes) + end_idx + 1
        if idx < n + 1 or idx > len(closes):
            continue
        window = closes[idx - n - 1:idx - 1]
        ma = sum(window) / n
        if ma == 0:
            continue
        total += 1
        if closes[idx - 1] > ma:
            above += 1
    if total == 0:
        return None
    return round(above / total * 100, 1)


def _is_rising(current: Optional[float], prior: Optional[float]) -> bool:
    return current is not None and prior is not None and current > prior


def _is_falling(current: Optional[float], prior: Optional[float]) -> bool:
    return current is not None and prior is not None and current < prior


def _valuation_stretched(earnings: Optional[dict[str, Any]]) -> tuple[Optional[float], Optional[float]]:
    """Return (current_median_pe, stretch_threshold) for AI mega-caps if data is sufficient."""
    if not earnings:
        return None, None
    companies = earnings.get("companies") or []
    ai_tickers = set(config.AI_CAPEX_COHORTS.get("Capex Spenders", []) + config.AI_CAPEX_COHORTS.get("Compute / Accelerators", []))
    pes = [(c.get("symbol"), c.get("forward_pe")) for c in companies if c.get("forward_pe") and c.get("symbol") in ai_tickers]
    if len(pes) < 3:
        return None, None
    # We only have a current snapshot of earnings; no history. Return current median only.
    pe_median = sorted(p[1] for p in pes)[len(pes) // 2]
    return pe_median, VALUATION_STRETCH_PE


def compute_risk(snapshot: dict[str, Any], earnings: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    hist = snapshot.get("histories", {})
    extra = hist.get("extra", {})

    signals: list[dict[str, Any]] = []
    fragility_flags: list[dict[str, str]] = []

    # Lookback for "is it getting worse" dynamics.
    LB = -10

    # 1. Breadth (% of sectors & indices above 50-day MA)
    core_extra = {s: extra.get(s, []) for s in list(config.INDICES) + list(config.SECTORS)}
    breadth = indicators.pct_above_ma(core_extra, n=50)
    bval = breadth.get("breadth_pct")
    breadth_prior = _breadth_pct_at(core_extra, LB, n=50)
    if bval is not None:
        if bval >= 75:
            tone, note = "bullish", "broad participation"
            if _is_rising(bval, breadth_prior):
                fragility_flags.append({"flag": f"breadth overheating and rising ({bval}% > 50DMA)", "flip": "breadth falls back below 65%"})
        elif bval >= 55:
            tone, note = "bullish", "healthy breadth"
        elif bval >= 40:
            tone, note = "neutral", "narrowing breadth"
        elif bval >= 25:
            tone, note = "bearish", "poor breadth"
        else:
            tone, note = "bearish", "breadth washed out"
            fragility_flags.append({"flag": f"breadth washed out ({bval}% > 50DMA)", "flip": "breadth recovers above 35%"})
        signals.append({"name": "Breadth", "tone": tone, "value": f"{bval}% above 50DMA", "note": note})

    # 2. Concentration (RSP/SPY 3-month ROC)
    conc = _ratio_roc_3m(hist.get("RSP", []), hist.get("SPY", []))
    conc_prior = _ratio_roc_at(hist.get("RSP", []), hist.get("SPY", []), LB)
    if conc is not None:
        if conc < -3:
            tone, note = "bearish", "leadership narrowing"
            if _is_falling(conc, conc_prior):
                fragility_flags.append({"flag": f"leadership narrowing (RSP/SPY {conc:+.1f}% and falling)", "flip": "RSP/SPY turns up or stabilizes"})
        elif conc > 3:
            tone, note = "bullish", "leadership broadening"
        else:
            tone, note = "neutral", "stable concentration"
        signals.append({"name": "Concentration (RSP/SPY)", "tone": tone, "value": f"{conc:+.1f}% 3m", "note": note})

    # 3. VIX complacency
    vix = indicators.vix_signal(hist.get("^VIX", []))
    vix_ratio_prior = _vix_ratio_at(hist.get("^VIX", []), LB)
    if vix.get("signal") != "no data":
        if vix["signal"] == "complacent":
            tone, note = "bullish", "vol suppressed"
            if vix.get("ratio") is not None and vix_ratio_prior is not None and vix["ratio"] < vix_ratio_prior:
                fragility_flags.append({"flag": f"VIX complacency deepening (VIX {vix.get('level')} vs MA {vix.get('ma')})", "flip": "VIX climbs back above its 50-day MA"})
        elif vix["signal"] == "elevated":
            tone, note = "bearish", "vol elevated"
        else:
            tone, note = "neutral", "vol normal"
        signals.append({"name": "VIX", "tone": tone, "value": f"{vix.get('level')} vs MA {vix.get('ma')}", "note": note})

    # 4. Credit risk appetite (HYG/LQD)
    credit = _ratio_roc_3m(hist.get("HYG", []), hist.get("LQD", []))
    credit_prior = _ratio_roc_at(hist.get("HYG", []), hist.get("LQD", []), LB)
    if credit is not None:
        if credit < -1:
            tone, note = "bearish", "credit risk-off"
        elif credit > 1:
            tone, note = "bullish", "credit risk-on"
            if _is_rising(credit, credit_prior):
                fragility_flags.append({"flag": f"credit risk-on accelerating (HYG/LQD {credit:+.1f}% and rising)", "flip": "HYG/LQD 3m ROC turns negative"})
        else:
            tone, note = "neutral", "credit steady"
        signals.append({"name": "Credit (HYG/LQD)", "tone": tone, "value": f"{credit:+.1f}% 3m", "note": note})

    # 5. Small-cap participation (IWM/SPY)
    small = _ratio_roc_3m(hist.get("IWM", []), hist.get("SPY", []))
    if small is not None:
        if small < -3:
            tone, note = "bearish", "small-caps lagging"
        elif small > 3:
            tone, note = "bullish", "small-caps leading"
        else:
            tone, note = "neutral", "small-caps in line"
        signals.append({"name": "Small-cap (IWM/SPY)", "tone": tone, "value": f"{small:+.1f}% 3m", "note": note})

    # 6. Equity-bond correlation
    corr = _correlation(hist.get("SPY", []), hist.get("TLT", []))
    corr_prior = _correlation_at(hist.get("SPY", []), hist.get("TLT", []), LB)
    if corr is not None:
        if corr > 0.3:
            tone, note = "bearish", "positive stock-bond correlation (hedges fail)"
            if _is_rising(corr, corr_prior):
                fragility_flags.append({"flag": f"stock-bond correlation rising into inflationary territory ({corr})", "flip": "correlation falls back below 0.2"})
        elif corr < -0.3:
            tone, note = "bullish", "negative correlation (normal hedges work)"
        else:
            tone, note = "neutral", "correlation near zero"
        signals.append({"name": "Stock-bond correlation", "tone": tone, "value": f"{corr}", "note": note})

    # 7. Momentum / drawdown
    trend = indicators.trend_state(hist.get("SPY", []))
    dd = trend.get("drawdown_pct")
    if trend.get("state") != "unknown":
        if trend["state"] == "downtrend":
            tone, note = "bearish", "below 50 & 200 DMA"
        elif trend["state"] == "uptrend":
            tone, note = "bullish", "above 50 & 200 DMA"
        else:
            tone, note = "neutral", "mixed trend"
        signals.append({"name": "SPY trend", "tone": tone, "value": trend["state"], "note": note})
        if dd is not None and dd <= -10:
            fragility_flags.append({"flag": f"SPY in drawdown ({dd:.0f}% from highs)", "flip": "SPY reclaims its 50-day MA"})

    # 8. AI theme extension (parabolic moves + shallow drawdown)
    smh_roc = _roc_3m(extra.get("SMH", []))
    qqq_roc = _roc_3m(hist.get("QQQ", []))
    nvda_roc = _roc_3m(extra.get("NVDA", []))
    smh_roc_prior = _roc_at(extra.get("SMH", []), LB)
    qqq_roc_prior = _roc_at(hist.get("QQQ", []), LB)
    nvda_roc_prior = _roc_at(extra.get("NVDA", []), LB)
    ai_extended = (
        (smh_roc is not None and smh_roc > 25)
        or (qqq_roc is not None and qqq_roc > 25)
        or (nvda_roc is not None and nvda_roc > 25)
    )
    ai_accelerating = (
        _is_rising(smh_roc, smh_roc_prior)
        or _is_rising(qqq_roc, qqq_roc_prior)
        or _is_rising(nvda_roc, nvda_roc_prior)
    )
    if ai_extended and ai_accelerating:
        if dd is not None and dd > -5:
            leaders = []
            if smh_roc is not None and smh_roc > 25:
                leaders.append(f"SMH {smh_roc:+.0f}%")
            if qqq_roc is not None and qqq_roc > 25:
                leaders.append(f"QQQ {qqq_roc:+.0f}%")
            if nvda_roc is not None and nvda_roc > 25:
                leaders.append(f"NVDA {nvda_roc:+.0f}%")
            fragility_flags.append({
                "flag": f"AI theme extending ({', '.join(leaders)} 3m ROC) with shallow drawdown",
                "flip": "SMH/QQQ/NVDA 3m ROC falls below 15%",
            })

    # 9. Valuation stretch from earnings cache
    pe_median, stretch_threshold = _valuation_stretched(earnings)
    if pe_median is not None and stretch_threshold is not None and pe_median >= stretch_threshold:
        fragility_flags.append({
            "flag": f"AI mega-cap forward PE stretched (median {pe_median:.1f}x)",
            "flip": f"forward PE median falls below {VALUATION_STRETCH_PE:.0f}x",
        })

    # ---- Aggregate ----
    bullish = sum(1 for s in signals if s["tone"] == "bullish")
    bearish = sum(1 for s in signals if s["tone"] == "bearish")
    neutral = sum(1 for s in signals if s["tone"] == "neutral")
    total = len(signals)

    # Division metric: 0 = unanimous, higher = more divided.
    div = 1.0 - (abs(bullish - bearish) / max(total, 1))

    # For consensus-optimism scoring, count dynamic flags as one source of fragility.
    flag_count = len(fragility_flags)
    consensus_optimism = bullish >= 5 and bearish <= 1 and flag_count >= 2
    capitulation = bearish >= 5 and bullish <= 1 and (dd is not None and dd <= -10)

    if consensus_optimism:
        level, color, verdict = "RED", "#A32D2D", "Consensus optimism — fragility setup"
    elif capitulation:
        level, color, verdict = "RED", "#A32D2D", "Washout / trend break"
    elif bearish > bullish and (dd is not None and dd <= -8):
        level, color, verdict = "RED", "#A32D2D", "Risk-off, trend under pressure"
    elif abs(bullish - bearish) <= 1:
        level, color, verdict = "GREEN", "#3B6D11", "Divided sentiment — healthy tug-of-war"
    elif bearish >= bullish:
        level, color, verdict = "YELLOW", "#B9860B", "Leaning risk-off"
    else:
        level, color, verdict = "YELLOW", "#B9860B", "Leaning bullish"

    flip = _flip_conditions(consensus_optimism, capitulation, dd)

    return {
        "as_of": snapshot.get("as_of"),
        "risk_level": level,
        "color": color,
        "verdict": verdict,
        "division_score": round(div, 2),
        "counts": {"bullish": bullish, "bearish": bearish, "neutral": neutral},
        "consensus_optimism": consensus_optimism,
        "signals": signals,
        "fragility_flags": fragility_flags,
        "flip_conditions": flip,
        "thesis": (
            "A healthy bull market has divided sentiment. Unanimous optimism "
            "(everyone in the same trade, risk priced out) is a fragility setup, "
            "not a good sign."
        ),
    }


def _flip_conditions(consensus_optimism: bool, capitulation: bool, dd: Optional[float]) -> list[str]:
    if consensus_optimism:
        return [
            "Breadth falling back below ~55% (participation normalizing)",
            "VIX climbing back toward its average (vol returning)",
            "RSP/SPY stabilizing or turning up (leadership broadening)",
        ]
    if capitulation:
        return [
            "Credit (HYG/LQD) turning risk-on",
            "Breadth recovering above ~40%",
            "SPY reclaiming its 50-day MA",
        ]
    return [
        "Any 3+ signals flipping tone within a month",
        "Drawdown deepening past -10%",
        "Credit conditions sharply turning risk-off",
    ]
