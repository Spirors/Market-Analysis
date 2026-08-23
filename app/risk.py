"""Risk-divergence engine — the crown jewel.

Core thesis: a healthy bull market has DIVIDED sentiment. When sentiment stops
being divided — pure optimism, risk dismissed, everyone in the same trade — that
is a fragility setup, a structure for disaster, not a good sign.

This engine computes divergence signals from free market data and outputs a
GREEN / YELLOW / RED risk read with the specific evidence and the conditions
that would flip the call.
"""

import math
import statistics
from typing import Any, Optional

from . import config, indicators
from .indicators import _closes


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


def _paired_log_returns(a: list[float], b: list[float]) -> tuple[list[float], list[float]]:
    """Daily log returns of two aligned series; transitions touching a non-positive
    close are treated as missing and skipped (returned pairs stay aligned)."""
    ra: list[float] = []
    rb: list[float] = []
    for i in range(1, min(len(a), len(b))):
        if a[i] > 0 and a[i - 1] > 0 and b[i] > 0 and b[i - 1] > 0:
            ra.append(math.log(a[i] / a[i - 1]))
            rb.append(math.log(b[i] / b[i - 1]))
    return ra, rb


def _correlation(a_hist: list[dict], b_hist: list[dict], window: int = 126) -> Optional[float]:
    """Pearson correlation of daily returns over the last `window` bars."""
    a, b = _aligned_series(a_hist, b_hist)
    if len(a) < window + 1:
        return None
    ra, rb = _paired_log_returns(a, b)
    return _correlation_window(ra, rb, window)


def _correlation_at(a_hist: list[dict], b_hist: list[dict], end_idx: int, window: int = 126) -> Optional[float]:
    """Correlation ending at a specific historical index (negative = from end)."""
    a, b = _aligned_series(a_hist, b_hist)
    if not a:
        return None
    idx = end_idx if end_idx >= 0 else len(a) + end_idx + 1
    if idx < window + 1 or idx > len(a):
        return None
    ra, rb = _paired_log_returns(a[:idx], b[:idx])
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


def _roc_latest(hist: list[dict]) -> Optional[float]:
    """Latest-close ~3-month ROC (2dp), via the shared indicators.roc_at.

    Rounding/convention adapter only — keeps this engine's legacy idiom
    ``closes[-1] / closes[-63]`` (a 62-step span)."""
    val = indicators.roc_at(_closes(hist), 63)
    return round(val, 2) if val is not None else None


def _roc_prior(hist: list[dict], end_offset: int) -> Optional[float]:
    """Historical ~3-month ROC ending ``end_offset`` bars back (2dp).

    Legacy quirk preserved exactly: the prior-window variant spans one step
    more than :func:`_roc_latest` (its base sits a full 63 steps before the
    reference bar, i.e. ``lookback + 1`` list slots back), hence the +1."""
    val = indicators.roc_at(_closes(hist), 63 + 1, end_offset)
    return round(val, 2) if val is not None else None


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
    pe_median = statistics.median(p[1] for p in pes)
    return pe_median, config.VALUATION_STRETCH_PE


def compute_risk(snapshot: dict[str, Any], earnings: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    hist = snapshot.get("histories", {})
    extra = hist.get("extra", {})

    signals: list[dict[str, Any]] = []
    fragility_flags: list[dict[str, str]] = []

    # Lookback for "is it getting worse" dynamics.
    LB = config.RISK_LOOKBACK_BARS
    # Same reference bar as end-offset-from-latest for indicators.*_at helpers
    # (LB=-10 compares the close 10 bars back; offset = 9).
    prior_offset = -LB - 1

    # 1. Breadth (% of sectors & indices above 50-day MA)
    core_extra = {s: extra.get(s, []) for s in list(config.INDICES) + list(config.SECTORS)}
    breadth = indicators.pct_above_ma(core_extra, n=50)
    bval = breadth.get("breadth_pct")
    breadth_prior = indicators.breadth_pct_above_ma_at(core_extra, 50, end_offset=prior_offset)
    if bval is not None:
        overheat_tier, healthy_tier, narrowing_tier, poor_tier = config.RISK_BREADTH_TIERS
        if bval >= overheat_tier:
            tone, note = "bullish", "broad participation"
            if _is_rising(bval, breadth_prior):
                fragility_flags.append({"side": "optimism", "flag": f"breadth overheating and rising ({bval}% > 50DMA)", "flip": "breadth falls back below 65%"})
        elif bval >= healthy_tier:
            tone, note = "bullish", "healthy breadth"
        elif bval >= narrowing_tier:
            tone, note = "neutral", "narrowing breadth"
        elif bval >= poor_tier:
            tone, note = "bearish", "poor breadth"
        else:
            tone, note = "bearish", "breadth washed out"
            fragility_flags.append({"side": "distress", "flag": f"breadth washed out ({bval}% > 50DMA)", "flip": "breadth recovers above 35%"})
        signals.append({"name": "Breadth", "tone": tone, "value": f"{bval}% above 50DMA", "note": note})

    # 2. Concentration (RSP/SPY 3-month ROC)
    conc = _ratio_roc_3m(hist.get("RSP", []), hist.get("SPY", []))
    conc_prior = _ratio_roc_at(hist.get("RSP", []), hist.get("SPY", []), LB)
    if conc is not None:
        if conc < -config.RISK_CONCENTRATION_BAND:
            tone, note = "bearish", "leadership narrowing"
            if _is_falling(conc, conc_prior):
                # Narrowing leadership is fragility OF the consensus long trade
                # (the classic top signature alongside euphoria), not market
                # breakage — hence optimism-side.
                fragility_flags.append({"side": "optimism", "flag": f"leadership narrowing (RSP/SPY {conc:+.1f}% and falling)", "flip": "RSP/SPY turns up or stabilizes"})
        elif conc > config.RISK_CONCENTRATION_BAND:
            tone, note = "bullish", "leadership broadening"
        else:
            tone, note = "neutral", "stable concentration"
        signals.append({"name": "Concentration (RSP/SPY)", "tone": tone, "value": f"{conc:+.1f}% 3m", "note": note})

    # 3. VIX complacency
    vix = indicators.vix_signal(hist.get("^VIX", []))
    vix_ratio_prior = indicators.vix_ma_ratio_at(hist.get("^VIX", []), end_offset=prior_offset)
    if vix.get("signal") != "no data":
        if vix["signal"] == "complacent":
            tone, note = "bullish", "vol suppressed"
            if vix.get("ratio") is not None and vix_ratio_prior is not None and vix["ratio"] < vix_ratio_prior:
                fragility_flags.append({"side": "optimism", "flag": f"VIX complacency deepening (VIX {vix.get('level')} vs MA {vix.get('ma')})", "flip": "VIX climbs back above its 50-day MA"})
        elif vix["signal"] == "elevated":
            tone, note = "bearish", "vol elevated"
        else:
            tone, note = "neutral", "vol normal"
        signals.append({"name": "VIX", "tone": tone, "value": f"{vix.get('level')} vs MA {vix.get('ma')}", "note": note})

    # 4. Credit risk appetite (HYG/LQD)
    credit = _ratio_roc_3m(hist.get("HYG", []), hist.get("LQD", []))
    credit_prior = _ratio_roc_at(hist.get("HYG", []), hist.get("LQD", []), LB)
    if credit is not None:
        if credit < -config.RISK_CREDIT_BAND:
            tone, note = "bearish", "credit risk-off"
        elif credit > config.RISK_CREDIT_BAND:
            tone, note = "bullish", "credit risk-on"
            if _is_rising(credit, credit_prior):
                fragility_flags.append({"side": "optimism", "flag": f"credit risk-on accelerating (HYG/LQD {credit:+.1f}% and rising)", "flip": "HYG/LQD 3m ROC turns negative"})
        else:
            tone, note = "neutral", "credit steady"
        signals.append({"name": "Credit (HYG/LQD)", "tone": tone, "value": f"{credit:+.1f}% 3m", "note": note})

    # 5. Small-cap participation (IWM/SPY)
    small = _ratio_roc_3m(hist.get("IWM", []), hist.get("SPY", []))
    if small is not None:
        if small < -config.RISK_SMALLCAP_BAND:
            tone, note = "bearish", "small-caps lagging"
        elif small > config.RISK_SMALLCAP_BAND:
            tone, note = "bullish", "small-caps leading"
        else:
            tone, note = "neutral", "small-caps in line"
        signals.append({"name": "Small-cap (IWM/SPY)", "tone": tone, "value": f"{small:+.1f}% 3m", "note": note})

    # 6. Equity-bond correlation
    corr = _correlation(hist.get("SPY", []), hist.get("TLT", []))
    corr_prior = _correlation_at(hist.get("SPY", []), hist.get("TLT", []), LB)
    if corr is not None:
        if corr > config.RISK_CORRELATION_BAND:
            tone, note = "bearish", "positive stock-bond correlation (hedges fail)"
            if _is_rising(corr, corr_prior):
                fragility_flags.append({"side": "distress", "flag": f"stock-bond correlation rising into inflationary territory ({corr})", "flip": "correlation falls back below 0.2"})
        elif corr < -config.RISK_CORRELATION_BAND:
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
        if dd is not None and dd <= config.RISK_DRAWDOWN_WASHOUT:
            fragility_flags.append({"side": "distress", "flag": f"SPY in drawdown ({dd:.0f}% from highs)", "flip": "SPY reclaims its 50-day MA"})

    # 8. AI theme extension (parabolic moves + shallow drawdown)
    smh_roc = _roc_latest(extra.get("SMH", []))
    qqq_roc = _roc_latest(hist.get("QQQ", []))
    nvda_roc = _roc_latest(extra.get("NVDA", []))
    smh_roc_prior = _roc_prior(extra.get("SMH", []), prior_offset)
    qqq_roc_prior = _roc_prior(hist.get("QQQ", []), prior_offset)
    nvda_roc_prior = _roc_prior(extra.get("NVDA", []), prior_offset)
    ai_extended = (
        (smh_roc is not None and smh_roc > config.RISK_AI_EXTENSION_ROC)
        or (qqq_roc is not None and qqq_roc > config.RISK_AI_EXTENSION_ROC)
        or (nvda_roc is not None and nvda_roc > config.RISK_AI_EXTENSION_ROC)
    )
    ai_accelerating = (
        _is_rising(smh_roc, smh_roc_prior)
        or _is_rising(qqq_roc, qqq_roc_prior)
        or _is_rising(nvda_roc, nvda_roc_prior)
    )
    if ai_extended and ai_accelerating:
        if dd is not None and dd > config.RISK_DRAWDOWN_SHALLOW:
            leaders = []
            if smh_roc is not None and smh_roc > config.RISK_AI_EXTENSION_ROC:
                leaders.append(f"SMH {smh_roc:+.0f}%")
            if qqq_roc is not None and qqq_roc > config.RISK_AI_EXTENSION_ROC:
                leaders.append(f"QQQ {qqq_roc:+.0f}%")
            if nvda_roc is not None and nvda_roc > config.RISK_AI_EXTENSION_ROC:
                leaders.append(f"NVDA {nvda_roc:+.0f}%")
            fragility_flags.append({
                "side": "optimism",
                "flag": f"AI theme extending ({', '.join(leaders)} 3m ROC) with shallow drawdown",
                "flip": "SMH/QQQ/NVDA 3m ROC falls below 15%",
            })

    # 9. Valuation stretch from earnings cache
    pe_median, stretch_threshold = _valuation_stretched(earnings)
    if pe_median is not None and stretch_threshold is not None and pe_median >= stretch_threshold:
        fragility_flags.append({
            "side": "optimism",
            "flag": f"AI mega-cap forward PE stretched (median {pe_median:.1f}x)",
            "flip": f"forward PE median falls below {config.VALUATION_STRETCH_PE:.0f}x",
        })

    # ---- Aggregate ----
    bullish = sum(1 for s in signals if s["tone"] == "bullish")
    bearish = sum(1 for s in signals if s["tone"] == "bearish")
    neutral = sum(1 for s in signals if s["tone"] == "neutral")

    # For consensus-optimism scoring, only OPTIMISM-side flags count as
    # evidence of euphoria. Distress-side flags (washed-out breadth, rising
    # stock-bond correlation, SPY drawdown) describe breakage, not euphoria —
    # letting them satisfy this gate could label a selloff "consensus
    # optimism". They remain visible in the card and still feed the washout /
    # risk-off paths via signal tones and drawdown.
    flag_count = sum(1 for f in fragility_flags if f.get("side") == "optimism")
    # Gates scale with available signal coverage: signals silently drop out when
    # their data is missing, so absolute counts (>=5) were unreachable on thin
    # days. Require a >=60% supermajority of the tone-bearing signals that
    # actually produced a verdict this run, floored at 3; with no tone-bearing
    # data neither path fires.
    total_tone = sum(1 for s in signals if s["tone"] in ("bullish", "bearish", "neutral"))
    tone_gate = max(config.RISK_TONE_GATE_MIN, math.ceil(config.RISK_TONE_GATE_RATIO * total_tone))
    consensus_optimism = (
        total_tone > 0 and bullish >= tone_gate and bearish <= 1 and flag_count >= 2
    )
    capitulation = (
        total_tone > 0 and bearish >= tone_gate and bullish <= 1 and (dd is not None and dd <= config.RISK_DRAWDOWN_WASHOUT)
    )

    if consensus_optimism:
        level, color, verdict = "RED", "#A32D2D", "Consensus optimism — fragility setup"
    elif capitulation:
        level, color, verdict = "RED", "#A32D2D", "Washout / trend break"
    elif bearish > bullish and (dd is not None and dd <= config.RISK_DRAWDOWN_RISK_OFF):
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
