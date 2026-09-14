---
name: risk-divergence
description: Run the trend-shift risk engine (GREEN/YELLOW/RED divergence read). Use when asked about market risk, trend shifts, pullbacks, end of a bull run, or when sentiment stops being divided.
---

# Risk Divergence Engine

The crown-jewel engine for this tool. Core thesis: **a healthy bull market has
divided sentiment; when sentiment stops being divided — pure optimism, risk
dismissed, everyone in the same trade — that is a fragility setup.**

## Where the code lives

- `app/risk.py` — `compute_risk(snapshot)` returns:
  - `risk_level` (GREEN / YELLOW / RED) + `verdict`
  - `division_score` (0 = unanimous, 1 = maximally divided)
  - `signals` (each with `tone`, `value`, `note`)
  - `fragility_flags` (consensus-optimism / capitulation markers)
  - `flip_conditions` (what would change the call)

## Signals computed (free data)

Breadth (% > 50DMA), concentration (RSP/SPY), VIX complacency, credit
(HYG/LQD), small-cap (IWM/SPY), stock-bond correlation, SPY trend/drawdown.

## Interpreting

- `consensus_optimism` → RED even though nominally bullish (fragility setup).
- `capitulation` / deep drawdown → RED (trend break).
- Divided signals → GREEN/YELLOW (healthy tug-of-war).

## Command

```bash
python -c "from app import service; import json; d=service.get_dashboard(); print(json.dumps(d['risk'], default=str))"
```
