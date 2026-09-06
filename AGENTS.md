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
4. `docs/HANDOFF.md` — where the last session left off
5. latest entry in `docs/SESSION_LOG.md` (not the whole file — just the
   most recent dated entry)
6. `docs/DECISIONS.md`
7. `docs/RUNBOOK.md` — exact operational procedures

`ARCHITECTURE.md`, `API.md`, and `TESTING.md` are **not** part of this list
— read them on demand when a task actually touches that area, to keep
session-start cost low as the docs grow.

## During Work

- Keep `docs/HANDOFF.md` aligned with current status and next actions as
  they change.
- Record durable decisions ("we tried X and it failed because Y", anything
  a future session must not silently re-litigate) in `docs/DECISIONS.md`
  the moment you confirm them.
- Keep `docs/RUNBOOK.md` in sync with any change to operational commands.
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
  **not** a substitute for `docs/SESSION_LOG.md`, which is git-tracked and
  is the actual cross-session/cross-machine continuity record. Read
  today's local log with `app.changelog.read_day()`. The orchestrator
  decides what counts as "meaningful" — structural changes, user-visible
  behavior changes, and scheduler/install/remove events all qualify;
  routine fetches do not.

## Session End

- Update `docs/HANDOFF.md`: `Last updated` timestamp
  (`YYYY-MM-DD HH:MM UTC`), current state, top 3 next actions, blockers.
- Append a new timestamped entry to `docs/SESSION_LOG.md`.
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
  not modify them (see `docs/DECISIONS.md`).
- **Server lifecycle rules in `docs/RUNBOOK.md` are non-negotiable.**
  Every turn that launches a process must reap and verify it before
  ending, per that runbook — this is the single most common source of
  the "stuck process" complaint when skipped.

## Commits

See `docs/RUNBOOK.md` for the full commit conventions (scoped messages,
what the scheduler owns vs. what the agent commits directly).

## Skills

See `ARCHITECTURE.md` for the full reused/custom skills list
(`macro-regime-detector`, `serenity-chokepoint-investing`,
`macro-rates-monitor`, plus custom `.opencode/skills/`).

## See also

- `README.md` — project pitch, quick start
- `ROADMAP.md` — phase-level plan, what's in scope right now
- `docs/HANDOFF.md` — session-to-session state
- `docs/SESSION_LOG.md` — append-only, git-tracked session history
- `docs/DECISIONS.md` — durable decisions and confirmed root causes
- `docs/RUNBOOK.md` — exact operational procedures (server lifecycle,
  commit conventions, Playwright stealth guidance for future browser
  automation)
- `ARCHITECTURE.md` — module map, section-to-code map, known quirks
- `API.md` — HTTP routes, dashboard payload shape
- `TESTING.md` — test pointers, known gaps
- `Summary.md` — plain-English project overview
- `docs/` (audit files) — `fix-log-2026-08-22.md`,
  `improvements-log-2026-08-22.md`, `park-log-2026-08-23.md`,
  `audit-2026-08-26.md`
