# AGENTS.md

AI-readable reference for **{{REPO_DISPLAY_NAME}}**. This file holds
the session protocol and commit conventions. All hard rules (data
integrity, commit hygiene, frozen files, shared components, session
continuity, etc.) live in the `project-rules` skill — load it via
the `skill` tool before any non-trivial work and pass it to every
subagent dispatch.

> AGENT: replace this stub with a 2-3 sentence description of what
> this project IS — its purpose, audience, and the rough shape of
> the codebase. Keep it concrete; vague intros age badly.

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
8. The `project-rules` skill (via the `skill` tool) — load once per session
   so the hard rules are top-of-context

`ARCHITECTURE.md`, `API.md`, and `TESTING.md` (if present) are **not**
part of this list — read them on demand when a task actually touches
that area, to keep session-start cost low as the docs grow.

## During Work

- Keep `project_rules/HANDOFF.md` aligned with current status and next actions
  as they change.
- Record durable decisions ("we tried X and it failed because Y", anything
  a future session must not silently re-litigate) in `project_rules/DECISIONS.md`
  the moment you confirm them.
- Keep `project_rules/RUNBOOK.md` in sync with any operational-command change.
- **Before dispatching any subagent** (fixer, explorer, oracle, designer, etc.)
  — and before doing non-trivial work yourself — invoke the `project-rules`
  skill and include its output in the subagent's prompt. AGENTS.md does not
  auto-inject into subagent sessions; this is how the hard rules reach them.

## Session End

- Update `project_rules/HANDOFF.md`: `Last updated` timestamp
  (`YYYY-MM-DD HH:MM UTC`), current state, top 3 next actions, blockers.
- Append a new timestamped entry to `project_rules/SESSION_LOG.md`.
- Confirm no secrets were added to tracked files.

## Hard rules (pointers)

The full text of every hard rule lives in the `project-rules` skill
(so it survives subagent dispatch). Load the skill once per session
for the canonical text. As a quick reference, the rule areas are:

- **Data integrity** — never fabricate data; no hard external service
  dependencies in the default setup; cross-view consistency.
- **Frozen files** — anything under the frozen-reference directory is
  not modified.
- **Commit hygiene** — one logical change per commit; scope-prefixed
  messages; never amend without being asked.
- **Shared components** — persistence key must be a required prop;
  round-trip test every consumer after extraction.
- **File ownership** — files written by automated pipelines aren't
  committed from interactive sessions.
- **Session continuity** — update HANDOFF on session end, append to
  SESSION_LOG, record decisions in DECISIONS the moment they confirm,
  keep RUNBOOK in sync.
- **Process hygiene** — every launched process must be reaped and
  verified before the turn ends.

If a rule and a user instruction conflict, ask before proceeding.

## Commits

See `project_rules/RUNBOOK.md` for the full commit conventions (scoped
messages, what the scheduler owns vs. what the agent commits directly).

## Skills

> AGENT: list the project's skills here — both custom skills shipped
> under `.opencode/skills/` and any external skills the project relies
> on (e.g. domain-analysis skills). One line per skill is enough; link
> the skill's `SKILL.md` if it's non-obvious how to use it.

**Project-specific hard rules live in the `project-rules` skill.**
Invoke it (and include its output in any subagent dispatch) before
doing non-trivial work — see the rule in *During Work* above.

## See also

- `README.md` — project pitch, quick start
- `project_rules/ROADMAP.md` — phase-level plan, what's in scope right now
- `project_rules/HANDOFF.md` — session-to-session state
- `project_rules/SESSION_LOG.md` — append-only, git-tracked session history
- `project_rules/DECISIONS.md` — durable decisions and confirmed root causes
- `project_rules/RUNBOOK.md` — exact operational procedures
- `ARCHITECTURE.md` — module map, section-to-code map (if exists)
- `API.md` — HTTP routes, payload shape (if exists)
- `TESTING.md` — test pointers, known gaps (if exists)
- `SUMMARY.md` — plain-English project overview (if exists)
