# 2026-09-08 — feat(bottleneck): up/down reorder + rename pencil

Bottleneck section gains interactive controls mirroring the Portfolio
section's established patterns:

## Backend

- New `app/bottleneck_prefs.py` — persistence layer for user overrides
  (order + renames) in `data/bottleneck_prefs.json`. The canonical
  `BOTTLENECK_CATEGORIES` constant is never mutated; prefs are applied
  at serve time.
- `app/bottleneck.py` — `bottleneck_read()` now calls `_apply_prefs()`
  which layers user order + renames on top of the ranked output.
  `category_original` field added to each category dict so the frontend
  can track canonical names after renames.
- 2 new API endpoints in `app/api.py`: `POST /api/bottleneck/categories/reorder`
  and `PUT /api/bottleneck/categories/{name}?new_name=...`.
- Cache-patching pattern mirrors `portfolio._patch_dashboard_cache()`.

## Frontend

- `static/js/cards.js` — `renderBottleneck()` enhanced with rename
  pencil (✎), move-up/down (↑/↓) buttons, inline rename input
  (`_startEditForCategory`), and reorder helper (`_moveBottleneckCategoryBy`).
  Module-level `bottleneckData` tracks categories with canonical names.
- `static/js/api.js` — 2 new fetch helpers: `reorderBottleneckCategories`
  and `renameBottleneckCategory`.
- `static/style.css` — `.bn-rename-btn`, `.bn-move-up`, `.bn-move-down`,
  `.bn-name-input` styles mirroring the portfolio `.pf-*` counterparts.

## Tests

- `tests/test_bottleneck_prefs.py` — 18 backend tests covering prefs
  persistence, reorder validation, rename validation, `bottleneck_read`
  integration, and API endpoint contracts.
- `tests/frontend/bottleneck-move.spec.mjs` — 7 Playwright tests for
  reorder (boundary state, swap, stopPropagation, reload persistence,
  single-category, chained swaps).
- `tests/frontend/bottleneck-rename.spec.mjs` — 6 Playwright tests for
  rename (inline input, Enter saves, Escape cancels, blur empty restores,
  stopPropagation, reload).

## Docs

- `project_rules/API.md` — 2 new endpoints documented.
- `project_rules/DECISIONS.md` — decision about prefs storage location
  and rationale.

## Files changed

- `app/bottleneck_prefs.py` (new)
- `app/bottleneck.py` (modified — `_apply_prefs`, `category_original` field)
- `app/api.py` (modified — 2 new endpoints)
- `static/js/cards.js` (modified — enhanced `renderBottleneck`)
- `static/js/api.js` (modified — 2 new fetch helpers)
- `static/style.css` (modified — new control styles)
- `tests/test_bottleneck_prefs.py` (new)
- `tests/frontend/bottleneck-move.spec.mjs` (new)
- `tests/frontend/bottleneck-rename.spec.mjs` (new)
- `project_rules/API.md` (modified)
- `project_rules/HANDOFF.md` (modified)
- `project_rules/SESSION_LOG.md` (this entry)
- `project_rules/DECISIONS.md` (modified)
- `project_rules/ROADMAP.md` (modified)
