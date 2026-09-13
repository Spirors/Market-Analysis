# Test isolation: autouse `tests/conftest.py` redirects every user-data path

**Date:** 2026-09-08
**Status:** confirmed + shipped.
**Pointer:** see `project_rules/DECISIONS.md` "Test isolation: autouse
`tests/conftest.py` redirects every user-data path (2026-09-08)" for the
one-line summary.

## The problem

Before 2026-09-08, test isolation was a per-test responsibility. Tests
that mutated persisted state were expected to monkeypatch
`portfolio.PORTFOLIOS_PATH` (or the relevant module-level constant) to a
`tmp_path` location — and the existing tests mostly did. But the rule
wasn't documented as a hard rule, and there was no safety net:

- 18 of 23 test files had *no* isolation setup. Most never touched
  persisted state, so this was fine — but the moment a new test added a
  portfolio, an event, or a prefs write, it could silently corrupt
  `data/portfolios.json`.
- `tests/test_validation.py` has 1 portfolio reference (an import via
  `app.market`) and no explicit isolation. Not currently a corruption
  vector, but a future test in that file that called `create_portfolio`
  would write to the real file.
- The module-level constants are evaluated at import time
  (`PORTFOLIOS_PATH = config.DATA_DIR / "portfolios.json"` at
  `app/portfolio.py:95`). Patching `config.DATA_DIR` later does NOT
  update `PORTFOLIOS_PATH`. A test that patched the wrong layer would
  silently write to the real file — no exception, no warning, the test
  passes, the user loses their portfolios.

The cost of getting isolation wrong is total loss of the user's
`data/portfolios.json`. That's not a recoverable mistake (no Git
recovery unless the user committed their portfolios, which the project
does not do — see `app/portfolio.py` module docstring: "Persistence:
single file holding all portfolios"). A test bug that wrote garbage
portfolios would replace the user's real holdings with garbage and
they'd find out the next time they refreshed the dashboard.

## The decision

Add a new Core rule "Test isolation" to
`.opencode/skills/project-rules/SKILL.md` and enforce it with an
autouse fixture in a new `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def _isolate_data_files(monkeypatch, tmp_path):
    # User-data paths — the most critical first.
    monkeypatch.setattr(portfolio, "PORTFOLIOS_PATH", tmp_path / "portfolios.json")
    monkeypatch.setattr(bottleneck_prefs, "_PREFS_PATH", tmp_path / "bottleneck_prefs.json")
    monkeypatch.setattr(store, "SUPPRESSED_PATH", tmp_path / "suppressed_sources.json")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "REGIME_DIR", tmp_path / "regime")
    monkeypatch.setattr(config, "EVENTS_PATH", tmp_path / "events.json")
    monkeypatch.setattr(config, "ANALYSIS_DB_PATH", tmp_path / "analysis.db")
    monkeypatch.setattr(changelog, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(store, "_READY", False)
    monkeypatch.setattr(store, "_analysis_repo", None)
    yield
```

pytest applies autouse fixtures before per-test fixtures, so tests that
already declare `tmp_portfolios` / `tmp_store` / etc. override the
autouse's values — the autouse is the *floor* of isolation, not the
ceiling. A test that forgets to set up isolation still gets the
autouse's protection.

## What is and isn't redirected

**Redirected** (state a test could mutate):
- `app.portfolio.PORTFOLIOS_PATH` — the user's portfolios
- `app.bottleneck_prefs._PREFS_PATH` — the user's bottleneck reorder/rename prefs
- `app.store.SUPPRESSED_PATH` — news source blocklist
- `app.config.DATA_DIR` + `CACHE_DIR` + `REGIME_DIR` + `EVENTS_PATH` + `ANALYSIS_DB_PATH`
- `app.changelog.LOG_DIR` — daily changelog (gitignored)
- `app.store._READY` and `app.store._analysis_repo` singletons reset

**Not redirected** (read-only assets, or non-user data):
- `app.config.STATIC_DIR` — points at the `static/` tree, no user state
- `app.config.BASE_DIR` — repo root, used for STATIC_DIR
- Anything in `archive/` — frozen reference material

## Why a top-level autouse, not a per-test fixture

Per-test fixtures require every test to remember to declare them.
Forgetting is silent and catastrophic — see "The problem" above. An
autouse is impossible to forget: it applies to every test in the
repository by default. Per-test fixtures still work because pytest
applies autouse fixtures first, so an explicit `tmp_portfolios` in
`tests/test_portfolio.py` overrides the autouse's value with its own
(same `tmp_path`, but explicit — easier for a reader to see which
paths are touched).

## How to add a new user-data path

When you add a new `config.X = BASE_DIR / "data" / "..."` (or any
module-level constant pointing at user data), add a
`monkeypatch.setattr(<module>, "<CONST>", tmp_path / "...")` line to
`_isolate_data_files` in the same change. The fixture is the contract;
an unpatched new path is a silent regression waiting for the next test
run.

## Verification

- Existing `tests/test_portfolio.py` (96 portfolio refs) + new
  `tests/test_bottleneck_prefs.py` (15 refs) + `tests/test_api_contract.py`
  (8 refs) — 101 tests pass with the autouse active.
- Full suite (excluding `tests/test_thirteenf.py` network-heavy and
  `tests/test_service_coverage.py` long-running, both per `AGENTS.md`)
  — exit code 0.
- Pre-existing per-test fixtures (`tmp_portfolios` in
  `tests/test_portfolio.py:9-12`, `tmp_store` in
  `tests/test_api_contract.py:29-35`) override the autouse without
  conflict; their explicit values take precedence.

## Mistakes to avoid

- **Don't patch `config.DATA_DIR` and call it a day.** Module-level
  path constants like `PORTFOLIOS_PATH` are bound at import time. The
  autouse fixture patches the bound names on the importing module —
  not just `config.DATA_DIR`.
- **Don't redirect `STATIC_DIR` or `BASE_DIR`.** They're read-only
  assets, not user state. Redirecting them can break tests that
  resolve paths through them.
- **Don't forget to reset the `store` singletons.** `_READY` and
  `_analysis_repo` cache references to the original paths. Without
  the reset, the next `store._ensure_ready()` call still points at
  the real `data/events.json` and writes to it.
- **Don't drop per-test fixtures in favor of the autouse.** Tests
  that already declare `tmp_portfolios` / `tmp_store` are clearer to
  read — the autouse is the safety net, not a replacement for
  explicit isolation.
