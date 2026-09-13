---
type: source
title: "AI Valuation (Beneficiary) Implementation Plan"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/superpowers/plans/2026-09-10-ai-valuation-breadth-hover.md"
original_sha256: "4034cd665a8ab78f48bfc34c962924fbd8cf6b029525e105ae2138d081940106"
stored_path: ".raw/captured/4034cd665a8ab78f48bfc34c962924fbd8cf6b029525e105ae2138d081940106.md"
source_kind: "ai-valuation-plan"
tags:
  - source
  - ai-valuation-plan
---

# AI Valuation (Beneficiary) Implementation Plan

6-task plan to re-introduce a forward-PE valuation signal for the AI capex-cycle gauge. Creates app/ai_valuation.py with 12h on-disk cache for beneficiary cohort PEs (excluding Capex Spenders), applies +25 score shift when median PE >= 30x, adds per-bar hover on the BREADTH - AI Proxies chart showing forward PE and cohort median, and restores the Valuation (Beneficiary) meta cell on the AI gauge.

## Citation

- **Original:** `inbox/docs/superpowers/plans/2026-09-10-ai-valuation-breadth-hover.md`
  - SHA-256: `4034cd665a8ab78f48bfc34c962924fbd8cf6b029525e105ae2138d081940106`
- **Captured:** `.raw/captured/4034cd665a8ab78f48bfc34c962924fbd8cf6b029525e105ae2138d081940106.md`

## Key claims

- Valuation median uses only beneficiary cohorts — Capex Spenders is excluded because its PE reflects the broader market.
  - *Evidence:* "Cohort scope: valuation median uses beneficiary cohorts only — Compute / Accelerators, Memory, Photonics / Optics, Equipment / Packaging, Neocloud / Infrastructure, Power / Data Center, Applications. Capex Spenders is excluded."
- The score shift is +25 when median beneficiary PE >= 30x.
  - *Evidence:* "Score shift: +25 to gauge score when median_pe >= 30x. No shift below 30x."
- Forward PE values come only from yf.Ticker(sym).info['forwardPE']; missing/NaN/negative are filtered.
  - *Evidence:* "Forward PE values come from yf.Ticker(sym).info['forwardPE'] only. Missing/None/NaN/negative PEs are filtered out."
- The cache has a 12-hour on-disk TTL with atomic temp+os.replace writes.
  - *Evidence:* "AI_VALUATION_CACHE_TTL_HOURS = 12. Cache: on-disk JSON at config.AI_VALUATION_CACHE_PATH with a 12-hour TTL."

## Concepts

- `ai-valuation`
- `forward-pe`
- `beneficiary-cohort`
- `cache-ttl`
- `score-shift`

## Entities

- `ai_valuation.py`
- `ai_sentiment.py`
- `service.py`
- `cards.js`
