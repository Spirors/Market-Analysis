# 2026-09-06 — ΓÇö ROADMAP Phase 2 expanded: audit scope-in + 3 new bullets

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

## 2026-09-06 ΓÇö ROADMAP Phase 2 expanded: audit scope-in + 3 new bullets

Planning-only pass per user request. `ROADMAP.md` Phase 2 only ΓÇö no
application code touched.

- **Extended the existing "Codebase health audit" bullet** to explicitly
  scope in the portfolio-mutation stale-on-reload cluster: add or delete
  a row inside a portfolio writes correctly server-side, but a plain
  page reload shows stale state while the in-page Refresh button (full
  data / news / earnings / regime refresh) brings it current. Same
  pattern for whole-portfolio add/delete and for portfolio rename. The
  audit's job is to classify whether this is the same "shared component
  with independently-keyed persisted state" risk class already flagged
  for `tickerTable.js`, a separate dashboard-cache staleness issue (├á
  la `app/earnings.py` and `app/portfolio.py`'s cache-patching
  pattern), or both ΓÇö the answer decides the shape of the refactor
  pass below.

- **Added the missing "refactor pass" bullet** that the audit's own
  text referred to. Explicitly gated on the audit's output: unify how
  ALL portfolio mutations invalidate / patch the cached dashboard
  payload, modeled on `app/earnings.py`'s cache-patching pattern (per
  `AGENTS.md`: "patch the cache instead of rebuilding"). 9 mutation
  functions (create/delete/rename portfolio, add/edit/remove holding,
  add/edit/remove cash row); best-effort semantics so a failed patch
  degrades to "stale until `QUOTE_TTL`," never a hard error; bumps
  `vintage["portfolios"]` so the per-card "As of" stamp reflects the
  mutation time.

- **Added "Diagnose earnings watchlist false-positive 'invalid symbol'
  error"** ΓÇö do-not-blind-patch directive. Require diagnostic logging
  around the `validate_symbol` call chain in `app/earnings.py` (log
  the actual request + raw yfinance response/exception + final
  verdict: valid / network error / genuinely invalid), run the repro
  with logging in place BEFORE proposing a fix, and check the specific
  hypothesis that a failed/timed-out/rate-limited yfinance call is
  being treated as "confirmed invalid" instead of "couldn't verify"
  (yfinance is the sole source after Stooq removal per `README.md`).
  Note: prior session attempted this in commit `a2c793a` (and again
  in `80d0fef` for the add/remove cache-miss path); if it's still
  firing, find out WHY before patching again. Require a regression
  test that mocks the yfinance response ΓÇö a test that only catches
  the bug when Yahoo is rate-limiting the runner isn't a regression
  test, it's a flake.

- **Added "Fix portfolio rename layout shift (regression)"** ΓÇö root
  cause hypothesis: the existing `.pf-name-input { min-width: 160px }`
  rule (from the already-closed portfolio-name-input fix in commit
  `4716e02`, refined in `974d988`) is wider than some portfolios'
  rendered title width, so entering edit mode visibly shoves the
  pencil icon / value / close button to the right. Fix without
  reintroducing the original too-narrow bug (the pre-`4716e02`
  `flex: 1; min-width: 0` rule stretched the input to ~87% of header
  width). The right answer is content-sized, not header-filling ΓÇö
  revisit whether `min-width: 160px` is the right floor or whether
  it should be `max(min-content, 8ch)` or similar.

- **Each new bullet carries the same verification bar** as the Phase 0
  items: reproduce with the original repro steps ΓåÆ fix ΓåÆ re-verify
  with those same steps (not a looser one) ΓåÆ regression test ΓåÆ
  commit hash. Don't mark anything done on manual eyeballing alone.

Next session: still Phase 2. The codebase health audit is the natural
entry point ΓÇö its output on the stale-on-reload cluster unblocks the
new refactor pass bullet directly below it.


