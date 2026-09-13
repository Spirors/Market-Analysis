---
type: source
title: "AI Capex Cycle Gauge Implementation Plan"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/superpowers/plans/2026-08-20-ai-capex-cycle-gauge.md"
original_sha256: "fb0ad700f3370536340a036136385193894b42c6ae31f098ffc2b57c2e134c0d"
stored_path: ".raw/captured/fb0ad700f3370536340a036136385193894b42c6ae31f098ffc2b57c2e134c0d.md"
source_kind: "ai-capex-plan"
tags:
  - source
  - ai-capex-plan
---

# AI Capex Cycle Gauge Implementation Plan

6-task plan to add an AI capex-cycle gauge card below the risk banner. Defines 8 cohorts (Capex Spenders, Compute/Accelerators, Memory, Photonics, Equipment, Neocloud, Power/DC, Applications) with ticker lists. Implements cohort ROC, breadth, tone, news sentiment scoring, and valuation flag. Frontend adds gauge needle, verdict, component table, and flip conditions.

## Citation

- **Original:** `inbox/docs/superpowers/plans/2026-08-20-ai-capex-cycle-gauge.md`
  - SHA-256: `fb0ad700f3370536340a036136385193894b42c6ae31f098ffc2b57c2e134c0d`
- **Captured:** `.raw/captured/fb0ad700f3370536340a036136385193894b42c6ae31f098ffc2b57c2e134c0d.md`

## Key claims

- The gauge uses 8 cohorts covering the full AI supply chain from hyperscalers to power/data-center.
  - *Evidence:* "AI_CAPEX_COHORTS = {'Capex Spenders': [...], 'Compute / Accelerators': [...], ...}"
- The gauge score is a composite of cohort ROC, spenders-vs-beneficiaries spread, news sentiment, and valuation stretch.
  - *Evidence:* "score += sum((c['roc_3m_pct'] or 0) for c in valid_cohorts) / len(valid_cohorts) * 2; score += spread * 1.5; score += news['score'] * 0.3; if valuation['stretched']: score -= 15."
- Verdicts range from 'Cycle under pressure' to 'Euphoric / fragility setup' at defined thresholds.
  - *Evidence:* "score >= 60: 'Euphoric / fragility setup'; score >= 20: 'Healthy expansion'; ... score < -60: 'Cycle under pressure'."

## Concepts

- `ai-capex-gauge`
- `cohort-roc`
- `cohort-breadth`
- `news-sentiment`
- `valuation-flag`

## Entities

- `ai_sentiment.py`
- `config.py`
- `market.py`
- `service.py`
