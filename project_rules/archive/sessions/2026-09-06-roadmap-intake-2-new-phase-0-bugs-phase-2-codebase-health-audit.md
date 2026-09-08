# 2026-09-06 — ΓÇö Roadmap intake: 2 new Phase 0 bugs + Phase 2 codebase health audit

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

## 2026-09-06 ΓÇö Roadmap intake: 2 new Phase 0 bugs + Phase 2 codebase health audit

User asked to log 3 items on the roadmap with tightened wording; no fixes
attempted this session.

- `ROADMAP.md` Phase 0 gains:
  - **Fix: earnings watchlist add button broken.** Same shared-state risk
    profile as the `tickerTable.js` column-order regression; add a per-section
    addΓåÆreload round-trip regression test in the same change so the fix
    can't silently regress again.
  - **UX: portfolio name input collapses to single line** so the surrounding
    empty space becomes the click target (currently the tall input is the
    only focusable region).
- `ROADMAP.md` Phase 2 gains:
  - **Codebase health audit (precursor to any large refactor).** Invoke the
    `reflect` / `simplify` / `codemap` skill to produce a prioritized debt
    list with file:line evidence; subsequent refactor work is planned
    against that list rather than guessed at.
- `project_rules/HANDOFF.md` Top 3 next actions updated ΓÇö earnings-watchlist regression
  replaces the shared-component-audit item (audit is now Phase 2 work, not
  Phase 0 follow-up).
- `app/changelog.log_change("doc", ...)` logged the intake.
- Priority order is unchanged: stuck-process and section-position regressions
  remain #1 and #2; portfolio name input UX is logged but not in top 3.
- Next session: still Phase 0 ΓÇö the stuck-process regression first, per
  `project_rules/HANDOFF.md` Top 3.


