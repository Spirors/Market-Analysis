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

2026-09-27 - The app audit (`docs/audit/`) is closed: every section has a
section file and every P2 decision is answered and landed. The last pass made
the AI gauge honest (shared history cache, guarded recompute, PE cache age) and
the bottleneck editor accessible (validation, unsaved-changes guards, focus,
labels). The frontend suite is **221 passed / 0 failed**. Full state is
`docs/audit/README.md`.

## Active audit - canonical state

The multi-session app + wiki audit lives in **`docs/audit/`**. Read
`docs/audit/README.md` first - canonical for scope, priorities, status board,
backlog, open decisions and the verified test baseline. `docs/audit/wiki.md` is
the wiki retrieval audit (COMPLETE); `docs/audit/next-session.md` is the resume
prompt. Do not copy its tables here.

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
  5 --no-rerank`. Navigation hubs and `_retired/**` pollute results by design.
- **A green frontend suite is now the norm:** 221 passed / 0 failed. A new
  failure is a real regression, not baseline drift.
- **The regime card's date is the detector's `metadata.generated_at`**, not the
  refresh vintage; the generic `.vintage-note` is suppressed for that card.
- **Market "As of" means the spot source date when known, else the fetch time;**
  the commodities card renders `spot.attribution` + source date, and
  `cov["futures"]` is dropped.
- **The AI gauge reads the shared `history_universe_symbols()` cache**, its
  serve-time recompute degrades to `—` instead of 500ing, and it must never read
  "unavailable" as healthy (no `— ok`, no fabricated needle).
- **Event timestamps are explicit UTC** (`Z`); readers treat a missing designator
  as UTC, so legacy naive rows still compare correctly.
- **Never fetch a URL taken from untrusted content without a public-host guard**
  (the research-probe SSRF fix, `ff9fc12`).
- **Tickers are US-listed only, ADR-mapped.** `_strip_non_us_tickers`,
  `_resolve_tickers`, `_filter_dead_sources` are the deterministic nets.

## Active Threads

- The audit is closed and all P2 decisions are answered. Remaining, optional:
  `06-A` (17 inline bottleneck tooltips) stays DEFERRED - needs a DOM/design
  pass; and P3 polish recorded in the section files (02-L/N/O/P/Q; 06-I..06-O).
- Tracked, out of scope (`docs/audit/README.md` Sec 13, `06-X`): a cancelled
  bottleneck job's serial lock can be held up to the request timeout - cancel is
  honest (`cancelling`) but not yet interruptible.
