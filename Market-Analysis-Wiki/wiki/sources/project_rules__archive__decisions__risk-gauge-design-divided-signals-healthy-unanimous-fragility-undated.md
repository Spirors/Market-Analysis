---
type: source
title: "Risk gauge design — divided signals = healthy, unanimous = fragility"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/risk-gauge-design-divided-signals-healthy-unanimous-fragility-undated.md"
original_sha256: "d12f63d365a549b15c26b43bdba128605da0bc4d75d2a0e12a9b106669897486"
stored_path: ".raw/captured/d12f63d365a549b15c26b43bdba128605da0bc4d75d2a0e12a9b106669897486.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Risk gauge design — divided signals = healthy, unanimous = fragility

In app/risk.py, divided signals across the 9 cross-asset inputs are healthy; unanimous optimism is the fragility signal (RED fires on consensus optimism, not just bad numbers). Do not fix app/risk.py to fire on raw bearishness — unanimous bearishness is not the RED trigger.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/risk-gauge-design-divided-signals-healthy-unanimous-fragility-undated.md`
  - SHA-256: `d12f63d365a549b15c26b43bdba128605da0bc4d75d2a0e12a9b106669897486`
- **Captured:** `.raw/captured/d12f63d365a549b15c26b43bdba128605da0bc4d75d2a0e12a9b106669897486.md`

## Key claims

- The risk gauge RED fires on unanimous optimism (fragility), not unanimous bearishness.
- Do not refactor app/risk.py to fire on raw bearishness — the divided-signals-healthy framing is intentional.

## Concepts

- `risk-gauge`
- `divided-signals`
- `fragility`

## Entities

- `app/risk.py`
- `RISK_SIGNAL_TOTAL`
- `ai_market_sentiment_gauge.html`
