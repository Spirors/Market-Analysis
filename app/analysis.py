"""Rule-based AI Analysis: deterministic synthesis of the dashboard engines.

NO LLM, no API keys. Every sentence below is a template with computed facts
interpolated from the assembled dashboard payload; sections that are missing
or unavailable are excluded from scoring and listed under
`inputs_used["unavailable"]`. Nothing is ever defaulted or guessed.

Weighted vote (tone: bullish +1 / neutral 0 / bearish -1; fractional where
noted), score = sum(weight * tone) / sum(weights) * 100 in [-100, 100]:

  input                       weight   mapping
  risk engine level           3        GREEN +1 / YELLOW 0 / RED -1
  regime label                2        Broadening +1 / Transitional 0 /
                                       Concentration -0.5 / Inflationary -0.5 /
                                       Contraction -1
  breadth (% > 50DMA)         2        >=60 +1 / <45 -1 / else 0
  VIX signal                  1        elevated -1 / normal 0 / complacent +0.5
  SPY trend                   1        uptrend +1 / mixed 0 / downtrend -1
  index futures day move avg  1        >=+0.3% +1 / <=-0.3% -1 / else 0
  bottleneck category momentum 1       >+5% +0.5 / <-5% -0.5 / else 0
  earnings recs net           1        bull-caution share >=+.25 +0.5 / <=-.25 -0.5
  events tone (last 60 days)  1        net bullish +0.5 / net bearish -0.5
  13F AI-cohort overlap       1        AI name in top-3 of >=50% funds -> -0.5
"""

from datetime import date, timedelta
from typing import Any

from . import config

# Per-input weights (mirrors the table in the module docstring); the coverage
# denominator is derived from this table so it can never drift from it.
_WEIGHTS = {
    "risk_engine": 3.0,
    "regime": 2.0,
    "breadth_pct_above_50dma": 2.0,
    "vix": 1.0,
    "spy_trend": 1.0,
    "index_futures_day_avg": 1.0,
    "bottleneck_avg_momentum_40d": 1.0,
    "earnings_recs": 1.0,
    "events_last_60d": 1.0,
    "thirteenf": 1.0,
}
_TOTAL_WEIGHT = sum(_WEIGHTS.values())


def _stance_from_score(score: float) -> str:
    if score >= 25:
        return "Risk-On"
    if score > -10:
        return "Neutral"
    if score > -35:
        return "Cautious"
    return "Risk-Off"


def _confidence_from_score(score: float, weight_used: float) -> int:
    conf = min(100.0, abs(score) * 1.2)
    coverage = weight_used / _TOTAL_WEIGHT
    # Order matters: check the tightest cap first. The previous nesting
    # (`55 if cov<0.7 else (35 if cov<0.4 else 100)`) made the 35 tier
    # unreachable -- coverage < 0.4 was captured by the 55 arm.
    cap = 35.0 if coverage < 0.4 else (55.0 if coverage < 0.7 else 100.0)
    return int(round(min(conf, cap)))


def _signed(v: float | None, nd: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:+.{nd}f}"


def _events_tone(events: list[dict[str, Any]], as_of_date: date | None) -> tuple[int, int]:
    """(bullish_tags, bearish_tags) among events published in the last
    ``config.NEWS_LOOKBACK_DAYS`` days (≈ two months). Stale events must never
    affect the synthesis — only the fresh half of the news timeline counts."""
    if as_of_date is None:
        return 0, 0
    cutoff = as_of_date - timedelta(days=config.NEWS_LOOKBACK_DAYS)
    bull = bear = 0
    for e in events or []:
        try:
            pub = date.fromisoformat((e.get("published") or "")[:10])
        except (TypeError, ValueError):
            continue
        if pub < cutoff:
            continue
        tags = e.get("tags") or []
        if "bullish" in tags:
            bull += 1
        if "bearish" in tags:
            bear += 1
    return bull, bear


def build_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    """Synthesize the dashboard payload into a stance + narrative (deterministic)."""
    inputs_used: dict[str, Any] = {}
    unavailable: list[str] = []
    bullets: list[str] = []
    divergences: list[str] = []
    watch: list[str] = []

    num = 0.0   # sum of weight * tone
    den = 0.0   # sum of weights actually scored

    def add(tone: float, weight: float) -> None:
        nonlocal num, den
        num += weight * tone
        den += weight

    # ---- 1. Risk-divergence engine ----
    risk = payload.get("risk") or {}
    rlevel = risk.get("risk_level")
    rcounts = risk.get("counts") or {}
    if rlevel in ("GREEN", "YELLOW", "RED"):
        add({"GREEN": 1.0, "YELLOW": 0.0, "RED": -1.0}[rlevel], 3)
        verdict = risk.get("verdict") or ""
        inputs_used["risk_engine"] = (
            f"{rlevel} — {verdict} (bull {rcounts.get('bullish', 0)}"
            f" / bear {rcounts.get('bearish', 0)} / neutral {rcounts.get('neutral', 0)})"
        )
        bullets.append(
            f"Risk engine reads {rlevel} ({verdict}): {rcounts.get('bullish', 0)} bullish"
            f" vs {rcounts.get('bearish', 0)} bearish signals."
        )
        if risk.get("consensus_optimism"):
            divergences.append(
                f"Consensus optimism: {rcounts.get('bullish', 0)} of"
                f" {sum(rcounts.values())} signals bullish at once — unanimity is the"
                " fragility, not the strength."
            )
        for flag in (risk.get("fragility_flags") or [])[:2]:
            text = flag.get("flag") if isinstance(flag, dict) else flag
            if text:
                watch.append(str(text))
        for flip in (risk.get("flip_conditions") or [])[:2]:
            watch.append(f"Flip condition: {flip}")
    else:
        unavailable.append("risk engine")

    # ---- 2. Regime ----
    regime = payload.get("regime") or {}
    rlabel = (regime.get("regime") or {}).get("regime_label")
    if rlabel and not regime.get("error"):
        comp = regime.get("composite") or {}
        cscore = comp.get("composite_score")
        zone = comp.get("zone")
        rconf = (regime.get("regime") or {}).get("confidence")
        add(
            {"Broadening": 1.0, "Transitional": 0.0, "Concentration": -0.5,
             "Inflationary": -0.5, "Contraction": -1.0}.get(rlabel, 0.0),
            2,
        )
        inputs_used["regime"] = f"{rlabel} (composite {cscore}/100, zone {zone})"
        bullets.append(
            f"Regime detector: {rlabel} — composite {cscore if cscore is not None else '—'}/100"
            f" in the {zone or '—'} zone, confidence {rconf or '—'}."
        )
    else:
        unavailable.append("regime")

    # ---- 3. Indicators: breadth / VIX / trend ----
    ind = payload.get("indicators") or {}
    bpct = (ind.get("breadth") or {}).get("breadth_pct")
    if bpct is not None:
        add(1.0 if bpct >= 60 else (-1.0 if bpct < 45 else 0.0), 2)
        inputs_used["breadth_pct_above_50dma"] = bpct
    vix = ind.get("vix") or {}
    vlevel, vsig = vix.get("level"), vix.get("signal")
    if vlevel is not None and vsig and vsig != "no data":
        add(-1.0 if vsig == "elevated" else (0.5 if vsig == "complacent" else 0.0), 1)
        inputs_used["vix"] = f"{vlevel} ({vsig} vs MA {vix.get('ma')})"
    spy_trend = ((ind.get("spy") or {}).get("trend") or {})
    tstate, tdd = spy_trend.get("state"), spy_trend.get("drawdown_pct")
    if tstate and tstate != "unknown":
        add({"uptrend": 1.0, "mixed": 0.0, "downtrend": -1.0}.get(tstate, 0.0), 1)
        inputs_used["spy_trend"] = f"{tstate}, drawdown {tdd}%"
    if bpct is not None or (vlevel is not None and vsig != "no data") or (tstate and tstate != "unknown"):
        parts = []
        if bpct is not None:
            parts.append(f"breadth {bpct}% of sectors & indices above their 50-day MA")
        if tstate and tstate != "unknown":
            parts.append(f"SPY trend {tstate} ({tdd:+.1f}% from its 52-week high)" if tdd is not None else f"SPY trend {tstate}")
        if vlevel is not None and vsig and vsig != "no data":
            parts.append(f"VIX {vlevel} ({vsig})")
        bullets.append("Tape check: " + "; ".join(parts) + ".")
    else:
        unavailable.append("indicators/breadth")

    # ---- 4. Futures risk appetite ----
    fut = payload.get("futures") or {}
    moves = [
        (f.get("symbol"), f.get("chg_pct"))
        for f in (fut.get("index_futures") or [])
        if f.get("chg_pct") is not None
    ]
    if moves:
        avg = sum(p for _, p in moves) / len(moves)
        add(1.0 if avg >= 0.3 else (-1.0 if avg <= -0.3 else 0.0), 1)
        detail = ", ".join(f"{s.replace('=F', '')} {_signed(p)}%" for s, p in moves)
        inputs_used["index_futures_day_avg"] = round(avg, 2)
        bullets.append(
            f"Index futures {'lean risk-on' if avg >= 0.3 else ('lean risk-off' if avg <= -0.3 else 'are flat')} today:"
            f" {detail} (avg {_signed(round(avg, 2))}%)."
        )
        if avg <= -1.0 and rlevel == "GREEN":
            divergences.append(
                f"Index futures average {_signed(round(avg, 2))}% today while the risk engine still reads GREEN."
            )
    else:
        unavailable.append("futures")

    # ---- 5. Bottleneck chokepoint momentum ----
    bn = payload.get("bottleneck") or {}
    cats = bn.get("categories") or []
    scores = [c.get("proxy_40d_roc_pct") for c in cats if c.get("proxy_40d_roc_pct") is not None]
    if scores:
        avg_bn = sum(scores) / len(scores)
        add(0.5 if avg_bn > 5 else (-0.5 if avg_bn < -5 else 0.0), 1)
        strongest = bn.get("strongest_signal") or {}
        inputs_used["bottleneck_avg_momentum_40d"] = round(avg_bn, 2)
        s_txt = (
            f"; strongest layer {strongest.get('layer')}"
            f" {_signed(strongest.get('proxy_40d_roc_pct'))}% 40d" if strongest.get("layer") else ""
        )
        bullets.append(
            f"Bottleneck proxies average {_signed(round(avg_bn, 2))}% 40-day momentum across"
            f" {len(scores)} categories{s_txt}."
        )
    else:
        unavailable.append("bottleneck")

    # ---- 6. Earnings recs ----
    earn = payload.get("earnings") or {}
    recs = [c.get("rec_signal") for c in (earn.get("companies") or []) if c.get("rec_signal")]
    if recs:
        n_bull = sum(1 for r in recs if r == "Bullish")
        n_caut = sum(1 for r in recs if r == "Cautious")
        share = n_bull / len(recs) - n_caut / len(recs)
        add(0.5 if share >= 0.25 else (-0.5 if share <= -0.25 else 0.0), 1)
        inputs_used["earnings_recs"] = f"{n_bull} Bullish / {n_caut} Cautious / {len(recs) - n_bull - n_caut} Neutral"
        bullets.append(
            f"Earnings watchlist rules rate {n_bull} Bullish / {n_caut} Cautious /"
            f" {len(recs) - n_bull - n_caut} Neutral across {len(recs)} tracked names."
        )
    else:
        unavailable.append("earnings recs")

    # ---- 7. Recent event flow ----
    events = payload.get("events") or []
    try:
        as_of_date = date.fromisoformat((payload.get("as_of") or "")[:10])
    except (TypeError, ValueError):
        as_of_date = None
    e_bull, e_bear = _events_tone(events, as_of_date)
    if e_bull + e_bear > 0:
        add(0.5 if e_bull > e_bear else (-0.5 if e_bear > e_bull else 0.0), 1)
        inputs_used["events_last_60d"] = f"{e_bull} bullish-tagged / {e_bear} bearish-tagged"
        bullets.append(
            f"Event flow (last {config.NEWS_LOOKBACK_DAYS} days): {e_bull} bullish-tagged vs {e_bear} bearish-tagged high-impact events."
        )

    # ---- 8. Superinvestor 13F concentration / AI overlap ----
    tf = payload.get("thirteenf") or {}
    funds = tf.get("funds") or []
    if funds:
        ai_tickers = {t for tickers in config.AI_CAPEX_COHORTS.values() for t in tickers}
        overlap = sum(
            1 for f in funds
            if any(h.get("ticker") in ai_tickers for h in (f.get("top") or [])[:3])
        )
        top_weights = [
            f["top"][0]["weight_pct"]
            for f in funds
            if f.get("top") and f["top"][0].get("weight_pct") is not None
        ]
        avg_top = round(sum(top_weights) / len(top_weights), 1) if top_weights else None
        add(-0.5 if funds and overlap / len(funds) >= 0.5 else 0.0, 1)
        inputs_used["thirteenf"] = (
            f"{len(funds)} funds parsed for {tf.get('quarter') or '—'};"
            f" AI-cohort names in top-3 of {overlap}/{len(funds)} funds;"
            f" average top holding weight {avg_top if avg_top is not None else '—'}%"
        )
        bullets.append(
            f"Superinvestor 13F ({tf.get('quarter') or 'quarter —'}): {len(funds)} funds parsed;"
            f" AI-cohort names sit in the top-3 holdings of {overlap}/{len(funds)} funds;"
            f" average top holding weight {avg_top if avg_top is not None else '—'}%."
        )
        if tf.get("errors"):
            watch.append(f"13F fetch errors for {len(tf['errors'])} fund(s) — those funds are omitted.")
    else:
        unavailable.append("superinvestor 13F")

    # ---- Cross-engine divergences (only genuine disagreements) ----
    if rlevel == "GREEN" and bpct is not None and bpct < 45:
        divergences.append(
            f"Risk engine reads GREEN but breadth is only {bpct}% above the 50-day MA."
        )
    if rlevel == "RED" and bpct is not None and bpct >= 60:
        divergences.append(
            f"Risk engine reads RED while breadth is strong at {bpct}% above the 50-day MA."
        )
    conc = next(
        (s for s in (risk.get("signals") or []) if str(s.get("name", "")).startswith("Concentration")),
        None,
    )
    if rlabel == "Broadening" and conc and conc.get("tone") == "bearish":
        divergences.append(
            f"Regime says Broadening but the concentration signal is bearish"
            f" (RSP/SPY {conc.get('value')} — {conc.get('note')})."
        )
    if vsig == "complacent" and bpct is not None and bpct < 45:
        divergences.append(
            f"VIX complacency ({vlevel}) into weak participation ({bpct}% above 50DMA)."
        )

    # ---- Aggregate stance ----
    score = round(num / den * 100, 1) if den else 0.0
    stance = _stance_from_score(score)
    confidence = _confidence_from_score(score, den)

    headline_parts = []
    if rlevel:
        headline_parts.append(f"risk engine {rlevel}")
    if bpct is not None:
        headline_parts.append(f"breadth {bpct}%")
    if vlevel is not None and vsig != "no data":
        headline_parts.append(f"VIX {vlevel}")
    if moves:
        headline_parts.append(f"futures {_signed(round(sum(p for _, p in moves) / len(moves), 2))}%")
    headline = (
        f"{stance}: " + ", ".join(headline_parts) + "."
        if headline_parts else f"{stance}: insufficient engine data to cite specifics."
    )

    if unavailable:
        inputs_used["unavailable"] = unavailable
        bullets.append(
            "Excluded from scoring (unavailable this run): " + ", ".join(unavailable) + "."
        )

    return {
        "generated_at": payload.get("as_of"),
        "stance": stance,
        "confidence": confidence,
        "headline": headline,
        "bullets": bullets[:6],
        "divergences": divergences,
        "watch": watch[:6],
        "inputs_used": inputs_used,
        "score": score,
    }
