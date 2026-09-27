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

2026-09-27 - The app audit (`docs/audit/`) moved from findings to fixes: all nine
sections are now deep-audited and the tracked backlog is closed except for a
short list of product decisions (regime timestamp, market "As of" meaning,
unrendered spot attribution). The frontend suite is fully green
(198 passed / 0 failed). The wiki retrieval decisions are closed. Full state and
the remaining decisions live in `docs/audit/README.md`.

## Active audit - canonical state

The multi-session app + wiki audit lives in **`docs/audit/`**. Read
`docs/audit/README.md` first - it is canonical for scope, priorities, status
board, backlog, open decisions and the verified test baseline.
`docs/audit/wiki.md` is the wiki retrieval audit (COMPLETE);
`docs/audit/next-session.md` is the resume prompt. Do not copy its tables here.

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory: 103 live source pages and 55 durable
  decisions under `### decision (55)`.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`), through a `claude-obsidian.transaction.v1` bundle - never a host
  Edit. Methodology is Generic. Product root: `../claude-obsidian`.
- **The retrieval index is rebuilt at session end:** `contextual-prefix.py --all
  --no-llm`, then `bm25-index.py build`; query read-only with `retrieve.py --top
  5 --no-rerank`. Navigation hubs and `_retired/**` pollute results by design.
- **A green frontend suite is now the norm:** 198 passed / 0 failed. A new
  failure is a real regression, not baseline drift.
- **Event timestamps are explicit UTC** (`Z`); readers treat a missing designator
  as UTC, so legacy naive rows still compare correctly.
- **Never fetch a URL taken from untrusted content without a public-host guard**
  (the research-probe SSRF fix, `ff9fc12`).
- **Tickers are US-listed only, ADR-mapped.** `_strip_non_us_tickers`,
  `_resolve_tickers`, `_filter_dead_sources` are the deterministic nets.

## Active Threads

- The audit is awaiting four product decisions and two small cleanups -
  `docs/audit/README.md` Sec 13 and `docs/audit/next-session.md`. Do not restate
  them here.
- Open: a cancelled bottleneck job's serial lock can be held up to the request
  timeout - cancel is honest (`cancelling`) but not yet interruptible.
