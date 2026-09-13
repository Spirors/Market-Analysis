---
type: source
title: "Portfolio Section Implementation Plan"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/superpowers/plans/2026-09-04-portfolio.md"
original_sha256: "7188dcb5649d9eb6e98cea6f4e3b25cbc7abd22aa790613ac9575967c49a4614"
stored_path: ".raw/captured/7188dcb5649d9eb6e98cea6f4e3b25cbc7abd22aa790613ac9575967c49a4614.md"
source_kind: "portfolio-plan"
tags:
  - source
  - portfolio-plan
---

# Portfolio Section Implementation Plan

11-task implementation plan for a multi-portfolio section with editable cells, cash row, totals, and shared tickerTable.js framework. Backend-first: data layer (app/portfolio.py) with CRUD + enrichment, then 10 API routes. Frontend: shared tickerTable.js framework, portfolio renderer with serenity-style expand/collapse, earnings refactor to use tickerTable.js, and Playwright tests.

## Citation

- **Original:** `inbox/docs/superpowers/plans/2026-09-04-portfolio.md`
  - SHA-256: `7188dcb5649d9eb6e98cea6f4e3b25cbc7abd22aa790613ac9575967c49a4614`
- **Captured:** `.raw/captured/7188dcb5649d9eb6e98cea6f4e3b25cbc7abd22aa790613ac9575967c49a4614.md`

## Key claims

- Portfolio data persists in data/portfolios.json which is gitignored by the existing data/* rule.
  - *Evidence:* "data/portfolios.json is the single source of truth for portfolios and column prefs. data/* is gitignored."
- The tickerTable.js shared framework reduces earnings.js from ~300 LOC to ~80 LOC.
  - *Evidence:* "earnings.js ~300 LOC → ~80 LOC. Reduced to EARN_COLUMNS metadata + watch-stars persistence + a thin renderEarnings(earn) that calls createTickerTable(...)."
- Symbol validation flows through the existing earnings.validate_symbol — single source of truth.
  - *Evidence:* "Symbol validation flows through the existing earnings.validate_symbol(sym). Single source of truth — no second validator."

## Concepts

- `portfolio-section`
- `tickerTable`
- `serenity-expand`
- `cash-row`
- `column-prefs`

## Entities

- `portfolio.py`
- `tickerTable.js`
- `portfolio.js`
- `earnings.js`
- `api.js`
