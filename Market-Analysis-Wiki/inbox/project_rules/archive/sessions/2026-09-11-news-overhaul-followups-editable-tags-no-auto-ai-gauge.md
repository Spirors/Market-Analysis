# 2026-09-11 — News overhaul follow-ups: editable tags + no AI-gauge auto-refresh

> Verbose companion to the pointer at `project_rules/SESSION_LOG.md`.
> The live SESSION_LOG keeps only the latest entry in full per
> AGENTS.md hybrid layout; this file holds the verbose detail
> (file:line citations, test breakdowns, verification matrix) so a
> future session implementing or debugging can read it without
> re-deriving from scratch.

## Commit

`fa2c976` — `fix(news): make all pills editable + drop auto AI-gauge
refresh on tag edits`

## Why these follow-ups

The user reviewed the 2026-09-10 news overhaul (commit `4734cc9`) and
reported two issues:

1. **Tags weren't editable.** The `user_edited` lock was in place, but
   the fixed-dimension pills (category / actor / direction / region) had
   no UI to change them. Only user / `ai` tags opened a popover. The
   user's original request "make the tags editable for manual fix when
   heuristic fails" wasn't satisfied.
2. **AI gauge auto-refresh was unwanted.** Adding the `ai` tag to a news
   event should not flip the gauge — only the global Refresh button
   should trigger the recompute.

## Two fixes

### Fix 1 — every pill is editable

**Backend.** New `store.update_event_dimensions(link, dimensions)` function
in `app/store.py` and a new `POST /api/events/dimensions` endpoint in
`app/api.py`.

```python
# app/store.py
_DIMENSION_VALUES: dict[str, frozenset[str]] = {
    "category": frozenset({"macro", "micro"}),
    "actor": frozenset({"government", "company"}),
    "direction": frozenset({"bullish", "bearish", "neutral"}),
    "region": frozenset({
        "us", "global", "asia", "europe", "middle-east",
        "russia-ukraine", "korea", "japan", "china", "other",
    }),
}
```

Validates field names against the keys, values against the allowed
sets. `None` / empty string clears the dimension (column becomes null,
pill disappears from the merged display tags). On any change, sets
`user_edited=True` so the RSS-refresh lock fires (the override survives
the next re-ingest).

Empty `dimensions` dict is a valid no-op (no field change → no lock
arm). Returns the updated event payload (with merged display `tags`)
or `None` if the link was not found.

**Frontend.** Two-mode popover in `static/js/events.js`:

- **Fixed-dimension pills** (where `TAG_TO_FIELD[tag]` is set): the
  rename row (`#tagPopRenameRow`) is hidden and the dimension row
  (`#tagPopDimensionRow`) is shown, populated with the allowed values
  for that field via `FIELD_VALUES`. A "(clear)" option is appended
  when the current tag is truthy (you can null the dimension out).
  Save button → `applyDimensionUpdate(link, field, selectedValue)`.

- **User / `ai` tags** (where `TAG_TO_FIELD[tag]` is empty): the
  dimension row is hidden and the rename row is shown with the
  existing free-text input. Save button → `applyTagUpdate(link, [next], [oldTag])`.

**Region pill moved.** Previously rendered in the row metadata strip
(`regionPill` in `renderEventItem`); now rendered as a regular pill
in the tag line so it shares the same popover as the other dimensions.
This avoids duplicating region info in two places.

**All pills clickable.** Removed the `!FIXED_DIMENSIONS.includes(t)`
gate in `renderEventItem` so every pill carries `data-act="tag-edit"`.
The `data-field` attribute is set to the dimension field name when
the pill belongs to a fixed dimension (empty string for user / `ai`).
The click handler passes `data-field` to `openTagPopover` which
branches accordingly.

### Fix 2 — no AI-gauge auto-refresh

**Backend.** Removed the `service._recompute_ai_sentiment(...)` call
and the `ai_sentiment` field from `POST /api/events/tags`:

```python
# app/api.py — updated endpoint
return {"updated": updated, "events": store.list_events(limit=500)}
```

The defensive `try/except` wrapper is gone (no compute to defend
against). The endpoint is simpler and faster.

**Frontend.** Removed `renderAISentiment(resp.ai_sentiment)` call from
`events.js:applyTagUpdate` and the `import { renderAISentiment } from
"./cards.js"` import. No other code change — the gauge still updates
when the user clicks the global Refresh button (`/api/dashboard` →
`_enrich` → `_recompute_ai_sentiment` reads the current `events.json`).

## Test matrix

### Backend — `tests/test_store.py` (+85 lines, 8 new tests)

| Test | Status | What it proves |
|---|---|---|
| `test_update_event_dimensions_sets_provided_field` | PASS | Single-field update; unrelated columns untouched |
| `test_update_event_dimensions_clears_field_with_none` | PASS | `None` clears the column and removes the pill from merged tags |
| `test_update_event_dimensions_updates_multiple_fields` | PASS | Multi-field update; old dimensions removed from tags, new ones present |
| `test_update_event_dimensions_sets_user_edited_lock` | PASS | Subsequent upsert with conflicting value keeps the override |
| `test_update_event_dimensions_returns_none_for_unknown_link` | PASS | Unknown link → `None` |
| `test_update_event_dimensions_rejects_unknown_field` | PASS | Unknown field name → `ValueError` |
| `test_update_event_dimensions_rejects_invalid_value` | PASS | Invalid value → `ValueError` |
| `test_update_event_dimensions_empty_dict_is_noop` | PASS | Empty dict doesn't touch the row or arm the lock |

### Backend — `tests/test_api_contract.py` (+90 lines, 9 new tests)

| Test | Status | What it proves |
|---|---|---|
| `test_events_tags_does_not_recompute_ai_sentiment` | PASS (replaces obsolete test) | Spy confirms zero `service._recompute_ai_sentiment` calls on tag edit; `ai_sentiment` field absent from response |
| `test_events_dimensions_updates_field` | PASS | Single-field update via endpoint |
| `test_events_dimensions_clears_field_with_null` | PASS | `null` clears the column |
| `test_events_dimensions_multiple_fields` | PASS | Multi-field update via endpoint |
| `test_events_dimensions_arms_user_edited_lock` | PASS | Endpoint response carries `user_edited=True` |
| `test_events_dimensions_rejects_unknown_field` | PASS | Unknown field → 400 |
| `test_events_dimensions_rejects_invalid_value` | PASS | Invalid value → 400 |
| `test_events_dimensions_404_for_unknown_link` | PASS | Unknown link → 404 |
| `test_events_dimensions_400_for_missing_link` | PASS | Missing link in body → 400 |

### Frontend — `tests/frontend/news-grouping.spec.mjs` (+147 lines, 5 new tests)

Describe block "Editable news tags (manual fix for mis-classified events)":

| Test | Status | What it proves |
|---|---|---|
| `every pill on a row is clickable (fixed dimensions + auto ai + user tags)` | PASS | All pills carry `data-act="tag-edit"`; no inert fixed dimensions |
| `clicking a fixed-dimension pill opens a <select>-based popover` | PASS | Rename row hidden, dimension row visible, `<select>` populated with `["macro", "micro", "(clear)"]`, Save dispatches POST `/api/events/dimensions` |
| `the popover also offers 'clear' to null out a dimension` | PASS | "(clear)" option → POST with `category: null` |
| `dimension edit arms user_edited lock (refresh cannot undo it)` | PASS | Override changes pill from `macro` to `micro`; original `macro` pill gone |
| `clicking a user-added (or auto 'ai') tag opens the free-text popover` | PASS | Dimension row hidden, rename row visible with input pre-filled |

Describe block "AI gauge does NOT auto-refresh on tag edits":

| Test | Status | What it proves |
|---|---|---|
| `tagging 'ai' leaves the gauge showing its pre-tag score until Refresh` | PASS | After tagging, gauge still shows "Score 38" (the pre-tag value) |

## Verification commands

```powershell
# Backend (full suite minus long-running + flaky files)
python -m pytest tests/ -k "not portfolio_cache_sync and not thirteenf and not service_coverage" -q
# → 459 passed in 119.64s (was 443, net +16)

# Targeted backend
python -m pytest tests/test_store.py tests/test_api_contract.py -x -q
# → 73 passed (42 + 31)

# Frontend (news section only)
npx playwright test tests/frontend/news-grouping.spec.mjs --reporter=list
# → 12 passed in 4.9s (was 7, net +5)
```

## Operational notes

- **Static server lifecycle.** Playwright's `webServer` block silently
  didn't auto-start on Windows in this session; the foreground form
  was used (`Start-Process` with captured PID, `Stop-Process` in
  `finally`) per RUNBOOK.md §"Server lifecycle checklist" step 2.
  No orphan server left running at session end.

## Files committed

```
M  app/api.py                                (+28 / −15)
M  app/store.py                              (+76 / −2)
M  static/index.html                         (+8)
M  static/js/api.js                          (+16)
M  static/js/events.js                       (+~80 / −~40)
M  static/style.css                          (+20)
M  tests/frontend/news-grouping.spec.mjs     (+147)
M  tests/test_api_contract.py                (+90)
M  tests/test_store.py                       (+85)
```

`data/events.json` is gitignored and unchanged on disk — no
intervention. The next 17:00 `MarketAnalysis-EventsCommit` scheduled
task will commit any drift there.