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

2026-09-26 — Session closed. The Bottleneck ("Serenity") section's phase-2 items
are done: the review panel now shows the researched sources, and the final thesis
is a **strict refinement** of the draft chain. Commits `32bbaea`, `e68f5d4`,
`ff95a3a`, `6697270`. Detail:
[[sources/decision__serenity-underdog-semantics-and-research-stages-2026-09-25|Underdogs are $3B emerging names…]].

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory: 101 live source pages and 53 durable
  decisions under `### decision (53)`. Counts are unchanged — the phase-2 closure
  was folded into the existing decision page.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`): `.vault-meta/transactions/` holds root-owned mode-700 state the
  engine reads before it starts. Methodology is Generic. Product root:
  `../claude-obsidian`.
- **A skill has no capabilities; the harness does.** The same skill researches
  inside an opencode session and cannot research inside the app's bare
  `chat/completions` call.
- **The drafting budget is set by reasoning, not by the draft.**
  `deepseek-v4.1-flash` is a reasoning model whose reasoning tokens share
  `max_tokens`: `MAX_TOKENS = 64_000` with `REQUEST_TIMEOUT_S = 600`.
- **`_reconcile_fill` makes the final a strict refinement of the skeleton**:
  skeleton layers (by name, case-insensitively) and tickers survive; only the
  skeleton's own content is restored. `job.fill_adjustments` records what was
  kept; `job.skeleton` keeps the first pass.
- **A generation worker must not outlive its test.** `tests/conftest.py` drains
  `topic_agent._generation_lock` before and after each test, while the temp paths
  are still patched — otherwise the worker writes the temp job list over the real
  `data/bottleneck_jobs.json`.
- Browser verification: Playwright is the mocked gate, and the live DOM check ran
  through a throwaway Playwright script against the real backend. The
  `agent-browser` CLI hangs under a redirected-pipe wrapper, and the built-in
  `browser.*` tools were disconnected this session.

## Active Threads

- Open beyond phase 2: with the 600s drafting timeout, **Cancel only takes effect
  between attempts** — a cancel can look unresponsive for up to 10 minutes.
- Watch: a terminal generation failure hides the six-stage list.
- Watch: generation is ~5-8 minutes and bills the Go subscription via the CLI.
- Watch: `sources/project_rules__API.md` is stale beyond the bottleneck routes.
- Watch: `static/style.css.orig` is still a stale tracked backup.
- Watch: 4 pre-existing frontend failures (news-row chips, portfolio-star-scope,
  dash-layout x2).
- Watch: 4 local commits are not yet pushed to `origin/main`.
