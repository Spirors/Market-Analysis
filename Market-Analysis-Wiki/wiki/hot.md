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

2026-09-25 — The Bottleneck (chokepoint) section is topic-driven now. The 5
hardcoded categories, their reorder/rename prefs and the old flat layer table are
gone, replaced by user-authored topics with expandable per-stock thesis cards, an
in-app drafting agent that writes nothing until you apply it, and 13 JSON routes.
Ten commits, `a40c85e..099e932`. The plan file that drove it is retired; its
durable content is in the decision pages.

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The wiki vault is the project's persistent memory: 100 live source pages and 52
  durable decisions under `### decision (52)`.
- Vault writes require WSL **as root** (`wsl -d Ubuntu-22.04 -u root`): the vault's
  `.vault-meta/transactions/` holds root-owned mode-700 state dirs from earlier
  sessions, and the engine reads that directory before it can start. Always pass an
  explicit `--vault`. `.vault-meta/mode.json` is absent, so the methodology is
  Generic. Product root: `../claude-obsidian`.
- All project skills live in `.agents/skills/`. **`serenity-aleabitoreddit` is
  installed locally and gitignored** (upstream `license: null`); only
  `skills-lock.json` is tracked, for provenance. `agent-browser` ships only a
  discovery stub — its CLI is not installed.
- **One cached value per number, and the reader owns the invariant.** See
  [[sources/decision__one-cached-value-per-number-and-the-reader-owns-the-invariant-2026-09-25]];
  [[sources/decision__bottleneck-section-is-topic-driven-2026-09-25]] carries the
  section's frozen design; [[sources/decision__bottleneck-section-api-and-agent-contract-2026-09-25|Bottleneck section API and agent contract]].
- Subagent dispatch fails for a whole session if its agent-model binding is
  poisoned. See [[sources/decision__a-poisoned-agent-model-binding-is-inherited-by-child-sessions-2026-09-25|A poisoned agent-model binding is inherited by child sessions]].

## Recent Changes

- docs(wiki) f347f6e — session-end transaction: 3 decision pages, index
  47 -> 50, log, hot.
- feat(bottleneck) 099e932 — accordion topics + expandable thesis cards, empty
  state, create/edit/delete, generate-review-apply, import/export, skill bar.
- feat(bottleneck) a34c99d — 13 routes; `GET /topics` is the single render call.
- feat(bottleneck) 7e4d6c6 — `app/topic_agent.py`: the app's only keyed path and
  only child-process spawn site.
- feat(bottleneck) 62289b6 — topic-driven engine; `BOTTLENECK_CATEGORIES` and
  `bottleneck_prefs` deleted.
- feat(ai-valuation) b41c5ac — `per_ticker_metrics` beside the cohort PE set.
- chore(skills) 8800256 + chore(config) a40c85e — skill swap + `.env.example`.

## Active Threads

- Watch: `sources/project_rules__API.md` is stale beyond the bottleneck routes —
  it predates the `thirteenf`/`ai_analysis` removal too. A callout marks it.
- Watch: `data/bottleneck_prefs.json` left on disk, unreferenced.
- Watch: `static/style.css.orig` is still a stale tracked backup (pre-existing).
- Watch: `tests/test_lifecycle.py`'s watchdog calls `os._exit(0)` ~60s in, so run
  the backend suite with `--ignore=tests/test_lifecycle.py` plus a separate
  lifecycle invocation.
- Watch: 4 pre-existing frontend Playwright failures (news-row chips,
  portfolio-star-scope, dash-layout x2); the 2 bottleneck-move specs were deleted
  with the old renderer.
- Watch: the agent's `skill_snapshot` hash uses a different scheme from
  `skills-lock.json`'s `computedHash`.
- Watch: the dashboard still publishes a `bottleneck` key that nothing reads now.
