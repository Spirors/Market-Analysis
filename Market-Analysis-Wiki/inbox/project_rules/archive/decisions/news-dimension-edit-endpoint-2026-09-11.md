# 2026-09-11 — News dimension-edit endpoint: manual fix for heuristic mis-classifications

> Verbose companion to the pointer at `project_rules/DECISIONS.md`.

## Problem

The 2026-09-10 news overhaul (commit `4734cc9`) added a `user_edited`
lock and shipped the existing tag-edit popover, but the fixed-dimension
pills (category / actor / direction / region) had no UI to change them.
When the heuristic put a story in the wrong category, the user couldn't
fix it from the timeline.

## Decision

Add a new endpoint + helper that overrides fixed dimensions:

- **Backend**: `store.update_event_dimensions(link, dimensions)` in
  `app/store.py` — validates each field against `_DIMENSION_VALUES`,
  sets only the named fields, treats `None` / empty string as "clear",
  arms `user_edited` on any change.
- **API**: `POST /api/events/dimensions` in `app/api.py` — body is
  `{link, category?, actor?, direction?, region?}`; only the named
  fields are updated. Returns `{updated, events}` to mirror
  `update_event_tags`. Errors: 400 on unknown field / invalid value;
  404 on unknown link; 400 on missing link.
- **Frontend**: popover branches on tag type:
  - Fixed-dimension pills → `<select>` of valid values + Remove
  - User / `ai` tags → existing free-text rename input + Remove
- **Region**: moved from the row metadata strip into the regular pill
  line so it shares the same popover as the other dimensions.

## Why a separate endpoint

`/api/events/tags` modifies the row's `tags` array (user-managed list).
`/api/events/dimensions` modifies the row's `category / actor /
direction / region` columns (heuristic-set, but manually overridable).
The two columns are conceptually different: tags are loose labels;
dimensions are typed slots with a closed allowed-value set.

Splitting them keeps the contracts honest:
- The tag endpoint can accept any free-text label (validated by the
  regex whitelist only).
- The dimension endpoint validates against a typed enum and can
  give precise 400 errors for "unknown field" vs "invalid value".

## Why no rename of a fixed-dimension to an arbitrary string

If we allowed free-text "rename" of `macro` to `earnings-watch`, the
row's `category` column would still be `macro` (only the `tags` array
would change). The pill rendering reads from the merged `tags` field
(category + actor + direction + region + user tags), so the user
would see `earnings-watch` as a pill — but the row's `category`
column would still be `macro`, and the category-based filter chips
would still match the row.

That's confusing. The popover for fixed dimensions uses a `<select>`
with the allowed values so the user can't end up in that inconsistent
state.

## API contract

### Request

```http
POST /api/events/dimensions
Content-Type: application/json

{
  "link": "https://example.com/story",
  "category": "micro",
  "direction": "bullish"
}
```

Any of `category`, `actor`, `direction`, `region` may be present or
absent. `null` or `""` clears the named dimension.

### Response (200 OK)

```json
{
  "updated": {
    "link": "...",
    "category": "micro",
    "actor": "government",
    "direction": "bullish",
    "region": "us",
    "tags": ["micro", "government", "bullish", "us"],
    "user_edited": true,
    ...
  },
  "events": [ ... ]
}
```

### Errors

- 400 — missing link, unknown field name, invalid value, non-dict body
- 404 — link not found in `data/events.json`

## Lock semantics

Same lock as `update_event_tags`: on any change, `user_edited` is set
to `True`. The RSS-refresh path in `upsert_events` checks this flag
and skips overwrite. So once a dimension is manually overridden,
every subsequent refresh (manual or scheduled) leaves it alone.

This means: if the user manually sets `category: micro` and then the
source retitles the article to "match" the macro keyword, the column
stays `micro`. The trade-off is the same as for tag edits — user
intent wins over heuristic re-derivation.

## Files touched

- `app/store.py` (+76 / −2)
- `app/api.py` (+28 / −15)
- `static/index.html` (+8) — popover dimension row
- `static/js/api.js` (+16) — `updateEventDimensions` helper
- `static/js/events.js` (+~80 / −~40) — popover branches, pills
  clickable, region moved into pill line
- `static/style.css` (+20) — `.tag-pop-dimension` styling
- `tests/test_store.py` (+85)
- `tests/test_api_contract.py` (+90)
- `tests/frontend/news-grouping.spec.mjs` (+147)

## Verification

```powershell
python -m pytest tests/test_store.py tests/test_api_contract.py -x -q
# 73 passed (42 + 31)

npx playwright test tests/frontend/news-grouping.spec.mjs --reporter=list
# 12 passed in 4.9s
```