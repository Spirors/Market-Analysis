# 2026-09-05 — ΓÇö Committed the docs split-out (ROADMAP Phase 1, commit `52e5b92`)

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

## 2026-09-05 ΓÇö Committed the docs split-out (ROADMAP Phase 1, commit `52e5b92`)

- Read the new `AGENT-WORKFLOW-PROMPT.md` first per user's updated kickoff
  instruction, then the rest of the new doc set
  (`AGENTS.md`, `README.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `API.md`,
  `TESTING.md`, plus `project_rules/HANDOFF.md`, `project_rules/SESSION_LOG.md` ΓÇö this file,
  `project_rules/DECISIONS.md`, `project_rules/RUNBOOK.md`).
- Moved the 4 frozen `ai_*.html` reference files from repo root to
  `archived/` (still frozen, still untouched ΓÇö just not first-class at
  top level anymore).
- Staged everything except `data/events.json` for that commit; per
  `project_rules/RUNBOOK.md` the EventsCommit scheduled task owns `events.json` and
  its unstaged timestamp updates will be picked up at the next 17:00 run.
- `AGENTS.md` shrank from ~450 ΓåÆ 110 lines. Phase 1 of `ROADMAP.md` is
  closed by this commit; the two Phase 0 bugs remain open and are still
  the top next actions.
- Next session: Phase 0 ΓÇö fix the stuck-process regression first, then
  the `tickerTable.js` cross-section-state regression.


