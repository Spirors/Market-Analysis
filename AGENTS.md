# AGENTS.md

AI-readable reference for the Market Analysis Tool. This file holds only
the session protocol and commit conventions. All hard rules (data
integrity, server lifecycle, frozen files, shared UI components,
tooltip-on-card-change, changelog logging, etc.) live in the
`project-rules` skill — see `.opencode/skills/project-rules/SKILL.md`
and the "Hard rules" pointers below.

## What this is

Local webapp for macro-trend market analysis (regime classification,
breadth/vol/yield indicators, chokepoint bottlenecks, filtered news
timeline, trend-shift risk-divergence engine). Free, no-key data sources,
runs entirely locally on Windows. See `README.md` for the pitch and
`ARCHITECTURE.md` for the stack and module map.

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

`ARCHITECTURE.md`, `API.md`, and `TESTING.md` are **not** part of this list
— read them on demand when a task actually touches that area, to keep
session-start cost low as the docs grow.

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
dispatch). The canonical rule sections are:

- **Data integrity** — never fabricate market data; free, no-key sources
  only; cross-view consistency.
- **Frozen files** — the `archived/ai_*.html` reference snapshots and
  `archived/AGENT-WORKFLOW-PROMPT.md` are not modified.
- **Server lifecycle** — every turn that launches a process must reap
  and verify it; see `project_rules/RUNBOOK.md` for the full checklist.
- **File ownership** — `data/events.json` belongs to the scheduler task,
  not interactive sessions.
- **Commit hygiene** — one logical change per commit; scope-prefixed
  messages; never amend without being asked.
- **Shared UI components** — persistence key must be a required prop.
- **Card behavior + tooltip = same change** — update the matching
  tooltip file whenever card behavior changes.
- **Risk-gauge design** — RED fires on consensus optimism, not raw
  bearishness.
- **Commodities spot pricing** — FRED + Minted Metal, not `yfinance
  fast_info`.
- **Changelog logging** — every meaningful change must call
  `app.changelog.log_change(category, message)`.

If a rule and a user instruction conflict, ask before proceeding.

## Commits

See `project_rules/RUNBOOK.md` for the full commit conventions (scoped
messages, what the scheduler owns vs. what the agent commits directly).

## Skills

See `ARCHITECTURE.md` for the full reused/custom skills list
(`macro-regime-detector`, `serenity-chokepoint-investing`,
`macro-rates-monitor`, plus custom `.opencode/skills/`).

**Project-specific hard rules live in
`.opencode/skills/project-rules/SKILL.md`.** Invoke that skill (and
include its output in any subagent dispatch) before doing non-trivial
work — see the rule in *During Work* above.

## See also

- `README.md` — project pitch, quick start
- `project_rules/ROADMAP.md` — phase-level plan, what's in scope right now
- `project_rules/HANDOFF.md` — session-to-session state
- `project_rules/SESSION_LOG.md` — append-only, git-tracked session history
- `project_rules/DECISIONS.md` — durable decisions and confirmed root causes
- `project_rules/RUNBOOK.md` — exact operational procedures (server
  lifecycle, commit conventions, Playwright stealth guidance for future
  browser automation)
- `ARCHITECTURE.md` — module map, section-to-code map, known quirks
- `API.md` — HTTP routes, dashboard payload shape
- `TESTING.md` — test pointers, known gaps
- `Summary.md` — plain-English project overview
- Historical one‑off logs are in `docs/logs/` – load on demand only.
