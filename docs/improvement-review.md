# Improvement Review — Remaining Work

**Updated:** 2026-08-22 (after error-fix pass)
**Branch:** `fix/review-errors` — all confirmed **errors** were fixed there (17 commits). See **`docs/fix-log.md`** for the plain-language story of everything that was fixed, how it was verified, and the choices made.

This file now lists only what is **left**: suggested improvements (not yet implemented, by design) and parked items that need your decision before anyone touches them.

---

## 1. Suggested improvements (not bugs — implement when you choose)

### Analysis engines
- **Consolidate duplicated math into `app/indicators.py`.** ROC-at-index exists 4× (risk / indicators / ai_sentiment / bottleneck), breadth counting 3×, VIX-ratio 2×. One canonical tested implementation prevents future drift.
- **Add test suites:** golden tests for `analysis` weights/confidence and risk-gate reachability (incl. sparse-data cases), store dedupe/migration tests, cache-semantics test ("empty results are never cached"), FastAPI TestClient contract tests for the 12 endpoints. Every fixed bug was catchable by a unit test.
- **De-network the bottleneck ranking** (`bottleneck.py:240-243`): ~45–55 sequential per-symbol fetches on a cold cache during dashboard builds. Pre-fetch proxies into the bulk snapshot so ranking is pure computation.
- **Move true knobs to `config.py`** (risk tone tiers, ai_sentiment weights/cutoffs, regime timeout/days, bottleneck lookback, earnings TTL). Derived values (like `_TOTAL_WEIGHT`, already fixed) should stay next to their tables, not in config.

### Data layer & ops
- **Surface degradation in the UI:** engines should emit coverage metadata ("7 of 9 signals live") and cards should show a small "sources ok" badge — today a source outage looks identical to genuine calm.
- **Per-section vintage stamps end-to-end**, recorded by `build_analysis`, so mixed-age data is visible.
- **Scheduler hardening:** rotate logs (`data/logs/` grows unbounded), reconsider the 1-hour execution limit (a slow full refresh can be killed mid-write), document that InteractiveToken tasks don't run while logged off.

### Frontend
- **Split `static/app.js` (~1,260 lines) into ES modules** (api / format / cards / earnings / events / layout); standardize event delegation; serve the card label map from a `/api/meta` endpoint instead of hand-mirroring `config.py`.
- **Accessibility pass:** keyboard-operable accordion + sortable columns, aria-labels on ↻/✕ buttons, footer contrast to WCAG AA, small-screen breakpoint.

---

## 2. Parked — needs your decision (do NOT auto-fix)

These are real findings, but fixing them changes analysis outputs or security posture, so they wait for you:

| Item | Where | Why it needs you |
|------|-------|------------------|
| SMH + SOXX both in the breadth universe | `config.py:76-77` | Semis are double-counted in every breadth figure (risk engine + indicators). Fixing changes all breadth-derived numbers. |
| Fragility flags mix bull- and bear-side flags | `risk.py:193,202,226,242,284` | Contradictory flags can satisfy the *consensus optimism* gate. Fixing changes RED verdict semantics. |
| Division score is degenerate and unused | `risk.py:332` | With zero data it reads "maximally divided/healthy". Decide: give it a role in verdicts or remove it. |
| Missing ROC treated as 0 ("neutral") | `ai_sentiment.py:50-51` | `roc or 0` conflates None with zero momentum. Fixing changes gauge scores. |
| Regime reports never expire | `regime.py:10-14,48-52` | A months-old report is served as current forever once one exists. Adding a TTL is a small feature — confirm the max age you want. |
| Cross-process refresh lock + SQLite WAL/busy_timeout | `service.py`, `store.py` | In-process duplicate refreshes are now blocked, but the 09:00 scheduled task can still overlap the server. A file lock + WAL changes DB behavior — worth doing deliberately. |
| Auth posture for mutation endpoints | `api.py` | DELETE/suppress/watchlist/refresh are unauthenticated (localhost-bound). DNS-rebinding can reach them. Options: Host-header allowlist middleware (cheap) vs tokens (friction). Your call. |
| Suspect Stooq symbol mapping | `market.py:106,176` | Unverified recon claim: `^`/`=`/`-` stripping may produce invalid Stooq codes (`GSPC` vs `^SPX`, `GC=F` vs `gc.f`). Needs a manual check against Stooq's symbol directory; if wrong, index/commodity fallbacks silently fail today. |
| Event delete precedence when BOTH link and source given | `api.py:34-40` | Currently link wins silently. Fine to keep — just confirming it's intentional. |

---

## 3. Context

- Original full findings (per-module detail with file:line refs) are preserved in git history: commit `047c9db` on `main`.
- Fixed-error inventory with commit hashes: `docs/fix-log.md`.
