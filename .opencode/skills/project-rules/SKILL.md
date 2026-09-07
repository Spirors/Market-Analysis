---
name: project-rules
description: Hard rules + session-continuity scaffolding for any project. In a fresh repo, invoke this skill to scaffold AGENTS.md + project_rules/ with placeholder seed files. In an existing repo, load before any non-trivial work so the universal hard rules reach every agent (especially subagents that don't auto-inject AGENTS.md).
---

# Initialisation

This skill is portable. Before loading it into a new repo, replace these
placeholders with the new repo's values (search for `{{...}}` throughout
this file). Defaults are shown in the table below.

| Placeholder | Meaning | Suggested default |
|-------------|---------|----------------------|
| `{{REPO_NAME}}` | Full GitHub-style repo identifier (`org/name`). | `<org>/<repo>` |
| `{{REPO_DISPLAY_NAME}}` | Human-readable project name used in titles and commit scope prefixes. | `<Project Name>` |
| `{{DATA_DIR}}` | Directory holding the local JSON cache, pid file, and daily changelog. | `data` |
| `{{SERVER_COMMAND}}` | Command used to start the local dev server (and any sub-flags referenced). | `<server-start-command>` |
| `{{FROZEN_HTML_DIR}}` | Directory holding reference HTML snapshots that must never be edited. | `archive` |

The skill body is project-agnostic by design. Repo-specific files
(`app/`, `src/`, `static/js/`, etc.) are not mentioned by path — when a
rule needs to anchor to a file, the agent identifies that file from the
repo's own layout.

---

# Bootstrap — use this skill to scaffold a new repo

If the repo doesn't yet have an `AGENTS.md` or a `project_rules/`
directory, this is what to do.

## Steps the agent performs on invocation

1. **Ask the user for the bootstrap values** that aren't derivable from
   the working tree:
   - `{{REPO_DISPLAY_NAME}}` — the human-readable project name. If a
     remote exists, use the repo's GitHub description or the directory
     name as a default.
   - `{{REPO_NAME}}` — derivable from `git config --get remote.origin.url`
     in most cases.
   - `{{SERVER_COMMAND}}` — only if the project will run a server.
   - `{{DATA_DIR}}` — default `data` is fine for most projects.
   - `{{FROZEN_HTML_DIR}}` — only if the project ships frozen reference
     snapshots.
2. **Read every file in `templates/`** (this skill ships with them):
   - `templates/AGENTS.md`
   - `templates/ARCHITECTURE.md`
   - `templates/API.md`
   - `templates/TESTING.md`
   - `templates/project_rules/HANDOFF.md`
   - `templates/project_rules/SESSION_LOG.md`
   - `templates/project_rules/DECISIONS.md`
   - `templates/project_rules/RUNBOOK.md`
   - `templates/project_rules/ROADMAP.md`
3. **Substitute every `{{...}}` placeholder** with the bootstrap values.
4. **Write the substituted files** to the repo at the corresponding
   paths (`AGENTS.md`, `ARCHITECTURE.md`, `API.md`, `TESTING.md` at
   repo root; `project_rules/*.md` under a new `project_rules/`
   directory). Create `project_rules/archive/` if the SESSION_LOG
   template references it. The agent should ask the user before
   writing any of the three root-level files (ARCHITECTURE / API /
   TESTING) that don't apply to the project — a CLI or library won't
   need `API.md`, for example; the AGENTS.md "See also" list should
   be edited to drop the ones not written.
5. **Confirm to the user**: list the files created and remind them to
   edit each placeholder section as the project develops.

## What the bootstrap is not

The bootstrap does not commit anything. It writes working-tree files
and reports. The user (or the agent, on instruction) reviews the
generated content and commits it themselves — the first commit message
typically looks like:

```
chore(docs): initialise AGENTS.md + project_rules/ via project-rules skill
```

## After the bootstrap

Each generated file has at least one placeholder section explicitly
marked `> AGENT: replace this stub as the project develops`. The agent
fills those in during normal work (DECISIONS entries on every durable
choice, HANDOFF on session end, etc.). The bootstrap is hands-off after
the initial write — the skill's rules (below) govern how each file
gets maintained.

---

# Core rules (universal — apply to any project)

These are the non-negotiable rules. Treat any violation as a bug. If a
rule and a user instruction conflict, ask before proceeding.

---

## Data integrity

- **Never fabricate data the system should fetch.** Every figure the
  system presents must trace to a fetched source, stamped with an "as
  of" timestamp. If a source is unavailable, mark the value `null` /
  `—` — never invent a number to fill the gap.
- **No hard external service dependencies in the default setup.** Free,
  no-key sources only (open data feeds, public APIs, RSS, etc.). Paid
  keys can be plugged in later but introduce licensing cost and
  supply-chain risk — a project that stops working when a free tier is
  rate-limited has a hidden dependency. If you must accept a paid
  source, make sure every code path has a free-source fallback that
  surfaces the missing data as `null`, not as an error.
- **Cross-view consistency.** Numbers and names that appear in multiple
  views must agree. If you change a value in one place, find every other
  place it appears and update them in the same change.

## Frozen files

- **Anything under `{{FROZEN_HTML_DIR}}/` (or an analogous "do not edit"
  directory) is frozen reference material.** Adapting these files
  silently corrupts the design system they encode. If a refactor
  conflicts with a frozen file, the refactor loses — find another way.
- **Historical decisions, prompts, and templates that seeded the
  current workflow are also frozen.** They document how the project got
  to its current shape; editing them rewrites history. Cite them from
  new docs instead of mutating them.

## Commit hygiene

- **One logical change per commit.** Don't bundle a refactor with a bug
  fix. Fix the bug, verify, commit. Refactor separately.
- Scope-prefixed messages: `feat(scope): ...`, `fix(scope): ...`,
  `chore(scope): ...`, `docs(scope): ...`, `refactor(scope): ...`,
  `test(scope): ...`. The scope identifies the area of the codebase.
- Never amend an existing commit unless explicitly asked.
- Code, config, `AGENTS.md`, and `project_rules/` changes commit
  immediately after verification — these are the project's working
  memory, not the kind of change you batch for later.

## Shared UI / shared logic components

- **Shared components must take their persistence key as a required
  prop, never hardcode or default it.** When two sections share a
  component (e.g. a table component consumed by both "Earnings" and
  "Portfolio", a logger consumed by two subsystems), a hardcoded or
  default key silently merges state across every caller. State keys
  must stay keyed per-consumer.
- **After any shared-component extraction: round-trip test every
  consumer independently.** For each one: change something → reload →
  confirm the same state comes back, for *that specific consumer*.
  Cross-contamination between consumers sharing one component is the
  single most common bug class from this kind of refactor.

## File ownership

- **Files written by automated pipelines (scheduled tasks, watchers,
  CI-side jobs) are not for interactive sessions to commit.** Unstaged
  timestamp updates in your working tree are normal for those files —
  ignore them, or let the pipeline's commit job pick them up at the
  next run. If you must edit such a file by hand, coordinate with the
  pipeline owner so the next automated run doesn't clobber your change.

## Session continuity

- **Update `project_rules/HANDOFF.md` at session end.** Include:
  `Last updated` timestamp (`YYYY-MM-DD HH:MM UTC`), current state,
  top 3 next actions, blockers.
- **Append a new entry to `project_rules/SESSION_LOG.md`** dated and
  titled so a future session can scan the latest entry alone — don't
  force them to re-read the whole log. Older entries rotate to
  `project_rules/archive/session-log-archive.md` once the live log
  exceeds ~10 entries.
- **Record durable decisions in `project_rules/DECISIONS.md` the
  moment you confirm them** — not from memory later. Each entry keeps
  the core problem, the decision, and especially the rationale
  ("mistakes to avoid" framing). Don't delete superseded entries; mark
  them superseded so the history of *why* stays intact.
- **Keep `project_rules/RUNBOOK.md` in sync with any operational-
  command change.** A runbook that drifts from the actual commands is
  worse than no runbook at all.
- **Hard rules propagate through this skill, not through AGENTS.md
  alone.** AGENTS.md auto-injects into the parent orchestrator but
  **not** into subagent sessions. Whenever you dispatch a subagent,
  include this skill's content in the dispatch prompt (the parent
  orchestrator should do this automatically when it sees the
  `project-rules` skill listed in AGENTS.md). The skill survives
  subagent dispatch; AGENTS.md does not.
- **Every meaningful change must call the project's changelog
  helper** (typically `app.changelog.log_change(category, message)` or
  the equivalent) so it lands in the local daily changelog
  (`{{DATA_DIR}}/logs/summary-YYYY-MM-DD.md`, gitignored). The
  changelog is a quick local audit trail, not a substitute for
  `project_rules/SESSION_LOG.md` (git-tracked, survives across
  machines).

## Process hygiene

- **Every turn that launches a process must reap and verify it before
  ending.** "Agent forgot to reap" is the single most common bug
  class in long-running agent workflows. Verify port-release and
  process-gone before the turn ends. For projects that ship a
  `project_rules/RUNBOOK.md`, the full checklist lives there — this
  rule points you to it; the runbook enforces the how.
- **Subagent dispatches must include the rules they need.** Static
  context loses to dynamic task context under load. Hand the relevant
  rules to the subagent inline in the dispatch prompt, not via a
  reference they may not follow.
