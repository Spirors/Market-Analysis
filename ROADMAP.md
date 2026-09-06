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

- [ ] **Fix: stuck process on test launch.** Root cause + fix per
      `AGENT-WORKFLOW-PROMPT.md` §3a. Add the reap-and-verify checklist
      inline wherever `AGENTS.md` documents a command that spawns a process.
- [ ] **Fix: section position not saving.** Root cause + fix per
      `AGENT-WORKFLOW-PROMPT.md` §3b (shared `tickerTable.js` cross-section
      state). Add a regression test per section (Earnings, Portfolio) so a
      future shared-component change can't silently break persistence again.
- [ ] **Fix: earnings watchlist add button broken.** Same shared-state
      risk profile as the `tickerTable.js` column-order regression; add a
      per-section add→reload round-trip regression test in the same change
      so the fix can't silently regress again.
- [ ] **UX: portfolio name input collapses to single line** so the
      surrounding empty space becomes the click target (currently the tall
      input is the only focusable region).
- [ ] Stand up the session-continuity docs (see `AGENT-WORKFLOW-PROMPT.md`
      §4): `docs/HANDOFF.md`, `docs/SESSION_LOG.md`, `docs/DECISIONS.md`,
      `docs/RUNBOOK.md`. Seed `docs/DECISIONS.md` with the two findings above
      so they survive context resets without needing a memory plugin.
- [ ] Run the full test suite (`python -m pytest`) and confirm both fixes are
      covered, not just manually verified.

## Phase 1 — Documentation consolidation

Goal: `AGENTS.md` should hold only things that are (a) stable and (b) an
agent must see on every single session — not the whole project encyclopedia.

- [ ] Split the current `AGENTS.md` (~450 lines) into:
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
- [ ] `AGENTS.md` should end with a short "see also" list pointing at every
      split-out doc, so an agent that only reads `AGENTS.md` still knows
      where to go for runbook/decisions/architecture/API/testing detail.
- [ ] Re-verify the "Recent activity" and "Known test gaps" sections migrate
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
