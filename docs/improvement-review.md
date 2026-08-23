# Market-Analysis — Full Section Review & Improvement Recommendations

**Date:** 2026-08-22
**Scope:** All backend engines, data layer, persistence, ops, API surface, frontend, tests.
**Method:** Three parallel recon passes (analysis engines · data layer & ops · frontend), followed by an independent verification pass (@oracle) that adjudicated the 10 highest-stakes claims against the code. All findings below are **verified** unless explicitly noted as corrected/overstated.

---

## 1. Executive summary

The codebase is functional and well-scoped, but the review surfaced **two dead analysis signals**, **one confidence-cap bug**, **systemic concurrency fragility** (server vs scheduled refresh), **failure-poisoned caches**, and **one real stored-XSS vector**. Test coverage exists for only 2 of ~16 modules — and both untested core modules (`risk.py`, `analysis.py`) contain the most serious correctness bugs. Every P0 defect below was catchable by a unit test.

**Highest-impact verified items (cross-lane):**

| # | Issue | Where | Severity |
|---|-------|-------|----------|
| 1 | Valuation-stretch condition mathematically unreachable → risk signal #9 and AI-gauge −15 penalty never fire (**confirmed**) | `risk.py:168-171,319`, `ai_sentiment.py:105-108,155-156` | High (correctness) |
| 2 | Failed fetches cached as empty results for full TTL — an outage silently blanks breadth/risk/ROC inputs for 24h (**confirmed; biggest integrity violation in the codebase**) | `market.py:144-148,208-210,299`, `thirteenf.py:299-300` | High (data integrity) |
| 3 | No single-flight guard + no cross-process coordination → N parallel refreshes, torn `dashboard.json` possible (**confirmed**; sqlite3's default ~5s busy-wait is the only accidental mitigation) | `service.py:82-88`, `store.py:14`, scheduler tasks | High |
| 4 | RSS-derived hrefs not scheme-checked → stored XSS via `javascript:` URIs (**confirmed**; exploitability low — one trusted feed) | `app.js:26-30,932,320` | Medium-High |
| 5 | `_TOTAL_WEIGHT = 15` vs table sum 14 → coverage understated; bites as a **threshold-flipping bug at the confidence caps** (e.g., weight_used=10: true 71.4% → uncapped, computed 66.7% → capped at 55) (**confirmed, impact refined**) | `analysis.py:31` | Medium-High |
| 6 | Two of three RED gates unreachable below 5 live signals (**confirmed with correction** — the third path is relative and survives) | `risk.py:336-337` vs `:343` | Medium |
| 7 | `feedparser.parse(url)` has no timeout — the only network call in the app without one; undated entries bypass the 48h window (**confirmed**) | `news.py:288,299` | Medium |
| 8 | Sequential per-proxy fetches inside bottleneck ranking on cold cache (**confirmed, count corrected: ~45–55**, not ~80 — ~20 proxies overlap the bulk snapshot) | `bottleneck.py:240-243` | Medium (perf) |
| 9 | Watchlist POST skips validation; symbols reach cache filenames — a scoped file-write primitive (**confirmed**) | `api.py:64-66`, `earnings.py:226`, `market.py:27-28` | Medium |
| 10 | `init_db()` runs on every store op; `DROP TABLE IF EXISTS news` unconditional (wasteful); legacy-events drop **is** schema-guarded — real costs are per-op lock churn vs the scheduler process; destructive path low-probability but high-blast-radius (**confirmed with correction**) | `store.py:77-80` (+6 call sites) | Medium |

---

## 2. Analysis engines

### 2.1 `app/risk.py` (~390 ln) — risk-divergence engine

- ✅ **Dead signal #9 (verified):** `_valuation_stretched` returns median & Q3 of *one sorted array*; median index `len//2` ≤ Q3 index `int(len*0.75)`, so `pe_median >= q3` requires exact float ties → unreachable. Root cause: no PE *history* exists, so the "vs top quartile" design can't work — needs absolute bands or persisted history (:168-171,:319).
- ✅ **RED gates vs sparse data (verified, narrowed):** max 7 tone-bearing signals; `consensus_optimism` (bullish≥5) and `capitulation` (bearish≥5) are unreachable below 5 signals (:336-337). The third RED path (:343, `bearish > bullish and dd <= -8`) is relative and survives — so 2 of 3 gates, not all of RED.
- **Division score degenerate + unused:** with `total == 0`, `div = 1.0` ("maximally healthy") despite zero evidence; score plays no role in verdict logic (:332).
- **Fragility-flag set mixes directions:** bull-side flags (:193,:226,:242) and bear-side flags (:202,:284) counted together toward the *consensus optimism* gate.
- **Unguarded `math.log`:** crashes on close ≤ 0 (:45,:58).
- **Duplication:** `_vix_ratio_at` reimplements `indicators.vix_signal`; `_roc_3m` duplicated ×4 across modules; breadth universe built twice.
- **Breadth double-counting:** INDICES+SECTORS universe includes both SMH and SOXX (`config.py:76-77`) → semis weighted twice in every breadth figure here and in indicators.
- **Hardcoded knobs:** `LB = -10`, breadth tiers 75/55/40/25, ±3 concentration/small-cap, ±1 credit, corr ±0.3, dd −5/−8/−10, count gates 5/1.
- **Tests:** none.

### 2.2 `app/ai_sentiment.py` (~185 ln)

- ✅ **Same dead-stretch pattern (verified):** threshold is Q3 of the identical list (:105-108) → the −15 penalty at :155-156 never applies.
- **Inconsistent "stretched" definition vs risk.py:** uses *all* earnings-cache companies (:99) while risk.py filters to AI-cohort tickers — two different stretch flags from one cache.
- **None-vs-zero conflation:** `r = roc or 0` treats missing ROC as 0.0; missing breadth becomes silent "neutral 50" (:50-51).
- **Median isn't a true median:** `sorted(pes)[len//2]` is upper-middle for even n (:103-104); same pattern in risk.py.
- **Magic weights/cutoffs:** ×2 ROC, ×1.5 spread, ×0.3 news, −15 valuation; verdict cutoffs ±60/±20 (:148-168).
- **Tests:** only `compute_ai_news_sentiment` basics + `_cohort_tone` branches; scoring path and `compute_valuation_flag` untested (a test would have caught the dead flag).

### 2.3 `app/bottleneck.py` (~325 ln)

- ✅ **Sequential fetches in ranking loop (verified, count corrected):** per-proxy `get_history(sym, days=120)` for missing symbols — ~68 unique proxies exist, ~20 overlap `AI_CAPEX_COHORTS` (already bulk-snapshotted) → **~45–55 sequential fetches on cold cache** (per-symbol 24h TTL thereafter) (:240-243). Slow first load + rate-limit exposure + mixed data vintages in one read.
- **Truthiness filter drops valid zeros, keeps NaN:** `[x["close"] for x in h if x.get("close")]` (:246).
- **Confusing sort semantics:** layers sorted most-negative-first ("most stressed"), while `strongest_signal` = max ROC (:275 vs :304-308).
- **Duplicated ticker data:** proxy lists inline-repeat names from `config.AI_CAPEX_COHORTS`; 40-day lookback hardcoded (:249).
- **Noisy averaging:** single-proxy layers (BOTZ, TSLA) get full weight in stream/category means.
- **Tests:** structure-only; `_rank_layer`, `_average_score`, `_sort_layers`, `bottleneck_read` untested.

### 2.4 `app/indicators.py` (~179 ln)

- **Arbitrary drawdown baseline:** short histories (<1y) silently compute "52-week" drawdown over less data, no flag (:78).
- **Unguarded log domain:** negative prices raise (:62).
- **Triplicated ROC logic** (see §5 theme 1).
- **Placeholder payload key:** `"RSP/SPY": None` shipped in output (:171).
- **Tests:** none — despite being the purest, most testable functions in the lane.

### 2.5 `app/analysis.py` (~337 ln)

- ✅ **Wrong total-weight constant (verified, impact refined):** `_TOTAL_WEIGHT = 15.0`; docstring weights sum to 3+2+2+1×7 = **14** (:31). Not a uniform 7% haircut — it flips at the cap thresholds (0.7/0.4 in `_confidence_from_score`): e.g., weight_used=10 → true coverage 0.714 (cap 100) vs computed 0.667 (**capped at 55**). Fix: derive from the weight table, never hand-maintain.
- **Unknown regime labels consume weight:** unexpected labels score neutral but still spend weight 2 (:136).
- **Narrow exception handling:** catches only `ValueError` from date parsing; non-string input raises uncaught `TypeError` (:65,:237).
- **Inconsistent breadth semantics:** ≥60/<45 here vs 75/55/40/25 tiers in risk.py — cross-engine "divergence" checks compare different scales (:151).
- **Silent truncation:** watch list capped at 2 flags/flips, bullets at 6 (:117-122).
- **Tests:** none — synthesis logic (including this bug) untested.

### 2.6 `app/regime.py` (~56 ln)

- **Unbounded staleness:** latest report chosen by filename glob sort, no TTL check → months-old report served forever once any exists (:10-14,:48-52).
- **Incomplete exception handling:** only `TimeoutExpired` caught; `OSError`/`FileNotFoundError` propagate into refresh (:29-34).
- **Blocking request path:** cold `GET /api/regime` triggers synchronous detection with hardcoded 300s timeout (:31,:53).
- **No schema validation** of globbed JSON; `days=600` hardcoded (:17).

---

## 3. Data layer, persistence & ops

### Cross-cutting: no real cross-process coordination

`store._lock` is a `threading.Lock` (`store.py:14`) — process-local only. The daily 09:00 task runs `python run.py --refresh` as a separate OS process while uvicorn serves `/api/refresh`. Verified nuance: Python's sqlite3 default ~5s busy-wait provides *accidental* partial mitigation, but `upsert_events` holds one transaction across many rows and `save_json` (:308-312) is non-atomic `write_text` → torn `dashboard.json` is possible. `IgnoreNew` prevents each task overlapping *itself*; DailyRefresh ↔ NewsRefresh ↔ server overlap freely.

### 3.1 `app/market.py` (~324 ln)

- ✅ **Negative caching (verified — biggest integrity violation found):** `get_history` caches `[]` when both sources fail (:144-148); bulk caches `{}` unconditionally (:208-210); futures cache failed all-null quotes (:299). `_fresh` (:31-39) serves empty payloads for full TTL. An outage silently blanks breadth/risk/ROC inputs for a day — direct violation of the project's core data rule. Only `get_quotes` has partial mitigation (per-symbol Stooq refill).
- **One bad bulk download kills all quotes silently:** whole yfinance call wrapped in `except Exception: pass` (:79-80); empty result → unpaced per-symbol Stooq loop blocking a request thread.
- **Cache key ignores symbol list:** global `"quotes"` key; partial payloads cached; Stooq backfills never persisted → re-fetched every call within TTL (:86-91).
- ⚠️ **Suspect Stooq symbol mapping (recon-only, unverified):** `sym.replace("^","").replace("=","").replace("-","")` yields codes like `GSPC`/`GCF` — likely invalid Stooq symbols (`^SPX`, `gc.f`) → index/commodity fallbacks may fail silently to None (:106,:176). Worth a manual check.
- **No retries/backoff/rate-limit detection** anywhere; bare excepts at :125-126,:169-170,:194-195,:235-236.
- `_HISTORY_CORE` hardcoded list belongs in config (:198).

### 3.2 `app/news.py` (~331 ln)

- ✅ **No fetch timeout (verified):** `feedparser.parse(url)` (:288) exposes no timeout and sets none internally — the only network call in the app without one; a stalled connection hangs the refresh thread/task indefinitely (hangs raise nothing, so the `except Exception` never fires).
- ✅ **Window bypass (verified):** `ts is not None and ts < cutoff` lets undated entries through (:299) — bounded by the ≥6.0 importance filter, but the 48h rule is bypassed. Fallback stamps `published = now` (:312) — fabricated-timestamp edge case vs the no-fabrication rule.
- Feed errors swallowed into `entries=[]`, not surfaced (:290-291).
- Scoring double-counts across overlapping term lists; `IMPORTANCE_THRESHOLD` duplicated by `IMPACT_BANDS` floor (:124 vs :127).

### 3.3 `app/store.py` (~319 ln)

- ✅ **Migration behavior (verified with correction):** `init_db()` runs on every store op (:120,:228,:235,:259,:278,:294); `DROP TABLE IF EXISTS news` (:77) is unconditional (harmless but wasteful); the legacy-`events` drop (:78-80) **is guarded** by schema detection and only fires on genuinely legacy schemas. Real costs: per-op overhead + write-lock churn against the scheduler process. Destructive path is low-probability but high-blast-radius — live-ingested events aren't re-seedable.
- **Cross-process SQLite exposure:** no WAL, no explicit `busy_timeout`; connections created per-call and never closed (handle leak until GC).
- **Dedupe edge cases:** merge overwrites original title/source/summary (last-writer-wins destroys provenance, :150-171); merged-away link discarded so delete-by-link can't remove the duplicate; impact escalation applied cross-source but same-link re-fetch overwrites impact back down; `_days_apart` returns 0 on parse failure → undated items always "in window" → over-merging (:60-61).
- **Non-atomic JSON writes:** direct `write_text` (:308-312) — concurrent readers see truncated JSON → spurious cache miss → duplicate refresh; interleaved writers corrupt files.

### 3.4 `app/thirteenf.py` (~301 ln)

- **Empty-snapshot poisoning:** EDGAR outage during rebuild still saves `{funds: [], errors: [...]}` with fresh `cached_at` → failure cached **20 days** (:299-300).
- **Sequential worst case ≈13 min** inside a synchronous request path.
- `issuer_ticker_map` caches `company_tickers.json` forever, silent `{}` on first-fetch failure (:78-94).
- Pacing global `_last_request_at` not thread-safe (:31,:41-43); UA lacks contact info SEC guidance asks for (:25).

### 3.5 `app/earnings.py` (~330 ln)

- **Rebuild cost:** 3+ network calls × ~15+ symbols, sequential, unpaced — synchronously inside `/api/dashboard` whenever the 30-min cache lapses.
- ✅ **Watchlist add skips validation (verified):** POST handler calls `add_ticker` directly (`api.py:64-66`); `add_ticker` (:226) only strips/uppers — `validate_symbol` exists but is never enforced. Symbol flows into `hist_{sym}_{days}` → `CACHE_DIR / f"{key}.json"` (`market.py:27-28`); `..` segments resolve on write (limited to `*.json`). Trivial today (localhost) but a file-write primitive that pairs badly with DNS-rebinding exposure (§5).
- Fast-path patch rows carry different `as_of` than rest of payload (:251); `EARNINGS_TTL` hardcoded (:17).

### 3.6 `app/scheduler.py` (~286 ln)

- `ExecutionTimeLimit PT1H` (:134): slow full refresh can be hard-killed mid-write → corrupt JSON caches (amplified by non-atomic writes).
- Delete-then-create install (:194-196): failed CREATE after DELETE loses the schedule (no rollback).
- Unbounded log growth (:153-155), no rotation.
- InteractiveToken tasks silently don't run when logged off — refreshes just stop.

### 3.7 `app/service.py` (~118 ln)

- ✅ **Duplicate refreshes (verified):** staleness check → synchronous `refresh_all(full=False)` with no single-flight guard (:82-88); sync endpoints run in FastAPI's threadpool → N stale requests = N parallel ~1-min refreshes (compounding rate-limiting that feeds the negative-caching bug). Same collision with the 09:00 process.
- Double `dashboard.json` write per full refresh (:40,:78).
- No per-section error isolation: one exception fails the entire dashboard 500.
- `regime.get_regime()` can trigger a 300s subprocess inside `_enrich` on an ordinary serve when no report exists (:104-105).

### 3.8 `app/api.py` + `run.py`

- **Unauthenticated mutations:** DELETE `/api/events`, suppress, watchlist add/remove, `POST /api/refresh?full=true` all open. 127.0.0.1 binding mitigates remote access but not DNS-rebinding — a webpage can trigger expensive refreshes or purge the event DB.
- `delete_event`: neither/nor of `link`/`source` → 200 no-op instead of 400; silent precedence (:34-40).
- `limit` params unvalidated (negative limit = unlimited rows).
- Single uvicorn worker, no graceful-shutdown hook for in-flight refresh writes.

---

## 4. Frontend

### 4.1 `static/app.js` (~1258 ln), `index.html` (~183 ln), `style.css` (~618 ln)

- **Stale-response races (top frontend issue):** every refresh path can silently render older data over newer; single-section refresh desyncs the header `as_of` timestamp vs card contents; failed mutations blank or crash cards; no `res.ok` checks before `res.json()` (:996-1008, :1217-1228, :753-769, :1240-1254).
- ✅ **URL-scheme XSS vector (verified):** `escapeHtml` (:26-30) escapes only `&<>"'` — attribute breakout prevented, but scheme injection passes untouched at :932 (news links, from external RSS persisted to SQLite) and :320 (13F manager links). Exploitability low (one trusted feed, curated seeds); fix is one line: allowlist `http(s):`. Minor residual holes: `risk_level` (:50), `ai.score` (:204), style-attr colors (:45-46,:585,:135).
- **Error routing misattribution:** all fetch failures write to `#riskBody` regardless of section (:992,:1005); silent catches (:761,:768,:382); add-ticker failures give zero feedback.
- **Monolith structure:** 1,258 global-scope lines mixing API client, ~20 renderers, two subsystems, layout engine; dual wiring paradigms cause listener-rebinding churn (:558,:744-750,:842) and `renderSection` default-case duplication (:967-982); labelMap hand-mirrors `config.py`.
- **Accessibility:** accordion and sortable columns keyboard-inaccessible (:558,:732,:744); glyph-only buttons (↻/✕) unlabeled; footer contrast fails WCAG AA at 11px (:577-583); sub-416px overflow (:57).
- **Notably NOT broken:** localStorage handling (versioned, validated, quota-safe), first-load empty states, Chart.js CDN-failure degradation (:478-482), escaping of news titles/user tickers.

---

## 5. Cross-cutting themes & architecture gaps

1. **Degradation is invisible.** The "never fabricate" rule is honored literally (nulls), but negative caching (#3.1) means the user sees *fewer signals*, never *"Yahoo down since 09:00"* — indistinguishable from genuine calm. Engines should emit coverage metadata; the UI should show it.
2. **Mixed-vintage renders.** `_enrich` patches fresh events/earnings onto cached payloads of arbitrary age; `ai_analysis` can cite last run's regime while other cards show current data. No cross-view consistency test exists despite consistency being a stated hard rule.
3. **Test strategy is inverted.** Both existing tests cover pure math modules; the *buggy* code is also mostly pure (analysis weights/confidence, risk gates, valuation flag, cache semantics, store dedupe) — cheap to test. Zero HTTP-layer tests despite 12 endpoints, half mutating. Don't chase coverage %; add golden tests for scorers + TestClient contract tests with stubbed services.
4. **Duplicated math drifting apart:** `_roc_3m` ×4 (risk/indicators/ai_sentiment/bottleneck), breadth-at-index ×3, VIX-ratio ×2, median/Q3 ×2 — already producing two different "stretched" definitions and two breadth vocabularies.
5. **Config rule: enforce selectively.** Symbols/TTLs/feeds belong in `config.py`. Invariants that must track a table (`_TOTAL_WEIGHT`, dedupe thresholds tied to dedupe logic) should be *derived*, not configured — the total-weight bug is exactly what happens when they're duplicated.
6. **Auth posture: no auth, add Host pinning.** Default 127.0.0.1 bind is right. DNS-rebinding can reach mutating endpoints (DELETE events, suppress, watchlist→file write). Right-sized fix: Host-header allowlist middleware + input sanitization. Tokens/passwords are friction that outruns the threat model unless you habitually bind `0.0.0.0`.
7. **Failure-handling philosophy:** swallow-and-default everywhere (`except: pass`, empty-list caching, fabricated timestamps) — opposed to the core data-integrity rule; `logging` is imported nowhere in the codebase.

---

## 6. Roadmap (final, verified)

Nothing here is L-effort; the whole P0 fits in a day and removes every confirmed correctness defect.

### P0 — Correctness & data integrity

| # | Action | Effort | Why / risk if deferred |
|---|--------|--------|------------------------|
| 1 | Fix valuation-stretch logic (risk.py, ai_sentiment.py): absolute-band threshold now; optionally persist PE medians per refresh for a real historical quartile later | S | A whole signal + penalty is theater; risk engine permanently blind to valuation fragility |
| 2 | Never cache empty results (market.py): skip `_put` on empty (or short retry-TTL + `degraded` flag) for histories, bulk, futures | S-M | Any Yahoo hiccup silently degrades every engine for 24h — direct violation of the core rule |
| 3 | Derive `_TOTAL_WEIGHT` from the weight table | S | Confidence caps flip at wrong boundaries |
| 4 | Scale RED gates by available signals (shares instead of absolute counts, or `max(5, ceil(total*0.7))`) | S | RED unreachable precisely during partial-outage stress |
| 5 | Validate watchlist symbols at the API boundary (`^[A-Z0-9.^=-]{1,10}$`) before persistence/cache-key use | S | Scoped file-write primitive |

### P1 — Resilience

| # | Action | Effort | Why / risk if deferred |
|---|--------|--------|------------------------|
| 6 | Single-flight refresh: module-level lock + double-check in `get_dashboard`/`/api/refresh`; serve stale-with-note while one refresh runs | S-M | Thundering-herd refreshes trigger rate-limits that feed P0-2 |
| 7 | Timeout the feed: fetch bytes via `urlopen(timeout=15)` → `feedparser.parse(bytes)`; decide explicitly on undated entries (drop or keep-with-label) | S | Hung refresh threads/tasks |
| 8 | SQLite + JSON hygiene: WAL + `busy_timeout` via one connect-helper; atomic `save_json` (temp file + `os.replace`) | S | Locked-DB errors, torn dashboard.json |
| 9 | Host-header allowlist middleware + href scheme allowlist in app.js | S | Rebinding-driven mutations; `javascript:` links |
| 10 | Bulk-pull bottleneck proxies (extend snapshot symbol list) | S | Slow cold builds, extra rate-limit exposure |
| 11 | Call `init_db()` once at startup, not per op; log loudly if migration ever drops a table | S | Lock churn; silent destructive migration |
| 12 | Regime TTL + staleness surfacing; catch `SubprocessError`/`OSError`; move timeout/days to config | S | Months-old reports served as current |

### P2 — Maintainability & polish

| # | Action | Effort | Why |
|---|--------|--------|-----|
| 13 | Tests for scorers and API: golden tests (analysis weights/confidence, risk-gate reachability incl. sparse-data cases, valuation-flag impossibility), store dedupe/migration, cache semantics ("empty is never cached"), TestClient contract tests | M | Every P0 bug above was catchable by a unit test |
| 14 | Surface degradation in UI: per-card coverage/"sources ok" badge driven by engine metadata | M | Users can't distinguish "no signal" from "source down" |
| 15 | Per-section vintage stamps end-to-end, recorded by `build_analysis` | M | Mixed-vintage facts erode trust in reads |
| 16 | Consolidate shared math into `indicators.py` (ROC, breadth, VIX ratio, median/Q3) with unit tests; fix SMH+SOXX double-count | M-L | Drift elimination |
| 17 | Reclassify constants: derived values move next to their tables; `config.py` keeps only true knobs | M | Prevents more drift like the total-weight bug |
| 18 | Split app.js into ES modules; standardize event delegation; serve labelMap from `/api/meta` instead of hand-mirroring config | M-L | Maintainability tax paid on every change |
| 19 | Frontend stale-response fixes: generation counter/AbortController per fetch, `res.ok` checks, per-card error states, correct error routing | M | Dashboard's core promise is trustworthy consistent numbers |
| 20 | Accessibility pass (aria-expanded/sort/labels, contrast, small-screen breakpoint) | S | Trivial fixes, local-tool severity |
| 21 | Scheduler hardening: rotate logs, reconsider PT1H limit, document logged-off behavior | S | Silent refresh stoppage + corrupt-write amplification |

---

## 7. Verification log

Independent @oracle pass adjudicated the 10 highest-stakes recon claims:

| # | Claim | Verdict |
|---|-------|---------|
| 1 | Valuation stretch compares median to Q3 of same sample → dead code | **CONFIRMED** — median index ≤ Q3 index of one sorted array; requires exact float ties. Root cause: no PE history exists. |
| 2 | `_TOTAL_WEIGHT = 15` vs table sum 14 | **CONFIRMED, impact overstated by recon** — not uniform 7%; a threshold-flipping bug at the 0.7/0.4 confidence caps. |
| 3 | Unconditional DROP TABLE migration on every op | **MOSTLY CONFIRMED** — `init_db()` per-op call sites confirmed; `news` drop unconditional (wasteful); `events` drop **is schema-guarded**. Real cost: lock churn; destructive path low-probability/high-blast-radius. |
| 4 | escapeHtml passes `javascript:` hrefs | **CONFIRMED** — attribute breakout prevented, scheme injection passes; exploitability low; one-line fix. |
| 5 | Negative caching poisoning | **CONFIRMED** — histories/bulk/futures all cache failures for full TTL; biggest integrity violation in the codebase. |
| 6 | No single-flight; no cross-process coordination | **CONFIRMED** — nuance: sqlite3 default ~5s busy-wait is accidental partial mitigation; torn dashboard.json still possible. |
| 7 | feedparser hang; undated entries bypass window | **CONFIRMED** — only network call without a timeout; 48h rule bypassed for undated entries. |
| 8 | ~80 sequential fetches in ranking loop | **DIRECTIONALLY RIGHT, NUMBER OVERSTATED** — actual ~45–55 on cold cache (~20 proxies overlap bulk snapshot). |
| 9 | RED gates unreachable with sparse data | **PARTIALLY CONFIRMED** — 2 of 3 RED paths unreachable below 5 signals; third path is relative and survives. |
| 10 | Watchlist POST skips validation; symbols hit cache filenames | **CONFIRMED** — `..` resolves on write, limited to `*.json`; pairs badly with rebinding exposure. |

One recon item remains unverified (low stakes): the suspect Stooq symbol mapping in `market.py:106,176` (§3.1) — worth a manual spot-check against Stooq's symbol directory.
