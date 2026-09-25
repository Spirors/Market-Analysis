---
type: meta
title: Hot Cache
status: developing
created: 2026-09-13
updated: 2026-09-25
tags:
  - meta
  - hot-cache
---

# Recent Context

## Last Updated

2026-09-25 — The Bottleneck ("Serenity") section's underdog semantics and its
generation are reworked: underdogs are gated at **$3B** (the skill's own headroom
threshold) and defined as emerging stocks with great potential, the
core/extended tier is gone end to end, and a generation job reports four named
research stages (`refresh_skill → read_lens → draft → warm_metrics`). A real
generation now **completes**: the output cap was consumed by the model's
reasoning stream, and the prompt never stated each card field's type. Four
commits, `992efec..0d22495`. Decision page:
[[sources/decision__serenity-underdog-semantics-and-research-stages-2026-09-25|Underdogs are $3B emerging names…]].

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory: 101 live source pages and 53 durable
  decisions under `### decision (53)`.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`): `Market-Analysis-Wiki/.vault-meta/transactions/` holds root-owned
  mode-700 state from earlier sessions and the engine reads it before it can
  start. `mode.json` is absent, so the methodology is Generic. Product root:
  `../claude-obsidian`.
- **Browser verification is split by tool.** Playwright (`tests/frontend/`, 18
  specs) is the regression gate — but its `webServer` is a static
  `python -m http.server` with every endpoint mocked, so it never exercises the
  real backend. `agent-browser` covers exploratory passes; `open`, `snapshot` and
  `screenshot` are all verified live.
- **The drafting budget is set by reasoning, not by the draft.**
  `deepseek-v4.1-flash` on the Go lane is a reasoning model whose reasoning
  tokens share `max_tokens`: `MAX_TOKENS = 64_000` with `REQUEST_TIMEOUT_S = 600`,
  and the two must move together. A draft costs ~16k completion tokens (~13k of
  them reasoning), ~80s, ~$0.01.
- `.agents/skills/serenity-aleabitoreddit` is installed locally and gitignored
  (upstream `license: null`); only `skills-lock.json` is tracked.
- **One cached value per number, and the reader owns the invariant** — see the
  three 2026-09-25 decision pages: section design, API/agent contract, this rule.
- Subagent dispatch fails for a whole session if its agent-model binding is
  poisoned; replace the session rather than retrying.

## Active Threads

- Watch: with the 600s drafting timeout, **Cancel only takes effect between
  attempts** — an in-flight request is not aborted, so a cancel can look
  unresponsive for up to 10 minutes.
- Watch: a terminal generation failure hides the four-stage list, so the failing
  step is not visible (`renderJobPanel`'s `failed` branch).
- Watch: `sources/project_rules__API.md` is stale beyond the bottleneck routes;
  it predates the `thirteenf`/`ai_analysis` removal too. A callout marks it.
- Watch: `static/style.css.orig` is still a stale tracked backup.
- Watch: run the backend suite with `--ignore=tests/test_lifecycle.py` plus a
  separate lifecycle invocation — its watchdog calls `os._exit(0)` ~60s in.
- Watch: 4 pre-existing frontend failures (news-row chips, portfolio-star-scope,
  dash-layout x2).
- Watch: the agent's `skill_snapshot` hash differs in scheme from
  `skills-lock.json`'s `computedHash`.
- Watch: the dashboard still publishes a `bottleneck` key nothing reads now.
