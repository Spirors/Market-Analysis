# AGENTS.md

AI-readable reference for the Market Analysis Tool. This file holds only
hard rules, the session protocol, and commit conventions. Everything else
lives in the linked docs below — see "See also."

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
3. `ROADMAP.md` — current phase; only work inside it unless told otherwise
4. `project_rules/HANDOFF.md` — where the last session left off
5. latest entry in `project_rules/SESSION_LOG.md` (not the whole file — just the
   most recent dated entry)
6. `project_rules/DECISIONS.md`
7. `project_rules/RUNBOOK.md` — exact operational procedures

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
- When card behavior changes, update the matching tooltip in the same
  change. Card-header tooltips live in `static/js/cards.js` under
  `CARD_TOOLTIPS` (`initCardTooltips` attaches them). Per-element tooltips
  use HTML `title=` attributes in `static/js/events.js` (badges) and
  `static/js/earnings.js` (recommendation, watch buttons). The reusable
  component is `static/js/tooltip.js` (`attachTooltip()`).
- Every meaningful change must call `app.changelog.log_change(category,
  message)` so it's appended to `data/logs/summary-YYYY-MM-DD.md`.
  Categories: `scheduler`, `commit`, `shortcut`, `ui`, `doc`, `config`,
  `chore`. That file is gitignored (local daily changelog only) — it is
  **not** a substitute for `project_rules/SESSION_LOG.md`, which is git-tracked and
  is the actual cross-session/cross-machine continuity record. Read
  today's local log with `app.changelog.read_day()`. The orchestrator
  decides what counts as "meaningful" — structural changes, user-visible
  behavior changes, and scheduler/install/remove events all qualify;
  routine fetches do not.

## Session End

- Update `project_rules/HANDOFF.md`: `Last updated` timestamp
  (`YYYY-MM-DD HH:MM UTC`), current state, top 3 next actions, blockers.
- Append a new timestamped entry to `project_rules/SESSION_LOG.md`.
- Confirm no secrets were added to tracked files.

## Hard rules

- **Never fabricate market data.** Every number must trace to a fetched
  source (yfinance / SEC EDGAR / RSS) and be stamped with an "as of"
  timestamp. If a source is unavailable, mark it `null`/`—` — never invent
  a value.
- **Free, no-key sources only** (yfinance, MarketWatch / SCMP / Korea
  Herald RSS, SEC EDGAR via `curl_cffi`). `app/market.py` is designed so
  paid API keys can be plugged in later, but do not introduce a hard key
  dependency.
- **Keep the same fact consistent across views.** Numbers and company names
  that appear in multiple cards/tables must agree.
- **The 4 archived `ai_*.html` files are frozen reference material.** Do
  not modify them (see `project_rules/DECISIONS.md`).
- **`archived/AGENT-WORKFLOW-PROMPT.md` is frozen historical reference.**
  It was the original session-start workflow template that seeded the
  Phase 0/1 docs split; everything in it now lives in `AGENTS.md`,
  `docs/`, and the `project-rules` skill. 16 references in
  `project_rules/DECISIONS.md`, `project_rules/SESSION_LOG.md`, `ROADMAP.md`,
  `static/js/tickerTable.js`, `tests/test_run.py`, and
  `tests/frontend/section-position.spec.mjs` still cite its §3a/§3b
  hypotheses — those remain valid historical anchors. Do not modify
  the file (see `project_rules/DECISIONS.md`).
- **Server lifecycle rules in `project_rules/RUNBOOK.md` are non-negotiable.**
  Every turn that launches a process must reap and verify it before
  ending, per that runbook — this is the single most common source of
  the "stuck process" complaint when skipped.

## Commits

See `project_rules/RUNBOOK.md` for the full commit conventions (scoped messages,
what the scheduler owns vs. what the agent commits directly).

## Skills

See `ARCHITECTURE.md` for the full reused/custom skills list
(`macro-regime-detector`, `serenity-chokepoint-investing`,
`macro-rates-monitor`, plus custom `.opencode/skills/`).

**Project-specific hard rules live in `.opencode/skills/project-rules/SKILL.md`.**
Invoke that skill (and include its output in any subagent dispatch) before
doing non-trivial work — see the rule in *During Work* above.

## See also

- `README.md` — project pitch, quick start
- `ROADMAP.md` — phase-level plan, what's in scope right now
- `project_rules/HANDOFF.md` — session-to-session state
- `project_rules/SESSION_LOG.md` — append-only, git-tracked session history
- `project_rules/DECISIONS.md` — durable decisions and confirmed root causes
- `project_rules/RUNBOOK.md` — exact operational procedures (server lifecycle,
  commit conventions, Playwright stealth guidance for future browser
  automation)
- `ARCHITECTURE.md` — module map, section-to-code map, known quirks
- `API.md` — HTTP routes, dashboard payload shape
- `TESTING.md` — test pointers, known gaps
- `Summary.md` — plain-English project overview
- Historical one‑off logs are in `docs/logs/` – load on demand only.
