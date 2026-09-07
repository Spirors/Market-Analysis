---
name: project-rules
description: Hard rules for any agent working on the {{REPO_NAME}} repo. Load this skill BEFORE any non-trivial work — coding, refactor, data change, or UI edit. Especially load before dispatching or becoming a subagent (fixer, explorer, oracle, designer) since AGENTS.md does not auto-inject into subagent sessions and these rules will not otherwise reach them.
---

# Initialisation

This skill is portable. Before loading it into a new repo, replace these
placeholders with the new repo's values (search for `{{...}}` and the `{{...}}`
syntax throughout this file). Defaults are shown in the table below.

| Placeholder | Meaning | Default in this copy |
|-------------|---------|----------------------|
| `{{REPO_NAME}}` | Full GitHub-style repo identifier (`org/name`). | `Spirors/Market-Analysis` |
| `{{REPO_DISPLAY_NAME}}` | Human-readable project name used in titles and commit scope prefixes. | `Market Analysis Tool` |
| `{{DATA_DIR}}` | Directory holding the local JSON cache, pid file, and daily changelog. | `data` |
| `{{SERVER_COMMAND}}` | Command used to start the local dev server (and any sub-flags referenced). | `python run.py` |
| `{{FROZEN_HTML_DIR}}` | Directory holding reference HTML snapshots that must never be edited. | `archived` |

The skill body contains additional in-line references to repo-specific files
(e.g. `app/`, `static/js/`). Those are illustrative anchors of *where* the rule
applies in a Flask/FastAPI-style webapp — adapt them per repo rather than
parameterising every path.

---

# Project Rules — {{REPO_DISPLAY_NAME}}

These are the non-negotiable rules for this repo. Treat any violation as a
bug. If a rule and a user instruction conflict, ask before proceeding.

---

## Data integrity

- **Never fabricate market data.** Every number must trace to a fetched
  source (yfinance / SEC EDGAR / RSS) and be stamped with an "as of"
  timestamp. If a source is unavailable, mark it `null` / `—` — never
  invent a value.
- **Free, no-key sources only.** yfinance, MarketWatch / SCMP / Korea
  Herald RSS, SEC EDGAR via `curl_cffi`. `app/market.py` is designed so
  paid keys can be plugged in later, but do not introduce a hard key
  dependency. The Stooq CSV fallback was removed 2026-08-23 because Stooq
  now bot-walls non-browser clients — do not silently re-add it.
- **Cross-view consistency.** Numbers and company names that appear in
  multiple cards / tables must agree. If you change a number on one card,
  find every other place it appears and update them all in the same
  change.

## Frozen files

- **The 4 `{{FROZEN_HTML_DIR}}/ai_*.html` files are frozen reference
  material.** They seeded the analysis framework and design system used
  here. Do not modify them regardless of what else is being refactored.

## Server lifecycle (non-negotiable — single most common bug source)

Every turn that launches a process must reap and verify it before ending.
Full checklist lives in `project_rules/RUNBOOK.md`. The must-not-skip
rules:

- Default to FastAPI `TestClient` for verification — no port binding, no
  orphan risk. The Host header must be `127.0.0.1:8000` (DNS-rebinding
  allowlist middleware rejects `testserver` with a 403).
- **Never** use `Start-Process`, `nohup`, `&`, or `Invoke-Expression`-based
  detached launches. They have repeatedly hung the orchestrator and
  leaked zombie Python processes on port 8000.
- **Never** use `pythonw.exe` directly. It tries to detach from the parent
  console on startup and silently aborts when the detach leaves OS
  console-handle state inconsistent. Use `wscript.exe` + VBS with
  `shell.Run "python args", 0, False` (`WindowStyle=0` = `SW_HIDE`).
- After any launch: `Stop-Process -Id <pid> -Force` (or
  `taskkill /PID <pid> /F`, or `POST /api/shutdown`).
- Verify before ending the turn: `Get-Process python` empty,
  `Get-Process pythonw` empty, `Test-NetConnection -Port 8000` False.
- **Never** leave a server running "for the user to test." The user runs
  the server themselves via the desktop launcher (`launch.vbs` →
  `launch.bat`). An orchestrator-spawned server left running collides on
  port 8000 with the user's own launch and leaves stale lockfiles.

## File ownership

- **`{{DATA_DIR}}/events.json` is owned by the
  `MarketAnalysis-EventsCommit` scheduled task** (17:00 local daily). Do
  not commit `events.json` from interactive sessions — let the scheduler
  own it. Unstaged timestamp updates in your working tree are normal;
  ignore them.

## Commit hygiene

- **One logical change per commit.** Don't bundle a refactor with a bug
  fix. Fix the bug, verify, commit. Refactor separately.
- Scope-prefixed messages: `feat(scope): ...`, `fix(scope): ...`,
  `chore(scope): ...`, `docs(scope): ...`.
- Never amend an existing commit unless explicitly asked.
- Code, config, `AGENTS.md`, and `project_rules/` changes commit
  immediately after verification.

## Shared UI components

- **Shared UI components must take their persistence key as a required
  prop, never hardcode or default it.** When two sections share a
  component (e.g. `tickerTable.js` consumed by both Earnings and
  Portfolio, post-commit `914f406`), a hardcoded or default key silently
  merges state across every caller. `column_order` / `column_visibility`
  must stay keyed per-section (`earnings` vs `portfolio`).
- After any shared-component extraction: round-trip test every consumer
  independently. For each one: change something → reload → confirm the
  same state comes back, for *that specific consumer*. Cross-contamination
  between consumers sharing one component is the single most common bug
  class from this kind of refactor.

## Card behavior + tooltip = same change

When a card's behavior changes, update the matching tooltip in the same
commit:

- Card-header tooltips live in `static/js/cards.js` under `CARD_TOOLTIPS`
  (`initCardTooltips` attaches them).
- Per-element tooltips use HTML `title=` attributes in `static/js/events.js`
  (badges) and `static/js/earnings.js` (recommendation, watch buttons).
- The reusable component is `static/js/tooltip.js` (`attachTooltip()`).

## Risk-gauge design

`app/risk.py` fires RED on **consensus optimism**, not raw bearishness.
Divided signals across the 9 cross-asset inputs are healthy; unanimous
*optimism* is the fragility signal. Do not "fix" the engine to fire on
raw bearishness — unanimous bearishness is not the RED trigger,
unanimous optimism is. The rationale and the gauge-event seed mapping
live in `project_rules/DECISIONS.md`.

## Commodities spot pricing

Real cash-market spot for the Commodities card's Spot column comes from
FRED public CSV (energy) and Minted Metal public JSON (precious metals),
mapped back to the matching Yahoo futures ticker (`CL=F`, `BZ=F`,
`GC=F`, `NG=F`, `SI=F`). `yfinance`'s `fast_info` is broken in current
versions — do not reintroduce it for spot. FRED's LBMA gold series was
removed in January 2022 (IBA license change); the renderer is
oblivious to the source family via `spot.commodities_map`.

## Session continuity

- Update `project_rules/HANDOFF.md` at session end: `Last updated`
  timestamp, current state, top 3 next actions, blockers.
- Append a new entry to `project_rules/SESSION_LOG.md`.
- Record durable decisions in `project_rules/DECISIONS.md` the moment
  you confirm them — not from memory later.
- Keep `project_rules/RUNBOOK.md` in sync with any operational-command
  change.
- Every meaningful change must call
  `app.changelog.log_change(category, message)` so it is appended to
  `{{DATA_DIR}}/logs/summary-YYYY-MM-DD.md` (gitignored local daily
  changelog — not a substitute for `project_rules/SESSION_LOG.md`, which
  is git-tracked).
