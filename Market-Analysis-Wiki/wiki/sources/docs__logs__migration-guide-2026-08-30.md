---
type: source
title: "Migration Guide — Refactor 2026-08-30"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/logs/migration-guide-2026-08-30.md"
original_sha256: "5f18955fb6e700fcd42f6410047d73d5a23784272c02587f6292ac05dc2434b4"
stored_path: ".raw/captured/5f18955fb6e700fcd42f6410047d73d5a23784272c02587f6292ac05dc2434b4.md"
source_kind: "migration-guide"
tags:
  - source
  - migration-guide
---

# Migration Guide — Refactor 2026-08-30

Internal module change guide for the 2026-08-30 three-lane refactor (backend patterns, frontend tooltip/refresh, news relevance). The public HTTP API is unchanged. Covers Strategy pattern in risk.py, Repository pattern in store.py, Adapter protocols in market.py/thirteenf.py, Factory pattern in regime.py, finance-relevance scoring in news.py, and new tooltip.js/events.js frontend components.

## Citation

- **Original:** `inbox/docs/logs/migration-guide-2026-08-30.md`
  - SHA-256: `5f18955fb6e700fcd42f6410047d73d5a23784272c02587f6292ac05dc2434b4`
- **Captured:** `.raw/captured/5f18955fb6e700fcd42f6410047d73d5a23784272c02587f6292ac05dc2434b4.md`

## Key claims

- The public HTTP API was preserved byte-for-byte; only internal module patterns changed.
  - *Evidence:* "The refactor preserved the public HTTP API (/api/*) byte-for-byte (modulo as_of)."
- Cyclomatic complexity of compute_risk dropped from F(78) to D(27), a 65% reduction.
  - *Evidence:* "Cyclomatic complexity D (27), −65%."
- Test suite grew from 250 to 302 (+52) with full Playwright frontend coverage added.
  - *Evidence:* "Test suite: 250 → 302 (+52). Playwright (tests/frontend): 0 → 20 (+20)."

## Concepts

- `strategy-pattern`
- `repository-pattern`
- `adapter-protocol`
- `factory-pattern`
- `finance-relevance`

## Entities

- `risk.py`
- `store.py`
- `market.py`
- `regime.py`
- `tooltip.js`
