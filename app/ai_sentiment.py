"""AI capex cycle sentiment gauge.

Measures the health of the AI trade through Capex Spenders vs. Beneficiaries,
AI-tagged news flow, and forward valuation from the earnings cache.
"""

import math
import re
import statistics
from typing import Any, Optional

from . import config
from .indicators import _closes, breadth_pct_above_ma, roc_at


def _eq_weight_roc(histories: dict[str, list[dict]], tickers: list[str]) -> Optional[float]:
    """Equal-weight average of per-ticker ~3-month ROC across ``tickers``.

    Variant outer logic (multi-symbol aggregation, >=2 tickers required) kept
    here; the per-symbol ROC math delegates to indicators.roc_at."""
    rocs = []
    for sym in tickers:
        val = roc_at(_closes(histories.get(sym, [])), 63)
        if val is not None:
            rocs.append(val)
    if len(rocs) < 2:
        return None
    return round(sum(rocs) / len(rocs), 2)


def _cohort_tone(roc: Optional[float], breadth: Optional[float]) -> tuple[str, str]:
    # Unknown-dominant: a missing leg must never masquerade as neutral
    # (the old `roc or 0` / `breadth else 50` fabricated calm data).
    if roc is None or breadth is None:
        return "unknown", "insufficient data"
    r = roc
    b = breadth
    if r > 15 and b >= 60:
        return "bullish", "extended but strong"
    if r > 8 and b >= 50:
        return "bullish", "strong momentum + broad participation"
    if r > 5 and b >= 35:
        return "bullish", "momentum intact"
    if r < -8 and b <= 35:
        return "bearish", "negative momentum + weak breadth"
    if r < -5 or b <= 25:
        return "bearish", "momentum weakening / poor breadth"
    if r > 5 and b < 35:
        return "neutral", "positive momentum but poor breadth"
    return "neutral", "mixed"


def _event_text(e: dict[str, Any]) -> str:
    parts = [e.get("title", ""), e.get("summary", "")]
    return " ".join(parts).lower()


def _is_ai_event(text: str) -> bool:
    return any(re.search(rf"\b{re.escape(k)}\b", text) for k in config.AI_NEWS_KEYWORDS)


def compute_ai_news_sentiment(events: list[dict]) -> dict[str, Any]:
    """Net signed sentiment from AI-relevant events, scaled to roughly -100..100."""
    weights = []
    for e in events:
        text = _event_text(e)
        if not _is_ai_event(text):
            continue
        impact = str(e.get("impact") or "Low")
        tag_weight = {"Critical": 3, "High": 2, "Medium": 1, "Low": 0.5}.get(impact, 0.5)
        direction = str(e.get("direction") or "neutral")
        sign = {"bullish": 1, "bearish": -1, "neutral": 0}.get(direction, 0)
        weights.append(sign * tag_weight * 10)
    if not weights:
        return {"score": 0, "event_count": 0, "tone": "neutral", "note": "no AI-relevant events"}
    raw = sum(weights)
    score = round(math.copysign(min(abs(raw), 100), raw), 1)
    tone = "bullish" if score > 20 else "bearish" if score < -20 else "neutral"
    return {"score": score, "event_count": len(weights), "tone": tone, "note": f"{len(weights)} AI-relevant events"}


def compute_valuation_flag(earnings: dict[str, Any]) -> dict[str, Any]:
    """Median forward PE/PEG across AI cohorts; stretched if median PE >= VALUATION_STRETCH_PE."""
    companies = earnings.get("companies") or []
    pes = [c.get("forward_pe") for c in companies if c.get("forward_pe")]
    pEGs = [c.get("forward_peg") for c in companies if c.get("forward_peg")]
    if len(pes) < 4:
        return {"forward_pe": None, "forward_peg": None, "stretched": False, "note": "insufficient data"}
    pe_median = round(statistics.median(pes), 2)
    peg_median = round(statistics.median(pEGs), 2) if pEGs else None
    stretched = pe_median >= config.VALUATION_STRETCH_PE
    note = f"median forward PE {pe_median}" + (" — stretched" if stretched else "")
    return {"forward_pe": pe_median, "forward_peg": peg_median, "stretched": stretched, "note": note}


def compute_ai_sentiment(snapshot: dict[str, Any], events: list[dict], earnings: dict[str, Any]) -> dict[str, Any]:
    """Main entry point."""
    histories = snapshot.get("histories", {})
    extra = histories.get("extra", {})
    all_hist = {**histories, **extra}

    cohorts: list[dict[str, Any]] = []
    spenders_roc: Optional[float] = None
    beneficiary_rocs: list[float] = []

    for name, tickers in config.AI_CAPEX_COHORTS.items():
        roc = _eq_weight_roc(all_hist, tickers)
        breadth = breadth_pct_above_ma(all_hist, 50, symbols=tickers)
        tone, note = _cohort_tone(roc, breadth)
        cohorts.append({
            "name": name,
            "roc_3m_pct": roc,
            "breadth_pct": breadth,
            "tone": tone,
            "note": note,
        })
        if name == "Capex Spenders":
            spenders_roc = roc
        else:
            if roc is not None:
                beneficiary_rocs.append(roc)

    beneficiary_roc = round(sum(beneficiary_rocs) / len(beneficiary_rocs), 2) if beneficiary_rocs else None
    spread = None
    if spenders_roc is not None and beneficiary_roc is not None:
        spread = round(beneficiary_roc - spenders_roc, 2)

    news = compute_ai_news_sentiment(events)
    valuation = compute_valuation_flag(earnings)

    score = 0.0
    valid_cohorts = [c for c in cohorts if c["roc_3m_pct"] is not None]
    if valid_cohorts:
        score += sum((c["roc_3m_pct"] or 0) for c in valid_cohorts) / len(valid_cohorts) * config.AI_SENTIMENT_ROC_WEIGHT
    if spread is not None:
        score += spread * config.AI_SENTIMENT_SPREAD_WEIGHT
    score += news["score"] * config.AI_SENTIMENT_NEWS_WEIGHT
    if valuation["stretched"]:
        score -= config.AI_SENTIMENT_VALUATION_PENALTY
    score = round(max(-100, min(100, score)), 1)

    euphoric_cut, expansion_cut = config.AI_SENTIMENT_VERDICT_CUTOFFS
    if score >= euphoric_cut:
        verdict = "Euphoric / fragility setup"
    elif score >= expansion_cut:
        verdict = "Healthy expansion"
    elif score >= -expansion_cut:
        verdict = "Balanced / mixed"
    elif score >= -euphoric_cut:
        verdict = "Cooling / divergence"
    else:
        verdict = "Cycle under pressure"

    flip_conditions = [
        "Beneficiaries' 3m ROC flips below spenders' (spread turns negative)",
        "Breadth across beneficiary cohorts drops below 40%",
        "Forward PE median rises further or AI news turns decisively bearish",
    ]

    return {
        "as_of": snapshot.get("as_of"),
        "score": score,
        "verdict": verdict,
        "cohorts": cohorts,
        "spread_pct": spread,
        "news": news,
        "valuation": valuation,
        "flip_conditions": flip_conditions,
    }
