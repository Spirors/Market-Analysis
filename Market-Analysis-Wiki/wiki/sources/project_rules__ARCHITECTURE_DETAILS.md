---
type: source
title: "Architecture — Deep-Dive Module Descriptions"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/ARCHITECTURE_DETAILS.md"
original_sha256: "34b1b4791f0c462508cf708b074108fa20346befb40f54ee63858753821425f5"
stored_path: ".raw/captured/34b1b4791f0c462508cf708b074108fa20346befb40f54ee63858753821425f5.md"
source_kind: "architecture-details"
tags:
  - source
  - architecture-details
---

# Architecture — Deep-Dive Module Descriptions

Verbose per-module companion to ARCHITECTURE.md. Describes every app/ module's callers, cache layout, and design rationale. Key modules covered: config (symbols/feeds/TTLs), market (yfinance quotes + bulk histories), spot (FRED + Minted Metal commodities pricing), indicators (breadth/MAs/VIX), regime (subprocess wrapper for macro-regime-detector skill), risk (9-signal divergence engine), bottleneck (serenity chokepoint framework), ai_sentiment (capex-cycle gauge), thirteenf (SEC EDGAR 13F), analysis (deterministic weighted-vote synthesis), news (RSS ingestion + tagging), store (SQLite persistence), validation, portfolio, scheduler, service (refresh orchestration), lifecycle, lockfile, and changelog.

## Citation

- **Original:** `inbox/project_rules/ARCHITECTURE_DETAILS.md`
  - SHA-256: `34b1b4791f0c462508cf708b074108fa20346befb40f54ee63858753821425f5`
- **Captured:** `.raw/captured/34b1b4791f0c462508cf708b074108fa20346befb40f54ee63858753821425f5.md`

## Key claims

- app/risk.py is the crown jewel — scores 9 cross-asset signals and outputs GREEN/YELLOW/RED with per-signal evidence and fragility flags.
  - *Evidence:* "app/risk.py — the **risk-divergence engine** (crown jewel). Scores 9 cross-asset signals"
- app/spot.py uses FRED for energy and Minted Metal for precious metals; one Minted Metal fetch covers all precious metals.
  - *Evidence:* "FRED public CSV for energy (WTI/Brent/Henry Hub NG, daily), Minted Metal public JSON for precious metals (LBMA gold/silver, twice-daily)"
- app/thirteenf.py shows weight-% only, never dollar values, because EDGAR changed $ units across years.
  - *Evidence:* "Weight-% only — dollar values deliberately never shown (EDGAR changed $ units across years)."
- app/analysis.py is deterministic and NO-LLM — weighted-vote synthesis of every engine above.
  - *Evidence:* "app/analysis.py — deterministic, NO-LLM weighted-vote synthesis of every engine above"
- app/validation.py is the only surviving earnings artifact — extracted from the former app/earnings.py after the watchlist UI was removed.
  - *Evidence:* "app/validation.py — slim `validate_symbol` helper extracted from the former `app/earnings.py` (the watchlist UI was removed 2026-09-06)."

## Concepts

- `module-details`
- `cache-layout`
- `design-rationale`
- `callers-and-dependencies`
- `risk-divergence-engine`
- `capex-cycle-gauge`
- `cross-source-dedupe`

## Entities

- `app/config.py`
- `app/market.py`
- `app/spot.py`
- `app/indicators.py`
- `app/regime.py`
- `app/risk.py`
- `app/bottleneck.py`
- `app/ai_sentiment.py`
- `app/thirteenf.py`
- `app/analysis.py`
- `app/news.py`
- `app/seed_data.py`
- `app/store.py`
- `app/validation.py`
- `app/portfolio.py`
- `app/scheduler.py`
- `app/service.py`
- `app/lifecycle.py`
- `app/lockfile.py`
- `app/launcher_icon.py`
- `app/changelog.py`
- `app/api.py`
- `app/run.py`
