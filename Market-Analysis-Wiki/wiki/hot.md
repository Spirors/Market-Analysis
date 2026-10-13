---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-10-13
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-10-13 - Hosting phase 1 shipped: cross-platform lockfile fix (`b950f74`)
+ manual-trigger dry-run workflow (`pipeline-dry-run.yml`) on `main` - CI
green (run 38472612111), 812 backend tests green. **No schedules active; no
real data migrated.** Storage verdict: git-only private data repo recommended
over Supabase; **phase 2 awaits owner approval**. Branches:
`ci/dry-run-phase1` (test), `parked/hosting-phase1`.

## Where things live now

- **Live state = `wiki/hot.md` (here) + the code.** There is no separate canonical
  audit document in the repo.
- **The archived audit** = `sources/docs__audit__*` (summary + 9 sections + the
  wiki audit), grouped under `### history` in `wiki/index.md`. Historical; not live.
- The retrieval index is rebuilt at session end (`contextual-prefix.py --all
  --no-llm`, then `bm25-index.py build`).

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory; durable decisions live in
  `wiki/sources/` (`### decision (58)`).
- **Portfolio history**: the snapshot store is write-if-absent per settled US
  close date (~16:15 ET guard); a missing close nulls the holding AND the
  portfolio total (coverage-stamped) - never a partial sum; the writer rides
  `service.refresh_all`.
- **Portfolio Performance chart**: one aggregate total line for the selected
  set - dashed = retrospective-only stretch, solid from the first recorded
  snapshot; ranges persist at `localStorage.pfHistoryRange`.
- **Quotes are the latest live intraday print** (one bulk 5m/5d pull) with the
  prior close anchored to the last settled daily bar strictly before the print's
  session date; per-symbol cache `LIVE_QUOTE_TTL = 120s`; Refresh forces freshness.
- **Hosting (2026-10-13)**: GHA is the approved runner (Oracle dropped); the
  dry-run workflow is manual (`workflow_dispatch`) + `ci/**` push only - never
  `main`, no `schedule:`; heartbeats no-op until `HEALTHCHECK_URL` is set.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`), through a `claude-obsidian.transaction.v1` bundle - never a host
  Edit. Methodology is Generic. Product root: `../claude-obsidian`.
- **A green suite is the norm:** frontend **261 passed / 0 failed**, backend
  **812** tests green (serial `pytest -q` aborts on a pre-existing leaked
  lifecycle-watchdog thread; use a distributed run). A new failure is a real
  regression.
- **Card header extras render beside the `h2`, never inside it** (`00-V`, `00-W`).
  Keep it that way.
- **`/api/meta` is the sanctioned config-to-frontend channel**; consumers keep
  defaults that render identically if it fails.
- **Event timestamps are explicit UTC** (`Z`).
- **Never fetch a URL taken from untrusted content without a public-host guard.**
- **Tickers are US-listed only, ADR-mapped.**

## Active Threads

- **Hosting phase 2 (awaiting owner approval)**: storage = git-only private
  data repo (`captures/**` cloud-written, `data/**` local-only); open decision
  = missed-date catch-up policy; then schedules + `DATA_REPO_TOKEN`. Nothing
  scheduled; no real data migrated.
- Open, unowned: the serial `pytest -q` abort (leaked lifecycle-watchdog
  thread) - pre-existing, no owner yet.
