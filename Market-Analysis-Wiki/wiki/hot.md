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

2026-09-27 - The app audit (`docs/audit/`) is closed: every section is
deep-audited and all seven open decisions were answered and landed. The regime
card now shows the detector's own report date; the commodities card shows its
source date and attribution; the dead futures coverage flag is gone. The
frontend suite is **204 passed / 0 failed**. Full state is
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
- The vault is the project's memory: 103 live source pages and 55 durable
  decisions under `### decision (55)`.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`), through a `claude-obsidian.transaction.v1` bundle - never a host
  Edit. Methodology is Generic. Product root: `../claude-obsidian`.
- **The retrieval index is rebuilt at session end:** `contextual-prefix.py --all
  --no-llm`, then `bm25-index.py build`; query read-only with `retrieve.py --top
  5 --no-rerank`. Navigation hubs and `_retired/**` pollute results by design.
- **A green frontend suite is now the norm:** 204 passed / 0 failed. A new
  failure is a real regression, not baseline drift.
- **The regime card's date is the detector's `metadata.generated_at`**, not the
  refresh vintage; the generic `.vintage-note` is suppressed for that card.
- **Market "As of" means the spot source date when known, else the fetch time;**
  the commodities card renders `spot.attribution` + source date, and
  `cov["futures"]` is dropped.
- **Event timestamps are explicit UTC** (`Z`); readers treat a missing designator
  as UTC, so legacy naive rows still compare correctly.
- **Never fetch a URL taken from untrusted content without a public-host guard**
  (the research-probe SSRF fix, `ff9fc12`).
- **Tickers are US-listed only, ADR-mapped.** `_strip_non_us_tickers`,
  `_resolve_tickers`, `_filter_dead_sources` are the deterministic nets.

## Active Threads

- The audit is closed: `03-regime` and `05-market-quotes` are COMPLETE, the Sec 13
  backlog is empty, and `06-A` stays DEFERRED (needs a DOM/design pass).
- Tracked, out of scope (`docs/audit/README.md` Sec 13): a cancelled bottleneck
  job's serial lock can be held up to the request timeout - cancel is honest
  (`cancelling`) but not yet interruptible.
- Still pending, not part of this close-out: the `02-ai-sentiment` deep audit and
  the `06-bottleneck` editor/forms review.
