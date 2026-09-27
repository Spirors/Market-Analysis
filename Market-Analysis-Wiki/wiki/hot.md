---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-09-27
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-09-27 - The audit backlog and the runtime probes are done. `01-F1` was
**not** reproduced: with all histories empty the risk card degrades to
"insufficient data", it does not fabricate a GREEN. The last tracked surface
(08 focus/empty-states, 02-I, 04 deps) is closed and the probe-found a11y defect
`00-V` (header badges polluting the heading name) is fixed. Frontend **246
passed / 0 failed**; backend 763 green. Remaining: `00-W` (same-class follow-ups)
and the `04` narrow-width DESIGN pass. State: `docs/audit/README.md`.

## Active audit - canonical state

The multi-session app + wiki audit lives in **`docs/audit/`**. Read
`docs/audit/README.md` first - canonical for scope, priorities, status board,
backlog, open decisions and the verified test baseline. `docs/audit/wiki.md` is
the wiki retrieval audit (COMPLETE); `docs/audit/next-session.md` is the long-run
handoff prompt. Do not copy its tables here.

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory: 104 live source pages and 55 durable
  decisions under `### decision (55)`.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`), through a `claude-obsidian.transaction.v1` bundle - never a host
  Edit. Methodology is Generic. Product root: `../claude-obsidian`.
- **The retrieval index is rebuilt at session end:** `contextual-prefix.py --all
  --no-llm`, then `bm25-index.py build`.
- **A green suite is the norm:** frontend **246 passed / 0 failed**, backend 763
  tests green. A new failure is a real regression, not baseline drift.
- **Live-probe method:** run `python run.py` (port 8000) from a detached `git
  worktree` for an isolated `data/`, with a dead `HTTP(S)_PROXY` to force fetch
  failure without code edits. (A stale-cache `GET /api/dashboard` otherwise
  triggers a full network+write refresh.)
- **Header badges render in `.card-head` beside the `h2`**, never inside it, so a
  card heading's accessible name is the title alone (`00-V`, `c589a95`).
- **`/api/meta` is the sanctioned config-to-frontend channel** (`labels`,
  `groups`, `ai`); frontend consumers keep defaults that render identically if it
  fails. The AI tooltip's numbers come from `app/config.py` (`a8a6274`).
- **Native `title=` tooltips are converged onto `attachTooltip`** across
  bottleneck, shell, events and portfolio/`tickerTable` (`fe40eed`); documented
  natives remain in `tickerTable` and `watchColors`.
- **All 13 `CARD_TOOLTIPS` entries state as-of/freshness** (`2894c5e`).
- **A cancelled generation job is interruptible** (`8f40461`, `06-X`): job path
  `app/topic_agent.py`; abandonable completion thread + cancel-aware child reap.
- **Event timestamps are explicit UTC** (`Z`); `POST /api/events/dimensions`
  returns 400, not 500, for a non-string value (`1eaaa51`).
- **Never fetch a URL taken from untrusted content without a public-host guard.**
- **Tickers are US-listed only, ADR-mapped.**

## Active Threads

- `00-W` (tracked): the portfolio `.pf-grand-total` and the bottleneck card's
  `.cov-badge` are still inside their `<h2>` (same class as the fixed `00-V`);
  the portfolio one needs a spacing decision, the bottleneck one a spec update.
- `04`: the narrow-width chart-legibility check is a `DESIGN` task for a human
  visual pass.
