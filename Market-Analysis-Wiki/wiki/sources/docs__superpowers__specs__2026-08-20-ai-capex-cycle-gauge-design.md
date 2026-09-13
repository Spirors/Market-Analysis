---
type: source
title: "AI Capex Cycle Gauge — Design Spec"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/superpowers/specs/2026-08-20-ai-capex-cycle-gauge-design.md"
original_sha256: "edb7d898d0fea62fd1c872dc15b6f09ef21683f492294a6fa8ea9ef9b399ae2e"
stored_path: ".raw/captured/edb7d898d0fea62fd1c872dc15b6f09ef21683f492294a6fa8ea9ef9b399ae2e.md"
source_kind: "ai-capex-design"
tags:
  - source
  - ai-capex-design
---

# AI Capex Cycle Gauge — Design Spec

Design spec for the AI capex-cycle gauge card. Defines 8 cohorts (Capex Spenders through Applications), 6 inputs per cohort (3m ROC, breadth, tone) plus cross-cohort spread, news flow, and valuation. Gauge output is a -100 to +100 needle with 5 verdict zones. Backend adds config, market.py history inclusion, new ai_sentiment.py module, and service wiring.

## Citation

- **Original:** `inbox/docs/superpowers/specs/2026-08-20-ai-capex-cycle-gauge-design.md`
  - SHA-256: `edb7d898d0fea62fd1c872dc15b6f09ef21683f492294a6fa8ea9ef9b399ae2e`
- **Captured:** `.raw/captured/edb7d898d0fea62fd1c872dc15b6f09ef21683f492294a6fa8ea9ef9b399ae2e.md`

## Key claims

- The gauge answers whether the AI trade is healthy, extended, or cracking — it is interpretive, not predictive.
  - *Evidence:* "It answers: 'Is the AI trade healthy, extended, or cracking?' The gauge is interpretive, not predictive."
- Cohorts overlap by design (e.g., TSM in compute and equipment; CRM in spenders and applications).
  - *Evidence:* "Tickers overlap by design (e.g., TSM appears in compute and equipment; CRM/PLTR/NOW appear in spenders and applications)."
- The gauge output ranges from -100 (cycle broken) to +100 (euphoric/extended) with 5 defined zones.
  - *Evidence:* "A single needle from −100 (cycle broken) to +100 (euphoric/extended) with zones."

## Concepts

- `ai-capex-gauge`
- `cohort-scoring`
- `gauge-zones`
- `valuation-flag`

## Entities

- `ai_sentiment.py`
- `config.py`
- `market.py`
- `service.py`
