---
type: source
title: "Commodities spot pricing — FRED + Minted Metal, not Yahoo quotes"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/commodities-spot-pricing-fred-minted-metal-not-yahoo-quotes-undated.md"
original_sha256: "afc962b990b53c2306f80dd0918a14406dad30cf313905fbd52488f9668d3444"
stored_path: ".raw/captured/afc962b990b53c2306f80dd0918a14406dad30cf313905fbd52488f9668d3444.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Commodities spot pricing — FRED + Minted Metal, not Yahoo quotes

Real cash-market spot prices for the Commodities card come from FRED public CSV (energy) and Minted Metal public JSON (precious metals), mapped back onto matching Yahoo futures tickers, because Yahoo fast_info is broken in current yfinance versions.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/commodities-spot-pricing-fred-minted-metal-not-yahoo-quotes-undated.md`
  - SHA-256: `afc962b990b53c2306f80dd0918a14406dad30cf313905fbd52488f9668d3444`
- **Captured:** `.raw/captured/afc962b990b53c2306f80dd0918a14406dad30cf313905fbd52488f9668d3444.md`

## Key claims

- Commodities spot pricing uses FRED CSV for energy and Minted Metal JSON for precious metals, not Yahoo fast_info.

## Concepts

- `commodities`
- `data-sources`
- `yfinance-limitations`

## Entities

- `FRED`
- `Minted Metal`
- `yfinance`
