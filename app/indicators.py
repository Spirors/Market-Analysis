"""Indicator computation: breadth, moving averages, realized vol, VIX trend."""

import math
from typing import Any, Optional

from . import config


def _sma(vals: list[float], n: int) -> Optional[float]:
    if len(vals) < n:
        return None
    return sum(vals[-n:]) / n


def _closes(hist: list[dict]) -> list[float]:
    return [h["close"] for h in hist if h.get("close") is not None]


def pct_above_ma(histories: dict[str, list[dict]], n: int = 50) -> dict[str, Any]:
    """Fraction of symbols trading above their n-day moving average (breadth)."""
    above = 0
    total = 0
    detail = {}
    for sym, hist in histories.items():
        closes = _closes(hist)
        if len(closes) < n:
            continue
        ma = _sma(closes, n)
        if ma is None:
            continue
        total += 1
        cur = closes[-1]
        ok = cur > ma
        above += 1 if ok else 0
        pct = round((cur - ma) / ma * 100, 2) if ma else None
        detail[sym] = {
            "above": ok,
            "close": round(cur, 2),
            "ma": round(ma, 2),
            "pct_from_ma": pct,
        }
    breadth = (above / total * 100) if total else None
    return {
        "breadth_pct": round(breadth, 1) if breadth is not None else None,
        "above_count": above,
        "total": total,
        "detail": detail,
    }


def realized_vol(hist: list[dict], window: int = 21) -> Optional[float]:
    """Annualized realized volatility from daily returns (last `window` bars)."""
    closes = _closes(hist)
    if len(closes) < window + 1:
        return None
    windowed = closes[-(window + 1):]
    rets = []
    for i in range(1, len(windowed)):
        prev = windowed[i - 1]
        if prev == 0:
            continue
        rets.append(math.log(windowed[i] / prev))
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return round(math.sqrt(var) * math.sqrt(252) * 100, 2)


def trend_state(hist: list[dict], short: int = 50, long: int = 200) -> dict[str, Any]:
    """Classify trend: price vs short MA and long MA, plus % from 52w high."""
    closes = _closes(hist)
    if not closes:
        return {"state": "unknown", "reason": "no data"}
    cur = closes[-1]
    sma = _sma(closes, short)
    lma = _sma(closes, long)
    high = max(closes[-252:]) if len(closes) >= 5 else max(closes)
    drawdown = (cur / high - 1) * 100 if high else None

    above_short = sma is not None and cur > sma
    above_long = lma is not None and cur > lma

    if above_short and above_long:
        state = "uptrend"
    elif not above_short and not above_long:
        state = "downtrend"
    else:
        state = "mixed"
    return {
        "state": state,
        "close": round(cur, 2),
        "sma_short": round(sma, 2) if sma is not None else None,
        "sma_long": round(lma, 2) if lma is not None else None,
        "drawdown_pct": round(drawdown, 2) if drawdown is not None else None,
    }


def vix_signal(hist: list[dict], ma_window: int = 50) -> dict[str, Any]:
    """VIX level vs its own moving average (complacency detection)."""
    closes = _closes(hist)
    if not closes:
        return {"level": None, "signal": "no data"}
    level = closes[-1]
    ma = _sma(closes, ma_window)
    if ma is None:
        return {"level": round(level, 2), "signal": "unknown"}
    ratio = level / ma
    if ratio < 0.85:
        signal = "complacent"
    elif ratio > 1.25:
        signal = "elevated"
    else:
        signal = "normal"
    return {
        "level": round(level, 2),
        "ma": round(ma, 2),
        "ratio": round(ratio, 2),
        "signal": signal,
    }


def compute_indicators(snapshot: dict[str, Any]) -> dict[str, Any]:
    hist = snapshot.get("histories", {})
    extra = hist.get("extra", {})

    indices_hist = {s: extra.get(s, []) for s in config.INDICES}
    sectors_hist = {s: extra.get(s, []) for s in config.SECTORS}
    ai_tickers = list({t for tickers in config.AI_CAPEX_COHORTS.values() for t in tickers})
    ai_hist = {s: extra.get(s, []) for s in ai_tickers}

    core_hist = {**indices_hist, **sectors_hist}

    breadth_core = pct_above_ma(core_hist, n=50)
    breadth_indices = pct_above_ma(indices_hist, n=50)
    breadth_sectors = pct_above_ma(sectors_hist, n=50)

    breadth_ai = pct_above_ma(ai_hist, n=50)
    cohort_groups: list[dict[str, Any]] = []
    assigned: set[str] = set()
    for name, tickers in config.AI_CAPEX_COHORTS.items():
        symbols = [t for t in tickers if t in breadth_ai["detail"] and t not in assigned]
        assigned.update(symbols)
        if symbols:
            cohort_groups.append({"name": name, "symbols": symbols})
    breadth_ai["cohort_groups"] = cohort_groups

    spy_trend = trend_state(hist.get("SPY", []))
    spy_vol = realized_vol(hist.get("SPY", []))
    vix = vix_signal(hist.get("^VIX", []))

    # Cross-asset trend ratios (3-month rate of change).
    def _roc_3m(sym: str) -> Optional[float]:
        closes = _closes(hist.get(sym, []))
        if len(closes) < 63:
            return None
        base = closes[-63]
        if base == 0:
            return None
        return round((closes[-1] / base - 1) * 100, 2)

    return {
        "as_of": snapshot.get("as_of"),
        "breadth": breadth_core,
        "breadth_indices": breadth_indices,
        "breadth_sectors": breadth_sectors,
        "breadth_ai": breadth_ai,
        "spy": {"trend": spy_trend, "realized_vol_annual_pct": spy_vol},
        "vix": vix,
        "roc_3m_pct": {
            "RSP/SPY": None,  # computed in risk engine as ratio ROC
            "RSP": _roc_3m("RSP"),
            "IWM": _roc_3m("IWM"),
            "QQQ": _roc_3m("QQQ"),
            "HYG": _roc_3m("HYG"),
            "LQD": _roc_3m("LQD"),
            "TLT": _roc_3m("TLT"),
        },
    }
