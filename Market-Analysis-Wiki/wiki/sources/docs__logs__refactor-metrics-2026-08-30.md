---
type: source
title: "Refactor Metrics — 2026-08-30"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/logs/refactor-metrics-2026-08-30.md"
original_sha256: "f8e9779e059a8bc34b741f8b58cd4a78cd2651ea2fd1bebcb6359d37d848c9c4"
stored_path: ".raw/captured/f8e9779e059a8bc34b741f8b58cd4a78cd2651ea2fd1bebcb6359d37d848c9c4.md"
source_kind: "refactor-metrics"
tags:
  - source
  - refactor-metrics
---

# Refactor Metrics — 2026-08-30

End-of-day metrics capture for the three-lane refactor. Test suite grew from 250 to 302 pytest + 20 Playwright. compute_risk cyclomatic complexity dropped 65% (F→D). 52 new pytest tests across thirteenf, scheduler, run, indicators props, dashboard equivalence, news analyze, and store. Full file inventory and wall-clock breakdown (~55 min total).

## Citation

- **Original:** `inbox/docs/logs/refactor-metrics-2026-08-30.md`
  - SHA-256: `f8e9779e059a8bc34b741f8b58cd4a78cd2651ea2fd1bebcb6359d37d848c9c4`
- **Captured:** `.raw/captured/f8e9779e059a8bc34b741f8b58cd4a78cd2651ea2fd1bebcb6359d37d848c9c4.md`

## Key claims

- Test suite went from 250 to 302 pytest plus 20 Playwright tests, all passing.
  - *Evidence:* "pytest: 250 → 302 (+52). Playwright (tests/frontend): 0 → 20 (+20). Pass rate: 100%."
- compute_risk cyclomatic complexity went from F(78) to D(27), a 65% reduction.
  - *Evidence:* "app/risk.py :: compute_risk: F (78) → D (27) — −65%."
- Wall-clock time for the full refactor was approximately 55 minutes.
  - *Evidence:* "Total: ~55 min."

## Concepts

- `refactor-metrics`
- `cyclomatic-complexity`
- `test-delta`
- `wall-clock`

## Entities

- `risk.py`
- `store.py`
- `market.py`
- `regime.py`
- `news.py`
