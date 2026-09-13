# Per-portfolio scope must use composite keys, not nested Maps (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Per-portfolio scope must use composite keys, not nested Maps (2026-09-06)

**Status:** confirmed + fixed (commit `1fafbc1`).

Pre-fix `static/js/watchColors.js` used a single Map keyed by symbol
only for the Portfolio section's star state. Starring NVDA in
"Fidelity Main" also starred NVDA in "Fidelity Roth IRA" because the
Map was shared across every portfolio. Same bug class as the Phase 0
tickerTable.js per-section key bug (commit 94442b6 follow-ups) but
on a different axis: portfolio-id vs section.

The fix uses composite `"<pid>::<sym>"` keys in the SAME flat Map,
not a nested `Map<pid, Map<sym, color>>` structure. The composite-key
approach keeps the localStorage serialization flat, stays compatible
with the existing `saveWatchColors` / `loadSection` infrastructure,
and means the storage key (`pfWatchColors`) is unchanged — only the
value shape evolved.

**Rule for future per-section per-entity scope:** When adding
per-(section, entity) persistence (e.g. per-portfolio, per-strategy,
per-watchlist), use a composite key inside the same Map rather than
a nested Map. Define the composite key format in `watchColors.js`
(or its successor), expose `get*(entity, key)` / `set*(entity, key,
value)` helpers, and keep the internal key shape private to that
module.

**Per-section opt-in:** the `SECTIONS` config table now carries a
`keyBy` field (`"symbol"` for Earnings, `"portfolio"` for Portfolio).
When adding a third section that needs a different scope axis (e.g.
per-strategy, per-watchlist), add a new `keyBy` value and a parallel
set of helpers — don't extend the existing two.

