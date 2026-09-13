# Portfolio mutations must patch the cached dashboard payload (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Portfolio mutations must patch the cached dashboard payload (2026-09-06)

**Status:** confirmed + fixed (commit `b45858e`).

Pre-fix `app/portfolio.py` mutations (create/delete/rename portfolio,
add/edit/remove holding, add/edit/remove cash row) all wrote
`data/portfolios.json` correctly but never touched
`data/dashboard.json`. `service.get_dashboard` (app/service.py:283)
served the cached `dashboard.json` (with its embedded `portfolios`
sub-tree) until `QUOTE_TTL` expired or the in-page Refresh button
forced a full rebuild. Net effect: every portfolio mutation appeared
to silently fail until a manual Refresh, and the only "delete" that
"worked" was a phantom delete via stale cache + retry that produced a
404. The 44 stray "Test*" portfolios in `data/portfolios.json` were
the visible residue of this bug.

The reference pattern is `app/earnings.py:254-266` (add_ticker) and
`:283-291` (remove_ticker): after mutating `data/watchlist.json`,
patch `data/cache/earnings.json` in place via `store.save_json`. The
Portfolio module now follows the same shape with a new
`_patch_dashboard_cache(state)` helper (app/portfolio.py) called
after every `save_portfolios(state)`.

**Rule for future mutations:** Any new mutation function added to
`app/portfolio.py` MUST call `_patch_dashboard_cache(state)` after
saving, or it will re-introduce this exact bug. Extending the
regression test in `tests/test_portfolio_cache_sync.py` is the
mechanical reminder.

**Helper semantics:** best-effort — wraps the whole patch in a
`try/except` that silently returns on any failure. A failed patch
means the user sees stale data until QUOTE_TTL expires (same as
pre-fix), never a hard error. The patch updates
`cached["portfolios"]` with the freshly-enriched
(`enrich_portfolios` + `enrich_portfolios_with_earnings`) state and
bumps `vintage["portfolios"]` so the per-card "As of" stamp reflects
the mutation time.

