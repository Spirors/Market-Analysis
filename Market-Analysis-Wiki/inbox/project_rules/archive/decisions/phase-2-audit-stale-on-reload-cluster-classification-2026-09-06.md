# Phase 2 audit — stale-on-reload cluster classification (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Phase 2 audit — stale-on-reload cluster classification (2026-09-06)

**Status:** audit complete; classification decided; refactor pass landed
in commit `b45858e`. This entry exists so a future session doesn't
re-derive the classification from scratch.

**Cluster observed:** add/delete a row inside a portfolio writes
server-side, but a plain reload shows stale state while the in-page
Refresh button brings it current. Same for whole-portfolio add/delete
and rename. Repro: add/delete row → `data/portfolios.json` reflects →
plain reload shows pre-mutation state → click Refresh → current.

**Classification — two separate issues, NOT the same root cause:**

1. **Dashboard-cache staleness** (the actual cluster). Pre-fix
   `app/portfolio.py` mutations wrote `data/portfolios.json` correctly
   but never touched `data/dashboard.json`. `service.get_dashboard`
   served the cached `dashboard.json` (with embedded `portfolios`
   sub-tree) until `QUOTE_TTL` expired. **Fixed by `b45858e`** — new
   `_patch_dashboard_cache(state)` helper called after
   `save_portfolios(state)` in all 9 mutation functions. Mirrors
   `app/earnings.py`'s existing `EARNINGS_CACHE_PATH` patching pattern.

2. **`tickerTable.js` shared-component state namespacing** (NOT this
   cluster). Per-section localStorage key bug class. Fixed in `94442b6`
   follow-ups via `VALID_SECTIONS` allowlist + `_assertValidSection()`.
   Different bug, different file, different surface.

**Refactor pass (Phase 2 #2) — already landed in `b45858e`.** The
unification the ROADMAP bullet called for is exactly what `b45858e`
does. Both modules now share the same pattern (write source-of-truth
JSON → patch cached payload → bump `vintage[<key>]` → best-effort
try/except). The 5-test regression suite in
`tests/test_portfolio_cache_sync.py` covers add/remove holding +
add/delete portfolio through TestClient — extend for any new mutation
type.

**Remaining debt surfaced by the audit (none blocking):**

- No `tickerTable.js`-style "shared component consumed by 2+ sections
  with independently-keyed persisted state" candidate beyond the
  existing per-portfolio star scoping (`getPortfolioWatchColor(pid,
  sym)`, commit `1fafbc1`). The audit bullet found no other candidates.
- Cache-invalidation shape is consistent across `earnings` and
  `portfolio`. Template for any future module:
  `save_<thing>(state)` → `_patch_<cache>_cache(state)` (reads cached
  payload, replaces sub-tree, bumps `vintage[<key>]`, writes via
  `store.save_json`, wrap in try/except so a failed patch degrades to
  "stale until QUOTE_TTL").

**Conclusion:** Phase 2 #1 + #2 effectively done — `b45858e` lands the
unification. No new commits required. Future sessions should treat the
existing `_patch_dashboard_cache(state)` helper as the template for any
new module's cache-invalidation logic.

---

