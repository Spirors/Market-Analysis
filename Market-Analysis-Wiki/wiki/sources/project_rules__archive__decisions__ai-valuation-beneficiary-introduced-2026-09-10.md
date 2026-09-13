---
type: source
title: "AI Valuation (Beneficiary) introduced"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/ai-valuation-beneficiary-introduced-2026-09-10.md"
original_sha256: "fdb93571359f822756fd589e754d4383dd4f7f219332aff66d05bfeeb1b67eb7"
stored_path: ".raw/captured/fdb93571359f822756fd589e754d4383dd4f7f219332aff66d05bfeeb1b67eb7.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# AI Valuation (Beneficiary) introduced

Re-introduced a valuation signal scoped to AI beneficiary cohorts only (not spenders), using a 12-hour on-disk yfinance forward-PE cache. Median PE >= 30x adds a +25 score shift to the AI gauge, with the UI label reading 'Valuation (Beneficiary)' to make the cohort scope explicit.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/ai-valuation-beneficiary-introduced-2026-09-10.md`
  - SHA-256: `fdb93571359f822756fd589e754d4383dd4f7f219332aff66d05bfeeb1b67eb7`
- **Captured:** `.raw/captured/fdb93571359f822756fd589e754d4383dd4f7f219332aff66d05bfeeb1b67eb7.md`

## Key claims

- Valuation signal scoped to beneficiary cohorts only (excluding Capex Spenders) to keep the 'AI trade crowdedness' signal sharp.
- Median PE >= 30x applies a +25 score shift; classification happens after the shift to avoid reading 'Balanced' instead of 'Healthy expansion'.

## Concepts

- `ai-gauge`
- `valuation`
- `beneficiary-cohorts`

## Entities

- `app/ai_valuation.py`
- `AI_VALUATION_STRETCH_PE`
- `compute_ai_sentiment`
