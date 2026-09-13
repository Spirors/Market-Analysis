# 2026-09-06 — ΓÇö Archived AGENT-WORKFLOW-PROMPT.md

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

## 2026-09-06 ΓÇö Archived AGENT-WORKFLOW-PROMPT.md

Move-only pass per user request. `AGENT-WORKFLOW-PROMPT.md` ΓåÆ
`archived/AGENT-WORKFLOW-PROMPT.md` (git rename, history preserved).
The file's content is fully duplicated by `AGENTS.md` + `docs/` + the
`project-rules` skill, but 16 references in `project_rules/DECISIONS.md`,
`project_rules/SESSION_LOG.md`, `ROADMAP.md`, `static/js/tickerTable.js`,
`tests/test_run.py`, and `tests/frontend/section-position.spec.mjs`
still cite its ┬º3a (stuck-process) and ┬º3b (shared-component state)
hypotheses ΓÇö those remain valid historical anchors, so the file
moves rather than gets deleted.

Changes:
- `git mv` of the file (rename tracked in history).
- `archived/AGENT-WORKFLOW-PROMPT.md` gains a `FROZEN ΓÇö DO NOT MODIFY`
  header pointing readers at `AGENTS.md` + `project_rules/DECISIONS.md` for
  current state.
- `AGENTS.md` "Hard rules" gains a sibling bullet to the
  `archived/ai_*.html` frozen-reference note, naming the 16
  referencing files explicitly.
- The 16 historical references in docs/code/tests are LEFT UNCHANGED
  ΓÇö they're anchors, not pointers to current state, and rewriting
  them would mean touching closed decisions and frozen test comments
  for cosmetic clarity only. The new AGENTS.md hard-rule entry is
  the authoritative pointer.

Mirrors the `archived/ai_*.html` decision (commit `52e5b92`,
`project_rules/DECISIONS.md` "Frozen reference files are not touched, ever").

Next session: still Phase 2.


