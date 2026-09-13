# Testing

Read this **on demand** when writing or auditing tests — not part of
mandatory session-start reading (see `AGENTS.md`).

## Running tests

```
python -m pytest
```

- `tests/` — pytest suites (every file in the directory is collected; no
  `--ignore=` flags needed at the default invocation). See the
  backend-quick-reference table in `project_rules/ARCHITECTURE.md` for the
  per-module test mapping.
- `tests/frontend/` — Playwright frontend tests
  (`playwright.config.mjs`, `*.spec.mjs`), run against
  `http://127.0.0.1:8000` with no anti-bot middleware — no stealth
  configuration needed for these (see `project_rules/RUNBOOK.md` for when stealth
  guidance *does* apply).

## Test isolation — never touch the user's data

Every pytest run in this repo goes through an autouse fixture in
`tests/conftest.py` (`_isolate_data_files`) that monkeypatches every
module-level user-data path constant to a per-test `tmp_path` location:

- `app.portfolio.PORTFOLIOS_PATH` → `tmp_path/portfolios.json`
- `app.bottleneck_prefs._PREFS_PATH` → `tmp_path/bottleneck_prefs.json`
- `app.config.DATA_DIR` → `tmp_path` (covers cache, regime, events, analysis)
- `app.store.SUPPRESSED_PATH` → `tmp_path/suppressed_sources.json`
- `app.changelog.LOG_DIR` → `tmp_path/logs`
- `app.store._READY` / `app.store._analysis_repo` reset (singletons
  re-read the redirected paths on next call)

This means a test that forgets to set up its own isolation can never
corrupt the user's real `data/portfolios.json` (or any other persisted
state). Per-test fixtures that already redirect (`tmp_portfolios` in
`test_portfolio.py`, `tmp_store` in `test_api_contract.py`, etc.)
override the autouse — the autouse is the floor, not the ceiling.

**Why a top-level autouse instead of relying on every test to set up
isolation manually?** `tmp_path` constants are evaluated at module
import time (e.g. `PORTFOLIOS_PATH = config.DATA_DIR / "portfolios.json"`
in `app/portfolio.py:95`). Patching `config.DATA_DIR` alone does NOT
update the bound name. Forgetting to patch the bound name silently
writes to the real file — no exception, no warning, the test passes
and the user loses their portfolios on the next `git status`. The
autouse fixture makes that failure mode impossible.

**Adding a new user-data path?** Add a `monkeypatch.setattr(...)` line
to `_isolate_data_files` in the same change that introduces the path.
The rule lives in `.opencode/skills/project-rules/SKILL.md` §
"Test isolation".

Read-only assets (`static/index.html`, CSS, JS, `archive/*`) are not
redirected — only state a test could mutate.

## Coverage map

All app modules have direct test coverage (was an open ROADMAP Phase 2 #5
item, closed 2026-09-07):

| Module | Test file |
|---|---|
| `app/thirteenf.py` | `tests/test_thirteenf.py` (14 tests, mocked EDGAR) |
| `app/scheduler.py` | `tests/test_scheduler.py` (20 tests, mocked `schtasks` / `subprocess`) |
| `app/run.py` | `tests/test_run.py` (17 tests covering every CLI flag) |
| `app/service.py` | `tests/test_service_coverage.py` (23 tests, + `tests/test_api_contract.py`) |
| `app/validation.py` | `tests/test_validation.py` (19 tests covering the 4-scenario validate_symbol matrix + structural ordering) |
| `app/launcher_icon.py` | `tests/test_launcher_icon.py` (18 tests) |
| `app/lifecycle.py` | `tests/test_lifecycle.py` (13 tests) |

`app/seed_data.py` is pure data (hand-tagged events) — no tests needed.

## Frontend regression tests for shared components

The shared `tickerTable.js` factory is consumed by the Portfolio section
only (the Earnings watchlist was removed 2026-09-06). Per-portfolio
column state isolation — the regression class the original shared-
component refactor (commit `914f406`) was designed to prevent — is
covered by two tests in `tests/frontend/portfolio.spec.mjs`:

- `per-portfolio column visibility: hiding a column in Portfolio A does not
  affect Portfolio B` — verifies that the `pfVisible.portfolio.<pid>`
  localStorage keys + the `column_visibility` server-side keys stay
  scoped per-portfolio.
- `per-portfolio column order: reordering in Portfolio A does not affect
  Portfolio B` — same for `pfOrder.portfolio.<pid>` /
  `column_order.<pid>`.

If a future shared-component extraction adds a new section to
`static/js/tickerTable.js` (currently `VALID_SECTIONS = ["portfolio"]`),
add a paired regression test asserting per-section isolation across the
Sort / Visible / Order channels. See "Per-portfolio column state" in
`project_rules/DECISIONS.md` for the original rationale.
