---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-09-14
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-09-14T15:45:00Z - Forward-PE cooldown bug fixed; test suite repairs
committed; session closed.

## Key Recent Facts

- The project is a local-first FastAPI + vanilla-JS webapp for macro-trend
  market analysis. Free, no-key data sources (yfinance + English-edition RSS);
  runs locally on Windows. Vault managed by claude-obsidian; the product clone
  lives at C:\Users\Spirors\AppData\Local\Temp\opencode\claude-obsidian
  (TEMPORARY location - temp dirs are cleaned by Windows; move it somewhere
  durable before the next vault transaction). WSL writes go through
  `wsl -d Ubuntu-22.04`; the vault's .claude-obsidian.json is unreadable by
  the WSL identity (root-owned ACL), so always pass explicit --vault.
- 95 live source pages; 47 durable decisions under
  `### decision (47)` in [[wiki/index.md]].

## Recent Changes

- fix(ai-valuation) 1ba5288 - "Fwd PE data in Breadth - AI proxies not
  there sometime even when data is cached (refresh might be causing this
  issue)". Root cause: compute_indicators baked forward_pe into the
  payload at compute time, but on cold start the PE cache
  (data/ai_valuation.json) did not exist yet (the first serve-time AI-gauge
  recompute writes it ~20 s later); the 30-min indicators cooldown then
  re-served the PE-less payload on every Refresh click. Fix: extracted
  indicators.wire_forward_pe(breadth_ai) - idempotent merge from the
  on-disk cache that also drops PEs the cache no longer backs - called from
  all three paths (compute, cooldown-reuse in refresh_market, every serve
  in _enrich after the recompute). Verified live: 62/71 tickers carry
  forward_pe (9 ETF-type yfinance 404s legitimately null, shown as em dash);
  AI gauge valuation cell repopulated (median 23.6x < 30x).
- test(suite) 47e5a7f - repaired 3 pre-existing failures (clean-tree
  verified at ac18ca0): 2 rotted hardcoded fetched_at timestamps in
  test_ai_valuation.py (aged past the 12h TTL); missing
  fetch_beneficiary_pe stub in test_recompute_ai_sentiment_filters_ai_only
  (real ~62-ticker yfinance loop blew the 5 s timing tolerance).
- Backend full suite green; frontend breadth-ai-valuation.spec.mjs 7/7.
- Changelog entry: data/logs/summary-2026-09-14.md 15:07:39 fix.

## Active Threads

- None open. Next session may want to: relocate the claude-obsidian product
  clone out of Temp; address the 9 ETF-type tickers that have no forward PE
  (unknown-PE cohort members - verify the hover reads acceptably).
