---
type: source
title: "Portfolio reorder — dict key order, not a separate order field"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/portfolio-reorder-dict-key-order-not-a-separate-order-field-2026-09-07.md"
original_sha256: "a89953206d6387d80e459acbe41f6e33989a7ce1e5e9628decd1fe941c2adfb3"
stored_path: ".raw/captured/a89953206d6387d80e459acbe41f6e33989a7ce1e5e9628decd1fe941c2adfb3.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Portfolio reorder — dict key order, not a separate order field

Portfolio reorder persists by rebuilding the portfolios dict in the new key order on disk. Python json and JS JSON both preserve insertion order, so Object.values(portfolios) walks the new order without extra plumbing. A separate order field was rejected for introducing migration burden and dual source-of-truth risk.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/portfolio-reorder-dict-key-order-not-a-separate-order-field-2026-09-07.md`
  - SHA-256: `a89953206d6387d80e459acbe41f6e33989a7ce1e5e9628decd1fe941c2adfb3`
- **Captured:** `.raw/captured/a89953206d6387d80e459acbe41f6e33989a7ce1e5e9628decd1fe941c2adfb3.md`

## Key claims

- Portfolio reorder uses dict key order (insertion order) rather than a separate order field to avoid migration burden and dual source-of-truth.
- Caveat: JSON spec doesn't guarantee key order, but all production implementations preserve it.

## Concepts

- `portfolio-reorder`
- `persistence-schema`
- `dict-key-order`

## Entities

- `data/portfolios.json`
- `Object.values`
- `portfolio.py`
