# 2026-09-10 — Cross-module imports in the news stack: never add a `?v=…` query to one side without the other

> Verbose companion to the pointer at `project_rules/DECISIONS.md`.

## The bug

Mid-build, I added a `?v=20260910` query to the `events.js → cards.js`
import. Combined with `main.js`'s existing `?v=20260905c` on its
`cards.js` import and `cards.js`'s unversioned import of `events.js`,
the result was a silent module-graph split:

| URL loaded | Module record |
|---|---|
| `cards.js?v=20260905c` (from main.js) | cards.js **A** |
| `events.js?v=20260910` (from cards.js A) | events.js **C** |
| `cards.js?v=20260910` (from events.js C) | cards.js **D** |
| `events.js` no-version (from main.js) | events.js **B** |

Four module records for two logical modules. JS spec says each
distinct URL gets its own record; each record has its own top-level
`let` bindings.

## Symptom

Initial render correctly populated `eventsCache` in one instance.
Click handler — registered in a different instance — read `eventsCache`
from its own instance, which was still the initial `[]`. Net effect:
clicking the Month button saw zero events and rebuilt the dropdown with
a single "No months" option.

Stack trace from the browser console (the diagnostic that cracked it):

```
[TL_RENDER_NEWS] itemsLen=6 stack= at renderNews (events.js:190)
                           | at renderSection (cards.js?v=20260905c:892)
                           | at load (api.js:85)
```

`renderSection` was in cards.js A. It called `renderNews` from
events.js (the unversioned URL). But the stack doesn't show the
query-string stripped from the frame name, so it looked like the same
module. Empirically it wasn't — the click handler's eventsCache and
the renderNews eventsCache were two different arrays.

## Why this is sneaky

- No console errors.
- No test failures (until the assertion counts the dropdown options).
- The split only manifests when module A's function reads module A's
  state, AND module B's function writes module A's state. Cross-module
  reads/writes via imports hit the same trap.
- A version bump on one import looks like a harmless cache-bust — and
  in a single-module codebase it would be — but in a mutual-import pair
  it creates a hidden duplicate.

## Decision

For any pair of modules that import each other (directly or via a
chain), both import URLs must be byte-identical. Either:

1. **Both unversioned** (the events.js ↔ cards.js case here). Simple,
   safe, no version-mismatch pitfall. The trade-off: a change to one
   module won't invalidate the other's cache; the entry-point script
   tag in `index.html` is the only cache-bust knob.
2. **Both versioned with the same query string** (e.g. `?v=20260910`).
   Used when you want per-module cache invalidation AND a tight import
   contract.

Mix-and-match (one versioned, one not) is the failure mode.

## Rule of thumb

> If module X imports module Y and module Y imports module X, the two
> import statements must use the *exact same URL* — including any query
> string. Mismatch = silent split-state bug.

## How to detect this in code review

```bash
# Look for the asymmetry:
grep -E 'import.*from.*\?v=' static/js/*.js
```

If the same logical pair shows different `?v=` values (or one has
`?v=` and the other doesn't), it's a bug.

## Lesson for future work

The 2026-09-05 shared-component persistence decision and the
2026-09-08 holdings-reorder decision both captured silent-state-bug
patterns. This is the third entry in that series. The pattern class:
"two pieces of code look identical to the developer but execute in
separate runtime instances, so state changes silently don't propagate".
The antidote: per-RUNBOOK.md "no version mismatches in import pairs" —
make it a project-wide lint rule if this ever happens again.

## Files touched (the fix)

- `static/js/events.js` — dropped `?v=20260910` from
  `import { renderAISentiment } from "./cards.js";`
- `static/js/cards.js` — dropped `?v=20260910` from
  `import { renderNews } from "./events.js";`
- No source-of-truth change; just restoring the import-URL parity.