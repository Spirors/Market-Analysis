---
type: source
title: "Improvements Log — What Happened and What It Means"
status: imported
imported_at: 2026-09-13
original_path: "inbox/docs/logs/improvements-log-2026-08-22.md"
original_sha256: "a6018c5df9f58aa18f3a4783072e1343630fab4e53550f02a64fd33a42153d10"
stored_path: ".raw/captured/a6018c5df9f58aa18f3a4783072e1343630fab4e53550f02a64fd33a42153d10.md"
source_kind: "improvements-log"
tags:
  - source
  - improvements-log
---

# Improvements Log — What Happened and What It Means

Documents 16 commits implementing 8 approved improvements from the code review. Highlights include extracting math into a shared indicators library, centralizing config, bulk-fetching bottleneck tickers, adding per-card coverage badges and timestamps, safer scheduled tasks, frontend module split, and 51 new regression tests. Tests went from 9 to 61.

## Citation

- **Original:** `inbox/docs/logs/improvements-log-2026-08-22.md`
  - SHA-256: `a6018c5df9f58aa18f3a4783072e1343630fab4e53550f02a64fd33a42153d10`
- **Captured:** `.raw/captured/a6018c5df9f58aa18f3a4783072e1343630fab4e53550f02a64fd33a42153d10.md`

## Key claims

- The same calculations were hand-copied in four different files; now there is one canonical home in app/indicators.py.
  - *Evidence:* "The same calculations (momentum, market breadth, VIX-vs-average) were hand-copied in four different files. They agreed today, but nothing stopped them from drifting apart tomorrow."
- Tests went from 9 to 61, all passing in about a second, no internet needed.
  - *Evidence:* "Result: 16 commits. Tests went from 9 to 61, all passing in about a second, no internet needed."
- The 1,366-line app.js monolith became 8 small modules under static/js/.
  - *Evidence:* "The 1,366-line app.js monolith became 8 small modules under static/js/."

## Concepts

- `refactor`
- `test-coverage`
- `config-centralization`
- `frontend-modules`

## Entities

- `indicators.py`
- `config.py`
- `app.js`
- `cards.js`
