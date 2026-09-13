---
type: source
title: "Codebase audit — 2026-09-07"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/logs/audit-2026-09-07.md"
original_sha256: "230e3fa4684cb243c4887f53467583399ba2575022365fc32a0d110713c5718e"
stored_path: ".raw/captured/230e3fa4684cb243c4887f53467583399ba2575022365fc32a0d110713c5718e.md"
source_kind: "audit"
tags:
  - source
  - audit
---

# Codebase audit — 2026-09-07

Post-Phase-2 sweep identifying a P0 user-visible latency on portfolio mutations (~3s on cold cache from yfinance HTTP calls), a critical ImportError in test_service_coverage.py (deleted earnings module), and severe documentation drift in API.md, ARCHITECTURE.md, TESTING.md, and HANDOFF.md. Server lifecycle and data integrity were cleared.

## Citation

- **Original:** `inbox/docs/logs/audit-2026-09-07.md`
  - SHA-256: `230e3fa4684cb243c4887f53467583399ba2575022365fc32a0d110713c5718e`
- **Captured:** `.raw/captured/230e3fa4684cb243c4887f53467583399ba2575022365fc32a0d110713c5718e.md`

## Key claims

- Portfolio mutations cause ~3s latency on cold cache because _patch_dashboard_cache re-enriches all symbols.
  - *Evidence:* "Every portfolio mutation fires _patch_dashboard_cache(state) which calls enrich_portfolios(state). On a cold cache, enrich_portfolios does 1 bulk yf.download(7d) + 1 bulk yf.download(260d) + N × Ticker.info."
- test_service_coverage.py imports the deleted app.earnings module, breaking any test run.
  - *Evidence:* "tests/test_service_coverage.py:312,358,453 all do from app import earnings as earnings_mod. app/earnings.py was deleted 2026-09-06."
- API.md lists 14 routes but the actual code has 25+.
  - *Evidence:* "The file lists 14 routes but the actual code has 25+ (all Portfolio CRUD is undocumented)."
- NEWS_FEEDS in config.py lists MarketWatch + BBC Business but README still claims SCMP and Korea Herald.
  - *Evidence:* "README.md:40 claims news sources are 'MarketWatch / SCMP China / SCMP Business / Korea Herald' but app/config.py:242-245 actually lists MarketWatch + BBC Business."

## Concepts

- `portfolio-latency`
- `test-coverage`
- `doc-drift`
- `news-threshold`
- `data-integrity`

## Entities

- `portfolio.py`
- `test_service_coverage.py`
- `API.md`
- `ARCHITECTURE.md`
- `HANDOFF.md`
