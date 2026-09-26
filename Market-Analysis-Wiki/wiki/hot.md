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
generation are reworked: underdogs are gated at **$3B** and defined as emerging
stocks with great potential, the core/extended tier is gone, and a generation job
reports four named research stages (`refresh_skill → read_lens → draft →
warm_metrics`). A real generation now **completes and is labelled**: the output
cap was consumed by the model's reasoning, the prompt never stated each card
field's type, and generated layers carried no name, constraint or watch item.
Five commits, `992efec..58e87f6`. Decision page:
[[sources/decision__serenity-underdog-semantics-and-research-stages-2026-09-25|Underdogs are $3B emerging names…]].

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory: 101 live source pages and 53 durable
  decisions under `### decision (53)`.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`): `.vault-meta/transactions/` holds root-owned mode-700 state the
  engine reads before it starts. Methodology is Generic (`mode.json` absent).
  Product root: `../claude-obsidian`.
- **Browser verification is split by tool.** Playwright (`tests/frontend/`, 18
  specs) is the mocked regression gate; `agent-browser` covers exploratory
  passes, with `open`, `snapshot` and `screenshot` verified live.
- **The drafting budget is set by reasoning, not by the draft.**
  `deepseek-v4.1-flash` on the Go lane is a reasoning model whose reasoning
  tokens share `max_tokens`: `MAX_TOKENS = 64_000` with `REQUEST_TIMEOUT_S = 600`,
  and the two must move together. A draft costs ~19k completion tokens (~12k
  reasoning), ~100s, ~$0.01.
- **An upstream layer is `{name, physical_constraint, what_to_watch, stocks}`**,
  stated in the prompt, `_normalize_draft`, `_layer_block` and `_validate_layer`.
  The engine aliases a legacy `layer` key on read, so topics generated before the
  fix label themselves without migration.
- `.agents/skills/serenity-aleabitoreddit` is installed locally and gitignored
  (upstream `license: null`); only `skills-lock.json` is tracked.
- Subagent dispatch fails for a whole session if its agent-model binding is
  poisoned; replace the session rather than retrying.

## Active Threads

- Watch: **the backend gate is intermittently flaky** — a temp-file race between
  the job poller and the worker's `os.replace` gave 0, 1 and 5 failures on
  identical code. Never judge a change from a single suite run; re-run.
- Watch: with the 600s drafting timeout, **Cancel only takes effect between
  attempts** — an in-flight request is not aborted, so a cancel can look
  unresponsive for up to 10 minutes.
- Watch: a terminal generation failure hides the four-stage list, so the failing
  step is not visible (`renderJobPanel`'s `failed` branch).
- Watch: `sources/project_rules__API.md` is stale beyond the bottleneck routes;
  it predates the `thirteenf`/`ai_analysis` removal too. A callout marks it.
- Watch: `static/style.css.orig` is still a stale tracked backup.
- Watch: 4 pre-existing frontend failures (news-row chips, portfolio-star-scope,
  dash-layout x2).
- Watch: the agent's `skill_snapshot` hash differs in scheme from
  `skills-lock.json`'s `computedHash`.
- Watch: the dashboard still publishes a `bottleneck` key nothing reads now.
