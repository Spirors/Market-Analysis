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

2026-09-27 - The audit is closed apart from one design item. The probe-found a11y
family (`00-V`/`00-W`) is fully fixed: header extras (the coverage/cooldown
badges, the portfolio total, the bottleneck badge) now live in `.card-head`
beside the `h2`, so a heading's name is its title alone. Frontend **246 passed /
0 failed**; backend 763 green. The only open item is the `04` narrow-width
chart-legibility DESIGN check, which needs a human visual pass. State:
`docs/audit/README.md`.

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
- **Card header extras render beside the `h2`, never inside it.** The ⓘ button,
  the coverage/cooldown badges, the portfolio grand total and the bottleneck badge
  all live in `.card-head`, so a heading's accessible name is just its title
  (`00-V` `c589a95`, `00-W` `739cc4c`). Keep it that way.
- **Live-probe method:** run `python run.py` (port 8000) from a detached `git
  worktree` for an isolated `data/`, with a dead `HTTP(S)_PROXY` to force fetch
  failure without code edits. **Caveat:** the Playwright harness aborts the
  Chart.js CDN, so chart canvases never render in tests; and agent-browser did not
  hold a viewport session reliably here.
- **`/api/meta` is the sanctioned config-to-frontend channel** (`labels`,
  `groups`, `ai`); consumers keep defaults that render identically if it fails.
- **Native `title=` tooltips are converged onto `attachTooltip`** across
  bottleneck, shell, events and portfolio/`tickerTable` (`fe40eed`).
- **All 13 `CARD_TOOLTIPS` entries state as-of/freshness** (`2894c5e`).
- **A cancelled generation job is interruptible** (`8f40461`, `06-X`).
- **Event timestamps are explicit UTC** (`Z`); `POST /api/events/dimensions`
  returns 400, not 500, for a non-string value (`1eaaa51`).
- **Never fetch a URL taken from untrusted content without a public-host guard.**
- **Tickers are US-listed only, ADR-mapped.**

## Active Threads

- `04` (DESIGN, needs a human visual pass): narrow-width legibility of the
  `breadth` / `breadth-ai` charts. A bounded candidate — `.chart-box` horizontal
  scroll + canvas `min-width` at <=720px — is recorded for approval in
  `docs/audit/README.md` Sec 13.
