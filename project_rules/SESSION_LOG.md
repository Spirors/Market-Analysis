# Session Log

Append-only. Newest entry at the bottom. This file is git-tracked -- unlike
`data/logs/summary-YYYY-MM-DD.md`, which is gitignored and local-only per
`AGENTS.md`. Use this file for anything that needs to survive across
machines or a fresh checkout; keep using the existing `data/logs/` changelog
for its original local-daily-changelog purpose.

> Hybrid layout: the **latest entry is in full** (so the session-start
> read per AGENTS.md is one click deep), **older entries are pointers**
> with full text in `archive/sessions/<slug>.md` (one file per session).
> Once this file exceeds `{{SESSION_LOG_ROTATION_ENTRIES}}` entries
> (currently 10 — the skill default; the prior 5-entry override was
> reverted in commit `38bf801` because the retrofit to hybrid layout
> shrunk each pointer to ~6 lines, making the more aggressive rotation
> unnecessary), the oldest pointer is dropped — the archive file is
> the source of truth.

---

## 2026-09-08 — Phase 2 #7 closed: scheduler + VBS launcher docs audit

**Summary:** Docs audit closed. RUNBOOK.md gains a "Scheduled tasks
(3-task setup)" section (task table + InteractiveToken logged-off
limitation + 4-step "stuck scheduled refresh" recovery procedure) and
an "Anti-patterns — launch paths that bypass the runtime backstop"
section enumerating wrong launch paths (notebook without
`--auto-reap`, `Start-Process` / `nohup` / `pythonw`) and the
explicit warning that `--auto-reap <n>` on a scheduled refresh would
kill it mid-run because `scheduler.vbs` returns `False` = do-not-wait.
`tests/test_scheduler.py` gains 4 `launch.vbs` tests mirroring the
existing `scheduler.vbs` coverage (file exists, `shell.Run` + `, 0,
False`, no `pythonw`, sets `CurrentDirectory` via
`GetParentFolderName(WScript.ScriptFullName)`). New DECISIONS.md
pointer + archive file
`archive/decisions/scheduled-tasks-vbs-launcher-incident-surface-anti-patterns-2026-09-08.md`.

**Archive:** Full text in
`archive/sessions/2026-09-08-phase-2-7-scheduler-vbs-launcher-docs-audit.md`.

---

## 2026-09-08 — feat(bottleneck): up/down reorder + rename pencil

**Summary:** Bottleneck section gains interactive controls mirroring the Portfolio section's move/rename pattern: per-category ↑ / ↓ chevrons + ✎ rename pencil. Backend persistence in `data/bottleneck_prefs.json`; canonical `BOTTLENECK_CATEGORIES` constant is never mutated. 2 new API endpoints, 18 backend tests + 13 Playwright tests.

**Archive:** Full text in `archive/sessions/2026-09-08-feat-bottleneck-up-down-reorder-rename-pencil.md`.

---

## 2026-09-08 — Test isolation: autouse `tests/conftest.py` redirects every user-data path

**Problem.** Test isolation was a per-test responsibility. 18 of 23
test files had no isolation setup, and the module-level path
constants (`PORTFOLIOS_PATH = config.DATA_DIR / "portfolios.json"`
at `app/portfolio.py:95`, etc.) are evaluated at import time — so
patching `config.DATA_DIR` alone does NOT update the bound name. A
test that forgot to patch the right layer would silently write to
the real `data/portfolios.json`: no exception, no warning, the test
passes, the user loses their portfolios.

**Decision.** Add a new Core rule "Test isolation" to
`.opencode/skills/project-rules/SKILL.md` and enforce it with an
autouse pytest fixture in a new `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def _isolate_data_files(monkeypatch, tmp_path):
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

pytest applies autouse fixtures before per-test fixtures, so tests
that already declare `tmp_portfolios` / `tmp_store` / etc. override the
autouse's values — the autouse is the safety net that catches tests
that forget to set up isolation.

### Files

- `tests/conftest.py` (new — autouse `_isolate_data_files` fixture)
- `.opencode/skills/project-rules/SKILL.md` (new Core rule "Test isolation")
- `project_rules/TESTING.md` (new "Test isolation — never touch the
  user's data" section explaining the pattern + how to add a new path)
- `AGENTS.md` (added "Test isolation" to the Hard rules pointers list)
- `project_rules/DECISIONS.md` (new pointer entry)
- `project_rules/archive/decisions/test-isolation-autouse-conftest-py-redirects-every-user-data-path-2026-09-08.md`
  (new — full rationale, mistakes-to-avoid, verification)

### Verification

- `python -m pytest tests/test_portfolio.py tests/test_bottleneck_prefs.py tests/test_api_contract.py`:
  **101 passed** in ~62 s.
- `python -m pytest tests/test_validation.py tests/test_changelog.py tests/test_lifecycle.py tests/test_store.py tests/test_portfolio_cache_sync.py tests/test_dashboard_equivalence.py tests/test_lockfile.py`:
  exit=0.
- `python -m pytest tests/ -k "not thirteenf and not service_coverage"`:
  exit=0 (full suite minus the two known-skip files per `AGENTS.md`).
- Pre-existing per-test fixtures (`tmp_portfolios` in
  `tests/test_portfolio.py:9-12`, `tmp_store` in
  `tests/test_api_contract.py:29-35`) override the autouse without
  conflict; their explicit values take precedence as expected.

### Notes for the next session

- Module-level path constants are bound at import time — the autouse
  must patch each importing module's bound name separately, NOT just
  `config.DATA_DIR`. This is the failure mode that motivated the rule.
- Read-only assets (`static/`, `archive/`) are intentionally NOT
  redirected — only state a test could mutate.
- When adding a new user-data path, add the monkeypatch line to
  `_isolate_data_files` in the same change. The fixture is the
  contract; an unpatched new path is a silent regression.

---

## 2026-09-07 — Audit follow-up closure: P3/P4/P5/P6 (3 commits)

**Summary:** Closed the remaining audit-2026-09-07 follow-ups. P0 (perf) and the

**Archive:** Full text in `archive/sessions/2026-09-07-audit-follow-up-closure-p3-p4-p5-p6-3-commits.md`.

---

## 2026-09-07 — Front-end nuclear renderBody fix (audit-2026-09-07 P0 follow-up)

**Summary:** User reported that add/delete holding felt fast but add/delete/rename

**Archive:** Full text in `archive/sessions/2026-09-07-front-end-nuclear-renderbody-fix-audit-2026-09-07-p0-follow-up.md`.

---

## 2026-09-07 — Mass expand/collapse fix + portfolio move up/down

**Summary:** Two changes to the Portfolio card: (1) fix `.pf-toggle-all` label stuck on "▼ all" by adding a `renderHeaderControls()` call after `renderBody()`, (2) add per-row ↑ / ↓ chevrons that swap with the neighbor and POST to `/api/portfolios/reorder`. 431 backend tests pass (+10 new reorder tests); Playwright 73 pass / 20 fail (pre-existing baseline). 2 commits land the work.

**Archive:** Full text in `archive/sessions/2026-09-07-mass-expand-collapse-fix-and-portfolio-move-up-down.md`.

---

## 2026-09-08 — Holdings row reorder + "↺ Default order" restored (silent-disabled-at-runtime bug)

**Summary:** User reported "I don't see it in the front-end" for the
holdings ▲/▼ row reorder and the "↺ Default order" button. Root cause:
`static/js/tickerTable.js:166` had `reorderEnabled = section === "portfolio"`
but every per-portfolio instance is created with
`section: "portfolio.<pid>"` (`portfolio.js:559`), so the check was
always FALSE. Both buttons were silently absent from every portfolio
— the help text in `cards.js:793` advertised the feature, the renderer
hid it. Same anti-pattern class as the 2026-09-05 shared-component
persistence decision: silent collapse of per-entity state into a
single hardcoded key. Fix: widen `reorderEnabled` to mirror
`_assertValidSection`, add boundary-disable on row buttons (matches
portfolio-card / bottleneck / layout-card pattern), give the action
column an explicit 90px width (`table-layout: fixed` + 3 buttons
overflowed silently), and add
`tests/frontend/portfolio-holdings-reorder.spec.mjs` (7 tests). Net
Playwright delta vs. baseline: +7 passing, -7 failing. Python: 424
passed, 0 failed.

**Archive:** Full text in `archive/sessions/2026-09-08-holdings-row-reorder-and-default-order-restored-silent-disabled-at-runtime-bug.md`.

---

## 2026-09-08 — Captured: Start-Process + PID-0 reap mistake (operational discipline)

**Summary:** During the same session I bypassed
`RUNBOOK.md` §"Anti-patterns" by launching the static test server with
`Start-Process` (because Playwright's `webServer` block hadn't
auto-started in time). The reap then failed with "Access is denied"
22× because `Get-NetTCPConnection` `TimeWait` entries report
`OwningProcess = 0` (System Idle Process) and PID 0 can't be stopped
by a regular user. Captured both as a decision entry so a future
session that hits the same time-pressure moment reads "the
runbook is not 'sometimes wrong'" instead of repeating the bypass.
Rule of thumb: (a) debug the harness when its auto-start fails, don't
bypass it — for static servers, run server + test in one foreground
bash call with a captured PID; (b) reap filters must drop PID 0
(`Where-Object OwningProcess -gt 0`).

**Archive:** Full text in `archive/sessions/2026-09-08-captured-start-process-and-pid-0-reap-mistake-operational-discipline.md`.


