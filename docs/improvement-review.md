# Improvement Review — Status After Improvements Pass

**Updated:** 2026-08-22 (after improvements pass)
**Branch:** `improvements/review-2026-08-22` — all eight **suggested improvements** from §1 are now implemented there (16 commits), plus one bonus bug the new tests caught. Plain-language details: **`docs/improvements-log-2026-08-22.md`**. The earlier error-fix round lives on `main` (log: `docs/fix-log-2026-08-22.md`).

---

## 1. Implemented (this branch)

| Improvement | Outcome |
|---|---|
| Consolidate duplicated math into `indicators.py` | One canonical, tested set of helpers; duplicates deleted; outputs verified bit-identical |
| Centralize engine knobs in `config.py` | ~24 constants moved (risk tiers/bands, AI-gauge weights/cutoffs, regime timeout/days, bottleneck lookback, earnings TTL, core symbol list) — values unchanged |
| De-network bottleneck ranking | All 68 proxy symbols prefetch in the bulk snapshot; per-symbol fallback no longer triggers on normal builds |
| Regression test suites | 5 new suites, 51 tests (61 total, ~1.2 s, fully offline): analysis golden paths, risk-gate reachability incl. sparse data, store integrity, cache semantics, API contracts |
| Surface degradation in UI | Per-section `coverage` counts; cards show a tiny "n/m" badge only when something is missing |
| Per-section vintage stamps | Each card can show its own "As of HH:MM" from payload `vintage` — no more implied single timestamp |
| Scheduler hardening | Daily-dated logs auto-pruned after 30 days (`--logfile-prefix`), 4-hour execution limit, overwrite-safe install, logged-off limitation documented |
| Split `app.js` into ES modules | 8 modules under `static/js/`; labels served by `GET /api/meta` from config (in-JS fallback identical); behavior preserved |

**Bonus fix caught by the new tests:** `_confidence_from_score` had a misordered ternary making the 35% low-coverage cap unreachable (very-low-coverage syntheses capped at 55 instead). Fixed in `5c7602a`; regression test unskipped and green.

---

## 2. Parked — still needs your decision (do NOT auto-fix)

These are real findings, but fixing them changes analysis outputs or security posture, so they wait for you:

| Item | Where | Why it needs you |
|------|-------|------------------|
| SMH + SOXX both in the breadth universe | `config.py` | Semis are double-counted in every breadth figure (risk engine + indicators). Fixing changes all breadth-derived numbers. |
| Fragility flags mix bull- and bear-side flags | `app/risk.py` | Contradictory flags can satisfy the *consensus optimism* gate. Fixing changes RED verdict semantics. |
| Division score is degenerate and unused | `app/risk.py` | With zero data it reads "maximally divided/healthy". Decide: give it a role in verdicts or remove it. |
| Missing ROC treated as 0 ("neutral") | `app/ai_sentiment.py` | `roc or 0` conflates None with zero momentum. Fixing changes gauge scores. |
| Regime reports never expire | `app/regime.py` | A months-old report is served as current forever once one exists. Adding a TTL is a small feature — confirm the max age you want. |
| Cross-process refresh lock + SQLite WAL/busy_timeout | `service.py`, `store.py` | In-process duplicate refreshes are blocked, but the 09:00 scheduled task can still overlap the server. A file lock + WAL changes DB behavior — worth doing deliberately. |
| Auth posture for mutation endpoints | `app/api.py` | DELETE/suppress/watchlist/refresh are unauthenticated (localhost-bound). DNS-rebinding can reach them. Options: Host-header allowlist middleware (cheap) vs tokens (friction). Your call. |
| Suspect Stooq symbol mapping | `app/market.py` | Unverified recon claim: `^`/`=`/`-` stripping may produce invalid Stooq codes (`GSPC` vs `^SPX`, `GC=F` vs `gc.f`). Needs a manual check against Stooq's symbol directory; if wrong, index/commodity fallbacks silently fail today. |
| Event delete precedence when BOTH link and source given | `app/api.py` | Currently link wins silently. Fine to keep — just confirming it's intentional. |

---

## 3. Notes

- The stale dev server noticed during testing (PID on port 8000, started before these changes) will serve old code until restarted — restart `python run.py` to see the new frontend and `/api/meta`.
- Original full findings (per-module detail with file:line refs) are preserved in git history: commit `047c9db` on `main`.
