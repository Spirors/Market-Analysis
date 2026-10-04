---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-10-04
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-10-04 - The app audit is closed and ARCHIVED. Its finished files now live in
the vault as `sources/docs__audit__*` (filed under the index's `### history`
group) with immutable captures under `.raw/captured/`; the repo's `docs/audit/`
was removed. Those pages are reference-only - do not read them as current status.
All audit items are now closed: the last one, the `04` narrow-width chart-legibility
check, was visually verified fine. Frontend **246 passed / 0 failed**; backend 763
green.

## Where things live now

- **Live state = `wiki/hot.md` (here) + the code.** There is no longer a separate
  canonical audit document in the repo.
- **The archived audit** = `sources/docs__audit__*` (summary + 9 sections + the
  wiki audit), grouped under `### history` in `wiki/index.md`. Historical; not live.
- The retrieval index is rebuilt at session end (`contextual-prefix.py --all
  --no-llm`, then `bm25-index.py build`).

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory; durable decisions live in
  `wiki/sources/` (`### decision (55)`).
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`), through a `claude-obsidian.transaction.v1` bundle - never a host
  Edit. Methodology is Generic. Product root: `../claude-obsidian`.
- **A green suite is the norm:** frontend **246 passed / 0 failed**, backend 763
  tests green. A new failure is a real regression, not baseline drift.
- **Card header extras render beside the `h2`, never inside it.** The ⓘ button,
  the coverage/cooldown badges, the portfolio grand total and the bottleneck badge
  all live in `.card-head`, so a heading's accessible name is just its title
  (`00-V` `c589a95`, `00-W` `739cc4c`). Keep it that way.
- **`/api/meta` is the sanctioned config-to-frontend channel** (`labels`,
  `groups`, `ai`); consumers keep defaults that render identically if it fails.
  The AI tooltip's numbers come from `app/config.py` (`a8a6274`).
- **Native `title=` tooltips are converged onto `attachTooltip`** across
  bottleneck, shell, events and portfolio/`tickerTable` (`fe40eed`); only
  documented natives remain in `tickerTable` and `watchColors`.
- **All 13 `CARD_TOOLTIPS` entries state as-of/freshness** (`2894c5e`).
- **A cancelled generation job is interruptible** (`8f40461`, `06-X`); the job
  path is `app/topic_agent.py`.
- **Event timestamps are explicit UTC** (`Z`); `POST /api/events/dimensions`
  returns 400, not 500, for a non-string value (`1eaaa51`).
- **Never fetch a URL taken from untrusted content without a public-host guard.**
- **Tickers are US-listed only, ADR-mapped.**

## Active Threads

- None. The audit is fully closed; no tracked items remain. The history of what
  was done is in `wiki/log.md` and the archived `sources/docs__audit__*` pages.
