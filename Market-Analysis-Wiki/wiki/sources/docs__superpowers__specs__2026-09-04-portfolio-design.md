---
type: source
title: "Portfolio Section — Design Spec"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/superpowers/specs/2026-09-04-portfolio-design.md"
original_sha256: "b4d4e5855f2e2f0a22bf68de1746d5667422359d5c53c631b5cad4a8d3c8caf6"
stored_path: ".raw/captured/b4d4e5855f2e2f0a22bf68de1746d5667422359d5c53c631b5cad4a8d3c8caf6.md"
source_kind: "portfolio-design"
tags:
  - source
  - portfolio-design
---

# Portfolio Section — Design Spec

Design spec for a multi-portfolio dashboard section with serenity-style expand/collapse, editable holdings cells, cash row, per-portfolio totals, and grand total. Defines data/portfolios.json schema, 10 API routes, shared tickerTable.js framework (reducing earnings.js from ~300 to ~80 LOC), column reorder via buttons, and comprehensive backend + Playwright testing strategy.

## Citation

- **Original:** `inbox/docs/superpowers/specs/2026-09-04-portfolio-design.md`
  - SHA-256: `b4d4e5855f2e2f0a22bf68de1746d5667422359d5c53c631b5cad4a8d3c8caf6`
- **Captured:** `.raw/captured/b4d4e5855f2e2f0a22bf68de1746d5667422359d5c53c631b5cad4a8d3c8caf6.md`

## Key claims

- Column prefs are managed entirely on the client via localStorage — the PUT route exists but portfolio ignores server-stored prefs.
  - *Evidence:* "Column prefs are managed entirely on the client via localStorage (pfOrder.<section>, pfVisible.<section>). The PUT /api/portfolios/columns/{section} route still exists ... but the portfolio section ignores server-stored column prefs."
- Per-holding PUT endpoints exist because autosave debounce fires per-cell (400ms), not per-portfolio.
  - *Evidence:* "The autosave debounce fires per-cell (400ms after last keystroke). Hitting PUT /api/portfolios/{id} with the whole holdings list on every cell change would rewrite all holdings."
- Cash row has kind='cash' discriminator and is always rendered last, fixed position.
  - *Evidence:* "Cash row discriminator: {'kind': 'cash'} distinguishes it from ticker holdings. Rendered last in every expanded portfolio's holdings table, fixed position."
- No live price fields are stored in JSON — prices are fetched live from yfinance at serve time.
  - *Evidence:* "No live price fields in JSON. Prices are fetched live from yfinance via market._quote_snapshot([unique_symbols])."

## Concepts

- `portfolio-section`
- `data-model`
- `api-surface`
- `tickerTable`
- `column-prefs`

## Entities

- `portfolio.py`
- `api.py`
- `tickerTable.js`
- `portfolio.js`
- `earnings.js`
