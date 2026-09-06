# Session Log

Append-only. Newest entry at the bottom. This file is git-tracked — unlike
`data/logs/summary-YYYY-MM-DD.md`, which is gitignored and local-only per
`AGENTS.md`. Use this file for anything that needs to survive across
machines or a fresh checkout; keep using the existing `data/logs/` changelog
for its original local-daily-changelog purpose.

---

## 2026-09-05 — Bootstrap: adopted plain-Markdown session continuity

- Diagnosed two open bugs against the live `AGENTS.md` (stuck process on
  test launch; section position not saving) — see `docs/HANDOFF.md` for
  current status and `AGENT-WORKFLOW-PROMPT.md` for the working hypotheses.
- Considered a vector-DB memory plugin (`opencode-mem`) for cross-session
  continuity; decided against it for this project — see
  `AGENT-WORKFLOW-PROMPT.md` §4 for the reasoning.
- Adopted a plain-Markdown session-start/during/end protocol instead
  (`docs/HANDOFF.md`, `docs/SESSION_LOG.md` — this file, `docs/DECISIONS.md`,
  `docs/RUNBOOK.md`), based on a pattern shared in r/opencodeCLI.
- Drafted `ROADMAP.md` Phase 0–3 and flagged that `AGENTS.md` (~450 lines)
  should eventually split into these `docs/` files plus
  `ARCHITECTURE.md`/`API.md`/`TESTING.md` (Phase 1).
- Next session should pick up Phase 0: fix the two open bugs first.
