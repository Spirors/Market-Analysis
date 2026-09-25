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

2026-09-25 — The Bottleneck section is topic-driven now: the 5 hardcoded
categories, their reorder/rename prefs and the flat layer table are gone,
replaced by user-authored topics with per-stock thesis cards, an in-app drafting
agent that writes nothing until you apply, and 13 JSON routes. Ten commits,
`a40c85e..099e932`. The plan file that drove it is retired; its durable content
is in the decision pages. `AGENTS.md` was then trimmed to 189 lines: rules stay,
rationale moved to the vault pages it links.

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The vault is the project's memory: 100 live source pages and 52 durable
  decisions under `### decision (52)`.
- Vault writes need WSL **as root** (`wsl -d Ubuntu-22.04 -u root`, explicit
  `--vault`): `Market-Analysis-Wiki/.vault-meta/transactions/` holds root-owned
  mode-700 state from earlier sessions and the engine reads it before it can
  start. `mode.json` is absent, so the methodology is Generic. Product root:
  `../claude-obsidian`.
- **Browser verification is split by tool.** Playwright (`tests/frontend/`, 18
  specs) is the regression gate — but its `webServer` is a static
  `python -m http.server` with every endpoint mocked, so it never exercises the
  real backend. `agent-browser` covers exploratory passes and screenshots; its
  local `SKILL.md` is only a stub over `agent-browser skills get core`.
- `.agents/skills/serenity-aleabitoreddit` is installed locally and gitignored
  (upstream `license: null`); only `skills-lock.json` is tracked.
- **One cached value per number, and the reader owns the invariant** — see the
  three 2026-09-25 decision pages: section design, API/agent contract, this rule.
- Subagent dispatch fails for a whole session if its agent-model binding is
  poisoned; replace the session rather than retrying.

## Active Threads

- Watch: `agent-browser`'s `screenshot`/`snapshot` are unverified end-to-end;
  three attempts hung on the wrapper, not the tool. Run it directly, output to a
  file.
- Watch: `sources/project_rules__API.md` is stale beyond the bottleneck routes;
  it predates the `thirteenf`/`ai_analysis` removal too. A callout marks it.
- Watch: `data/bottleneck_prefs.json` left on disk, unreferenced.
- Watch: `static/style.css.orig` is still a stale tracked backup.
- Watch: run the backend suite with `--ignore=tests/test_lifecycle.py` plus a
  separate lifecycle invocation — its watchdog calls `os._exit(0)` ~60s in.
- Watch: 4 pre-existing frontend failures (news-row chips, portfolio-star-scope,
  dash-layout x2).
- Watch: the agent's `skill_snapshot` hash differs in scheme from
  `skills-lock.json`'s `computedHash`.
- Watch: the dashboard still publishes a `bottleneck` key nothing reads now.
