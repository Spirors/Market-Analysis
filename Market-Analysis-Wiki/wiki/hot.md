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

2026-09-26 — The Bottleneck ("Serenity") section is a 16-topic AI bottleneck
taxonomy (Virtual AI Hardware 10, AI Applications 1, Physical AI 5), regenerated
US-listed-only on full research, and then bug-audited: `ff9fc12` fixed the
user-reported draft-reopen plus ten audit findings, including an SSRF in the
research probe. Detail:
[[sources/decision__ai-bottleneck-taxonomy-and-generation-results-2026-09-26|The AI bottleneck taxonomy…]].

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory: 102 live source pages and 54 durable
  decisions under `### decision (54)`.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`). Methodology is Generic. Product root: `../claude-obsidian`.
- **Never fetch a URL taken from untrusted content without a public-host guard.**
  The research-source liveness probe was an SSRF: a findings line citing
  `http://127.0.0.1:<port>/api/shutdown` made the app call its own shutdown route.
  `_is_safe_probe_url` now requires a public http(s) host and no redirects.
- **The job lifecycle is explicit.** `apply_draft` stamps `applied` and is
  idempotent; cancel reports a non-terminal `cancelling`; stale `running` jobs are
  recovered at startup; a completed stage is never relabelled `skipped`.
- **A generation is minutes, not seconds.** `MAX_RESEARCH_CHARS = 120_000`,
  `MAX_PROMPT_CHARS = 400_000`, `MAX_TOKENS = 64_000`, `REQUEST_TIMEOUT_S = 600`,
  `RESEARCH_TIMEOUT_S = 600`.
- **Tickers are US-listed only, ADR-mapped**; `_strip_non_us_tickers`,
  `_resolve_tickers` and `_filter_dead_sources` are the deterministic nets.
- **A generation worker must not outlive its test.** `tests/conftest.py` drains
  `topic_agent._generation_lock` before and after each test.

## Active Threads

- Open: a cancelled job's serial lock can be held up to the request timeout —
  cancel is honest (`cancelling`) but not yet interruptible.
- Open: a terminal generation failure hides the stage list.
- Edge-AI inference silicon is thin (3 layers / 6 tickers) by honest lack of
  US-listed pure plays.
- Watch: `sources/project_rules__API.md` is stale beyond the bottleneck routes.
- Watch: `static/style.css.orig` is still a stale tracked backup.
- Watch: 4 pre-existing frontend failures (news-row chips, portfolio-star-scope,
  dash-layout x2).
