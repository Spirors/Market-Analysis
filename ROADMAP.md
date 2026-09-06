# ROADMAP.md — Market Analysis Tool

This file tracks **phase-level status**: what's currently in scope, what's
next, and what's explicitly frozen until earlier phases close. It is the
first thing an agent should check after `AGENTS.md` before starting work.

Day-to-day granular changes still go in `data/logs/summary-YYYY-MM-DD.md` per
the existing changelog convention — this file doesn't replace that, it sits
one level above it.

Rule for agents: don't start a Phase N+1 item while a Phase N item is open,
unless explicitly told to.

---

## Phase 0 — Stop the bleeding (do this first)

- [x] **Fix: stuck process on test launch.** Root cause + fix per
      `AGENT-WORKFLOW-PROMPT.md` §3a. Closed via `app/lifecycle.py`
      (runtime backstop: `--auto-reap` watchdog + `data/server.pid` +
      `/api/shutdown` cleanup). Full root cause + decision in
      `docs/DECISIONS.md`. Regression tests in `tests/test_lifecycle.py`
      (13) and `tests/test_run.py` (6 new).
- [x] **Fix: section position not saving.** Root cause + fix per
      `AGENT-WORKFLOW-PROMPT.md` §3b. Investigation: per-section keys
      (`pfSort.{section}`, `pfVisible.{section}`, `pfOrder.{section}`)
      are correctly namespaced. Defensive fix in `static/js/tickerTable.js`:
      exported `VALID_SECTIONS` allowlist + `_assertValidSection()` guard
      throws immediately if a caller forgets `section` or passes an
      unknown value, preventing the silent collapse-to-shared-key
      regression the AGENT-WORKFLOW-PROMPT.md §3b hypothesis warned
      about. Regression tests in `tests/frontend/section-position.spec.mjs`
      (7) cover per-section isolation across Sort / Visible / Order
      channels plus reload round-trip.
- [x] **Fix: earnings watchlist add button broken.** Root cause: in
      `static/js/tickerTable.js`, `drawControls()` rebuilds the entire
      controls subtree (including the add input + Add button) on every
      column reorder / sort / reset, but `wireAddInput()` was only called
      from the public `render()` entry point (once). After the first
      column reorder, the freshly-created add input + button had no
      event listeners and the Add button silently did nothing. Fix:
      `wireAddInput()` now runs at the end of `drawControls()`, so every
      rebuild re-attaches the listeners (listeners attach to fresh DOM
      nodes so discarded elements and their listeners are GC'd
      naturally — no leak). Regression tests in
      `tests/frontend/watchlist-add.spec.mjs` (8) cover the add flow
      after column reorder / sort / visibility toggle / multiple
      back-to-back reorders, plus Enter-key + input-validation paths.
- [x] **UX: portfolio name input collapses to single line.** Root cause:
      `.pf-name-input` had `flex: 1; min-width: 0` which stretched the
      inline rename input to ~87% of the header width on a typical
      desktop layout, leaving the surrounding empty space too narrow to
      hit. Fix: `static/style.css` switches to `flex: 0 0 auto; width: auto;
      min-width: 160px; max-width: 100%` so the input sizes to its
      content while still being usable on narrow headers. Regression
      test in `tests/frontend/portfolio-name-input.spec.mjs` asserts the
      input width ratio stays under 50% of header width plus the
      single-line / blur / Enter-saves UX behaviors.
- [x] Stand up the session-continuity docs (see `AGENT-WORKFLOW-PROMPT.md`
      §4): `docs/HANDOFF.md`, `docs/SESSION_LOG.md`, `docs/DECISIONS.md`,
      `docs/RUNBOOK.md`. Seed `docs/DECISIONS.md` with the two findings above
      so they survive context resets without needing a memory plugin.
      Closed by the docs-split commits `52e5b92` and `8583711`.
- [x] Run the full test suite (`python -m pytest`) and confirm both fixes are
      covered, not just manually verified. 400 Python tests pass
      (`tests/` excluding `test_thirteenf.py` network-heavy + `test_service_coverage.py`
      long-running); both run separately also pass. 15 Playwright
      frontend tests pass across the three new spec files.

## Phase 1 — Documentation consolidation

Goal: `AGENTS.md` should hold only things that are (a) stable and (b) an
agent must see on every single session — not the whole project encyclopedia.

**Status:** closed in commits `52e5b92` (docs split-out) + `8583711`
(`project-rules` skill + AGENTS.md dispatch rule). `AGENTS.md` is now ~119
lines (target was <150); the split-out docs exist on disk and are wired
into the Session Start read order. A note in `docs/DECISIONS.md` records
why this phase ran ahead of Phase 0 (the docs themselves were needed to
diagnose the Phase 0 bugs without losing the root cause on context reset).

- [x] Split the current `AGENTS.md` (~450 lines) into:
  - `AGENTS.md` — hard rules, commit conventions, and the Session
    Start/During/End protocol (see `AGENT-WORKFLOW-PROMPT.md`). Nothing
    else. Target: under ~150 lines.
  - `docs/RUNBOOK.md` — the local server lifecycle / launch-verify-reap
    procedure, exact commands, VBS hidden-launch pattern. This is the fix
    for the stuck-process bug recurring: today it's prose buried mid-`AGENTS.md`;
    it needs to be step-by-step and read first, every session.
  - `docs/DECISIONS.md` — durable decisions currently scattered across
    "Key quirks" and "Recent activity" (Stooq removal, pythonw.exe vs
    wscript.exe, FRED/Minted Metal spot pricing, etc.), plus new findings
    from the current bug fixes.
  - `docs/HANDOFF.md` — current state, top 3 next actions, blockers.
    Updated every session.
  - `docs/SESSION_LOG.md` — append-only, timestamped, **git-tracked**.
    Note: this replaces relying on `data/logs/summary-YYYY-MM-DD.md` for
    cross-session continuity — that file is gitignored per `AGENTS.md` and
    doesn't survive across machines/git syncs. Keep it for its original
    purpose (local daily changelog) but don't treat it as the continuity
    record.
  - `ARCHITECTURE.md` — module map, backend module quick-reference,
    section-to-code map.
  - `API.md` — HTTP API table, dashboard payload sections.
  - `TESTING.md` — test suite pointers + known test gaps.
  - Keep `ROADMAP.md` (this file) as the single phase-level "what's next" doc.
  - Keep `Summary.md` as-is for plain-English project history.
- [x] `AGENTS.md` should end with a short "see also" list pointing at every
      split-out doc, so an agent that only reads `AGENTS.md` still knows
      where to go for runbook/decisions/architecture/API/testing detail.
- [x] Re-verify the "Recent activity" and "Known test gaps" sections migrate
      cleanly and nothing gets silently dropped in the split.

## Phase 2 — Refactor debt

- [ ] **Codebase health audit (precursor to any large refactor).** Invoke
      the `reflect` / `simplify` / `codemap` skill to produce a prioritized
      debt list with file:line evidence; the refactor pass below is then
      planned against that list rather than guessed at.
- [ ] Close known test gaps called out in the current `AGENTS.md`:
      `app/thirteenf.py` (network-heavy, currently only indirectly tested),
      `app/scheduler.py` (Windows-only, no tests / needs a mock),
      `app/run.py` CLI flags (not exercised by tests).
- [ ] Audit for other shared-component extractions with the same risk
      profile as `tickerTable.js` (any component consumed by 2+ sections
      with independently-keyed persisted state) and add per-consumer
      regression tests proactively, before another bug forces it.
- [ ] Revisit whether the current 3-scheduled-task Windows Task Scheduler
      setup and the VBS-wrapper launch pattern are documented clearly enough
      that "stuck launch" incidents can't recur through a different code path
      than the one fixed in Phase 0.

## Phase 3 — Feature work (frozen until Phase 0 & 1 close)

- [ ] (Add next features here once the above is stable — don't let this
      section grow while Phase 0 items are still open.)

---

## Non-goals / explicitly out of scope

- Modifying the 4 archived `ai_*.html` reference files — frozen, per
  `AGENTS.md`.
- Introducing paid/keyed data sources — free/no-key only, per `AGENTS.md`.
