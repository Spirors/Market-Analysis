# Commodities spot pricing: FRED + Minted Metal, not Yahoo quotes (undated)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Commodities spot pricing: FRED + Minted Metal, not Yahoo quotes

Yahoo's `fast_info` is broken in current `yfinance` versions, so real
cash-market spot for the Commodities card comes from FRED public CSV
(energy) and Minted Metal public JSON (precious metals) instead, mapped
back onto the matching Yahoo futures ticker so the renderer doesn't need to
know the source family.

