# AGENTS.md

AI-readable reference for the Market Analysis Tool. This file holds
only the session protocol and commit conventions. All hard rules (data
integrity, server lifecycle, frozen files, shared UI components,
tooltip-on-card-change, changelog logging, etc.) live in the
`project-rules` skill — see `.opencode/skills/project-rules/SKILL.md`
and the "Hard rules" pointers below.

## What this is

Local webapp for macro-trend market analysis (regime classification,
breadth/vol/yield indicators, chokepoint bottlenecks, filtered news
timeline, trend-shift risk-divergence engine). Free, no-key data sources,
runs entirely locally on Windows. See `README.md` for the pitch and
`project_rules/ARCHITECTURE.md` for the stack and module map.

## Session Start

Read in this exact order before doing anything else:

1. This file (`AGENTS.md`)
2. `README.md`
3. `project_rules/ROADMAP.md` — current phase; only work inside it unless told otherwise
4. `project_rules/HANDOFF.md` — where the last session left off
5. latest entry in `project_rules/SESSION_LOG.md` (not the whole file — just the
   most recent dated entry)
6. `project_rules/DECISIONS.md`
7. `project_rules/RUNBOOK.md` — exact operational procedures
8. `.opencode/skills/project-rules/SKILL.md` (via the `skill` tool) — load
   the hard rules once per session so they are top-of-context

`project_rules/ARCHITECTURE.md`, `project_rules/ARCHITECTURE_DETAILS.md`,
`project_rules/API.md`, and `project_rules/TESTING.md` are **not** part of
this list — read them on demand when a task actually touches that area,
to keep session-start cost low as the docs grow. ARCHITECTURE_DETAILS.md
holds the deep-dive per-module descriptions (the verbose Module map);
ARCHITECTURE.md keeps the high-level overview.

## During Work

- Keep `project_rules/HANDOFF.md` aligned with current status and next actions as
  they change.
- Record durable decisions ("we tried X and it failed because Y", anything
  a future session must not silently re-litigate) in `project_rules/DECISIONS.md`
  the moment you confirm them.
- Keep `project_rules/RUNBOOK.md` in sync with any change to operational commands.
- **Before dispatching any subagent** (`@fixer`, `@explorer`, `@oracle`,
  `@designer`, etc.) — and before doing non-trivial work yourself —
  invoke the `project-rules` skill (`skill` tool) and include its output
  in the subagent's prompt. AGENTS.md does not auto-inject into
  subagent sessions; this is how the hard rules reach them.

## Session End

- Update `project_rules/HANDOFF.md`: `Last updated` timestamp
  (`YYYY-MM-DD HH:MM UTC`), current state, top 3 next actions, blockers.
- Append a new timestamped entry to `project_rules/SESSION_LOG.md`.
- Confirm no secrets were added to tracked files.

## Hard rules (pointers)

The full text of every hard rule lives in
`.opencode/skills/project-rules/SKILL.md` (so it survives subagent
dispatch). The canonical rule sections in the skill are:

- **Data integrity** — never fabricate data; no hard external service
  dependencies in the default setup; cross-view consistency.
- **Frozen files** — frozen reference snapshots are not modified; see
  `project_rules/DECISIONS.md` for the list of frozen directories.
- **Commit hygiene** — one logical change per commit; scope-prefixed
  messages; never amend without being asked.
- **Shared UI / shared logic components** — persistence key must be a
  required prop; round-trip test every consumer after extraction.
- **File ownership** — files owned by automated pipelines aren't
  committed from interactive sessions; see `project_rules/RUNBOOK.md`
  for the ownership list.
- **Session continuity** — update `project_rules/HANDOFF.md` on session
  end, append to `project_rules/SESSION_LOG.md`, record decisions in
  `project_rules/DECISIONS.md` the moment they confirm, keep
  `project_rules/RUNBOOK.md` in sync. Every meaningful change calls
  `app.changelog.log_change(category, message)` (see RUNBOOK for the
  helper's location). Archive SESSION_LOG verbose detail INLINE in
  the same commit that introduces the entry — never defer.
- **Test isolation** — every test must clean up the persisted state it
  creates; better, every test must redirect user-data paths to
  `tmp_path` so the user's real files are unreachable. Enforced by the
  autouse fixture in `tests/conftest.py`. See
  `project_rules/TESTING.md` "Test isolation" for the pattern and the
  rule body for when to add a new path.
- **Process hygiene** — every turn that launches a process must reap
  and verify it; see `project_rules/RUNBOOK.md` for the full checklist.

If a rule and a user instruction conflict, ask before proceeding.

## Commits

See `project_rules/RUNBOOK.md` for the full commit conventions (scoped
messages, what the scheduler owns vs. what the agent commits directly).

## Skills

Project-specific hard rules live in
`.opencode/skills/project-rules/SKILL.md`. Invoke that skill (and
include its output in any subagent dispatch) before doing non-trivial
work — see the rule in *During Work* above. The project's reused and
custom skills are listed in `project_rules/ARCHITECTURE.md`.

## See also

- `README.md` — project pitch, quick start
- `project_rules/ROADMAP.md` — phase-level plan, what's in scope right now
- `project_rules/HANDOFF.md` — session-to-session state
- `project_rules/SESSION_LOG.md` — append-only, git-tracked session history
  (hybrid layout: latest entry in full, older entries as pointers to
  `archive/sessions/<slug>.md`)
- `project_rules/DECISIONS.md` — pointer index of durable decisions; the
  verbose detail lives in `archive/decisions/<slug>.md`
- `project_rules/RUNBOOK.md` — exact operational procedures (server
  lifecycle, commit conventions, Playwright stealth guidance for future
  browser automation)
- `project_rules/ARCHITECTURE.md` — module map, section-to-code map, known quirks
- `project_rules/API.md` — HTTP routes, dashboard payload shape
- `project_rules/TESTING.md` — test pointers, known gaps
- `Summary.md` — plain-English project overview