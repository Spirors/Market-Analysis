# 2026-09-08 — Phase 2 #7 closed: scheduler + VBS launcher docs audit

Full text of the entry from `project_rules/SESSION_LOG.md`.

---

## 2026-09-08 — Phase 2 #7 closed: scheduler + VBS launcher docs audit

**Problem.** Phase 2 #7 (roadmap item, opened in the 2026-09-05
docs-split commit) asked: "Revisit whether the current 3-scheduled-task
Windows Task Scheduler setup and the VBS-wrapper launch pattern are
documented clearly enough that 'stuck launch' incidents can't recur
through a different code path than the one fixed in Phase 0."

**Audit findings.** Two launch paths share the VBS-wrapper pattern
(`wscript.exe <vbs>`, `WindowStyle=0`, `False` = do-not-wait):

1. Desktop shortcut → `launch.vbs` → `python run.py --open-browser`.
2. Scheduled tasks (×3) → `scheduler.vbs` → `python run.py
   <refresh|news-refresh|commit-events> --logfile-prefix ...`.

Plus a third, runtime-only layer: `app/lifecycle.py`'s auto-reap
watchdog (default 0 = disabled). Opt-in via `--auto-reap <s>` or
`$env:MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S=<s>`.

| Surface | Documented before | Gap |
|---|---|---|
| 3 task names + triggers + args | `app/scheduler.py` docstring + `ARCHITECTURE_DETAILS.md:85-91` | Not in `RUNBOOK.md` |
| VBS wrapper — why wscript + VBS not pythonw | `DECISIONS.md` "Hidden launchers" | None — clear |
| `scheduler.vbs` regression tests | 6 tests in `tests/test_scheduler.py` | None |
| `launch.vbs` regression tests | **0 tests** | Regressions slip through |
| Recovery — "stuck scheduled refresh" | Code comments only | Not in `RUNBOOK.md` as a procedure |
| `--auto-reap` vs `EXECUTION_TIME_LIMIT` | Implicit | Two layers look like one overlapping solution |
| Anti-patterns — wrong launch paths | Implicit | Not enumerated |

**Changes.**

- `project_rules/RUNBOOK.md`:
  - New "Scheduled tasks (3-task setup)" section: task table
    (`MarketAnalysis-DailyRefresh` 09:00, `MarketAnalysis-NewsRefresh`
    every 4 h, `MarketAnalysis-EventsCommit` 17:00), InteractiveToken
    logged-off limitation, `EXECUTION_TIME_LIMIT = "PT4H"` rationale,
    4-step recovery procedure for a stuck scheduled refresh.
  - New "Anti-patterns — launch paths that bypass the runtime
    backstop" section: 4 wrong patterns (notebook/ISE without
    `--auto-reap`, `Start-Process` / `nohup` / `&` / `Invoke-Expression`,
    `pythonw.exe`) and 3 right patterns (desktop `.lnk`, agent terminal
    with `--auto-reap 60`, scheduled tasks), plus the explicit warning
    that `--auto-reap <n>` on a scheduled refresh would kill it mid-run
    because `scheduler.vbs` returns `False` = do-not-wait.

- `tests/test_scheduler.py`:
  - 4 new `launch.vbs` tests mirroring the existing `scheduler.vbs`
    shape: file exists, `shell.Run` + `, 0, False` (hidden +
    non-blocking), targets `python run.py --open-browser` (no
    `pythonw`), and sets `CurrentDirectory` via
    `GetParentFolderName(WScript.ScriptFullName)`.

- `project_rules/DECISIONS.md`: new dated pointer entry "Scheduled
  tasks + VBS launcher — incident surface + anti-patterns
  (2026-09-08)" linking to the new archive file.

- `project_rules/archive/decisions/scheduled-tasks-vbs-launcher-incident-surface-anti-patterns-2026-09-08.md`:
  new archive file with the full audit (findings table, why a
  separate decision entry rather than folding into "Hidden launchers",
  lessons for future docs audits).

- `project_rules/HANDOFF.md`: Phase 2 #7 closed entry added to the
  `Last updated` blurb; re-prioritized to next-action slot 2.

- `data/logs/summary-2026-09-08.md`: `app.changelog.log_change("docs",
  "...")` called.

**Verification.**

- `python -m pytest tests/test_scheduler.py -q`: **24 passed in 0.45s**
  (20 pre-existing + 4 new `launch.vbs` tests). All four new tests
  pass first-try against the unmodified `launch.vbs`.

**Notes for the next session.**

- `RUNBOOK.md` now distinguishes the *python-side* runtime backstop
  (`--auto-reap`, in `app/lifecycle.py`) from the *schtasks-side*
  hard kill (`EXECUTION_TIME_LIMIT = "PT4H"`, in `scheduler.py:71`).
  They serve overlapping purposes at different layers; the runbook
  explicitly warns against applying `--auto-reap <n>` to a scheduled
  refresh (it would self-kill within `n` seconds of `wscript.exe`
  exiting because of `False` = do-not-wait in `scheduler.vbs:40`).
- If a future task adds a *fourth* hidden launcher (e.g. for a
  notebook-friendly background refresh), the anti-patterns section
  in `RUNBOOK.md` is the place to cross-link. The pattern is: VBS
  wrapper + `shell.Run "python ...", 0, False` + the python process
  inherits the parent's cmdline through `WScript.Arguments`.
- `launch.vbs` and `scheduler.vbs` now have matching test coverage
  in `tests/test_scheduler.py`. If a future refactor adds a third VBS
  launcher, mirror the same four-test shape so the three cannot drift
  apart unnoticed.
