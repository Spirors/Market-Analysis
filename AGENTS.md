# AGENTS.md

AI-readable reference for the Market Analysis Tool. Session protocol, hard
rules, and wiki pointers. **The project's persistent memory lives in the wiki
vault (`Market-Analysis-Wiki/wiki/`), not in this file.** Each hard-rule section
states the rule and links the vault page carrying its rationale and worked
examples.

## What this is

Local webapp for macro-trend market analysis (regime classification,
breadth/vol/yield indicators, chokepoint bottlenecks, filtered news timeline,
trend-shift risk-divergence engine). Free, no-key data sources, runs entirely
locally on Windows. See `README.md` for the pitch and
`Market-Analysis-Wiki/wiki/overview.md` for the knowledge-base structure.

## Session protocol

**Start.** Read `Market-Analysis-Wiki/wiki/hot.md` (≤ 500 words). If the task
domain is unclear, read `Market-Analysis-Wiki/wiki/index.md` next. Do **not**
read `Market-Analysis-Wiki/inbox/` — frozen archive, canonicalised in
`Market-Analysis-Wiki/wiki/sources/` and `.raw/captured/`.

**During work.** The Orchestrator triggers `wiki-ingest` / `save` / `wiki-fold`
transactions that update `log.md`, `index.md`, and the meta ledgers atomically.
Do **not** hand-edit `Market-Analysis-Wiki/wiki/log.md` — the transaction owns it. Durable decisions
become `Market-Analysis-Wiki/wiki/sources/` pages, listed under `### decision (52)`.

**End.** Fires when the Orchestrator is about to send a final response to a
non-trivial turn (no follow-up, no in-progress todos, no running background
tasks) **or** when the user explicitly closes the session. Full trigger set:
`Market-Analysis-Wiki/wiki/meta/session-memory-protocol.md`. At session end: rewrite `Market-Analysis-Wiki/wiki/hot.md`
(always **last**), append one entry to `Market-Analysis-Wiki/wiki/log.md`.

## Sub-agent rules

Detail: `Market-Analysis-Wiki/wiki/sources/project_rules__archive__decisions__hard-rule-propagation-project-rules-skill-not-agents-md-alone-undated.md`.

- **Only the Orchestrator writes to the wiki** and to user-data files.
  Sub-agents (Explorer, Oracle, Librarian, Fixer, Designer, Observer) are
  read-only; their drafts return to the Orchestrator, which applies them in one
  transaction.
- **Sub-agents do not read the wiki on their own.** Pass the relevant slice
  **inline in the dispatch prompt** (page slugs, line ranges, short quotes).
- **Explorer is grep / ast_grep / glob only** over the working tree. Explorer =
  codebase recon; Librarian = external docs; Oracle = architecture / risk /
  review.
- **Dispatch prompts must include the hard rules they need** — a sub-agent never
  sees this file.
- **Browser verification is split by tool.** Playwright (`tests/frontend/`, 18
  specs) is the regression gate; its `webServer` is a static `http.server` with
  every endpoint mocked, so it never touches the real backend. `agent-browser`
  covers the exploratory pass it cannot do (dogfooding, bug hunts, screenshots);
  its local `SKILL.md` is only a stub over `agent-browser skills get core`.
  **`open` is verified against the live app; `screenshot` / `snapshot` are not**,
  so prove them in-lane before a brief depends on them.

## Hard rules

Non-negotiable. Treat any violation as a bug. If a rule and a user instruction
conflict, ask before proceeding.

### Data integrity

- **Never fabricate data the system should fetch** — every figure traces to a
  fetched source stamped "as of"; unavailable → `null` / `—`.
- **No hard external service dependency in the default setup** — free, no-key
  sources only; every keyed path degrades to `null`, never to an error.
- **Cross-view consistency** — a number or name appearing in two views must
  agree; update every place in the same change.

Detail:
`Market-Analysis-Wiki/wiki/sources/decision__one-cached-value-per-number-and-the-reader-owns-the-invariant-2026-09-25.md`,
`Market-Analysis-Wiki/wiki/sources/project_rules__archive__decisions__market-data-yfinance-only-no-secondary-fallback-2026-08-23.md`.

### Frozen files

- **The four `archive/ai_*.html` reference snapshots are frozen.** A refactor
  that conflicts with a frozen file loses — find another way.
- **Historical decisions, prompts, and templates that seeded the workflow are
  frozen.** Cite them from new docs; never mutate them.
- **`Market-Analysis-Wiki/inbox/` is a frozen archive** — do not edit or re-read
  originals as live context.

Detail:
`Market-Analysis-Wiki/wiki/sources/project_rules__archive__decisions__frozen-reference-files-are-not-touched-ever-undated.md`,
`Market-Analysis-Wiki/wiki/sources/project_rules__archive__decisions__frozen-reference-snapshots-retrofit-extracted-from-agents-md-2026-09-08.md`.

### Commit hygiene

- **One logical change per commit.** Scope-prefix every message:
  `feat|fix|chore|docs|refactor|test(scope): ...`.
- **Never amend** an existing commit unless explicitly asked.
- Code, config, `AGENTS.md`, and wiki files commit immediately after
  verification.

Detail: `Market-Analysis-Wiki/wiki/sources/project_rules__RUNBOOK.md`.

### Shared UI / shared logic components

- **A shared component takes its persistence key as a required prop** — never
  hardcoded or defaulted, or one caller's state silently merges into another's.
- **After any extraction, round-trip test every consumer independently**
  (change → reload → the same state comes back, for *that* consumer).

Detail:
`Market-Analysis-Wiki/wiki/sources/project_rules__archive__decisions__open-tickertable-js-shared-component-persistence-2026-09-05.md`,
`Market-Analysis-Wiki/wiki/sources/project_rules__archive__decisions__shared-component-rebuilds-controls-subtree-listeners-must-be-re-wired-2026-09-06.md`,
`Market-Analysis-Wiki/wiki/sources/project_rules__archive__decisions__per-portfolio-scope-must-use-composite-keys-not-nested-maps-2026-09-06.md`.

### File ownership

- **Files written by automated pipelines are not for interactive sessions to
  commit.** Unstaged timestamp updates in those files are normal — ignore them,
  or let the pipeline's commit job pick them up. To edit one by hand, coordinate
  with the pipeline owner so the next run doesn't clobber it.

Detail: `Market-Analysis-Wiki/wiki/sources/project_rules__RUNBOOK.md`.

### Process hygiene

- **Every turn that launches a process must reap and verify it before ending** —
  port released, process gone. Checklist in `Market-Analysis-Wiki/wiki/sources/project_rules__RUNBOOK.md`.
- **Never drive a browser CLI through a redirected-pipe wrapper.** A spawned
  Chrome inherits the redirected stdout/stderr handles, so the pipe never
  reaches EOF and the wrapper hangs *after* the child exits; piping a native
  command into a truncating `Select-Object -First` hangs the same way. Redirect
  to a file and read it. Bound every wrapper with a per-command timeout and reap
  inside it — a foreground timeout kills the wrapper before its cleanup runs.

Detail:
`Market-Analysis-Wiki/wiki/sources/project_rules__archive__decisions__agent-terminal-servers-start-process-and-manual-reap-is-a-trap-2026-09-08.md`.

### Test isolation

- **Tests never touch the user's live data files** — the guarantee is that a
  test cannot *reach* them. Exempt: read-only assets (`static/`, `archive/`).
- **Redirect every user-data path to a per-test temp dir** via the autouse
  fixture in `tests/conftest.py`.
- **Module-level path constants bind at import time.** Patching
  `config.DATA_DIR` does NOT update a constant already bound from it — patch the
  bound name on the importing module, or the test silently writes the real file.
- **Add a new path to the fixture the same day you introduce it** — the fixture
  is the contract.

Detail:
`Market-Analysis-Wiki/wiki/sources/project_rules__archive__decisions__test-isolation-autouse-conftest-py-redirects-every-user-data-path-2026-09-08.md`.

### Wiki knowledge-base sync

- **The wiki is the project's persistent memory.** Read `Market-Analysis-Wiki/wiki/` (hot / index /
  log / overview / sources / meta), never the inbox originals.
- **Durable answers belong in the vault, not here**: `hot.md` points at them
  rather than duplicating them, and the engine folds substantive edits in
  automatically.
- **Answer roadmap / past-decision / architecture / methodology questions with a
  `wiki-query`**, not from scratch.
- **Run `wiki-lint` at the end of a session.**
- **The claude-obsidian skills (`wiki*`, `save`, `think`, `autoresearch`,
  `defuddle`, `obsidian-*`, `canvas`) are project-local under `.agents/skills/`**;
  the product root is the sibling `../claude-obsidian`.
- **Vault writes need WSL as root**: `wsl -d Ubuntu-22.04 -u root` with an
  explicit `--vault`. A non-root write fails with `CORRUPT_RUNTIME_STATE`.

Detail: `Market-Analysis-Wiki/wiki/sources/project_rules__RUNBOOK.md`,
`Market-Analysis-Wiki/wiki/meta/session-memory-protocol.md`.

### Documentation hygiene

- **Line count is a symptom, not a target.** Split a file when a section stops
  being needed on every read, not to hit a number. `AGENTS.md` aims at the
  WHAT/WHY/HOW shape: rules here, rationale in the vault pages linked above.
- **Threshold self-check.** After editing `AGENTS.md` or a `Market-Analysis-Wiki/wiki/**` file, run
  `wc -l`; if a file is over 200 lines *and* materially grown since its last
  edit, propose the split in that same session.

## Commits

Full commit conventions, scheduled-task ownership, and the server-lifecycle
checklist: `Market-Analysis-Wiki/wiki/sources/project_rules__RUNBOOK.md`.

## See also

- `README.md` — project pitch, quick start.
- `Summary.md` — plain-English project overview.
- `Market-Analysis-Wiki/wiki/index.md` — the knowledge base (canonical for past
  decisions, architecture, API, testing, and session history): 100 live source
  pages, the 52 durable decisions under `### decision (52)`, and the session log.
- `Market-Analysis-Wiki/wiki/overview.md` — vault structure and read/write roles.
