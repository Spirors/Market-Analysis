# 2026-09-06 — ΓÇö Phase 2 #1-#4 closed (5 commits, 427 tests pass)

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

## 2026-09-06 ΓÇö Phase 2 #1-#4 closed (5 commits, 427 tests pass)

User asked for Phase 2 worked top to bottom, with strict per-bullet
repro ΓåÆ fix ΓåÆ re-verify ΓåÆ regression test ΓåÆ commit. Audit (Phase 2 #1)
was the explicit prerequisite ΓÇö not to be skipped even though the
refactor pass seemed already covered by `b45858e`.

### Phase 2 #1 ΓÇö Codebase health audit (commit `8d6d104`)

Two findings appended to `project_rules/DECISIONS.md`:

- **Stale-on-reload cluster classification** ΓÇö dashboard-cache
  staleness (already fixed by `b45858e`), NOT the same root cause as
  the `tickerTable.js` shared-state class. The audit confirms this so
  Phase 2 #2 wouldn't be re-planned against a stale classification.

- **Earnings `validate_symbol` path diff** ΓÇö portfolio display uses
  `yf.download` (bulk, reliable in yfinance 1.6.0); earnings validation
  used `Ticker.info` (per-symbol, rate-limited) as PRIMARY with history
  fallback. Why `a2c793a` didn't stick: retry-with-1s-backoff around the
  same fundamentally-flaky call instead of switching to the reliable
  surface. Repro matrix (mocked, network-independent) covers all 4
  scenarios (A both work, B info-empty+bulk-works, C both empty, D
  info-full+bulk-empty).

### Phase 2 #2 ΓÇö Refactor pass: confirmed already done

Audit's classification said `b45858e` already covered the
stale-on-reload cluster (new `_patch_dashboard_cache(state)` helper
called after every `save_portfolios(state)` in all 9 mutation
functions, mirroring `app/earnings.py`'s pattern). No new commits
required.

### Phase 2 #3 ΓÇö Earnings "invalid symbol" bug fix (commit `735b5e7`)

Diagnostic evidence (path diff + 4-scenario repro) presented BEFORE
the fix per user instruction. Root cause: `validate_symbol` PRIMARY
was `Ticker.info` (per-symbol, rate-limited); portfolio display
PRIMARY is `yf.download` (bulk, reliable). User's exact hypothesis
confirmed: "validate_symbol relying on Ticker.info (known to be
flaky/rate-limited by Yahoo independent of symbol validity) while
portfolio's working path uses Ticker.history() / fast_info (more
reliable). If that split is the cause, the fix is to validate
existence the same way portfolio already does successfully ΓÇö not to
add retry/error-handling around a fundamentally flaky call."

Fix: `_validate_uncached` now uses `market.get_history` as PRIMARY
(bulk-download surface, same as portfolio), with `Ticker.info` as
SECONDARY + best-effort enrichment. Removed `_yf_info_with_retry`
(retrying a flaky call was masking the bug, not fixing it).

Verdicts preserved across all 4 scenarios. 21 tests in
`tests/test_earnings.py`: 4 scenarios + 4 structural (call-order,
no-retry-helper, no-sleep) + add_ticker / add_holding user-facing
paths + cache behaviour + input validation. Red-green verified: with
the fix reverted, 3 of 4 structural tests FAIL (the 4th passes
because it tests a property both implementations share).

### Phase 2 #4 ΓÇö Portfolio rename layout shift (commits `55400a9` + `8bb0f07`)

Pre-existing `.pf-name-input { min-width: 160px }` was wider than the
rendered title for short names like "IRA" (3 chars), so entering edit
mode shoved the pencil icon / totals / close button ~130px to the
right.

Fix: `static/style.css` swaps the pixel floor for
`field-sizing: content` (Chrome 123+ / Firefox 122+ / Safari 17.5+) +
`min-width: 8ch`. For "IRA" the input renders at ~74px (was 160-183px).
Older browsers fall back to the intrinsic 20-char size automatically.

Why not the originally-proposed `max(min-content, 8ch)` formula:
doesn't compose with `field-sizing: content` ΓÇö the browser ignores
the explicit min-width formula and uses the content-sized width
regardless. Plain `min-width: 8ch` is the correct hard floor once
`field-sizing: content` is doing the sizing. This lesson is recorded
in `project_rules/DECISIONS.md` ("Use `field-sizing: content` for content-sized
inputs in modern browsers, with `min-width: <ch>` as the usability
floor (NOT a fixed pixel value)").

2 new Playwright tests in
`tests/frontend/portfolio-name-input.spec.mjs` for the short-name
layout shift. Both FAIL on the pre-fix code (red-green verified).

### Aggregate session state

- 5 new commits: `8d6d104` (audit docs) + `735b5e7` (earnings fix) +
  `55400a9` (portfolio CSS fix) + `8bb0f07` (DECISIONS.md update) +
  this docs commit.
- 427 Python tests pass (was 419 + 4 scenario + 4 structural).
- 5 Playwright portfolio-name-input tests pass (was 3 + 2 new).
- No python processes running. Ports 8000/8123 free. Static server
  reaped before turn end (PID 10320 ΓåÆ Stop-Process).
- Phase 0 / Phase 1 / Phase 2 #1-#4 closed. Remaining Phase 2 items:
  - #5 ΓÇö test gaps (`app/thirteenf.py`, `app/scheduler.py`,
    `app/run.py` CLI flags)
  - #7 ΓÇö task scheduler / VBS launcher docs audit
  Both out of scope this turn (the user explicitly said "Work Phase 2
  top to bottom" through #4 only).
- Next session: Phase 2 #5 (test gaps), then Phase 2 #7, then Phase 3.



