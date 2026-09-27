---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-09-26
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-09-26 - The wiki audit's three parked decisions are closed: the retrieval
index is rebuilt at session end, corpus noise is accepted and documented, and
rerank stays lexical-only. Detail:
[[sources/decision__retrieval-index-rebuilt-at-session-end-2026-09-26|retrieval index decisions]].

## Active audit - canonical state

An active multi-session app + wiki audit lives in **`docs/audit/`**. Read
`docs/audit/README.md` first: it is canonical for scope, priorities, status
board, backlog, and the verified test baseline. `docs/audit/wiki.md` is the wiki
retrieval audit. Do not copy its tables here.

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory: 103 live source pages and 55 durable
  decisions under `### decision (55)`.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`), and go through a `claude-obsidian.transaction.v1` bundle - never a
  host Edit. Methodology is Generic. Product root: `../claude-obsidian`.
- **The retrieval index is rebuilt at session end:** `contextual-prefix.py --all
  --no-llm`, then `bm25-index.py build`; query read-only with `retrieve.py --top
  5 --no-rerank`. The navigation hubs and `_retired/**` pollute results by
  design (accepted).
- **Never fetch a URL taken from untrusted content without a public-host guard.**
  The research-source liveness probe was an SSRF; probes now require a public
  http(s) host and do not follow redirects (`ff9fc12`).
- **Tickers are US-listed only, ADR-mapped.** `_strip_non_us_tickers`,
  `_resolve_tickers`, and `_filter_dead_sources` are the deterministic nets.
- **The job lifecycle is explicit.** `apply_draft` is idempotent; cancel reports
  a non-terminal `cancelling`; stale `running` jobs are recovered at startup.

## Active Threads

- The app + wiki audit is in progress: `docs/audit/README.md` Sec 13 holds the
  open backlog and Sec 10 the test baseline - do not restate them here.
- Open: a cancelled bottleneck job's serial lock can be held up to the request
  timeout - cancel is honest (`cancelling`) but not yet interruptible.
- Watch: the three frontend baseline failures are stale specs, not product bugs
  (`docs/audit/README.md` Sec 10).
