---
type: source
title: "validate_symbol must distinguish yfinance unavailable from no profile"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/validate-symbol-must-distinguish-yfinance-unavailable-from-no-profile-2026-09-06.md"
original_sha256: "07546bd9b00a6d2f3c15f2d1f62760db68491c712f4da58b5003cf1c77f23f9b"
stored_path: ".raw/captured/07546bd9b00a6d2f3c15f2d1f62760db68491c712f4da58b5003cf1c77f23f9b.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# validate_symbol must distinguish yfinance unavailable from no profile

validate_symbol must distinguish network errors (yfinance unavailable) from genuinely-invalid symbols in the reason field so the frontend can show a meaningful error. A retry-with-1s-backoff and 60s TTL lru_cache were added for transient network errors.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/validate-symbol-must-distinguish-yfinance-unavailable-from-no-profile-2026-09-06.md`
  - SHA-256: `07546bd9b00a6d2f3c15f2d1f62760db68491c712f4da58b5003cf1c77f23f9b`
- **Captured:** `.raw/captured/07546bd9b00a6d2f3c15f2d1f62760db68491c712f4da58b5003cf1c77f23f9b.md`

## Key claims

- _yf_info now returns (dict, error_str) so callers can branch on error_str — network errors are distinguishable from empty results.
- Retry-with-1s-backoff and 60s TTL lru_cache absorb yfinance rate-limit bursts across quick successive validations.

## Concepts

- `validate-symbol`
- `yfinance-errors`
- `retry-pattern`

## Entities

- `_yf_info`
- `_yf_info_with_retry`
- `a2c793a`
