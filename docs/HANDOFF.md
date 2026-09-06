# Handoff

`Last updated`: 2026-09-05 (project-rules skill shipped — commit `8583711`).

## Current state

Docs split-out (ROADMAP Phase 1) committed. `AGENTS.md` is now ~115 lines and
holds only hard rules + the session protocol; architecture/API/testing
reference material lives in their own files. The session-start reading
order is now fronted by `AGENT-WORKFLOW-PROMPT.md` (per user direction).
Hard rules now also live in `.opencode/skills/project-rules/SKILL.md` and
are injected into every subagent dispatch by the orchestrator per the
"During Work" rule in `AGENTS.md`.
Phase 0 bugs remain unfixed — they were the trigger for the docs split but
haven't been touched in this session.

## Top 3 next actions

1. Phase 0: diagnose and fix the stuck-process-on-launch regression. Start
   from `docs/RUNBOOK.md` §Local server lifecycle and the hypotheses in
   `AGENT-WORKFLOW-PROMPT.md` §3a. Record the confirmed root cause in
   `docs/DECISIONS.md` once found.
2. Phase 0: diagnose and fix section position (column order) not persisting
   for Earnings/Portfolio. Start with the `tickerTable.js` cross-section
   hypothesis in `AGENT-WORKFLOW-PROMPT.md` §3b.
3. Once both Phase 0 bugs are fixed and tested, audit for other
   shared-component extractions with the same risk profile as
   `tickerTable.js` (ROADMAP Phase 2) before any new feature work.

## Blockers

None. `data/events.json` has unstaged scheduler timestamp updates — per
`docs/RUNBOOK.md` the `MarketAnalysis-EventsCommit` task owns that file,
not interactive sessions, so they will be picked up at the next 17:00
scheduled run.
