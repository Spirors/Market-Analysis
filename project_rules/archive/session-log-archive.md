# Session Log Archive

Append-only archive of older `project_rules/SESSION_LOG.md` entries that have
been rotated out of the live file. Date range: 2026-09-05 (3 entries).
Kept for historical reference — do not append new entries here.

---
## 2026-09-05 ΓÇö Bootstrap: adopted plain-Markdown session continuity

- Diagnosed two open bugs against the live `AGENTS.md` (stuck process on
  test launch; section position not saving) ΓÇö see `project_rules/HANDOFF.md` for
  current status and `AGENT-WORKFLOW-PROMPT.md` for the working hypotheses.
- Considered a vector-DB memory plugin (`opencode-mem`) for cross-session
  continuity; decided against it for this project ΓÇö see
  `AGENT-WORKFLOW-PROMPT.md` ┬º4 for the reasoning.
- Adopted a plain-Markdown session-start/during/end protocol instead
  (`project_rules/HANDOFF.md`, `project_rules/SESSION_LOG.md` ΓÇö this file, `project_rules/DECISIONS.md`,
  `project_rules/RUNBOOK.md`), based on a pattern shared in r/opencodeCLI.
- Drafted `ROADMAP.md` Phase 0ΓÇô3 and flagged that `AGENTS.md` (~450 lines)
  should eventually split into these `docs/` files plus
  `ARCHITECTURE.md`/`API.md`/`TESTING.md` (Phase 1).
- Next session should pick up Phase 0: fix the two open bugs first.

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
