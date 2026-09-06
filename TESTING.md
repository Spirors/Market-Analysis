# Testing

Read this **on demand** when writing or auditing tests — not part of
mandatory session-start reading (see `AGENTS.md`).

## Running tests

```
python -m pytest
```

- `tests/` — pytest suites (`test_bottleneck.py`, `test_ai_sentiment.py`,
  and the others listed per-module in `ARCHITECTURE.md`'s backend
  quick-reference table).
- `tests/frontend/` — Playwright frontend tests
  (`playwright.config.mjs`, `*.spec.mjs`), run against
  `http://127.0.0.1:8000` with no anti-bot middleware — no stealth
  configuration needed for these (see `docs/RUNBOOK.md` for when stealth
  guidance *does* apply).

## Known test gaps

- `app/thirteenf.py` has no isolated tests (network-heavy; tested
  indirectly via API contract).
- `app/scheduler.py` has no tests (Windows-only `schtasks.exe` wrapper;
  would need a mock).
- `app/run.py` CLI flags are not exercised by tests.
- `app/seed_data.py` is pure data (hand-tagged events) — no tests needed.
- (Add here) per-section regression tests for `tickerTable.js` consumers
  (Earnings, Portfolio) — called for in `docs/DECISIONS.md`'s open item on
  the `914f406` shared-component refactor, to catch cross-section
  persistence regressions before they ship.
