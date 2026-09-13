---
type: source
title: "Next earnings date extraction — yfinance 1.6.0 returns datetime.date, not datetime.datetime"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/archive/decisions/next-earnings-date-extraction-yfinance-1-6-0-returns-datetime-date-not-datetime-datetime-2026-09-07.md"
original_sha256: "a5e2318fc71610c5ced05007e65d2fa3e8198dfb9bcc2f7eb859fc0b0ce0e61c"
stored_path: ".raw/captured/a5e2318fc71610c5ced05007e65d2fa3e8198dfb9bcc2f7eb859fc0b0ce0e61c.md"
source_kind: "decision"
tags:
  - source
  - decision
---

# Next earnings date extraction — yfinance 1.6.0 returns datetime.date, not datetime.datetime

The next_earnings column rendered as '-' because _extract_next_earnings checked isinstance(ed, datetime) which matches datetime.datetime but not datetime.date. yfinance 1.6.0 returns datetime.date. Fix: check isinstance(ed, date) which covers both via subclassing.

## Citation

- **Original:** `inbox/project_rules/archive/decisions/next-earnings-date-extraction-yfinance-1-6-0-returns-datetime-date-not-datetime-datetime-2026-09-07.md`
  - SHA-256: `a5e2318fc71610c5ced05007e65d2fa3e8198dfb9bcc2f7eb859fc0b0ce0e61c`
- **Captured:** `.raw/captured/a5e2318fc71610c5ced05007e65d2fa3e8198dfb9bcc2f7eb859fc0b0ce0e61c.md`

## Key claims

- Check the base class (datetime.date) not the subclass (datetime.datetime) when extracting yfinance date fields, for forward-compatibility.
- Use .isoformat()[:10] to handle both date shapes and strip any time portion.

## Concepts

- `yfinance-compat`
- `earnings-date`
- `type-checking`

## Entities

- `_extract_next_earnings`
- `datetime.date`
- `yfinance 1.6.0`
