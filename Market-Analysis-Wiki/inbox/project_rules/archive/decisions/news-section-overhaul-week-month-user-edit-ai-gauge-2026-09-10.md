# 2026-09-10 — News section overhaul: umbrella decision

> Verbose companion to the pointer at `project_rules/DECISIONS.md`.
> The standalone rules live in their own archive files; this file is
> the feature-level summary.

## Three features in one commit

`4734cc9` ships three coordinated changes to the news timeline:

1. **Week/Month grouping toggle.** Both views, persisted per browser
   via `tlGroupingMode` + `tlSelectedMonth`; the existing
   `tlSelectedWeek` is untouched. Generic `buildGroups(items, mode)`
   in `static/js/events.js`. Segmented toggle inside `.tl-toolbar`.
2. **`user_edited` lock.** See
   `archive/decisions/news-user-edited-lock-2026-09-10.md`.
3. **AI gauge auto-refresh after manual AI tag.** `POST /api/events/tags`
   now returns `{updated, events, ai_sentiment}`. Defensive `try/except`
   around the recompute so transient market failures return
   `ai_sentiment: null` rather than 500-ing the tag save. Frontend
   re-renders only when the edit actually touched `"ai"`.

## Cross-cutting pitfall (caught and fixed)

See
`archive/decisions/news-cross-module-import-versioning-2026-09-10.md`.
The build went through a "module-graph split via versioned import"
mistake that silently made the click handler read `eventsCache=0`
even though `renderNews` had set it to 6. Fixed before commit; the
rule is now documented so future sessions don't relearn it.

## Verification matrix

| Surface | Tests | Status |
|---|---|---|
| Backend — `user_edited` lock | 4 in `test_store.py` | RED→GREEN |
| Backend — `ai_sentiment` in tag response | 1 in `test_api_contract.py` | RED→GREEN |
| Frontend — toggle + persistence + AI gauge re-render | 7 in `news-grouping.spec.mjs` | RED→GREEN |
| Backend — full suite (excl. portfolio_cache_sync / thirteenf / service_coverage) | 443 | PASS |
| Frontend — news section only | 7/7 | PASS |
| Frontend — full suite | 94 passed / 22 failed (baseline HEAD was 116 failed; net +94) | Net improvement |

## Operational notes

- Static server lifecycle per RUNBOOK.md step 2 (foreground form,
  captured PID, `Stop-Process` in `finally`). Playwright's `webServer`
  block silently didn't auto-start on Windows this session; the
  fallback was used without leaving an orphan.
- `data/events.json` NOT committed from this session (scheduler-owned).
  The next 17:00 `MarketAnalysis-EventsCommit` task will pick up any
  drift.
- `git stash` was used mid-session to compare baseline failures
  (HEAD without my changes) vs. the post-change state. Popped cleanly,
  no working-tree drift.

## Why "ship as one commit"

The three features are coupled: Feature 3 (AI gauge auto-refresh)
needs the `ai_sentiment` field in the tag response, which is the same
backend change Feature 1 + Feature 2 sit alongside. Splitting into
three commits would leave intermediate states where:
- Commit 1 (toggle) alone: works fine, no breakage.
- Commit 2 (lock) alone: works fine, no breakage.
- Commit 3 (AI gauge): frontend would call `renderAISentiment`
  expecting the function to exist; if events.js were committed
  first without cards.js's `export`, the import would silently
  resolve to `undefined`.

Bundling avoids that import-before-export window. The features are
also semantically related (all "make the news section match user
intent better") so a future reader of `git log` benefits from seeing
them as a single narrative change.