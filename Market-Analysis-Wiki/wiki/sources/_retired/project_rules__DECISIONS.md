---
type: source
title: "Decisions — Durable Decision Log"
status: retired
imported_at: 2026-09-13
retired_at: 2026-09-13
superseded_by: "wiki/index.md ### decision (47)"
original_path: "inbox/project_rules/DECISIONS.md"
original_sha256: "95c019d585cbb134811d373c4345c7495c452dcb941d462912c04c43ec2b8e6c"
stored_path: ".raw/captured/95c019d585cbb134811d373c4345c7495c452dcb941d462912c04c43ec2b8e6c.md"
source_kind: "decisions"
tags:
  - source
  - decisions
  - retired
---

# Decisions — Durable Decision Log

> [!deprecated] This umbrella page was retired 2026-09-13. The 47 durable
> decisions are now individual source pages under
> [[wiki/sources/project_rules__archive__decisions__|wiki/sources/]],
> listed in [[wiki/index.md]] under `### decision (47)`. The captured
> source content is preserved below for historical reference.

Pointer index of durable decisions, one sentence each, with archive/decisions/<slug>.md for verbose detail. Decisions accumulate and are never deleted — superseded entries are marked as such. Covers data integrity (yfinance-only, commodities spot pricing), launch patterns (wscript.exe + VBS), shared-component persistence rules, lifecycle fixes, news heuristic expansions, per-section cooldowns, and the AI Valuation feature.

## Citation

- **Original:** `inbox/project_rules/DECISIONS.md`
  - SHA-256: `95c019d585cbb134811d373c4345c7495c452dcb941d462912c04c43ec2b8e6c`
- **Captured:** `.raw/captured/95c019d585cbb134811d373c4345c7495c452dcb941d462912c04c43ec2b8e6c.md`

## Key claims

- Market data uses yfinance only; the Stooq CSV fallback was removed because Stooq now serves stale/broken data.
  - *Evidence:* "The former Stooq CSV fallback was removed because Stooq now serves a"
- Frozen reference files (`ai_*.html`) are never modified; they serve as archived gauge designs.
  - *Evidence:* "The four `ai_*.html` files at repo root are frozen reference material"
- Per-portfolio scope must use composite keys (e.g. `pfSort.portfolio.<pid>`), not nested Maps, to prevent silent cross-entity state leakage.
  - *Evidence:* "Pre-fix `static/js/watchColors.js` used a single Map keyed by symbol"
- Module-level path constants are bound at import time; patching `config.DATA_DIR` alone does NOT update the bound name — the autouse fixture patches each module separately.
  - *Evidence:* "Module-level path constants are bound at import time — the autouse must patch each importing module's bound name separately"
- Cross-module JS imports must use identical URLs (both versioned or both unversioned) to avoid silent module duplication.
  - *Evidence:* "The JS spec creates a fresh module record per URL, so the version mismatch silently duplicated both modules"

## Concepts

- `data-integrity`
- `frozen-reference-files`
- `shared-component-persistence`
- `test-isolation`
- `module-import-versioning`
- `news-heuristic-expansion`
- `per-section-cooldowns`

## Entities

- `app/config.py`
- `app/lifecycle.py`
- `app/portfolio.py`
- `app/news.py`
- `app/store.py`
- `app/validation.py`
- `app/scheduler.py`
- `app/ai_sentiment.py`
- `app/ai_valuation.py`
- `static/js/tickerTable.js`
- `static/js/cards.js`
- `static/js/events.js`
- `data/events.json`
- `data/portfolios.json`
- `data/bottleneck_prefs.json`
- `tests/conftest.py`
