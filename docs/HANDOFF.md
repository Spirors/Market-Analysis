# Handoff

`Last updated`: 2026-09-06 (roadmap intake — 2 new Phase 0 bugs + Phase 2 codebase health audit logged).

## Current state

Docs split-out (ROADMAP Phase 1) committed. `AGENTS.md` is now ~115 lines and
holds only hard rules + the session protocol; architecture/API/testing
reference material lives in their own files. The session-start reading
order is now fronted by `AGENT-WORKFLOW-PROMPT.md` (per user direction).
Hard rules now also live in `.opencode/skills/project-rules/SKILL.md` and
are injected into every subagent dispatch by the orchestrator per the
"During Work" rule in `AGENTS.md`.
Phase 0 now has 4 open items (2 original regressions + earnings watchlist
add broken + portfolio name input UX). Phase 2 gains a codebase health
audit item that should run before any large refactor pass.

## Top 3 next actions

1. Phase 0: diagnose and fix the stuck-process-on-launch regression. Start
   from `docs/RUNBOOK.md` §Local server lifecycle and the hypotheses in
   `AGENT-WORKFLOW-PROMPT.md` §3a. Record the confirmed root cause in
   `docs/DECISIONS.md` once found.
2. Phase 0: diagnose and fix section position (column order) not persisting
   for Earnings/Portfolio. Start with the `tickerTable.js` cross-section
   hypothesis in `AGENT-WORKFLOW-PROMPT.md` §3b.
3. Phase 0: diagnose and fix the earnings watchlist add regression (same
   shared-state risk profile as `tickerTable.js`; add a per-section
   add→reload round-trip regression test in the same change).

## Blockers

None. `data/events.json` has unstaged scheduler timestamp updates — per
`docs/RUNBOOK.md` the `MarketAnalysis-EventsCommit` task owns that file,
not interactive sessions, so they will be picked up at the next 17:00
scheduled run.
