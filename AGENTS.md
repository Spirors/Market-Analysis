# AGENTS.md

AI-readable reference for the Market Analysis Tool. Session protocol, hard
rules, and wiki pointers. **The project's persistent memory lives in the wiki
vault (`Market-Analysis-Wiki/wiki/`), not in this file.**

## What this is

Local webapp for macro-trend market analysis (regime classification,
breadth/vol/yield indicators, chokepoint bottlenecks, filtered news
timeline, trend-shift risk-divergence engine). Free, no-key data sources,
runs entirely locally on Windows. See `README.md` for the pitch and the
wiki at `Market-Analysis-Wiki/wiki/overview.md` for the knowledge-base
structure.

## Session protocol

**Start.** Read `Market-Analysis-Wiki/wiki/hot.md` (≤ 500 words). If the task
domain is unclear, read `wiki/index.md` next. Do **not** read
`Market-Analysis-Wiki/inbox/project_rules/` — frozen archive, canonicalised in
`wiki/sources/`.

**During work.** The Orchestrator triggers `wiki-ingest` / `save` / `wiki-fold`
transactions that update `log.md`, `index.md`, and the meta ledgers atomically.
Do **not** hand-edit `wiki/log.md` — the transaction owns it. Durable
decisions become individual source pages under `wiki/sources/` and appear
under `### decision (47)` in `wiki/index.md`.

**End.** Fires when the Orchestrator is about to send a final response to a
non-trivial turn (no follow-up, no in-progress todos, no running background
tasks) **or** when the user explicitly closes the session. See
`wiki/meta/session-memory-protocol.md` for the full trigger set. At session
end: rewrite `wiki/hot.md` (always **last**), append one entry to
`wiki/log.md`.

## Sub-agent rules

- **Only the Orchestrator writes to the wiki.** Sub-agents (Explorer,
  Oracle, Librarian, Fixer, Designer, Observer) are read-only on the wiki
  and on user-data files. Sub-agent drafts return to the Orchestrator,
  which applies them in one transaction.
- **Sub-agents do not read the wiki on their own.** The Orchestrator
  passes relevant wiki context **inline in the dispatch prompt**
  (page slugs, line ranges, short quotes).
- **Explorer is grep / ast_grep / glob only** over the working tree.
  Dispatch Explorer for codebase recon; dispatch Librarian for external
  docs; dispatch Oracle for architecture / risk / review.
- Sub-agent dispatch prompts must include the relevant hard rules inline
  (the sub-agent does not see `AGENTS.md`).

## Hard rules

These are non-negotiable. Treat any violation as a bug. If a rule and a
user instruction conflict, ask before proceeding.

### Data integrity

- **Never fabricate data the system should fetch.** Every figure the
  system presents must trace to a fetched source, stamped with an "as
  of" timestamp. If a source is unavailable, mark the value `null` / `—`
  — never invent a number to fill the gap.
- **No hard external service dependencies in the default setup.** Free,
  no-key sources only. Paid keys can be plugged in later but introduce
  licensing cost and supply-chain risk. Every paid-source code path must
  have a free-source fallback that surfaces the missing data as `null`,
  not as an error.
- **Cross-view consistency.** Numbers and names that appear in multiple
  views must agree. If you change a value in one place, find every other
  place it appears and update them in the same change.

### Frozen files

- **The four `archive/ai_*.html` reference snapshots at the repo root
  are frozen material from a prior project.** They must never be
  modified regardless of ongoing refactors. Any refactor that conflicts
  with a frozen file loses — find another way.
- **Historical decisions, prompts, and templates that seeded the
  current workflow are also frozen.** They document how the project got
  to its current shape; editing them rewrites history. Cite them from
  new docs instead of mutating them.
- **The `Market-Analysis-Wiki/inbox/project_rules/` directory is a
  frozen archive.** Its content is canonicalised in
  `Market-Analysis-Wiki/wiki/sources/`. Do not edit or re-read originals
  as live context.

### Commit hygiene

- **One logical change per commit.** Don't bundle a refactor with a
  bug fix. Fix the bug, verify, commit. Refactor separately.
- Scope-prefixed messages: `feat(scope): ...`, `fix(scope): ...`,
  `chore(scope): ...`, `docs(scope): ...`, `refactor(scope): ...`,
  `test(scope): ...`.
- **Never amend an existing commit unless explicitly asked.**
- Code, config, `AGENTS.md`, and wiki files commit immediately after
  verification — these are the project's working memory.

### Shared UI / shared logic components

- **Shared components must take their persistence key as a required
  prop, never hardcode or default it.** When two sections share a
  component, a hardcoded or default key silently merges state across
  every caller. State keys must stay keyed per-consumer.
- **After any shared-component extraction: round-trip test every
  consumer independently.** For each one: change something → reload →
  confirm the same state comes back, for *that specific consumer*.
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

### Process hygiene

- **Every turn that launches a process must reap and verify it
  before ending.** "Agent forgot to reap" is the single most common
  bug class in long-running agent workflows. Verify port-release and
  process-gone before the turn ends. Full checklist in
  `Market-Analysis-Wiki/wiki/sources/project_rules__RUNBOOK.md`.
- **Subagent dispatches must include the rules they need.** Static
  context loses to dynamic task context under load. Hand the
  relevant rules to the subagent inline in the dispatch prompt, not
  via a reference they may not follow.

### Test isolation

- **Tests must never touch the user's live data files.** The *real*
  guarantee is that the test never *reaches* the user's files in the
  first place.
- **Default to redirecting every user-data path to a per-test temp
  directory.** Enforce via an autouse pytest fixture in a top-level
  `tests/conftest.py` that monkeypatches every module-level path
  constant (e.g. `app.portfolio.PORTFOLIOS_PATH`,
  `app.config.DATA_DIR`, `app.changelog.LOG_DIR`) to `tmp_path`.
- **Module-level path constants are evaluated at import time.**
  `PORTFOLIOS_PATH = config.DATA_DIR / "portfolios.json"` binds the
  path once when the module loads — patching `config.DATA_DIR` later
  does NOT update `PORTFOLIOS_PATH`. You must patch the bound name on
  the importing module, or the test silently writes to the real file.
- **Add a new path to the autouse fixture the same day you introduce
  it.** The fixture is the contract; an unpatched new path is a silent
  regression waiting for the next test run.
- **Read-only assets are exempt.** Static files (`static/index.html`,
  CSS, JS) and frozen reference material (`archive/`) are not user data
  and must not be redirected.

### Wiki knowledge-base sync

- **The wiki is the project's persistent memory.** Read paths point at
  `Market-Analysis-Wiki/wiki/` (hot / index / log / overview / sources /
  meta), never at the inbox originals.
- **After any substantive edit to a wiki page**, the wiki engine folds
  the change into the vault automatically; no manual `wiki-ingest`
  call is required.
- **Before answering questions about roadmap, past decisions,
  architecture, or methodology**, run a `wiki-query` against the
  vault instead of re-deriving from scratch.
- **Run `wiki-lint` at the end of a session** or on request.
- **Vault writes require WSL on this machine** — read-only queries
  work natively. See `wiki/sources/project_rules__RUNBOOK.md` for
  the launch path.

### Documentation hygiene

- **Line count is a diagnostic symptom, not a target.** Do not split
  a file just to hit a number — split it when a section stops being
  needed on every read. The goal for `AGENTS.md` is the
  WHAT/WHY/HOW shape.
- **Threshold self-check.** Periodically — and especially after any
  edit to `AGENTS.md` or a `wiki/**` file — run `wc -l` on each. If a
  file exceeds 200 lines *and* has grown materially since its last
  edit, propose the split in that same session rather than deferring
  it.

## Commits

See `wiki/sources/project_rules__RUNBOOK.md` (the operational runbook,
ingested as a source page) for the full commit conventions, scheduled-task
ownership, and the server-lifecycle checklist.

## See also

- `README.md` — project pitch, quick start.
- `Summary.md` — plain-English project overview.
- `Market-Analysis-Wiki/wiki/index.md` — the project's knowledge base
  (canonical source of truth for past decisions, architecture, API,
  testing, and session history). It lists all 99 source pages, the
  47 durable decisions under `### decision (47)`, and the session log.
- `Market-Analysis-Wiki/wiki/overview.md` — vault structure and
  read/write roles.