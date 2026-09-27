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

2026-09-27 - The long-run handoff, the parked decisions and the last deferred
item (`02-O`) are all landed, plus one bug found by the probe recon (`08-U`).
Frontend **242 passed / 0 failed**; backend 758 tests green. Remaining: `02-I`
(refresh-time compute omits `valuation=`) and the `01`/`08`/`00`/`04` runtime
probes. Full state is `docs/audit/README.md`.

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
  --no-llm`, then `bm25-index.py build`; query read-only with `retrieve.py --top
  5 --no-rerank`.
- **A green suite is the norm:** frontend **242 passed / 0 failed**, backend 758
  tests green. A new failure is a real regression, not baseline drift.
- **`/api/meta` is the sanctioned config-to-frontend channel** (`labels`,
  `groups`, and now `ai`). Frontend consumers keep built-in defaults that render
  identically if the endpoint fails; `meta.js` replaces fields in place.
- **The AI-sentiment tooltip's numbers come from `app/config.py`** via that
  channel (`aiConfig`), not hard-coded literals (`a8a6274`).
- **Native `title=` tooltips are converged onto `attachTooltip`** across
  bottleneck (06-A), shell, events and portfolio/`tickerTable` (`fe40eed`). Only
  documented natives remain: the `tickerTable` arrow buttons (tooltip surface
  sits behind the Columns menu, `z-index 90` vs `100`), the disabled reorder
  branch, and the `watchColors` star (its `title` must equal its `aria-label`).
- **All 13 `CARD_TOOLTIPS` entries state as-of/freshness** (`2894c5e`); the info
  buttons are named from the visible `<h2>` title (`fd44083`).
- **A cancelled generation job is interruptible** (`8f40461`, `06-X`): job path
  `app/topic_agent.py`; the HTTP completion runs on an abandonable daemon thread
  and child processes are cancelled/killed/reaped.
- **`POST /api/events/dimensions` returns 400, not 500, for a non-string value**
  (`1eaaa51`).
- **Event timestamps are explicit UTC** (`Z`); readers treat a missing designator
  as UTC.
- **Never fetch a URL taken from untrusted content without a public-host guard.**
- **Tickers are US-listed only, ADR-mapped.**

## Active Threads

- The audit backlog is closed except `02-I` (refresh-time compute omits
  `valuation=`). The `01`/`08`/`00`/`04` runtime probes are the remaining
  unverified surface; the probe recon (`python run.py`, port 8000, `Host:
  127.0.0.1`) found `08-U` and confirmed a stale-cache `GET /api/dashboard`
  triggers network + writes.
