---
type: source
title: "Earnings watchlist section removed"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/earnings-watchlist-section-removed-2026-09-06.md"
original_sha256: "cf24f1dc18facec2497c05178f478309f804e909807186cc0e6c54072c3ff742"
stored_path: ".raw/captured/cf24f1dc18facec2497c05178f478309f804e909807186cc0e6c54072c3ff742.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Earnings watchlist section removed

The entire Earnings watchlist section was removed except for validate_symbol (still used by portfolio add). If a section's only reason for existing is the data it fetches, removing the section means removing the data fetch too — don't keep a thin backend wrapper 'just in case'.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/earnings-watchlist-section-removed-2026-09-06.md`
  - SHA-256: `cf24f1dc18facec2497c05178f478309f804e909807186cc0e6c54072c3ff742`
- **Captured:** `.raw/captured/cf24f1dc18facec2497c05178f478309f804e909807186cc0e6c54072c3ff742.md`

## Key claims

- Removing a dashboard section that only exists for its own fetched data means removing the data fetch too; don't keep a thin wrapper.
- validate_symbol was kept because portfolio.add_holding depends on it — it has a consumer outside the removed section.

## Concepts

- `module-removal`
- `earnings-watchlist`
- `validate-symbol`

## Entities

- `app/earnings.py`
- `app/validation.py`
- `RISK_SIGNAL_TOTAL`
