# 2026-09-05 — ΓÇö `project-rules` skill ships (commit `8583711`)

Full text of the entry from `project_rules/SESSION_LOG_ARCHIVE.md`
(retrofit 2026-09-08: the archive was split into per-session files
under `archive/sessions/<slug>.md`. This file is the single source
of truth for the verbose detail; the live `SESSION_LOG.md` holds
the full text for the latest entry and pointers for older entries).

---

## 2026-09-05 ΓÇö `project-rules` skill ships (commit `8583711`)

- User flagged that AGENTS.md feels ignored at times. Diagnosed: OMO-slim
  subagents (fixer / explorer / oracle / designer) don't auto-inject
  AGENTS.md ΓÇö only the parent orchestrator does. Static system context
  also loses to dynamic task context under load.
- Designed a hand-off pattern instead of fighting it: hard rules live in
  a skill, orchestrator injects skill output into every subagent dispatch
  prompt.
- Created `.opencode/skills/project-rules/SKILL.md` with the full
  rule set pulled from AGENTS.md + project_rules/DECISIONS.md.
- Added the "invoke project-rules before dispatch" rule to AGENTS.md
  "During Work" and a pointer to the skill under "Skills."
- Logged the design rationale in project_rules/DECISIONS.md (new entry:
  "Hard-rule propagation: project-rules skill, not AGENTS.md alone").
- Next session: confirm the skill actually fires on the first subagent
  dispatch of any new task ΓÇö and that AGENTS.md + the skill stay in
  sync over time.


