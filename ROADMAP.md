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
      the `reflect` / `simplify` / `codemap` skill trio to produce a
      prioritized debt list with file:line evidence; the refactor pass
      below is then planned against that list rather than guessed at.
      **Explicitly scope in the portfolio-mutation stale-on-reload
      cluster:** add or delete a row inside a portfolio writes
      correctly server-side, but a plain page reload shows stale state
      on the dashboard while the in-page Refresh button (full data /
      news / earnings / regime refresh) brings it current. Same pattern
      for whole-portfolio add/delete and for portfolio rename. Confirmed
      repro: add or delete a row in an existing portfolio →
      `data/portfolios.json` reflects the change → plain reload shows
      the pre-mutation state → click Refresh → state becomes current.
      The audit's job is to classify this: is it the same
      "shared component consumed by 2+ sections with independently-keyed
      persisted state" risk class already flagged for `tickerTable.js`,
      a separate dashboard-cache staleness issue (cache-invalidation
      shape, à la the existing pattern in `app/earnings.py` and
      `app/portfolio.py`), or both? The audit's output decides whether
      the refactor pass below lands as a state-namespacing fix, a
      cache-invalidation unification, or both — don't pre-decide before
      the audit runs.
- [ ] **Refactor pass: unify portfolio-mutation cache invalidation
      (gated on the audit above).** Once the audit has classified the
      stale-on-reload cluster, unify how ALL portfolio mutations
      invalidate / patch the cached dashboard payload. **Model the
      shape on `app/earnings.py`'s cache-patching pattern** (per
      `AGENTS.md`: patch the cache in place rather than rebuilding the
      whole dashboard). Specifically: one helper called after every
      `save_portfolios(state)` site (currently 9 mutation functions —
      create / delete / rename portfolio, add / edit / remove holding,
      add / edit / remove cash row); best-effort semantics so a failed
      patch degrades to "stale until `QUOTE_TTL`," never a hard error;
      bump `vintage["portfolios"]` so the per-card "As of" stamp
      reflects the mutation time. **Verification bar** (repro → fix →
      re-verify with same repro → regression test → commit hash):
      reproduce the original repro steps, fix, re-verify with those
      same steps (not a looser one), regression test, commit hash.
      Don't mark done on manual eyeballing alone.
- [ ] **Diagnose earnings watchlist false-positive "invalid symbol"
      error (do not blind-patch — multiple prior sessions have
      attempted a fix here without it landing).** Repro: entering
      "NVDA" (a mega-cap, unambiguously valid ticker) into the
      Earnings Watchlist Add field returns "invalid symbol."
      **Required approach:** add real diagnostic logging around the
      `validate_symbol` call chain in `app/earnings.py` — log the
      actual request, the raw yfinance response / exception, and the
      final verdict (valid / network error / genuinely invalid). Run
      the repro with the diagnostic logging in place BEFORE proposing
      a fix; capture the log output as evidence. Flag the specific
      hypothesis worth checking: yfinance is now the sole market-data
      source (Stooq was removed for bot-walling per `README.md`) — a
      failed / timed-out / rate-limited call may be getting treated
      as "confirmed invalid" instead of "couldn't verify."
      Distinguishing these two is the same two-axis fix the prior
      session attempted (commit `a2c793a`); if it didn't land, find
      out WHY before patching again. Require a regression test that
      mocks the yfinance response so this isn't only network-dependent
      to catch — a test that only catches the bug when Yahoo is
      rate-limiting the test runner isn't a regression test, it's a
      flake. **Verification bar** (repro → fix → re-verify with same
      repro → regression test → commit hash): reproduce the original
      repro steps, fix, re-verify with those same steps (not a looser
      one), regression test, commit hash. Don't mark done on manual
      eyeballing alone.
- [ ] **Fix portfolio rename layout shift (regression).** Root cause
      hypothesis: the existing `.pf-name-input { min-width: 160px }`
      rule (from the already-closed portfolio-name-input fix in
      commit `4716e02`, refined in `974d988`) is wider than some
      portfolios' rendered title width, so entering edit mode visibly
      shoves the pencil icon / value / close button to the right.
      **Fix without reintroducing the original too-narrow-input bug**
      (the pre-`4716e02` `flex: 1; min-width: 0` rule stretched the
      input to ~87% of header width). The right answer is
      content-sized, not header-filling — revisit whether
      `min-width: 160px` is the right floor or whether it should be
      `max(min-content, 8ch)` or similar. **Verification bar**
      (repro → fix → re-verify with same repro → regression test →
      commit hash): reproduce with the original repro steps (rename a
      portfolio whose rendered title is shorter than 160px → header
      layout shifts), fix, re-verify with those same steps, regression
      test (`tests/frontend/portfolio-name-input.spec.mjs` extended),
      commit hash. Don't mark done on manual eyeballing alone.
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
