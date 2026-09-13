---
type: source
title: "Phase 2 audit — earnings validate_symbol path diff"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/phase-2-audit-earnings-validate-symbol-path-diff-2026-09-06.md"
original_sha256: "7a6a82b30264fb32b3101a36ec52f007f5d06c23a9a2e9fc2fdeafeef165b7a7"
stored_path: ".raw/captured/7a6a82b30264fb32b3101a36ec52f007f5d06c23a9a2e9fc2fdeafeef165b7a7.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Phase 2 audit — earnings validate_symbol path diff

Earnings validation used yf.Ticker.info (per-symbol, rate-limited) while portfolio enrichment used yf.download (bulk, reliable). The fix makes _validate_uncached use market.get_history (bulk-download) as primary, with Ticker.info as secondary, eliminating the rate-limit false-negative.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/phase-2-audit-earnings-validate-symbol-path-diff-2026-09-06.md`
  - SHA-256: `7a6a82b30264fb32b3101a36ec52f007f5d06c23a9a2e9fc2fdeafeef165b7a7`
- **Captured:** `.raw/captured/7a6a82b30264fb32b3101a36ec52f007f5d06c23a9a2e9fc2fdeafeef165b7a7.md`

## Key claims

- validate_symbol was switched to use market.get_history (bulk-download) as primary, matching the reliable path portfolio enrichment already uses.
- A full yfinance outage (both Ticker.info and yf.download failing) is the only case that returns valid=False; single-surface rate-limit no longer causes false-negative.

## Concepts

- `validate-symbol`
- `yfinance-paths`
- `rate-limiting`

## Entities

- `app/validation.py`
- `market.get_history`
- `yf.Ticker.info`
