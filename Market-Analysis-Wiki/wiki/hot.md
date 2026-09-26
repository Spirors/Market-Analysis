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

2026-09-26 — The Bottleneck ("Serenity") section is rebuilt as a 16-topic AI
bottleneck taxonomy (Virtual AI Hardware 10, AI Applications 1, Physical AI 5),
all regenerated US-listed-only on full research. Commit `61259a6` raised the
research cap to 120k and added US/ADR mapping, a resolution drop and a
source-liveness filter. Detail:
[[sources/decision__ai-bottleneck-taxonomy-and-generation-results-2026-09-26|The AI bottleneck taxonomy…]].

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory: 102 live source pages and 54 durable
  decisions under `### decision (54)`.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`): `.vault-meta/transactions/` holds root-owned mode-700 state the
  engine reads before it starts. Methodology is Generic. Product root:
  `../claude-obsidian`.
- **A generation is minutes, not seconds.** The research stage browses through
  the opencode CLI; `MAX_RESEARCH_CHARS = 120_000`, `MAX_PROMPT_CHARS = 400_000`,
  `MAX_TOKENS = 64_000`, `REQUEST_TIMEOUT_S = 600`, `RESEARCH_TIMEOUT_S = 600`.
- **Tickers are US-listed only, ADR-mapped.** The prompts require a US line
  (X-FAB -> XFABF, LPKF -> LPKFF, ASE -> ASX); `_strip_non_us_tickers`,
  `_resolve_tickers` and `_filter_dead_sources` are the deterministic nets;
  `job["dropped_tickers"]` records what a run removed.
- **A generation worker must not outlive its test.** `tests/conftest.py` drains
  `topic_agent._generation_lock` before and after each test, while the temp paths
  are still patched.
- **A long batch is resumable.** The driver writes a per-topic report only after
  the topic is applied, and skips a topic whose report exists; it must never
  clear the job store on resume.

## Active Threads

- Edge-AI inference silicon is thin (3 layers / 6 tickers) by honest lack of
  US-listed pure plays.
- Open (pre-existing): Cancel only takes effect between attempts (600s timeout);
  a terminal generation failure hides the stage list.
- Watch: `sources/project_rules__API.md` is stale beyond the bottleneck routes.
- Watch: `static/style.css.orig` is still a stale tracked backup.
- Watch: 4 pre-existing frontend failures (news-row chips, portfolio-star-scope,
  dash-layout x2).
