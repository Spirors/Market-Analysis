# AGENTS.md

AI-readable reference for the Market Analysis Tool. This file holds the
session protocol, hard rules, and wiki knowledge-base pointers.
**The project's persistent memory lives in the wiki vault
(`Market-Analysis-Wiki/`)**, not in this file. 

Wiki pages (`Market-Analysis-Wiki/wiki/sources/<slug>.md`)
cite each source back to its canonical path + SHA-256 + immutable
capture (`.raw/captured/<sha>.md`).

## What this is

Local webapp for macro-trend market analysis (regime classification,
breadth/vol/yield indicators, chokepoint bottlenecks, filtered news
timeline, trend-shift risk-divergence engine). Free, no-key data
sources, runs entirely locally on Windows. See `README.md` for the
pitch and `Market-Analysis-Wiki/inbox/project_rules/ARCHITECTURE.md`
for the stack and module map.

## Session Start

Read in this exact order before doing anything else:

1. This file (`AGENTS.md`)
2. `README.md`
3. `Market-Analysis-Wiki/inbox/project_rules/ROADMAP.md` — current phase; only work inside it unless told otherwise
4. `Market-Analysis-Wiki/inbox/project_rules/HANDOFF.md` — where the last session left off
5. latest entry in `Market-Analysis-Wiki/inbox/project_rules/SESSION_LOG.md` (not the whole file — just the most recent dated entry)
6. `Market-Analysis-Wiki/inbox/project_rules/DECISIONS.md`
7. `Market-Analysis-Wiki/inbox/project_rules/RUNBOOK.md` — exact operational procedures

`Market-Analysis-Wiki/inbox/project_rules/ARCHITECTURE.md`,
`Market-Analysis-Wiki/inbox/project_rules/ARCHITECTURE_DETAILS.md`,
`Market-Analysis-Wiki/inbox/project_rules/API.md`, and
`Market-Analysis-Wiki/inbox/project_rules/TESTING.md` are **not** part of
this list — read them on demand when a task actually touches that
area, to keep session-start cost low as the docs grow.
ARCHITECTURE_DETAILS.md holds the deep-dive per-module descriptions
(the verbose Module map); ARCHITECTURE.md keeps the high-level
overview.

## During Work

- Keep `Market-Analysis-Wiki/inbox/project_rules/HANDOFF.md` aligned with
  current status and next actions as they change.
- Record durable decisions ("we tried X and it failed because Y",
  anything a future session must not silently re-litigate) in
  `Market-Analysis-Wiki/inbox/project_rules/DECISIONS.md` the moment you
  confirm them.
- Keep `Market-Analysis-Wiki/inbox/project_rules/RUNBOOK.md` in sync with
  any change to operational commands.

## Session End

- Update `Market-Analysis-Wiki/inbox/project_rules/HANDOFF.md`:
  `Last updated` timestamp (`YYYY-MM-DD HH:MM UTC`), current state, top
  3 next actions, blockers.
- Append a new timestamped entry to
  `Market-Analysis-Wiki/inbox/project_rules/SESSION_LOG.md`.
- Confirm no secrets were added to tracked files.

## Hard rules

These are the non-negotiable rules. Treat any violation as a bug. If a
rule and a user instruction conflict, ask before proceeding.

### Data integrity

- **Never fabricate data the system should fetch.** Every figure the
  system presents must trace to a fetched source, stamped with an "as
  of" timestamp. If a source is unavailable, mark the value `null` /
  `—` — never invent a number to fill the gap.
- **No hard external service dependencies in the default setup.**
  Free, no-key sources only (open data feeds, public APIs, RSS, etc.).
  Paid keys can be plugged in later but introduce licensing cost and
  supply-chain risk — a project that stops working when a free tier
  is rate-limited has a hidden dependency. If you must accept a paid
  source, make sure every code path has a free-source fallback that
  surfaces the missing data as `null`, not as an error.
- **Cross-view consistency.** Numbers and names that appear in
  multiple views must agree. If you change a value in one place, find
  every other place it appears and update them in the same change.

### Frozen files

- **The four `archive/ai_*.html` reference snapshots at the repo
  root are frozen material from a prior project** that seeded the
  analysis framework and design system. They must never be modified
  regardless of ongoing refactors. Any refactor that conflicts with a
  frozen file loses — find another way.
- **Historical decisions, prompts, and templates that seeded the
  current workflow are also frozen.** They document how the project
  got to its current shape; editing them rewrites history. Cite them
  from new docs instead of mutating them.

### Commit hygiene

- **One logical change per commit.** Don't bundle a refactor with a
  bug fix. Fix the bug, verify, commit. Refactor separately.
- Scope-prefixed messages: `feat(scope): ...`, `fix(scope): ...`,
  `chore(scope): ...`, `docs(scope): ...`, `refactor(scope): ...`,
  `test(scope): ...`. The scope identifies the area of the codebase.
- Never amend an existing commit unless explicitly asked.
- Code, config, `AGENTS.md`, and `Market-Analysis-Wiki/inbox/` changes
  commit immediately after verification — these are the project's
  working memory, not the kind of change you batch for later.

### Shared UI / shared logic components

- **Shared components must take their persistence key as a required
  prop, never hardcode or default it.** When two sections share a
  component (e.g. a table component consumed by both "Earnings" and
  "Portfolio", a logger consumed by two subsystems), a hardcoded or
  default key silently merges state across every caller. State keys
  must stay keyed per-consumer.
- **After any shared-component extraction: round-trip test every
  consumer independently.** For each one: change something → reload
  → confirm the same state comes back, for *that specific consumer*.
  Cross-contamination between consumers sharing one component is the
  single most common bug class from this kind of refactor.

### File ownership

- **Files written by automated pipelines (scheduled tasks, watchers,
  CI-side jobs) are not for interactive sessions to commit.** Unstaged
  timestamp updates in your working tree are normal for those files —
  ignore them, or let the pipeline's commit job pick them up at the
  next run. If you must edit such a file by hand, coordinate with the
  pipeline owner so the next automated run doesn't clobber your
  change.

### Session continuity

- **Update `Market-Analysis-Wiki/inbox/project_rules/HANDOFF.md` at
  session end.** Include: `Last updated` timestamp
  (`YYYY-MM-DD HH:MM UTC`), current state, top 3 next actions,
  blockers.
- **Append a new entry to
  `Market-Analysis-Wiki/inbox/project_rules/SESSION_LOG.md`** dated and
  titled so a future session can scan the latest entry alone — don't
  force them to re-read the whole log.
- **SESSION_LOG.md uses a hybrid layout to keep session-start reads
  cheap.** The latest entry stays in full (it's the one agents read
  per the AGENTS.md Session Start protocol); older entries in the
  live file are pointers — title, date, one-line summary, link to
  `archive/sessions/<slug>.md`. The verbose detail (test breakdowns,
  commit hashes, file:line references) lives in the per-session
  archive file.
- **Archive the verbose detail INLINE — same commit as the
  SESSION_LOG entry that introduces it.** When you ship a feature,
  the commit that adds the verbose SESSION_LOG entry MUST also create
  the matching `archive/sessions/<slug>.md` file. When a newer commit
  takes the "latest" spot (pushing your entry down), the same commit
  MUST convert your entry to a pointer in the live file and link to
  the archive file already on disk. Never leave a verbose entry
  behind "to convert later" — drift accumulates silently and the live
  file bloats until a session-end audit has to clean it up. The
  conversion is part of the work, not a follow-up.
- **Record durable decisions in
  `Market-Analysis-Wiki/inbox/project_rules/DECISIONS.md` the moment you
  confirm them** — not from memory later. Each entry keeps the core
  problem, the decision, and especially the rationale ("mistakes to
  avoid" framing). Don't delete superseded entries; mark them
  superseded so the history of *why* stays intact.
- **DECISIONS.md is a pointer index, not a wall of prose.** Each
  entry in the live file is a short pointer — title, date, status,
  one-sentence summary, and a link. The verbose detail (code
  snippets, test breakdowns, verification matrices, file:line
  references) lives in `archive/decisions/<slug>.md`. Decisions do
  not rotate; they accumulate.
- **DECISIONS.md summaries are one sentence each, no exceptions —
  archive the verbose detail INLINE in the same commit.**
- **Keep `Market-Analysis-Wiki/inbox/project_rules/RUNBOOK.md` in sync
  with any change to operational-command change.** A runbook that
  drifts from the actual commands is worse than no runbook at all.
- **Every meaningful change must call the project's changelog
  helper** (typically `app.changelog.log_change(category, message)`
  or the equivalent) so it lands in the local daily changelog
  (`data/logs/summary-YYYY-MM-DD.md`, gitignored). The changelog is a
  quick local audit trail, not a substitute for the SESSION_LOG.

### Process hygiene

- **Every turn that launches a process must reap and verify it
  before ending.** "Agent forgot to reap" is the single most common
  bug class in long-running agent workflows. Verify port-release and
  process-gone before the turn ends. For projects that ship a
  RUNBOOK.md, the full checklist lives there — this rule points you
  to it; the runbook enforces the how.
- **Subagent dispatches must include the rules they need.** Static
  context loses to dynamic task context under load. Hand the
  relevant rules to the subagent inline in the dispatch prompt, not
  via a reference they may not follow.

### Test isolation

- **Tests must never touch the user's live data files.** Every test
  that creates persisted state (portfolios, events, prefs, analysis
  runs, changelog entries, etc.) is responsible for cleaning up
  after itself — but cleanup is best-effort. The *real* guarantee is
  that the test never *reaches* the user's files in the first place.
- **Default to redirecting every user-data path to a per-test temp
  directory.** The recommended enforcement is an autouse pytest
  fixture in a top-level `tests/conftest.py` that monkeypatches every
  module-level path constant (e.g. `app.portfolio.PORTFOLIOS_PATH`,
  `app.config.DATA_DIR`, `app.changelog.LOG_DIR`) to `tmp_path`.
- **Module-level path constants are evaluated at import time.**
  `PORTFOLIOS_PATH = config.DATA_DIR / "portfolios.json"` binds the
  path once when the module loads. Patching `config.DATA_DIR` later
  does NOT update `PORTFOLIOS_PATH` — you must patch the bound name
  on the importing module. Tests that rely on the wrong layer
  silently write to the real file.
- **Add a new path to the autouse fixture the same day you
  introduce it.** If you add a new `config.X = .../data/...` (or any
  other user-data path) and reference it as a module-level constant,
  add a `monkeypatch.setattr(...)` line to the autouse fixture in
  the same change. The fixture is the contract; an unpatched new
  path is a silent regression waiting for the next test run.
- **Read-only assets are exempt.** Static files (`static/index.html`,
  CSS, JS) and frozen reference material (`archive/`) are not user
  data and must not be redirected — only state that a test could
  *mutate*.

### Wiki knowledge-base sync

- **After any substantive edit to `Market-Analysis-Wiki/inbox/**/*.md`,
  invoke the `wiki-ingest` skill to fold the change into the vault.**
  See the Wiki section below.

### Documentation hygiene

- **Line count is a diagnostic symptom, not a target.** Do not split
  a file just to hit a number — split it when a section stops being
  needed on every read. The goal for `AGENTS.md` is the
  WHAT/WHY/HOW shape (a short project description, the session
  protocol, hard rules inline, the wiki knowledge-base pointer, a
  see-also index); the line count is a check that the goal is being
  met, not the goal itself. Aggressive deletion of real guardrails in
  pursuit of a smaller file is the failure mode this rule exists to
  prevent.
- **Threshold self-check.** Periodically — and especially after any
  edit to `AGENTS.md` or a `Market-Analysis-Wiki/inbox/**/*.md` file —
  run `wc -l` on each. If a file exceeds 200 lines *and* has grown
  materially since its last edit, propose the split in that same
  session rather than deferring it. Deferred cleanup is how files
  reach 400+ lines in the first place.

## Commits

See `Market-Analysis-Wiki/inbox/project_rules/RUNBOOK.md` for the full
commit conventions (scoped messages, what the scheduler owns vs.
what the agent commits directly).

## Wiki

This project's knowledge base lives in `Market-Analysis-Wiki/`,
managed by the claude-obsidian skill set. Source documents (former
`project_rules/` + `docs/`) have been moved to `Market-Analysis-Wiki/inbox/`,
preserving their original directory structure.
- After any substantive edit to `Market-Analysis-Wiki/inbox/**/*.md`,
  invoke the `wiki-ingest` skill to fold the change in.
- Before answering questions about roadmap, past decisions,
  architecture, or methodology, invoke `wiki-query` against the vault
  instead of re-deriving from scratch.
- Run `wiki-lint` at the end of a session or on request.
- Vault writes require WSL on this machine — read-only queries work
  natively.

## See also

- `README.md` — project pitch, quick start
- `Market-Analysis-Wiki/inbox/project_rules/ROADMAP.md` — phase-level plan, what's in scope right now
- `Market-Analysis-Wiki/inbox/project_rules/HANDOFF.md` — session-to-session state
- `Market-Analysis-Wiki/inbox/project_rules/SESSION_LOG.md` — append-only, git-tracked session history (hybrid layout: latest entry in full, older entries as pointers to `archive/sessions/<slug>.md`)
- `Market-Analysis-Wiki/inbox/project_rules/DECISIONS.md` — pointer index of durable decisions; the verbose detail lives in `archive/decisions/<slug>.md`
- `Market-Analysis-Wiki/inbox/project_rules/RUNBOOK.md` — exact operational procedures (server lifecycle, commit conventions, Playwright stealth guidance for future browser automation)
- `Market-Analysis-Wiki/inbox/project_rules/ARCHITECTURE.md` — module map, section-to-code map, known quirks
- `Market-Analysis-Wiki/inbox/project_rules/ARCHITECTURE_DETAILS.md` — deep-dive per-module descriptions
- `Market-Analysis-Wiki/inbox/project_rules/API.md` — HTTP routes, dashboard payload shape
- `Market-Analysis-Wiki/inbox/project_rules/TESTING.md` — test pointers, known gaps
- `Market-Analysis-Wiki/wiki/index.md` — wiki catalog (after `wiki-ingest`)
- `Market-Analysis-Wiki/wiki/hot.md` — recent context (after `wiki-ingest`)
- `Market-Analysis-Wiki/wiki/log.md` — wiki operation log
- `Market-Analysis-Wiki/wiki/sources/<slug>.md` — 99 source pages with citations back to originals
- `Market-Analysis-Wiki/.raw/captured/<sha>.md` — content-addressed immutable archive (one capture per source)
- `Summary.md` — plain-English project overview
