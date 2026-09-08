# Portfolio reorder: dict key order, not a separate `order` field (2026-09-07)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Portfolio reorder: dict key order, not a separate `order` field (2026-09-07)

The portfolio reorder feature (move up / move down chevrons) persists
the order by rebuilding the `portfolios` dict in the new key order on
disk; Python's `json` and JS's `JSON` both preserve that sequence, so
the frontend's `Object.values(portfolios)` walks the new order
without any extra plumbing. Considered adding a top-level
`order: [pid, ...]` field (cleaner schema, easier to reason about)
but rejected because:

- It introduces a new field that needs migration handling for any
  existing `data/portfolios.json` that doesn't have it.
- The dict-key-order approach is what the file already uses
  implicitly (insertion order = render order). Reorder just makes
  the existing pattern explicit.
- The frontend already had to walk the dict in order — no extra
  iteration or index mapping required.
- A separate `order` field would be the second source of truth (the
  dict keys also have an order); a future bug where they diverge
  would be silent.

Caveat documented for the next agent: JSON's specification doesn't
*guarantee* object key order, but every JSON implementation in
production (Python's `json`, JS's `JSON`, Go's `encoding/json`, Java's
Jackson) preserves it. If a future version of Python's `json` ever
drops that guarantee, the on-disk order will need to migrate to an
explicit `order` field. Until then, dict-key-order is the cleanest
expression of the data shape.

