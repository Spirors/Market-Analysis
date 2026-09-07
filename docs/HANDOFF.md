# Handoff

`Last updated`: 2026-09-06 23:55 UTC (Phase 2 #1-#4 closed, 427 Python tests + 5 portfolio-name-input Playwright tests pass, no python processes, port 8000/8123 free).

## Current state

**Phase 0 / Phase 1 / Phase 2 #1-#4 all closed.** Five new commits this session
(`8d6d104` → `735b5e7` → `55400a9` → `8bb0f07` → this docs commit), all green:

- **Phase 2 #1 — Codebase health audit.** Commit `8d6d104`. Two findings
  appended to `docs/DECISIONS.md`:
  - **Stale-on-reload cluster classification:** dashboard-cache staleness
    issue, **already fixed by `b45858e`** — NOT the same root cause as the
    `tickerTable.js` shared-state risk class. The audit's job was to
    confirm this so the refactor pass (Phase 2 #2) wouldn't be re-planned
    against a stale classification.
  - **Earnings `validate_symbol` path diff:** portfolio display uses
    `yf.download` (bulk, reliable); earnings validation used `Ticker.info`
    (per-symbol, rate-limited) as PRIMARY with history fallback. Why
    `a2c793a` didn't stick: it added retry-with-1s-backoff around the
    same fundamentally-flaky call instead of switching to the reliable
    surface. Repro matrix (mocked, network-independent) covers all 4
    scenarios.
- **Phase 2 #2 — Refactor pass.** Already covered by `b45858e`. No
  additional work required. `app/portfolio.py:_patch_dashboard_cache(state)`
  called after every `save_portfolios(state)` in all 9 mutation functions.
- **Phase 2 #3 — Earnings "invalid symbol" diagnosis.** Commit `735b5e7`.
  `validate_symbol` now uses `market.get_history` (yf.download) as PRIMARY
  with `Ticker.info` as SECONDARY + enrichment. Removed `_yf_info_with_retry`
  (retrying a flaky call was the wrong shape of fix). 4 scenario tests +
  4 structural tests in `tests/test_earnings.py` — 3 of the structural
  tests fail on the pre-fix code (red-green verified). User-facing paths
  (`add_ticker`, `add_holding`) covered.
- **Phase 2 #4 — Portfolio rename layout shift.** Commit `55400a9` +
  docs `8bb0f07`. `.pf-name-input` swaps `min-width: 160px` (a fixed
  pixel floor wider than short rendered titles) for `field-sizing: content`
  + `min-width: 8ch`. For "IRA" the input renders at ~74px (was 160-183px).
  Older browsers fall back to the intrinsic 20-char size — no regression,
  just no improvement. 2 new Playwright tests in
  `tests/frontend/portfolio-name-input.spec.mjs` — both FAIL on the pre-fix
  code (red-green verified).
- **Phase 2 #5 — Test gaps (`app/thirteenf.py`, `app/scheduler.py`,
  `app/run.py` CLI flags).** NOT DONE — out of scope for this turn.
- **Phase 2 #6 — Shared-component audit.** Closed by the Phase 2 #1 audit —
  no new candidates found beyond the existing per-portfolio star scoping
  (`1fafbc1`).
- **Phase 2 #7 — Task scheduler / VBS launcher docs audit.** NOT DONE —
  out of scope for this turn.

Phase 0 / Phase 1 (both fully closed in prior sessions) remain green.

## Top 3 next actions

1. **Phase 2 #5 — close known test gaps.** `app/thirteenf.py`
   (network-heavy, currently only indirectly tested),
   `app/scheduler.py` (Windows-only, no tests / needs a mock),
   `app/run.py` CLI flags (partially covered by the recent
   `test_run.py` additions). The 3 remaining items in ROADMAP.md
   Phase 2.
2. **Phase 2 #7 — task scheduler / VBS launcher docs audit.**
   Revisit whether the 3-scheduled-task setup and the VBS-wrapper
   launch pattern are documented clearly enough that "stuck launch"
   incidents can't recur through a different code path than the one
   fixed in Phase 0.
3. **Phase 3 — feature work.** Once Phase 2 is fully closed, the
   roadmap says "(Add next features here once the above is stable —
   don't let this section grow while Phase 0 items are still open)."
   Currently empty. Suggest a backlog intake session before kicking
   off Phase 3 work.

## Blockers

None. `data/events.json` has unstaged scheduler timestamp updates — per
`docs/RUNBOOK.md` the `MarketAnalysis-EventsCommit` task owns that file,
not interactive sessions, so they will be picked up at the next 17:00
scheduled run.

## Notes for the next session

- **Earnings validation now uses yf.download as PRIMARY** (commit `735b5e7`).
  Any code that imports `earnings._yf_info_with_retry` will fail — the
  helper was removed. Use `earnings._yf_info` directly (or
  `earnings.market.get_history` for the bulk surface). The retry-with-
  backoff is intentionally gone — retrying a fundamentally-flaky call
  was masking the bug, not fixing it.
- **Portfolio rename input uses `field-sizing: content`** (commit `55400a9`).
  Any code that asserts `.pf-name-input { min-width: 160px }` will fail
  — the rule is now `field-sizing: content; min-width: 8ch;`. Older
  browsers (pre-Chrome 123 / pre-Firefox 122 / pre-Safari 17.5) fall
  back to the intrinsic 20-char size automatically.
- **Phase 2 audit decisions live in `docs/DECISIONS.md`** under
  "Phase 2 audit — stale-on-reload cluster classification" and
  "Phase 2 audit — earnings validate_symbol path diff". Read those
  before re-running the audit.
- **`docs/SESSION_LOG.md`** has accumulated ~12 dated entries — the file
  is now ~700 lines. Consider archiving pre-2026-09-06 entries to
  `docs/archive/SESSION_LOG-pre-2026-09-06.md` if size becomes a concern
  for next-session context.
- **The Playwright frontend tests need a static server on port 8123**
  (`python -m http.server 8123 --bind 127.0.0.1` from the repo root).
  Reap before the turn ends per the runbook — pytest's playwright
  harness auto-starts/reuses the server but interactive runs need it
  started manually and reaped explicitly.
- **The 5 commits this session are isolated** — each can be reverted
  individually without breaking the others. `8d6d104` (audit docs) is
  documentation only; `735b5e7` (earnings fix), `55400a9` (portfolio CSS
  fix), and the two docs commits are independent code/docs pairs.
- **The auto-reap watchdog (`app/lifecycle.py`)** is the runtime backstop
  for any future stuck-process regression. Agent terminal launches MUST
  use `--auto-reap 60` (or set `$env:MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S=60`).
  Documented in `docs/RUNBOOK.md` §Step 3a.
