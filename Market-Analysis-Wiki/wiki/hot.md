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

2026-09-27 - The app audit (`docs/audit/`) is closed and the bottleneck
section's last native tooltips are gone (06-A). The frontend suite is **224
passed / 0 failed**. The remaining work is optional and queued in
`docs/audit/next-session.md`, which is now a **long-run handoff prompt**. Full
state is `docs/audit/README.md`.

## Active audit - canonical state

The multi-session app + wiki audit lives in **`docs/audit/`**. Read
`docs/audit/README.md` first - canonical for scope, priorities, status board,
backlog, open decisions and the verified test baseline. `docs/audit/wiki.md` is
the wiki retrieval audit (COMPLETE); `docs/audit/next-session.md` is the long-run
handoff prompt (paste its block into a fresh session). Do not copy its tables
here.

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
- **A green frontend suite is now the norm:** 224 passed / 0 failed. A new
  failure is a real regression, not baseline drift.
- **The regime card's date is the detector's `metadata.generated_at`**, not the
  refresh vintage; the generic `.vintage-note` is suppressed for that card.
- **Market "As of" means the spot source date when known, else the fetch time;**
  the commodities card renders `spot.attribution` + source date, and
  `cov["futures"]` is dropped.
- **The AI gauge reads the shared `history_universe_symbols()` cache**, its
  serve-time recompute degrades to `-` instead of 500ing, and it must never read
  "unavailable" as healthy (no `- ok`, no fabricated needle).
- **Native `title=` tooltips are being converged onto `attachTooltip`**
  (bottleneck done, 06-A); shell/events/portfolio remain.
- **Event timestamps are explicit UTC** (`Z`); readers treat a missing designator
  as UTC, so legacy naive rows still compare correctly.
- **Never fetch a URL taken from untrusted content without a public-host guard**
  (the research-probe SSRF fix, `ff9fc12`).
- **Tickers are US-listed only, ADR-mapped.** `_strip_non_us_tickers`,
  `_resolve_tickers`, `_filter_dead_sources` are the deterministic nets.

## Active Threads

- The audit is closed. The remaining optional work is queued in the long-run
  handoff prompt (`docs/audit/next-session.md`): cross-section tooltip
  convergence (events/portfolio/shell), the `06-X` bottleneck cancel-lock, and
  the P3 polish batches.
- Tracked, out of scope (`docs/audit/README.md` Sec 13, `06-X`): a cancelled
  bottleneck job's serial lock can be held up to the request timeout - cancel is
  honest (`cancelling`) but not yet interruptible.
