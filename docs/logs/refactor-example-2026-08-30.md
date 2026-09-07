# Refactor Example — One Service, One Adapter, One Test

Minimal, runnable template showing the new pattern structure. Built
from the real `app/risk.py` Strategy extraction so you can run the
test as-is.

## The pattern: Strategy for cross-asset signals

`compute_risk` aggregates 9 cross-asset signals. Each signal is its
own strategy that returns a `RiskSignalResult` tuple. The orchestrator
is a thin loop that aggregates tone counts and applies gate logic.

## 1. The Protocol

```python
# app/risk.py (excerpt)
from typing import NamedTuple, Optional, Any

class RiskSignalResult(NamedTuple):
    name: Optional[str]            # None for signal-only (no tone) entries
    tone: Optional[str]            # "bullish" | "bearish" | "neutral" | None
    value: str                     # human-readable value, e.g. "65% above 50DMA"
    note: str                      # short caption
    fragility_flags: list[dict]    # [{"side": "optimism"|"distress", "flag": ..., "flip": ...}]

# Each strategy is a function with the same shape:
#   def _signal_breadth(ctx: dict[str, Any]) -> RiskSignalResult: ...
```

## 2. A concrete strategy: breadth % above 50DMA

```python
# app/risk.py (excerpt — _signal_breadth)
def _signal_breadth(ctx: dict[str, Any]) -> RiskSignalResult:
    bval = ctx["breadth_pct"]
    prior = ctx["breadth_prior"]
    if bval is None:
        return RiskSignalResult(None, None, "—", "no breadth data", [])
    overheat_tier, healthy_tier, narrowing_tier, poor_tier = ctx["breadth_tiers"]
    flags: list[dict] = []
    if bval >= overheat_tier:
        tone, note = "bullish", "broad participation"
        if _is_rising(bval, prior):
            flags.append({"side": "optimism",
                          "flag": f"breadth overheating and rising ({bval}% > 50DMA)",
                          "flip": "breadth falls back below 65%"})
    elif bval >= healthy_tier:
        tone, note = "bullish", "healthy breadth"
    elif bval >= narrowing_tier:
        tone, note = "neutral", "narrowing breadth"
    elif bval >= poor_tier:
        tone, note = "bearish", "poor breadth"
    else:
        tone, note = "bearish", "breadth washed out"
        flags.append({"side": "distress",
                      "flag": f"breadth washed out ({bval}% > 50DMA)",
                      "flip": "breadth recovers above 35%"})
    return RiskSignalResult("Breadth", tone, f"{bval}% above 50DMA", note, flags)
```

The same shape is used for every other signal (concentration, VIX,
credit, small-cap, correlation, SPY trend, AI theme, valuation
stretch).

## 3. The orchestrator (thin loop)

```python
# app/risk.py (excerpt — compute_risk body)
def compute_risk(snapshot, earnings=None):
    ctx = _build_context(snapshot, earnings)

    results = [
        _signal_breadth(ctx),
        _signal_concentration(ctx),
        _signal_vix(ctx),
        _signal_credit(ctx),
        _signal_smallcap(ctx),
        _signal_correlation(ctx),
        _signal_spy_trend(ctx),
        _signal_ai_theme(ctx),
        _signal_valuation(ctx),
    ]

    signals = [r for r in results if r.name is not None]
    fragility_flags = [f for r in results for f in r.fragility_flags]

    bullish = sum(1 for r in signals if r.tone == "bullish")
    bearish = sum(1 for r in signals if r.tone == "bearish")
    neutral = sum(1 for r in signals if r.tone == "neutral")

    # ... gate logic (RISK_TONE_GATE_MIN / RISK_TONE_GATE_RATIO,
    # consensus_optimism / capitulation / risk-off / divided / leaning-*)

    return {
        "risk_level": level,
        "color": color,
        "verdict": verdict,
        "counts": {"bullish": bullish, "bearish": bearish, "neutral": neutral},
        "signals": [r._asdict() for r in signals],
        "fragility_flags": fragility_flags,
        "flip_conditions": _flip_conditions(consensus_optimism, capitulation, dd),
    }
```

## 4. The test

```python
# tests/test_risk_gates.py (excerpt)
from app.risk import compute_risk

def test_fragility_flags_carry_side_tags():
    """Optimism-side flags are the only evidence for consensus optimism;
    distress-side flags describe market breakage, not euphoria."""
    snapshot = {
        "as_of": "2026-01-01",
        "histories": {"extra": {}, "SPY": [...], "RSP": [...], ...},
    }
    earnings = {"companies": [{"symbol": "NVDA", "forward_pe": 35.0},
                              {"symbol": "MSFT", "forward_pe": 32.0},
                              {"symbol": "GOOGL", "forward_pe": 28.0}]}
    out = compute_risk(snapshot, earnings)
    for flag in out["fragility_flags"]:
        assert flag["side"] in ("optimism", "distress")
    # The consensus-optimism gate consumes only optimism-side flags.
    optimism_flags = [f for f in out["fragility_flags"] if f["side"] == "optimism"]
    # If verdict is RED with "Consensus optimism" framing, all evidence
    # must be optimism-side.
    if "Consensus optimism" in out["verdict"]:
        assert len(optimism_flags) >= 2
```

Run it:

```bash
python -m pytest tests/test_risk_gates.py::test_fragility_flags_carry_side_tags -v
```

## 5. Adding a new signal

1. Implement `_signal_<name>(ctx)` returning `RiskSignalResult`. If the
   signal produces no tone verdict (e.g., a fragility-only signal),
   return `name=None`.
2. Append it to the `results` list in `compute_risk`.
3. Add a test in `tests/test_risk_gates.py` that pins the tone and
   the fragility side-tagging.
4. Bump `config.RISK_SIGNAL_TOTAL` if you want the new signal to
   count toward tone-supermajority gates.

That's it — no orchestrator rewiring required.
