---
type: source
title: "Architecture — Module Map and Section-to-Code Reference"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/ARCHITECTURE.md"
original_sha256: "86bca5db0fec59968d57316246bd240c6d9175983a18816649db68002075e8a4"
stored_path: ".raw/captured/86bca5db0fec59968d57316246bd240c6d9175983a18816649db68002075e8a4.md"
source_kind: "architecture"
tags:
  - source
  - architecture
---

# Architecture — Module Map and Section-to-Code Reference

High-level architecture: Python 3.12 + FastAPI + uvicorn backend, vanilla HTML/CSS/JS frontend with Chart.js CDN, SQLite + JSON storage. Runs entirely locally on Windows with no cloud or API keys. Provides a section-to-code map linking each dashboard card to its renderer and payload key, a backend module quick-reference table mapping each app/ module to its public entry points and test file, and known quirks (yfinance limitations, cross-device sync model, news ingest thresholds).

## Citation

- **Original:** `inbox/project_rules/ARCHITECTURE.md`
  - SHA-256: `86bca5db0fec59968d57316246bd240c6d9175983a18816649db68002075e8a4`
- **Captured:** `.raw/captured/86bca5db0fec59968d57316246bd240c6d9175983a18816649db68002075e8a4.md`

## Key claims

- Stack is Python 3.12 + FastAPI + uvicorn with vanilla JS frontend (Chart.js CDN), no cloud dependencies.
  - *Evidence:* "Python 3.12 + FastAPI + uvicorn. Frontend: vanilla HTML/CSS/JS (Chart.js CDN). Storage: SQLite + JSON + filesystem cache."
- data/events.json syncs via Git across devices; all other data/ contents are local cache and diverge by design.
  - *Evidence:* "Cross-device sync model. `data/events.json` syncs via Git; everything else in `data/` is local cache and stays diverged by design"
- News events must score >= IMPORTANCE_THRESHOLD (6.0) on the keyword-weighted composite and be published within 48h to be stored.
  - *Evidence:* "Live events must score >= 6.0 (`IMPORTANCE_THRESHOLD`) on the keyword-weighted composite are stored"
- Failed yfinance fetches surface as null and are never cached; there is no secondary data source.
  - *Evidence:* "yfinance can rate-limit or break; there is no secondary source (see `project_rules/DECISIONS.md`). Failed fetches surface as `null` and are never cached."

## Concepts

- `section-to-code-map`
- `cross-device-sync`
- `no-cloud-dependencies`
- `known-quirks`
- `skills-integration`

## Entities

- `app/config.py`
- `app/market.py`
- `app/indicators.py`
- `app/regime.py`
- `app/risk.py`
- `app/bottleneck.py`
- `app/ai_sentiment.py`
- `app/thirteenf.py`
- `app/analysis.py`
- `app/news.py`
- `app/store.py`
- `app/portfolio.py`
- `app/service.py`
- `app/api.py`
- `data/events.json`
- `data/dashboard.json`
- `static/js/cards.js`
