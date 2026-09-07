# project-rules skill — templates

These six files are the seed set the `project-rules` skill writes into
a fresh repo's working tree on bootstrap. Each file has `{{...}}`
placeholders for values the agent collects at bootstrap time
(typically by asking the user, or by reading `git config --get
remote.origin.url`) and `> AGENT: …` callouts for sections that
need to be filled in as the project develops (the bootstrap itself
doesn't fabricate project-specific content).

## The set

| File | Purpose | Frequency of update |
|------|---------|---------------------|
| `AGENTS.md` | Session protocol + commit conventions + hard-rule pointers | rarely (only when workflow changes) |
| `project_rules/HANDOFF.md` | Last session's state + top 3 next actions + blockers | every session end |
| `project_rules/SESSION_LOG.md` | Append-only dated log of what each session did | every session |
| `project_rules/DECISIONS.md` | Durable decisions + their rationale (mistakes to avoid) | every confirmed decision |
| `project_rules/RUNBOOK.md` | Run commands + operational checklist + commit conventions | every operational-command change |
| `project_rules/ROADMAP.md` | Phase-level plan; current phase + risks at top | end of each phase |

## Placeholders the agent substitutes at bootstrap

| Placeholder | Source |
|-------------|--------|
| `{{REPO_NAME}}` | `git config --get remote.origin.url` (parse `org/repo`) |
| `{{REPO_DISPLAY_NAME}}` | Ask user; default to remote description or directory name |
| `{{DATA_DIR}}` | Default `data` |
| `{{SERVER_COMMAND}}` | Ask user; empty if the project has no server |
| `{{FROZEN_HTML_DIR}}` | Default `archive`; empty if no frozen-reference files |

## What is NOT templated

- Project-specific architecture, API surface, testing strategy, etc.
  — those are repo-specific docs the project authors write themselves
  (`ARCHITECTURE.md`, `API.md`, `TESTING.md`, etc.). The bootstrap
  mentions them in `AGENTS.md` "See also" so they get linked from
  Session Start but doesn't generate them.

## Customising

Adding a new template file is fine. Update the Bootstrap section of
`SKILL.md` to list the new file in step 2 (read templates) and step
4 (write to repo).
