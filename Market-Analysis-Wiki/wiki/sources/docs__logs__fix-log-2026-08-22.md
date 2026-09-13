---
type: source
title: "Fix Log — What Happened and What's Left"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/logs/fix-log-2026-08-22.md"
original_sha256: "8535fa2e4eee36fa019b7a89d1636ab5502a3badc9435595335afd6bc710055d"
stored_path: ".raw/captured/8535fa2e4eee36fa019b7a89d1636ab5502a3badc9435595335afd6bc710055d.md"
source_kind: "fix-log"
tags:
  - source
  - fix-log
---

# Fix Log — What Happened and What's Left

Documents 17 commits fixing confirmed errors from the initial code review. Key fixes include: the dead valuation stretch signal, broken median calculation, RED gate requiring impossible signal counts, failed downloads cached as real data, EDGAR outages wiping 13F data, news fetch timeouts, XSS via javascript: links, and stale data overwriting newer data after refreshes.

## Citation

- **Original:** `inbox/docs/logs/fix-log-2026-08-22.md`
  - SHA-256: `8535fa2e4eee36fa019b7a89d1636ab5502a3badc9435595335afd6bc710055d`
- **Captured:** `.raw/captured/8535fa2e4eee36fa019b7a89d1636ab5502a3badc9435595335afd6bc710055d.md`

## Key claims

- The valuation stretch signal could never fire because it compared a list's median against its own top quartile.
  - *Evidence:* "The 'valuation stretch' signal could never fire. It compared a list's median against its own top-quartile — mathematically almost impossible."
- Failed Yahoo downloads were cached as real data for 24 hours.
  - *Evidence:* "Failed downloads were cached as if real. If Yahoo hiccuped, empty results were stored and served for 24 hours."
- RED alert could never trigger when only a subset of signals had data.
  - *Evidence:* "RED alert could never trigger on bad-data days. The RED rules demanded '5 bullish signals' even when only 3 signals had data."
- javascript: links from news feeds could execute stored XSS.
  - *Evidence:* "javascript: links from news feeds could execute. Link text was escaped, but the link address wasn't checked — a malicious feed headline could run script when clicked."

## Concepts

- `bug-fixes`
- `data-integrity`
- `security`
- `risk-engine`

## Entities

- `risk.py`
- `market.py`
- `api.py`
- `bottleneck.py`
