# Bottleneck category user prefs live in `data/bottleneck_prefs.json` (2026-09-08)

**Status:** confirmed + shipped.

## Core problem

The Bottleneck section needed user-customizable category order (reorder via ↑/↓
chevrons) and display names (rename via ✎ pencil), mirroring the Portfolio
section's established patterns. The canonical category list lives in
`app/bottleneck.py:BOTTLENECK_CATEGORIES` — a module constant that the
test suite (`tests/test_bottleneck.py` L17-22) asserts is stable.

## Decision

User prefs (order + renames) live in `data/bottleneck_prefs.json`, separate
from the `BOTTLENECK_CATEGORIES` module constant. The canonical list is
never mutated; prefs are applied at serve time by `bottleneck_read()`.

### State shape

```json
{
  "version": 1,
  "order": ["Robots", "Agentic AI", ...],
  "renames": {"Agentic AI": "My AI"}
}
```

### Rationale

1. **Test invariant preservation.** `test_bottleneck.py:L17-22` asserts
   `BOTTLENECK_CATEGORIES` has exactly 5 categories in definition order.
   If prefs mutated this constant, that test would break. Keeping it
   read-only preserves the invariant while letting users personalize.

2. **Graceful degradation.** Empty/invalid `prefs["order"]` falls back to
   canonical definition order. This means adding or removing a category
   upstream doesn't break the prefs file — the user just sees the new
   category appended at the end (or the missing one silently ignored).

3. **Canonical tracking.** The output includes a `category_original` field
   on each category dict, carrying the canonical name regardless of renames.
   This lets the frontend track which backend key to send for API calls
   (move/rename), even after display names collide from renames.

4. **Cache-patching pattern.** Follows the same
   `_patch_dashboard_cache` pattern as `app/portfolio.py` — structural
   patch only (order + names), bump the vintage stamp, skip on failure.
   The next full refresh rebuilds everything anyway.

### Failure modes

- **File missing/corrupt:** `load_prefs()` returns default (empty order,
  empty renames) — canonical order and names, no crash.
- **Stale order (category added/removed):** Invalid permutation → fallback
  to canonical order. User sees the new category appended; doesn't lose
  their other customizations.
- **Name collision after rename:** Two categories could end up with the
  same display name. The `category_original` field prevents API confusion;
  the frontend never sends display names to the backend.

## Files

- `app/bottleneck_prefs.py` — new persistence layer (load/save/reorder/rename)
- `app/bottleneck.py` — `_apply_prefs()` applied in `bottleneck_read()`
- `app/api.py` — 2 new endpoints (reorder + rename)
- `static/js/cards.js` — `renderBottleneck()` enhanced with controls
- `static/js/api.js` — 2 new fetch helpers
- `static/style.css` — new `.bn-*` control styles
- `tests/test_bottleneck_prefs.py` — 18 backend tests
- `tests/frontend/bottleneck-move.spec.mjs` — 7 Playwright tests
- `tests/frontend/bottleneck-rename.spec.mjs` — 6 Playwright tests
