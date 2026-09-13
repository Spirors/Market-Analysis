---
type: source
title: "Testing — Test Pointers and Known Gaps"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/TESTING.md"
original_sha256: "e12eeb177228ac3930844538c2d35fed8bac10a4f52f5e4ecc0aceb267209a7f"
stored_path: ".raw/captured/e12eeb177228ac3930844538c2d35fed8bac10a4f52f5e4ecc0aceb267209a7f.md"
source_kind: "testing"
tags:
  - source
  - testing
---

# Testing — Test Pointers and Known Gaps

Test suite documentation: run with `python -m pytest` for backend suites and `npx playwright test` for frontend. Explains the test isolation autouse fixture in tests/conftest.py that monkeypatches every module-level user-data path to tmp_path, preventing accidental corruption of user files. Provides a coverage map showing all app modules now have direct test coverage (Phase 2 item closed 2026-09-07). Notes frontend regression tests for shared tickerTable.js per-portfolio column state isolation.

## Citation

- **Original:** `inbox/project_rules/TESTING.md`
  - SHA-256: `e12eeb177228ac3930844538c2d35fed8bac10a4f52f5e4ecc0aceb267209a7f`
- **Captured:** `.raw/captured/e12eeb177228ac3930844538c2d35fed8bac10a4f52f5e4ecc0aceb267209a7f.md`

## Key claims

- All app modules have direct test coverage — the last open gap (thirteenf, scheduler, run.py CLI) was closed 2026-09-07.
  - *Evidence:* "All app modules have direct test coverage (was an open ROADMAP Phase 2 #5 item, closed 2026-09-07):"
- The autouse fixture in tests/conftest.py patches module-level path constants at import time, making silent user-data corruption impossible.
  - *Evidence:* "the autouse fixture makes that failure mode impossible."
- When adding a new user-data path, add the monkeypatch line to _isolate_data_files in the same change.
  - *Evidence:* "Adding a new user-data path? Add a `monkeypatch.setattr(...)` line to `_isolate_data_files` in the same change"
- Frontend regression tests cover per-portfolio column visibility and column order isolation across the Sort/Visible/Order channels.
  - *Evidence:* "per-portfolio column visibility: hiding a column in Portfolio A does not affect Portfolio B"
- app/seed_data.py is pure data (hand-tagged events) and needs no tests.
  - *Evidence:* "`app/seed_data.py` is pure data (hand-tagged events) — no tests needed."

## Concepts

- `test-isolation`
- `autouse-fixture`
- `coverage-map`
- `per-portfolio-column-state`
- `shared-component-regression`

## Entities

- `tests/conftest.py`
- `tests/test_thirteenf.py`
- `tests/test_scheduler.py`
- `tests/test_run.py`
- `tests/test_service_coverage.py`
- `tests/test_validation.py`
- `tests/test_launcher_icon.py`
- `tests/test_lifecycle.py`
- `tests/frontend/portfolio.spec.mjs`
- `app/seed_data.py`
- `static/js/tickerTable.js`
