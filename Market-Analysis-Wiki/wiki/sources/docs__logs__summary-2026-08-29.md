---
type: source
title: "Market Analysis Tool — Project Summary"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/logs/summary-2026-08-29.md"
original_sha256: "5fdc119588eea3abf1bb0a3e3b158ee735397466e025619b258f01d5450b26b7"
stored_path: ".raw/captured/5fdc119588eea3abf1bb0a3e3b158ee735397466e025619b258f01d5450b26b7.md"
source_kind: "summary"
tags:
  - source
  - summary
---

# Market Analysis Tool — Project Summary

Plain-English project overview covering what the dashboard shows (risk banner, fragility flags, macro regime, indicators, breadth, bottleneck, AI capex gauge, 13F superinvestors, earnings calendar, events timeline), what was built across 60 commits over 6 days (4 phases: bug fixes, improvements, parked decisions, news section hardening), and how to run it.

## Citation

- **Original:** `inbox/docs/logs/summary-2026-08-29.md`
  - SHA-256: `5fdc119588eea3abf1bb0a3e3b158ee735397466e025619b258f01d5450b26b7`
- **Captured:** `.raw/captured/5fdc119588eea3abf1bb0a3e3b158ee735397466e025619b258f01d5450b26b7.md`

## Key claims

- The project shipped 60 commits over 6 days with 250 tests passing, up from 9.
  - *Evidence:* "60 commits on main, fully merged with the improvements and parked-decisions branches. 250 tests passing (up from 9)."
- All data comes from free, public sources with no API keys and no cloud.
  - *Evidence:* "Everything the dashboard shows is fetched live from free, public data sources (no API keys, no paid subscriptions, no cloud)."
- The frozen reference HTML files are preserved as-is and never modified.
  - *Evidence:* "Frozen reference files preserved as-is (4 archived ai_*.html files)."

## Concepts

- `project-overview`
- `dashboard-cards`
- `data-sources`
- `test-suite`

## Entities

- `run.py`
- `config.py`
- `market.py`
- `risk.py`
