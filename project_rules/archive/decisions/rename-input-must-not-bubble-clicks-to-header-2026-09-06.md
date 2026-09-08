# Rename input must not bubble clicks to header (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Rename input must not bubble clicks to header (2026-09-06)

**Status:** confirmed + fixed (commit `974d988`).

Pre-fix `static/js/portfolio.js:200-207` header click handler's
skip list was `.pf-rename-btn, .pf-del, .pf-caret, .pf-pf-totals` —
missing `.pf-name-input`. When the user clicked inside the rename
input, the click bubbled up to the header handler and toggled
collapse, destroying the input mid-rename. Same root cause family
as the earlier Phase 0 "shared component cross-section state" bug
but on a different axis (event bubbling vs shared state).

**Fix (defense in depth):**
1. Added `.pf-name-input` to the skip list at line 202.
2. Added `e.stopPropagation()` on the input's click/focus/keydown
   handlers as belt-and-suspenders.

Either alone would suffice; both together prevent the next variant
of the same bug (e.g. if someone adds another child element to the
header without updating the skip list).

**Rule for inline-edit controls inside clickable containers:** When
a click handler on a parent toggles state, every interactive
descendant (inputs, dropdowns) MUST either be in the parent's
explicit skip list OR call `stopPropagation` on its own events.
Belt-and-suspenders — both, never just one.

**Plus CSS fix:** `.pf-rename-btn` in `static/style.css:1223` was
inheriting `font-weight: 600` and `border-radius: 6px` from the
generic `.mini` class while overriding `padding` to `0 4px`,
producing an oversized button that pushed the header layout.
Rewrote to `flex: 0 0 auto; font-size: 14px; font-weight: normal;
opacity: 0.6` (full opacity on hover/focus) — icon-only button
that fits naturally inline with the rename input.

**Rule for icon-only buttons sharing a generic button class:** When
adding a new icon-only button to a layout, do NOT rely on a generic
button class (`.mini`, `.btn`, etc.) for the base. Either define
the icon button as its own class with all required properties
explicit, or scope the generic class's properties via a more
specific selector.

