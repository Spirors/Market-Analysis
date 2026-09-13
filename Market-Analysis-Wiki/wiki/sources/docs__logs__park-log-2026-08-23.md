---
type: source
title: "Park Log — Resolving the Parked Review Items"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/logs/park-log-2026-08-23.md"
original_sha256: "731c3b218627528eb10e38c5f770bebff29fd3ac85bb4554639db4e938490493"
stored_path: ".raw/captured/731c3b218627528eb10e38c5f770bebff29fd3ac85bb4554639db4e938490493.md"
source_kind: "park-log"
tags:
  - source
  - park-log
---

# Park Log — Resolving the Parked Review Items

Resolves 9 items parked from the code review for user judgment. Key decisions: reject compound event deletes with 400, add Host-header allowlist middleware for DNS rebinding protection, remove the dead Stooq data fallback entirely, treat missing AI gauge cohort data as 'unknown' instead of fabricated neutral, drop SOXX from breadth to fix semiconductor double-count, add 3-day regime report expiry, remove the division_score metric, split fragility flags by optimism/distress side, and add cross-process lockfile for refresh overlap.

## Citation

- **Original:** `inbox/docs/logs/park-log-2026-08-23.md`
  - SHA-256: `731c3b218627528eb10e38c5f770bebff29fd3ac85bb4554639db4e938490493`
- **Captured:** `.raw/captured/731c3b218627528eb10e38c5f770bebff29fd3ac85bb4554639db4e938490493.md`

## Key claims

- The Stooq data fallback is entirely dead — every code returns error/JavaScript browser-verification pages.
  - *Evidence:* "every code — including certainly-valid ones like spy.us — returns an error/JavaScript browser-verification page from both stooq.com and stooq.pl."
- Fragility flags now carry a side tag ('optimism' or 'distress'); the consensus-optimism gate counts optimism-side only.
  - *Evidence:* "every flag carries side: 'optimism' | 'distress'; the gate counts optimism-side only."
- Regime reports expire after 3 days and are served flagged stale rather than hidden.
  - *Evidence:* "3-day max age (chosen over the suggested 7 — flags after just two missed daily runs)."
- Cross-process refresh overlap is blocked by a non-blocking O_CREAT|O_EXCL lockfile.
  - *Evidence:* "cross-process lockfile only; no WAL. For a single-user local app with tiny DB writes, WAL's concurrency gains are marginal."

## Concepts

- `host-allowlist`
- `stooq-removal`
- `fragility-side-tags`
- `regime-staleness`
- `cross-process-lock`

## Entities

- `api.py`
- `market.py`
- `risk.py`
- `regime.py`
- `lockfile.py`
