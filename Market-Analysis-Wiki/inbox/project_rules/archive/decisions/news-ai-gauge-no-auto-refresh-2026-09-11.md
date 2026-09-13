# 2026-09-11 — AI capex-cycle gauge does NOT auto-refresh on tag edits

> Verbose companion to the pointer at `project_rules/DECISIONS.md`.

## What changed and why

The 2026-09-10 news overhaul (commit `4734cc9`) introduced an
auto-refresh of the AI capex-cycle gauge whenever a tag edit touched
`"ai"`. The user reviewed the feature and clarified that they want
the gauge to stay stable while curating tags — only the global Refresh
button should trigger the recompute.

## What was removed

### Backend (`app/api.py`)

The `POST /api/events/tags` endpoint used to call
`service._recompute_ai_sentiment(...)` inside a defensive `try/except`
and include the result in the response as `ai_sentiment`. Removed:

```python
# REMOVED from app/api.py
ai_sentiment = None
try:
    ai_sentiment = service._recompute_ai_sentiment(store.list_events(limit=5000))
except Exception:
    pass
return {"updated": updated, "events": store.list_events(limit=500), "ai_sentiment": ai_sentiment}
```

The endpoint now returns just `{updated, events}`. Faster, simpler,
no defensive try/except needed.

### Frontend (`static/js/events.js`)

Removed the `renderAISentiment(resp.ai_sentiment)` call from
`applyTagUpdate` and the `import { renderAISentiment } from "./cards.js"`
line. The function still calls `renderNews(resp.events)` to re-render
the timeline.

## What still works

The gauge still updates whenever the user clicks the global Refresh
button:

1. `main.js` Refresh handler → `postFullRefresh()` → `await load()`
2. `api.js load()` → `fetchDashboard()` → `renderSectionFn("all", dashboardData)`
3. `cards.js renderSection` (default case) calls
   `renderAISentiment(data.ai_sentiment)`
4. The `data.ai_sentiment` payload was computed by
   `service.get_dashboard()` → `_enrich()` → `_recompute_ai_sentiment(events)`
   which reads the current `data/events.json` (including the user's
   tag edits).

So the flow is: user tags news → click Refresh → `/api/dashboard`
reads updated `events.json` → recomputes gauge → renders. The user
sees the gauge update exactly when they expect it (after clicking
Refresh), not as a surprise side effect of editing a tag.

## Why this is the right shape

The user wants two distinct moments:

1. **Tag curation moment** — focus on the news timeline, no AI gauge
   noise. Tag edits should not move other gauges around.
2. **Refresh moment** — explicit user-initiated full refresh. Every
   gauge updates together because the user asked for the new state.

Auto-refresh on tag edit collapses those two moments into one, which
is jarring: typing a tag in the AI-tag column would suddenly flip a
number on a different card. Separating them gives the user stable
visual state during curation.

## Files touched

- `app/api.py` (−14 / +2 — removed the try/except block + `ai_sentiment`
  field from response)
- `static/js/events.js` (−~10 / +2 — removed `renderAISentiment`
  import and the `if (resp.ai_sentiment ...)` block in
  `applyTagUpdate`)
- `tests/test_api_contract.py` (replaced `test_events_tags_returns_ai_sentiment`
  with `test_events_tags_does_not_recompute_ai_sentiment` using a
  spy)

## Verification

```powershell
python -m pytest tests/test_api_contract.py -x -q
# 31 passed (was 30, net +1 — added the new no-recompute test)

# The new test uses a spy to confirm zero calls to
# service._recompute_ai_sentiment when a tag edit is POSTed.
```