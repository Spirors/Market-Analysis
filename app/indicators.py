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


# ---- Shared cross-engine math ----------------------------------------------
#
# Canonical implementations of the small calculations that the risk,
# ai-sentiment, and bottleneck engines each used to carry their own copy of.
# Index arithmetic mirrors the original call sites bit-for-bit so numeric
# output is unchanged; where a legacy variant differs subtly from its
# siblings, the difference is documented on the helper (and on the adapter
# that preserves it in app/risk.py).


def roc_at(closes: list[float], lookback: int, end_offset: int = 0) -> Optional[float]:
    """Unrounded percent rate of change between two closes of one series.

    Compares ``closes[-(end_offset + 1)]`` (the "current" bar; ``end_offset=0``
    is the latest close) against the close ``lookback`` list slots earlier,
    i.e. ``closes[-(end_offset + lookback)]`` — matching the negative-index
    idiom the engines originally used (``closes[-63]``, ``closes[-40]``).

    Returns None when the window does not fit the series or the base close is
    0. Callers apply their own rounding.
    """
    n = len(closes)
    cur_i = n - 1 - end_offset
    base_i = n - end_offset - lookback
    if cur_i < 0 or cur_i >= n or base_i < 0:
        return None
    base = closes[base_i]
    if base == 0:
        return None
    return (closes[cur_i] / base - 1) * 100


def breadth_pct_above_ma(
    histories: dict[str, list[dict]],
    ma_window: int = 50,
    symbols: Optional[list[str]] = None,
) -> Optional[float]:
    """Breadth as a plain number: % of symbols whose latest close is above
    their ``ma_window``-day moving average. None when no symbol has data."""
    if symbols is not None:
        histories = {s: histories.get(s, []) for s in symbols}
    return pct_above_ma(histories, n=ma_window)["breadth_pct"]


def breadth_pct_above_ma_at(
    histories: dict[str, list[dict]],
    ma_window: int = 50,
    end_offset: int = 0,
) -> Optional[float]:
    """Historical breadth: % of symbols above their MA as of ``end_offset``
    bars back from the latest bar.

    Unlike :func:`pct_above_ma` (whose SMA includes the compared bar), each
    symbol's MA here covers the ``ma_window`` bars strictly *before* the
    compared close — the exact window the risk engine historically used.
    Symbols without enough history, and symbols whose baseline average is 0,
    are skipped.
    """
    above = total = 0
    for hist in histories.values():
        closes = _closes(hist)
        cur_i = len(closes) - 1 - end_offset
        start = cur_i - ma_window
        if cur_i < 0 or cur_i >= len(closes) or start < 0:
            continue
        ma = sum(closes[start:cur_i]) / ma_window
        if ma == 0:
            continue
        total += 1
        if closes[cur_i] > ma:
            above += 1
    if total == 0:
        return None
    return round(above / total * 100, 1)


def vix_ma_ratio_at(hist: list[dict], ma_window: int = 50, end_offset: int = 0) -> Optional[float]:
    """Level / own-MA ratio for a series as of ``end_offset`` bars back,
    unrounded. The MA covers the ``ma_window`` bars strictly before the
    compared close (the historical variant's window); :func:`vix_signal`
    computes the current ratio with an MA that *includes* the latest bar, so
    the two are intentionally not interchangeable."""
    closes = _closes(hist)
    cur_i = len(closes) - 1 - end_offset
    start = cur_i - ma_window
    if cur_i < 0 or cur_i >= len(closes) or start < 0:
        return None
    ma = sum(closes[start:cur_i]) / ma_window
    if ma == 0:
        return None
    return closes[cur_i] / ma


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
        if prev <= 0 or windowed[i] <= 0:
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
        val = roc_at(_closes(hist.get(sym, [])), 63)
        return round(val, 2) if val is not None else None

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
