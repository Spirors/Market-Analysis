# Handoff

`Last updated`: 2026-09-05 (bootstrap entry — created outside a live agent
session while setting up this doc set; the next real session should update
this properly at session end).

## Current state

Mid-refactor. Two active regressions are blocking everything else (see
`ROADMAP.md` Phase 0). The `914f406` Portfolio/Earnings `tickerTable.js`
share-out is the most recent structural change and is the prime suspect for
one of them. Documentation is also being split out of the monolithic
`AGENTS.md` into this `docs/` set (see `ROADMAP.md` Phase 1) — that split is
not done yet, so `AGENTS.md` is still the source of truth for architecture,
API, and test-gap detail until Phase 1 closes.

## Top 3 next actions

1. Diagnose and fix the stuck-process-on-launch regression. Start from
   `docs/RUNBOOK.md` §Local server lifecycle and the hypotheses in
   `AGENT-WORKFLOW-PROMPT.md` §3a. Record the confirmed root cause in
   `docs/DECISIONS.md` once found.
2. Diagnose and fix section position (column order) not persisting for
   Earnings/Portfolio. Start with the `tickerTable.js` cross-section-state
   hypothesis in `AGENT-WORKFLOW-PROMPT.md` §3b.
3. Once both are fixed and tested, start the `AGENTS.md` → `docs/*` split
   (Phase 1) so the runbook/decisions pattern is actually in place for the
   next round of bugs, not just this one.

## Blockers

None currently — both open bugs are believed to be reproducible locally
without external dependencies.
