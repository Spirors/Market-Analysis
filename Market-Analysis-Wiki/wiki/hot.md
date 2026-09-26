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

2026-09-26 — Session closed. The Bottleneck ("Serenity") section's generation now
**researches the web**: a skill is a prompt bundle with no capabilities (the
harness supplies the tools), so the app now shells out to the opencode CLI under
a read-only project agent between the chain draft and the final thesis. A
generation runs six stages — refresh skill → read lens → draft chain → research
web → draft thesis → pull market data. 13 commits, `992efec..76f7dcc`, all
pushed. Decision page:
[[sources/decision__serenity-underdog-semantics-and-research-stages-2026-09-25|Underdogs are $3B emerging names…]].

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory: 101 live source pages and 53 durable
  decisions under `### decision (53)`.
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
- **The research stage runs the opencode CLI**: `--standalone`, prompt on stdin,
  `opencode-go/<model>`, `cwd` = repo root, agent
  `.opencode/agents/researcher.md` (mode primary; edit/shell denied).
- **An upstream layer is `{name, physical_constraint, what_to_watch, stocks}`**,
  stated in the prompt, `_normalize_draft`, `_layer_block` and `_validate_layer`.
- Browser verification: Playwright is the mocked gate; `agent-browser`'s `open`,
  `snapshot` and `screenshot` are all verified live.
- Subagent dispatch fails for a whole session if its agent-model binding is
  poisoned; replace the session rather than retrying.

## Active Threads

- **Phase 2, user-reported:** the draft chain and the final thesis can disagree —
  `fill` may add, drop or rename layers and tickers relative to the skeleton, so
  the mid-run preview differs from the applied result. Pin down the observed case
  before designing the fix.
- **Phase 2:** researched sources are persisted on the job but not shown in the
  UI yet.
- Watch: with the 600s drafting timeout, **Cancel only takes effect between
  attempts** — a cancel can look unresponsive for up to 10 minutes.
- Watch: a terminal generation failure hides the six-stage list.
- Watch: generation is now ~5-8 minutes and bills the Go subscription via the CLI.
- Watch: `sources/project_rules__API.md` is stale beyond the bottleneck routes.
- Watch: `static/style.css.orig` is still a stale tracked backup.
- Watch: 4 pre-existing frontend failures (news-row chips, portfolio-star-scope,
  dash-layout x2).
- Watch: the agent's `skill_snapshot` hash differs in scheme from
  `skills-lock.json`'s `computedHash`.
- Watch: the dashboard still publishes a `bottleneck` key nothing reads now.
