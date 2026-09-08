---
name: project-rules
description: Hard rules + session-continuity scaffolding for any project. In a fresh repo, invoke this skill to scaffold AGENTS.md + project_rules/ with placeholder seed files. In a repo with an existing AGENTS.md, use retrofit mode to classify each section, extract project-specific material into project_rules/, and rewrite the root file down to hard-rule pointers + a see-also index. In an existing repo, load before any non-trivial work so the universal hard rules reach every agent (especially subagents that don't auto-inject AGENTS.md).
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
| `{{DOC_LINE_THRESHOLD}}` | Line count at which `AGENTS.md` or a `project_rules/*.md` file is considered for a Documentation-hygiene self-check split. See Core rules → Documentation hygiene. | `200` |
| `{{SESSION_LOG_ROTATION_ENTRIES}}` | Number of dated entries the live `project_rules/SESSION_LOG.md` may carry before older entries move to `project_rules/archive/sessions/<slug>.md`. | `10` |

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
   - `templates/project_rules/HANDOFF.md`
   - `templates/project_rules/SESSION_LOG.md`
   - `templates/project_rules/DECISIONS.md`
   - `templates/project_rules/RUNBOOK.md`
   - `templates/project_rules/ROADMAP.md`
   - `templates/project_rules/ARCHITECTURE.md`
   - `templates/project_rules/API.md`
   - `templates/project_rules/TESTING.md`
3. **Substitute every `{{...}}` placeholder** with the bootstrap values.
4. **Write the substituted files** to the repo at the corresponding
   paths: `AGENTS.md` at repo root; everything else under a new
   `project_rules/` directory. Create `project_rules/archive/` if
   the SESSION_LOG template references it. The agent should ask the
   user before writing any of `project_rules/ARCHITECTURE.md`,
   `project_rules/API.md`, `project_rules/TESTING.md` that don't
   apply to the project — a CLI or library won't need `API.md`, for
   example; the `AGENTS.md` "See also" list should be edited to drop
   the ones not written.
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

# Retrofit — use this skill to split a bloated AGENTS.md

Most real repos already have an `AGENTS.md` — usually one that has
grown to a few hundred lines and mixes universal hard rules with
project-specific reference material. Fresh-bootstrap mode cannot
help those repos. Retrofit mode can.

## When to use retrofit instead of bootstrap

- **Bootstrap**: repo has no `AGENTS.md` or no `project_rules/`.
  Write from the templates, substitute placeholders, stop.
- **Retrofit**: repo already has `AGENTS.md` (and probably some
  `project_rules/` files). Read what exists, classify every
  section, extract or merge, then rewrite the root file down to
  hard-rule pointers + a "see also" index.

## Steps the agent performs on invocation

1. **Inventory first.** Read the existing `AGENTS.md` and every
   existing `project_rules/*.md` before changing anything. Note
   line counts and which files already exist. The retrofit is
   lossless for project-specific content — you cannot inventory
   what you have not read.

2. **Classify each section of the existing `AGENTS.md`** into
   one of three buckets:

   - **(a) Universal hard rule** — a statement that would apply
     to *any* project (data-integrity rules, commit hygiene,
     session continuity, the subagent-dispatch propagation rule,
     etc.) that is not already covered by this skill's Core
     rules. Propose merging it into the corresponding Core-rules
     section. List the proposed additions for user confirmation
     before editing `SKILL.md` itself; never silently grow the
     skill's rule body with project-specific phrasing.

   - **(b) Project-specific reference material** — architecture
     map, API routes, test suite layout, stack list, project-
     specific skills, module-to-code maps, deployment notes —
     anything that describes *this* codebase rather than
     universal workflow. Extract verbatim into the matching
     `project_rules/{ARCHITECTURE,API,TESTING,DECISIONS}.md`,
     creating whichever file does not exist yet. When in doubt
     about which file, default to `ARCHITECTURE.md` (the
     catch-all for project-specific reference).

   - **(c) Stale or derivable content** — hardcoded `git log`
     snapshots, one-off commit lists, raw changelogs, anything
     the agent can regenerate from `git` or from another
     already-tracked file. Flag for **deletion** with a quoted
     reason; do not migrate this material into `project_rules/`.

3. **Present the plan to the user before writing anything.**
   Show the inventory, the three-bucket classification with line
   references, and which files will be created vs. appended vs.
   left alone. Wait for confirmation. Silent rewrites of a real
   repo's `AGENTS.md` are how trust in this skill gets lost.

4. **Apply the changes**, in this order:

   - Append `(b)` items to the matching `project_rules/*.md`
     files. **Never clobber `project_rules/DECISIONS.md`** —
     merge additively; if it already exists with content, append
     a dated `## Retrofit YYYY-MM-DD` section at the bottom and
     leave prior entries intact. The history of "why" stays
     readable.
   - For any `(a)` items the user confirms, edit `SKILL.md`
     Core rules to add them. The skill is the canonical home
     for universal rules; retrofit-extracted universal rules
     belong here, not in the target repo's `AGENTS.md`.
   - Rewrite `AGENTS.md` down to: a one-line pointer to the
     `project-rules` skill for hard rules, the session protocol
     (Session Start / During Work / Session End), and a "see
     also" index pointing at the new `project_rules/` files.
     Use the same template shape as bootstrap mode's output.
   - **Do not delete the `(c)` items.** Just leave them out
     of the rewritten `AGENTS.md`. If the user later asks to
     delete them, that is a separate `git rm` decision they
     own.

5. **Confirm to the user**: list every file touched (created,
   appended, rewritten) and explicitly remind them that
   `DECISIONS.md` entries were appended, not replaced.

## What retrofit is not

- **Not an automatic formatter.** Every classification is a
  judgment call. Always present the plan and wait for
  confirmation — never silently rewrite a real repo's
  `AGENTS.md`.
- **Not a history rewrite.** Retrofitting extracts content; it
  does not compress or rewrite prior entries in any
  `project_rules/*.md` file. `DECISIONS.md` especially must
  keep its history of "why" intact.
- **Not a substitute for the documentation-hygiene self-check**
  that prevents the next bloat cycle. After retrofitting, the
  threshold self-check rule (see Core rules → Documentation
  hygiene) is what keeps the file from growing back to the
  same bloated shape.

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
  force them to re-read the whole log.
- **SESSION_LOG.md uses a hybrid layout to keep session-start reads
  cheap.** The latest entry stays in full (it's the one agents read
  per the AGENTS.md Session Start protocol); older entries in the
  live file are pointers — title, date, one-line summary, link to
  `archive/sessions/<slug>.md`. The verbose detail (test breakdowns,
  commit hashes, file:line references) lives in the per-session
  archive file. When the live file exceeds
  `{{SESSION_LOG_ROTATION_ENTRIES}}` entries, drop the oldest pointer
  — the archive file is the source of truth for the dropped session.
- **Archive the verbose detail INLINE — same commit as the SESSION_LOG
  entry that introduces it.** When you ship a feature, the commit
  that adds the verbose SESSION_LOG entry MUST also create the
  matching `archive/sessions/<slug>.md` file. When a newer commit
  takes the "latest" spot (pushing your entry down), the same commit
  MUST convert your entry to a pointer in the live file and link to
  the archive file already on disk. Never leave a verbose entry
  behind "to convert later" — drift accumulates silently and the
  live file bloats until a session-end audit has to clean it up.
  The conversion is part of the work, not a follow-up.
- **Record durable decisions in `project_rules/DECISIONS.md` the
  moment you confirm them** — not from memory later. Each entry keeps
  the core problem, the decision, and especially the rationale
  ("mistakes to avoid" framing). Don't delete superseded entries; mark
  them superseded so the history of *why* stays intact.
- **DECISIONS.md is a pointer index, not a wall of prose.** Each entry
  in the live file is a short pointer — title, date, status, one-
  sentence summary, and a link. The verbose detail (code snippets,
  test breakdowns, verification matrices, file:line references) lives
  in `archive/decisions/<slug>.md`. Decisions do not rotate; they
  accumulate. The pattern keeps the live file scannable at session
  start while preserving the full rationale for when an agent is
  actually implementing or debugging.
- **DECISIONS.md summaries are one sentence each, no exceptions —
  archive the verbose detail INLINE in the same commit.** The
  one-sentence pointer lives in the live file; the rationale, code
  references, file:line citations, and verification matrix go in
  `archive/decisions/<slug>.md` at the SAME commit that introduces
  the DECISIONS entry. Never commit a multi-paragraph summary "to
  convert later" — the conversion never happens, the live file
  bloats, and a session-end audit has to retrofit the verbose detail.
  Same pattern as the SESSION_LOG archive-inline rule above.
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

## Documentation hygiene

- **Line count is a diagnostic symptom, not a target.** Do not
  split a file just to hit a number — split it when a section
  stops being needed on every read. The goal for `AGENTS.md` is
  the WHAT/WHY/HOW shape (a short project description, a one-line
  pointer to the skill for hard rules, the session protocol, a
  see-also index); the line count is a check that the goal is
  being met, not the goal itself. Aggressive deletion of real
  guardrails in pursuit of a smaller file is the failure mode
  this rule exists to prevent.
- **The SESSION_LOG archive pattern is general, not
  SESSION_LOG-specific.** Any `project_rules/*.md` that stops
  being "read in full, every time" can rotate to
  `project_rules/archive/<name>-archive.md` the same way
  `SESSION_LOG.md` does. The mechanism is the same: move older
  entries to the archive file, leave only the high-signal
  recent content in the live file, update the see-also index
  in `AGENTS.md` if the live file's purpose narrows. The
  threshold that triggers the rotation is per-project tunable
  via `{{SESSION_LOG_ROTATION_ENTRIES}}`.
- **Threshold self-check.** Periodically — and especially after
  any edit to `AGENTS.md` or a `project_rules/*.md` file — run
  `wc -l AGENTS.md project_rules/*.md` (or your shell's
  equivalent). If a file exceeds `{{DOC_LINE_THRESHOLD}}`
  lines *and* has grown materially since its last edit,
  **propose the split in that same session** rather than
  deferring it. Deferred cleanup is how `AGENTS.md` files reach
  400+ lines in the first place — the rule exists to break
  that loop. The split follows the Retrofit classifier: extract
  project-specific material to `project_rules/`, hoist
  universal rules into Core, flag derivable content for
  deletion.

## Process hygiene

- **Every turn that launches a process must reap and verify it before
  ending.** "Agent forgot to reap" is the single most common bug class
  in long-running agent workflows. Verify port-release and process-gone
  before the turn ends. For projects that ship a `project_rules/RUNBOOK.md`,
  the full checklist lives there — this rule points you to it; the
  runbook enforces the how.
- **Subagent dispatches must include the rules they need.** Static
  context loses to dynamic task context under load. Hand the relevant
  rules to the subagent inline in the dispatch prompt, not via a
  reference they may not follow.

## Test isolation

- **Tests must never touch the user's live data files.** Every test that
  creates persisted state (portfolios, events, prefs, analysis runs,
  changelog entries, etc.) is responsible for cleaning up after itself —
  but cleanup is best-effort. The *real* guarantee is that the test
  never *reaches* the user's files in the first place.
- **Default to redirecting every user-data path to a per-test temp
  directory.** The recommended enforcement is an autouse pytest fixture
  in a top-level `tests/conftest.py` that monkeypatches every module-
  level path constant (e.g. `app.portfolio.PORTFOLIOS_PATH`,
  `app.config.DATA_DIR`, `app.changelog.LOG_DIR`) to `tmp_path`.
  Per-test fixtures (e.g. `tmp_portfolios`) override the autouse; the
  autouse is the safety net that catches tests that forget.
- **Module-level path constants are evaluated at import time.**
  `PORTFOLIOS_PATH = config.DATA_DIR / "portfolios.json"` binds the path
  once when the module loads. Patching `config.DATA_DIR` later does NOT
  update `PORTFOLIOS_PATH` — you must patch the bound name on the
  importing module. Tests that rely on the wrong layer silently write to
  the real file.
- **Add a new path to the autouse fixture the same day you introduce
  it.** If you add a new `config.X = .../data/...` (or any other
  user-data path) and reference it as a module-level constant, add a
  `monkeypatch.setattr(...)` line to the autouse fixture in the same
  change. The fixture is the contract; an unpatched new path is a
  silent regression waiting for the next test run.
- **Read-only assets are exempt.** Static files (`static/index.html`,
  CSS, JS) and frozen reference material (`archive/`) are not user data
  and must not be redirected — only state that a test could *mutate*.

