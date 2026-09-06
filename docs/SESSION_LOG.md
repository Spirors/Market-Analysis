# Session Log

Append-only. Newest entry at the bottom. This file is git-tracked — unlike
`data/logs/summary-YYYY-MM-DD.md`, which is gitignored and local-only per
`AGENTS.md`. Use this file for anything that needs to survive across
machines or a fresh checkout; keep using the existing `data/logs/` changelog
for its original local-daily-changelog purpose.

---

## 2026-09-05 — Bootstrap: adopted plain-Markdown session continuity

- Diagnosed two open bugs against the live `AGENTS.md` (stuck process on
  test launch; section position not saving) — see `docs/HANDOFF.md` for
  current status and `AGENT-WORKFLOW-PROMPT.md` for the working hypotheses.
- Considered a vector-DB memory plugin (`opencode-mem`) for cross-session
  continuity; decided against it for this project — see
  `AGENT-WORKFLOW-PROMPT.md` §4 for the reasoning.
- Adopted a plain-Markdown session-start/during/end protocol instead
  (`docs/HANDOFF.md`, `docs/SESSION_LOG.md` — this file, `docs/DECISIONS.md`,
  `docs/RUNBOOK.md`), based on a pattern shared in r/opencodeCLI.
- Drafted `ROADMAP.md` Phase 0–3 and flagged that `AGENTS.md` (~450 lines)
  should eventually split into these `docs/` files plus
  `ARCHITECTURE.md`/`API.md`/`TESTING.md` (Phase 1).
- Next session should pick up Phase 0: fix the two open bugs first.

## 2026-09-05 — Committed the docs split-out (ROADMAP Phase 1, commit `52e5b92`)

- Read the new `AGENT-WORKFLOW-PROMPT.md` first per user's updated kickoff
  instruction, then the rest of the new doc set
  (`AGENTS.md`, `README.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `API.md`,
  `TESTING.md`, plus `docs/HANDOFF.md`, `docs/SESSION_LOG.md` — this file,
  `docs/DECISIONS.md`, `docs/RUNBOOK.md`).
- Moved the 4 frozen `ai_*.html` reference files from repo root to
  `archived/` (still frozen, still untouched — just not first-class at
  top level anymore).
- Staged everything except `data/events.json` for that commit; per
  `docs/RUNBOOK.md` the EventsCommit scheduled task owns `events.json` and
  its unstaged timestamp updates will be picked up at the next 17:00 run.
- `AGENTS.md` shrank from ~450 → 110 lines. Phase 1 of `ROADMAP.md` is
  closed by this commit; the two Phase 0 bugs remain open and are still
  the top next actions.
- Next session: Phase 0 — fix the stuck-process regression first, then
  the `tickerTable.js` cross-section-state regression.

## 2026-09-05 — `project-rules` skill ships (commit `8583711`)

- User flagged that AGENTS.md feels ignored at times. Diagnosed: OMO-slim
  subagents (fixer / explorer / oracle / designer) don't auto-inject
  AGENTS.md — only the parent orchestrator does. Static system context
  also loses to dynamic task context under load.
- Designed a hand-off pattern instead of fighting it: hard rules live in
  a skill, orchestrator injects skill output into every subagent dispatch
  prompt.
- Created `.opencode/skills/project-rules/SKILL.md` with the full
  rule set pulled from AGENTS.md + docs/DECISIONS.md.
- Added the "invoke project-rules before dispatch" rule to AGENTS.md
  "During Work" and a pointer to the skill under "Skills."
- Logged the design rationale in docs/DECISIONS.md (new entry:
  "Hard-rule propagation: project-rules skill, not AGENTS.md alone").
- Next session: confirm the skill actually fires on the first subagent
  dispatch of any new task — and that AGENTS.md + the skill stay in
  sync over time.

## 2026-09-06 — Roadmap intake: 2 new Phase 0 bugs + Phase 2 codebase health audit

User asked to log 3 items on the roadmap with tightened wording; no fixes
attempted this session.

- `ROADMAP.md` Phase 0 gains:
  - **Fix: earnings watchlist add button broken.** Same shared-state risk
    profile as the `tickerTable.js` column-order regression; add a per-section
    add→reload round-trip regression test in the same change so the fix
    can't silently regress again.
  - **UX: portfolio name input collapses to single line** so the surrounding
    empty space becomes the click target (currently the tall input is the
    only focusable region).
- `ROADMAP.md` Phase 2 gains:
  - **Codebase health audit (precursor to any large refactor).** Invoke the
    `reflect` / `simplify` / `codemap` skill to produce a prioritized debt
    list with file:line evidence; subsequent refactor work is planned
    against that list rather than guessed at.
- `docs/HANDOFF.md` Top 3 next actions updated — earnings-watchlist regression
  replaces the shared-component-audit item (audit is now Phase 2 work, not
  Phase 0 follow-up).
- `app/changelog.log_change("doc", ...)` logged the intake.
- Priority order is unchanged: stuck-process and section-position regressions
  remain #1 and #2; portfolio name input UX is logged but not in top 3.
- Next session: still Phase 0 — the stuck-process regression first, per
  `docs/HANDOFF.md` Top 3.

## 2026-09-06 - Phase 0 stuck-process regression closed (commit pending)

Trigger observed mid-session: an interactive test launch left
python run.py --open-browser bound to 127.0.0.1:8000 for 54+ minutes
because the agent's turn ended before the documented reap step. PID 9224
seen via Get-NetTCPConnection -LocalPort 8000, confirmed
python run.py --open-browser via Get-CimInstance Win32_Process.
Reaped during this session after the fix shipped.

Root cause: launch-test-reap is documented in AGENTS.md and
docs/RUNBOOK.md but enforcement is purely procedural. No runtime
backstop existed. Previous scheduler fix cc7f476 made the launch side
reliable (pythonw ban, lockfile, PID liveness) but did not address the
reap side.

Fix shipped in this session:

- New module app/lifecycle.py with write_server_pid_file(),
  
emove_server_pid_file(), start_auto_reap_watchdog(seconds).
  Server.pid records pid + parent_pid + started at startup, is
  cleaned on /api/shutdown and atexit, refuses to unlink foreign
  pids. Watchdog polls os.getppid() via app.lockfile._pid_alive
  every 10s and calls os._exit(0) once the parent has been gone for
  the configured grace (default 0 = disabled for desktop).
- 
un.py now writes data/server.pid at startup (also atexit-cleaned)
  and accepts --auto-reap <seconds> (or the env var
  MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S).
- app/api.py /api/shutdown removes the pid file before scheduling
  os._exit(0).
- docs/RUNBOOK.md §Step 3a documents the new flag + the manual orphan-
  recovery recipe (Get-Content data\server.pid -> Stop-Process -Id
  <pid> -Force -> Remove-Item data\server.pid).
- docs/DECISIONS.md Open entry replaced with confirmed root cause,
  fix details, and runbook additions.

Tests:

- tests/test_lifecycle.py (new, 13 tests): watchdog zero/negative/no-op,
  watchdog spawns thread, watchdog exits on parent-dead, watchdog does
  NOT exit when parent is alive, watchdog no-ops when os.getppid()==0,
  server.pid write/remove semantics (matching pid, foreign pid, missing
  file), /api/shutdown integration, env var name stability, clean
  import.
- tests/test_run.py (6 new tests): --auto-reap 0 no-op,
  --auto-reap N forwarded, env var fallback, flag overrides env,
  server.pid written at startup, atexit cleanup.
- Red-green verified: with the fix reverted, 	est_shutdown_endpoint_
  removes_server_pid fails.
- Full suite: 425 passed (excluding 	est_thirteenf.py, network-heavy
  and slow). 	est_service_coverage.py ran cleanly alone (62s, 25 tests).

Also reconciled ROADMAP.md:

- Phase 1 checkboxes flipped to done (docs split + project-rules skill
  shipped in commits 52e5b92, 8583711). Status line added noting
  the close.
- Phase 0 #1 flipped to done. Phase 0 #5 (session-continuity docs)
  also flipped to done (the docs split covered it). Phase 0 #6
  (full test suite) marked partially done — current suite passes; a
  final re-run after the remaining Phase 0 fixes close is queued.
- One-line note added to docs/DECISIONS.md explaining why Phase 1
  ran ahead of Phase 0 (docs were a prerequisite for preserving
  Phase 0 root-cause context across sessions).

Next session: Phase 0 #2 (section-position not persisting) and #3
(earnings-watchlist add) - both share the same `tickerTable.js`
cross-section-state risk profile; fix both in one change with per-section
round-trip regression tests.

## 2026-09-06 - Phase 0 #2 / #3 / #4 closed in autonomous loop (commits pending)

User stepped away and asked for the remaining Phase 0 items to be
worked through in a loop. Closed three bugs in one session with per-
section regression tests for each.

### Phase 0 #2 — section position (column order) per-section persistence

Investigation: per-section keys (pfSort.{section}, pfVisible.{section},
pfOrder.{section}) are correctly namespaced in static/js/tickerTable.js,
and the columns_put backend endpoint correctly keys
state["column_order"][section] per section. The bug class warned about
in AGENT-WORKFLOW-PROMPT.md §3b did NOT occur — the refactor was clean.

Defensive fix: static/js/tickerTable.js exports a VALID_SECTIONS
allowlist (["earnings", "portfolio"]) and _assertValidSection()
guards every load/save helper plus createTickerTable(). An undefined or
unknown section prop throws immediately instead of silently templating
pfSort.undefined / pfVisible.null and dropping every preference
change.

Regression coverage: tests/frontend/section-position.spec.mjs (7 tests)
verifies per-section isolation across Sort / Visible / Order, reload
round-trip, and the absence of bare pfOrder / pfVisible / pfSort
keys without a section suffix.

### Phase 0 #3 — earnings watchlist Add button broken after first column reorder

Root cause: in static/js/tickerTable.js, drawControls() rebuilds the
entire controlsSel subtree via el.innerHTML = ... on every column
reorder, header sort, and reset-sort. The pre-fix 
ender() entry point
called drawControls(); wireAddInput(); drawBody() — wireAddInput() was
wired ONCE. After the first column reorder, the freshly-created
.tt-input / .tt-add-btn had no event listeners and the Add button
silently did nothing.

Fix: wireAddInput() now runs at the end of drawControls(). Every
controls rebuild re-attaches the input/button listeners. Listeners
attach to fresh DOM nodes; the discarded elements (and their listeners)
are GC'd naturally — no leak.

Regression coverage: tests/frontend/watchlist-add.spec.mjs (8 tests)
covers the add flow under: initial render, column reorder, header sort,
visibility toggle, multiple back-to-back reorders, Enter-key, and
input-validation (disabled when empty / whitespace-only). Red-green
verified: with the fix reverted, 4 tests fail (3 wireAddInput regressions
+ 1 VALID_SECTIONS export check).

### Phase 0 #4 — portfolio name input UX

Pre-fix .pf-name-input had flex: 1; min-width: 0; which stretched
the inline rename input to ~87% of .pf-pf-header width (measured
1027 / 1184 px on a typical desktop). The surrounding empty space
inside the header was too narrow to hit.

Fix: static/style.css switches .pf-name-input to
flex: 0 0 auto; width: auto; min-width: 160px; max-width: 100%. The
input now sizes to its content while staying usable on narrow headers.

Regression coverage: tests/frontend/portfolio-name-input.spec.mjs (3
tests) asserts the input width ratio stays under 50% of header width,
plus the single-line + click-outside-to-blur + Enter-saves UX behaviors.
Red-green verified: without the fix, the width ratio is 0.857; with the
fix, it's < 0.5.

### Aggregate session state

- All four Phase 0 items closed.
- Phase 1 (docs split) + Phase 0 are both fully done.
- Test counts: 400 Python tests pass (excluding test_thirteenf.py network-
  heavy + test_service_coverage.py long-running); 15 Playwright frontend
  tests pass across the three new spec files.
- Next session: Phase 2 - invoke the reflect / simplify / codemap skill
  trio to produce a prioritized debt list with file:line evidence, then
  close the app/thirteenf.py / app/scheduler.py / app/run.py test
  gaps and audit for other shared-component extractions with the same
  risk profile as tickerTable.js.
