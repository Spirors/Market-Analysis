---
type: source
title: "Refactor Example — One Service, One Adapter, One Test"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/logs/refactor-example-2026-08-30.md"
original_sha256: "10ffa3423e61ae77e43f6fb8377dcd7164dff39c957aa792bab863e91e4f5f5e"
stored_path: ".raw/captured/10ffa3423e61ae77e43f6fb8377dcd7164dff39c957aa792bab863e91e4f5f5e.md"
source_kind: "refactor-example"
tags:
  - source
  - refactor-example
---

# Refactor Example — One Service, One Adapter, One Test

Minimal runnable template demonstrating the Strategy pattern extraction from compute_risk. Shows the RiskSignalResult NamedTuple, a concrete _signal_breadth strategy, the thin orchestrator loop, and a test verifying fragility side-tagging. Provides step-by-step instructions for adding a new signal without rewiring the orchestrator.

## Citation

- **Original:** `inbox/docs/logs/refactor-example-2026-08-30.md`
  - SHA-256: `10ffa3423e61ae77e43f6fb8377dcd7164dff39c957aa792bab863e91e4f5f5e`
- **Captured:** `.raw/captured/10ffa3423e61ae77e43f6fb8377dcd7164dff39c957aa792bab863e91e4f5f5e.md`

## Key claims

- Each signal is its own strategy function returning a RiskSignalResult tuple.
  - *Evidence:* "Each signal is its own strategy that returns a RiskSignalResult tuple."
- Adding a new signal requires only implementing _signal_<name>(ctx) and appending to the results list.
  - *Evidence:* "Adding a new signal: implement _signal_<name>(ctx) and append to the results list in compute_risk."
- Fragility flags carry side tags and the consensus-optimism gate consumes only optimism-side flags.
  - *Evidence:* "The consensus-optimism gate consumes only optimism-side flags."

## Concepts

- `strategy-pattern`
- `risk-signals`
- `fragility-flags`
- `orchestrator`

## Entities

- `risk.py`
- `RiskSignalResult`
- `test_risk_gates.py`
