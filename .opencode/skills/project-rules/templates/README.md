# project-rules skill — templates

These nine files are the seed set the `project-rules` skill writes into
a fresh repo's working tree on bootstrap. Each file has `{{...}}`
placeholders for values the agent collects at bootstrap time
(typically by asking the user, or by reading `git config --get
remote.origin.url`) and `> AGENT: …` callouts for sections that
need to be filled in as the project develops (the bootstrap itself
doesn't fabricate project-specific content).

## The set

| File | Purpose | Frequency of update |
|------|---------|---------------------|
| `AGENTS.md` | Session protocol + commit conventions + hard-rule pointers (only file at repo root) | rarely (only when workflow changes) |
| `project_rules/HANDOFF.md` | Last session's state + top 3 next actions + blockers | every session end |
| `project_rules/SESSION_LOG.md` | Append-only dated log of what each session did (hybrid layout: latest in full, older entries as pointers to `archive/sessions/<slug>.md`) | every session |
| `project_rules/DECISIONS.md` | Pointer index of durable decisions (verbose detail in `archive/decisions/<slug>.md`) | every confirmed decision |
| `project_rules/RUNBOOK.md` | Run commands + operational checklist + commit conventions | every operational-command change |
| `project_rules/ROADMAP.md` | Phase-level plan; current phase + risks at top | end of each phase |
| `project_rules/ARCHITECTURE.md` | Stack overview, module map, section-to-code map, known quirks | when the module layout or stack changes |
| `project_rules/ARCHITECTURE_DETAILS.md` | (Optional) Deep-dive per-module descriptions — split off from `ARCHITECTURE.md` when it crosses `{{DOC_LINE_THRESHOLD}}` lines | when ARCHITECTURE.md is split |
| `project_rules/API.md` | HTTP routes, payload shape, error contract | when routes are added / changed |
| `project_rules/TESTING.md` | Suite layout, conventions, known gaps | when test coverage changes |

The four `project_rules/` docs marked *conditional* — `ARCHITECTURE.md`,
`ARCHITECTURE_DETAILS.md` (only if the split happened), `API.md`,
`TESTING.md` — the bootstrap should ask the user which apply. A CLI or
library won't need `API.md`; a frontend-less backend project might skip
`TESTING.md`. Edit the `AGENTS.md` "See also" list at bootstrap to drop
the ones not written.

`AGENTS.md` is the only file the skill writes at the repo root; all
nine `project_rules/*.md` files (and the two `archive/` sub-folders)
live under `project_rules/`. This keeps the repo root uncluttered
and groups the docs the skill owns together.

## Archive folders (created by the pointer / hybrid patterns)

Two of the files above use a **live-index + archive** layout to keep
session-start reads cheap. The skill does not ship these archive
folders as templates — they're populated by the live files as entries
accumulate.

- `project_rules/archive/decisions/` — one file per durable decision
  (`<slug>.md`). Populated as DECISIONS.md entries grow. Each file
  holds the full verbose text; DECISIONS.md itself stays a pointer
  index. See `templates/project_rules/DECISIONS.md` for the entry
  shape.
- `project_rules/archive/sessions/` — one file per past session
  (`<slug>.md`). Populated as SESSION_LOG.md rotates the older
  entries out of the live file. The live file keeps the latest
  entry in full; older entries become pointers. See
  `templates/project_rules/SESSION_LOG.md` for the rotation workflow.

## Placeholders the agent substitutes at bootstrap

| Placeholder | Source |
|-------------|--------|
| `{{REPO_NAME}}` | `git config --get remote.origin.url` (parse `org/repo`) |
| `{{REPO_DISPLAY_NAME}}` | Ask user; default to remote description or directory name |
| `{{DATA_DIR}}` | Default `data` |
| `{{SERVER_COMMAND}}` | Ask user; empty if the project has no server |
| `{{FROZEN_HTML_DIR}}` | Default `archive`; empty if no frozen-reference files |
| `{{DOC_LINE_THRESHOLD}}` | Default `200`; tune per-project if the docs set is unusually large or small |
| `{{SESSION_LOG_ROTATION_ENTRIES}}` | Default `10`; bump for long-running projects that want a longer live log |

Plus the per-template placeholders (`{{MODULE_PATH}}`, `{{BASE_URL}}`,
`{{TEST_COMMAND}}`, etc.) that each template's AGENT stub explains
how to fill in.

## What is NOT templated

Project-specific domain docs (`SUMMARY.md`, contribution guides,
deployment runbooks, etc.). The skill's templates cover the docs that
every project needs; anything project-specific is the user's job to
add (and reference from `AGENTS.md` "See also").

## Customising

Adding a new template file is fine. Update the Bootstrap section of
`SKILL.md` to list the new file in step 2 (read templates) and step
4 (write to repo), then add it to this README's table.
