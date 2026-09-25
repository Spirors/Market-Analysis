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
Ten commits, `a40c85e..099e932`.

## Key Recent Facts

- Local-first FastAPI + vanilla-JS macro market-analysis webapp, free no-key
  sources (yfinance + English-edition RSS), running locally on Windows.
- The wiki vault is the project's persistent memory: 98 live source pages and 50
  durable decisions under `### decision (50)`.
- Vault writes require WSL (`wsl -d Ubuntu-22.04`, always pass an explicit
  `--vault`; `.vault-meta/mode.json` is absent, so the methodology is Generic).
  Product root: `../claude-obsidian`.
- All project skills live in `.agents/skills/`. **`serenity-aleabitoreddit` is
  installed locally and gitignored** (upstream `license: null`); only
  `skills-lock.json` is tracked, for provenance.
- **One cached value per number, and the reader owns the invariant.** See [[sources/decision__one-cached-value-per-number-and-the-reader-owns-the-invariant-2026-09-25|One cached value per number — the reader owns the cross-view invariant]];
  [[sources/decision__bottleneck-section-is-topic-driven-2026-09-25|Bottleneck section is topic-driven — the category model is gone]] carries the section's frozen design.

## Recent Changes

- feat(bottleneck) 099e932 — accordion topics + expandable thesis cards, empty
  state, create/edit/delete, generate-review-apply, import/export, skill bar.
- feat(bottleneck) a34c99d — 13 routes; `GET /topics` is the single render call.
- feat(bottleneck) 7e4d6c6 — `app/topic_agent.py`: the app's only keyed path and
  only child-process spawn site.
- feat(bottleneck) 62289b6 — topic-driven engine; `BOTTLENECK_CATEGORIES` and
  `bottleneck_prefs` deleted.
- feat(ai-valuation) b41c5ac — `per_ticker_metrics` beside the cohort PE set.
- feat(bottleneck) 261f72a — `app/bottleneck_topics.py`.
- chore(skills) 8800256 + chore(config) a40c85e — skill swap + `.env.example`.

## Active Threads

- Watch: `data/bottleneck_prefs.json` left on disk, unreferenced.
- Watch: `HANDOFF-bottleneck-section.md` is untracked at repo root; its phase table
  and refresh command are superseded by the decision pages.
- Watch: `static/style.css.orig` is still a stale tracked backup (pre-existing).
- Watch: `tests/test_lifecycle.py`'s watchdog calls `os._exit(0)` ~60s in, so run
  the backend suite with `--ignore=tests/test_lifecycle.py` plus a separate
  lifecycle invocation.
- Watch: 4 pre-existing frontend Playwright failures (news-row chips,
  portfolio-star-scope, dash-layout x2); the 2 bottleneck-move specs were deleted
  with the old renderer.
- Watch: the agent's `skill_snapshot` hash uses a different scheme from
  `skills-lock.json`'s `computedHash`; reconciling them is a small follow-up.
- Watch: the dashboard still publishes a `bottleneck` key that nothing reads now.
