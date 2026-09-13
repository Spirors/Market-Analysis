---
type: source
title: "Market data — yfinance only, no secondary fallback"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/market-data-yfinance-only-no-secondary-fallback-2026-08-23.md"
original_sha256: "40f8939ea01b36d80765d8cfdd8dff575d6c2725c83968de13b98690bb79ed69"
stored_path: ".raw/captured/40f8939ea01b36d80765d8cfdd8dff575d6c2725c83968de13b98690bb79ed69.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Market data — yfinance only, no secondary fallback

The Stooq CSV fallback was removed because Stooq now serves a JavaScript bot-wall to non-browser clients. There is currently no secondary source for market data — failed fetches surface as null and are never cached. Do not silently re-add a scraping-based fallback.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/market-data-yfinance-only-no-secondary-fallback-2026-08-23.md`
  - SHA-256: `40f8939ea01b36d80765d8cfdd8dff575d6c2725c83968de13b98690bb79ed69`
- **Captured:** `.raw/captured/40f8939ea01b36d80765d8cfdd8dff575d6c2725c83968de13b98690bb79ed69.md`

## Key claims

- No secondary market data fallback source; failed yfinance fetches surface as null and are never cached.
- Scraping-based fallbacks must not be re-added without confirming they can survive non-browser access long-term.

## Concepts

- `data-sources`
- `yfinance`
- `market-data`

## Entities

- `yfinance`
- `Stooq`
- `app/market.py`
