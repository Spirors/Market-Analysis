# 2026-09-10 — News `user_edited` lock: preserve manual edits across RSS refreshes

> Verbose companion to the pointer at `project_rules/DECISIONS.md`.

## Problem

The RSS refresh pipeline in `upsert_events()` (app/store.py:382)
re-derived fixed dimensions (category/actor/direction/region) from
the *current* title/summary text. If the heuristic later flipped an
event's category — e.g. the keyword list changed, or the publisher
rephrased a headline — the user's manual tag would stick but every
other field would silently snap to the new heuristic value. Worse, if
the source retitled the article, the user's mental model of "the
event I tagged with `ai`" could shift out from under them.

User's words: *"news that have been edited should not overwrite (fix
potential changes getting change due to pulling same news again)"*.

## Decision

Add a `user_edited: bool` field to every event row. Set to `True` by
`update_event_tags()` (the only entry point for user-driven mutation).
While set, `upsert_events()` short-circuits the entire update branch
and only refreshes `updated_at`. The event is then permanently locked
from RSS-side overwrites until the user explicitly removes their tags
(but `update_event_tags` re-sets `user_edited=True` on every call,
even tag-removal calls, so the lock is sticky).

## Schema

```python
_EVENT_FIELDS: tuple[str, ...] = (
    "link", "source", "title", "published", "date_label", "summary",
    "category", "actor", "direction", "region", "impact",
    "importance", "finance_relevance", "composite_importance", "source_weight",
    "tags", "first_seen", "updated_at", "user_edited",
)
```

`_build_event_payload` coerces missing `user_edited` to `False` so older
JSON files don't blow up on read.

## Mutation

```python
# app/store.py:update_event_tags
target["tags"] = sorted(set(current))
target["user_edited"] = True        # ← new
target["updated_at"] = _now_iso()
_save_state(state)
```

## Refresh lock

```python
# app/store.py:upsert_events
if target_row is not None:
    if target_row.get("user_edited"):
        # Lock: only touch updated_at. User's edits (title/summary/
        # category/actor/direction/region/tags) are preserved across
        # every subsequent RSS refresh, manual or scheduled.
        target_row["updated_at"] = now
    else:
        # Existing path: re-derive from current text.
        target_row.update({...})
```

## Trade-offs accepted

- **AI auto-tag never re-applied to a user-edited row.** If the user
  removes the `"ai"` tag from a row, then the publisher retitles the
  article to match AI keywords, the row stays un-tagged. This is the
  explicit behavior the user asked for.
- **No "unlock" affordance yet.** Once `user_edited=True`, the only
  way to make a row refreshable again is to delete it and re-pull it.
  Acceptable because (a) deletion always removes the row, and (b) the
  scheduler's `fetch_and_store` will re-insert it on the next refresh
  (as a fresh row with `user_edited=False`).
- **Lock fires on tag-removal too.** Removing a user tag sets
  `user_edited=True`, so the row becomes permanent. This matches
  "user manually touched this row" semantics.

## Tests added

```python
# tests/test_store.py
def test_update_event_tags_sets_user_edited_flag(tmp_store): ...
def test_upsert_events_skips_overwrite_when_user_edited(tmp_store): ...
def test_upsert_events_overwrites_normal_event(tmp_store): ...  # regression guard
def test_user_edited_default_false_for_unmodified_events(tmp_store): ...
```

All four fail on the pre-fix code, all four pass after. RED-GREEN
verified.

## Files touched

- `app/store.py` (+34 / −12)
- `tests/test_store.py` (+84)

## Verification

```powershell
python -m pytest tests/test_store.py -x -q
# 34 passed
```