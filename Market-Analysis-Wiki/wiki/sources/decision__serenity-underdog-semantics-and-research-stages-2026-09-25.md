---
type: source
title: "Underdogs are $3B emerging names, and generation reports four named research stages"
status: evergreen
created: 2026-09-25
updated: 2026-09-25
source_kind: decision
tags:
  - source
  - decision
  - bottleneck
  - serenity
---

# Underdogs are $3B emerging names, and generation reports four named research stages

Two changes to the Bottleneck ("Serenity") section, shipped together
(`992efec`, `db148e7`).

## 1. Underdogs: a $3B gate and a stated definition

`UNDERDOG_CEILING_DEFAULT` is **$3B**, not $10B. $3B is the skill's own headroom
threshold — `references/methodology.md:334`, "Small enough (<~$3B at call for his
moonshots) that institutional re-rating is still ahead?" — so the app's default
now matches the lens it drafts with. The per-topic `underdog_ceiling` override
stays: this is a default, not a hardcode.

Underdogs are defined as **emerging stocks with great potential**, and the
definition is written once and mirrored verbatim in the two places a reader meets
it: the per-topic note (`app/bottleneck.py:_topic_note`) and the section help text
(`static/js/cards.js`). "Great potential" is carried by the researched thesis card
(`why_chokepoint`, `catalyst`, `evidence`) — the ceiling is the mechanical gate,
and no metric is invented to express it.

The **core/extended conviction tier is removed end to end**: the constant, the
`tier_for_market_cap()` helper, the `conviction_tier` card field, its validation,
the tier pill and its CSS. Reason: at a $3B ceiling it collided with
`CORE_TIER_MAX = $3B`, so `extended` became unreachable and every underdog would
have been `core`. Re-cutting the cutoff lower would have meant inventing a number
the skill does not supply, so the tier went instead. Ranking is unchanged and
stays deterministic: 40-day ROC, descending, in the pure read engine.

## 2. Generation reports four named research stages

A generation job persists an ordered `stages` list — the frontend's progress
contract — with statuses `pending | running | done | skipped | failed` and a
`note` for any degraded step:

| key | label |
|---|---|
| `refresh_skill` | Refresh skill |
| `read_lens` | Read lens |
| `draft` | Draft thesis |
| `warm_metrics` | Pull market data |

- Only `draft` can fail the job; the other three are **non-fatal** and record a
  note instead (e.g. an offline `npx` refresh falls through to the cached lens).
- `warm_metrics` is bounded (~20s) and reuses the existing warm path rather than
  a parallel warmer; a timeout leaves the succeeded draft intact.
- Jobs persisted before the field existed are served as-is, and the panel falls
  back to the old indeterminate bar.
- Transport is unchanged: 1.5s polling of `GET /api/bottleneck/jobs/{id}`. There
  is no SSE or streaming anywhere in the app.

**Behaviour change to keep in mind:** stage 1 now actually runs the `npx` skill
refresh as part of a generation run. Before this, the refresh was reachable only
from the explicit `POST /skill/refresh` endpoint, so a generation could draft
from a stale lens.

Research reach is deliberately **skill-lens only**: refresh the skill, read its
reference files, and use the app's own market/news caches. The drafting call is a
single `chat/completions` request with no tools, so it cannot browse; live web
lookup would need a new mechanism and stays out of scope.

## Verified

Backend 633 passed (+ 13 lifecycle); Playwright 143 passed with the 4 known
pre-existing failures; the bottleneck spec 20 passed. Each commit was also tested
alone, so neither is a broken intermediate. Live against the real backend: the
four stages rendered and advanced (`refresh_skill: done`, so the npx refresh ran
for real), a degraded run showed `draft: failed` + `warm_metrics: skipped`, and a
hand-created topic stored `underdog_ceiling = 3000000000` with the chip reading
`≤ $3B` and zero tier pills.

`agent-browser screenshot` is now **verified** end-to-end (it saved a PNG); the
earlier "unverified" note came from three redirected-pipe wrapper hangs, not the
tool.

## Open follow-ups

1. **A real generation currently fails on the token budget.** The run returned
   `model response was empty (finish_reason='length'); reasoning tokens may have
   consumed the budget`. `MAX_TOKENS` is still 8000 and the injected lens is large
   (`references/theses.md` alone is ~136 KB), so reasoning consumes the budget
   before any content is emitted. This is **pre-existing** — neither commit
   touched `MAX_TOKENS`, temperature, timeouts, or the injected document list —
   but it blocks the feature's happy path until the budget is raised or the
   injected context is trimmed.
2. **A terminal failure hides the stage list.** `renderJobPanel()`'s `failed`
   branch shows only the error notice, so the "which step failed" view disappears
   exactly when it is wanted.
