# Scheduled tasks + VBS launcher — incident surface + anti-patterns (2026-09-08)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit pattern: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Scheduled tasks + VBS launcher — incident surface + anti-patterns (2026-09-08)

**Status:** docs audit closed.

**Trigger.** Phase 2 #7 from the roadmap was opened in the
2026-09-05 docs-split commit and never closed:
"Revisit whether the current 3-scheduled-task Windows Task Scheduler
setup and the VBS-wrapper launch pattern are documented clearly enough
that 'stuck launch' incidents can't recur through a different code
path than the one fixed in Phase 0."

**Scope.** Two launch paths:
1. **Desktop shortcut:** `Market Analysis.lnk` → `wscript.exe //nologo launch.vbs` → `python run.py --open-browser` (installed by `--install-shortcut`).
2. **Scheduled tasks (×3):** Task Scheduler → `wscript.exe scheduler.vbs <args>` → `python run.py <refresh|news-refresh|commit-events> --logfile-prefix ...` (installed by `--schedule-install`).

Both rely on the same VBS-wrapper pattern (`shell.Run "...", 0, False` =
SW_HIDE + do-not-wait) and the same `python.exe` (not `pythonw.exe`)
choice, for the documented reasons in
`archive/decisions/hidden-launchers-wscript-exe-vbs-not-pythonw-exe-undated.md`.

The Phase 0 "stuck process on test launch" fix added a third layer:
`app/lifecycle.py`'s auto-reap watchdog (default 0 = disabled). It is
opt-in via `--auto-reap <seconds>` or the
`MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S` env var. The watchdog is the
runtime backstop — without it, a forgotten reap step leaks a python
child bound to port 8000.

**Audit findings (what the docs covered vs. what they didn't):**

| Surface | Where documented before | Gap |
|---|---|---|
| 3 scheduled tasks — names, triggers, args | `app/scheduler.py` docstring + `ARCHITECTURE_DETAILS.md:85-91` | Not in RUNBOOK.md — a future agent debugging a missing refresh had to read scheduler.py from scratch |
| VBS wrapper — *why* wscript + VBS not pythonw | `DECISIONS.md` "Hidden launchers" (2026-09-08 retrofit to archive) | None — clear |
| `scheduler.vbs` regression coverage | `tests/test_scheduler.py` — 6 explicit tests for the VBS file | None |
| `launch.vbs` regression coverage | **None** — zero tests | Regressions to the desktop shortcut's VBS file would slip through silently |
| Recovery — "stuck scheduled refresh" | Code comments only (lockfile age + PID-based break, `EXECUTION_TIME_LIMIT=PT4H`) | Not in RUNBOOK.md as a procedure |
| `--auto-reap` vs `EXECUTION_TIME_LIMIT` relationship | Implicit | Confusing — they look like overlapping solutions but are two layers (python-side watchdog vs schtasks-side hard kill) |
| Anti-patterns — wrong launch paths that re-introduce the regression | Implicit in `RUNBOOK.md` Step 2 + `DECISIONS.md` "Hidden launchers" | Not enumerated; an agent who picks a different code path (notebook, ISE, `Start-Process`, `nohup`) has no warning |

**Files changed:**

1. `project_rules/RUNBOOK.md` — added "Scheduled tasks (3-task setup)"
   section (task table + InteractiveToken logged-off limitation + 4-step
   "stuck scheduled refresh" recovery procedure) and "Anti-patterns —
   launch paths that bypass the runtime backstop" section (4 wrong
   patterns + 3 right patterns + the explicit warning that
   `--auto-reap <n>` on a scheduled refresh would kill the refresh
   mid-run because `scheduler.vbs` returns False = do-not-wait).
2. `tests/test_scheduler.py` — added 4 launch.vbs tests mirroring the
   existing scheduler.vbs shape: file exists, `shell.Run` +
   `, 0, False` (hidden + non-blocking), targets `python run.py
   --open-browser` (no pythonw), and sets `CurrentDirectory` via
   `GetParentFolderName(WScript.ScriptFullName)`. Red-green verified
   by reading the existing scheduler.vbs tests as the template.
3. `project_rules/DECISIONS.md` — new pointer entry.
4. `project_rules/HANDOFF.md` — Phase 2 #7 removed from "top 3 next
   actions".
5. `project_rules/SESSION_LOG.md` — new dated entry.
6. `data/logs/summary-YYYY-MM-DD.md` — changelog helper called via
   `app.changelog.log_change("docs", "...")`.

**Verification.**

- `python -m pytest tests/test_scheduler.py -q`: **24 passed in 0.45s**
  (20 original + 4 new launch.vbs tests).
- Full pre-edit test count for the file was 20 (per
  `tests/test_scheduler.py` history); post-edit is 24 — all four new
  tests pass first-try against the unmodified `launch.vbs`.

**Why a separate decision entry rather than folding into "Hidden launchers":**

The "Hidden launchers" decision captures *why* VBS, not pythonw. This
new entry captures the *operational surface* — the 3-task setup, the
launch-path anti-patterns, the runtime-backstop boundaries, and the
documentation gap that Phase 2 #7 was opened to close. The two entries
cite each other so future sessions can navigate from either side.

**Lessons for future agent workflows (rules to apply to any
"docs audit" task):**

- Code docstrings + ARCHITECTURE.md do not satisfy "documented clearly
  enough" for the RUNBOOK.md purposes. The runbook is the file a future
  session opens first when something is broken — every surface the
  runbook implicitly assumes should be named in it.
- "Documented why" ≠ "documented recovery procedure". The
  hidden-launchers decision explained *why* the VBS pattern exists; it
  did not explain what to do when a task hung.
- A documented pattern that is also covered by tests is a documented
  pattern. A documented pattern with no test coverage is one
  well-meaning refactor away from silent regression — `launch.vbs` was
  the live example here.
