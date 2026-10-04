# Section 03 — Regime

**Status:** `COMPLETE` (deep audit 2026-09-27; 03-A/E fixed, 03-B/C/D decision landed `d169c62`)
**Priority:** 6 of 9
**Last updated:** 2026-09-27

**Covers (raw parts):** `regime` card (`index.html:63-66` band), renderer
`renderRegime` (`static/js/cards.js` ~`:109-157`).
**Backend:** `app/regime.py` (`run_regime_detection`, `get_regime`), the detector
skill `.agents/skills/macro-regime-detector/`, assembled in `app/service.py`.
**Evidence:** static + grep recon of the renderer, the producer, the freshness
plumbing and the tests. No runtime probe needed.

---

## 1. Purpose

A 6-component cross-asset regime classification ("Concentration / Broadening /
Contraction / Inflationary / Transitional") with a composite score, signal zone,
transition probability and confidence, plus a per-component traffic-light grid
and a stale-report banner.

## 2. Data path (verified)

```
detector skill → metadata.generated_at ("%Y-%m-%d %H:%M:%S")
  → config.REGIME_DIR/macro_regime_*.json
app/regime.get_regime() (regime.py:99-122)
  • latest file (:107-110); age from FILE MTIME (:111)
  • stale / age_days (:112-114) vs REGIME_MAX_AGE_DAYS = 3 (config.py:349)
  • NaN → null (:118)
service.refresh_all() (service.py:269-287)
  • full=True → run_regime_detection() (:280); else setdefault(get_regime()) (:283)
  • vintage["regime"] = _now_iso() (:284)   ← stamped even when detection did NOT re-run
service._enrich() (service.py:357-358) injects data["regime"] at serve time when
  absent — WITHOUT stamping vintage["regime"] (contrast events :330-332)
  → /api/dashboard → renderRegime (cards.js:708/:722 → :109)
```

## 3. Findings

1. **`TOOLTIP` · P1 — 03-A · the tooltip failed 3 of the 5 standard points**
   (no interpretation, no causes, no as-of). **FIXED** (`372ffd3`): the entry now
   covers all five, including the component-grid thresholds (green ≥70, red ≤35)
   and the detector's `generated_at` stamp.

2. **`DATA`/`TOOLTIP` · P2 — 03-B · the tooltip promises a stamp the card never
   shows (open decision).** The fixed tooltip says *"the report carries the
   detector's own `generated_at` stamp as its date"*, but `grep generated_at
   static/` matches only the tooltip prose — the card renders the generic
   refresh-time `.vintage-note` instead. *Why:* the copy points at a date the UI
   does not display. **RESOLVED** `d169c62`: the card renders
   `metadata.generated_at` verbatim and opts out of `.vintage-note`.

3. **`DATA` · P2 — 03-C · two freshness signals on one card can disagree (open
   decision).** The body banner is derived from `regime.age_days` (file **mtime**,
   `regime.py:111-114`); the footer `.vintage-note` is derived from
   `vintage.regime`, which `refresh_all:284` sets to **now** even when `:283`
   served a cached days-old report. A light refresh can therefore show
   *"Stale report (5.0d old)"* and *"As of <today> ET"* simultaneously. *Why:*
   the cross-view consistency rule; the card contradicts itself about its own age.
   **RESOLVED** `d169c62`: the refresh stamp is no longer shown, so it cannot
   contradict the mtime-based stale banner.

4. **`DATA` · P3 — 03-D · path-dependent stamp presence.** A `refresh_market()`-only
   cache has no `vintage.regime` → the stamp is removed (`cards.js:690-693`), and
   the `_enrich` serve path adds `regime` without a stamp (`service.py:357-358`)
   → the same card shows no date on some routes and a misleading fresh date on
   others. **RESOLVED** `d169c62`: the date is read from the report itself, so it
   is identical on every route.

5. **`UX` · P3 — 03-E · the component grid can vanish silently.** If
   `composite.component_scores` is absent the whole grid disappears with no `—`
   fallback (`cards.js:134`), unlike the kv rows which do fall back (`:150-153`).

## 4. Tooltip 5-point status

03-A is **fixed**: ①✓ ②✓ ③✓ ④✓ (deps pill + prose) ⑤✓ (cites the stamp). 03-B
is now closed too — the card renders the cited stamp (`d169c62`).

## 5. Fixes completed

- [x] **FIX-03-A** `TOOLTIP` P1 — tooltip rewritten to all 5 points; thresholds
      verified against `cards.js:104-105,138`. Commit `372ffd3`.
- [x] **FIX-03-B/C/D** `DATA` P2 — the card renders the detector report's own
      `metadata.generated_at` (verbatim, no zone claim) as its date, opts out of
      the generic refresh-time `.vintage-note` (`CARD_VINTAGE_KEY`), and
      `refresh_all` stamps `vintage["regime"]` only when detection actually
      re-ran. Commit `d169c62`.
- [x] **FIX-03-E** `UX` P3 — explicit muted `Component scores —` fallback when
      `component_scores` is absent. Commit `d169c62`.

## 6. Tracked TODOs / open decisions

- [x] **DECISION 03-B/C/D** — **RESOLVED** (user, 2026-09-27): the detector's
      `metadata.generated_at` is authoritative; the card suppresses the generic
      `.vintage-note`; `refresh_all` stamps `vintage["regime"]` only when
      detection actually re-runs. Commit `d169c62`.
- [x] `UX` P3 — component-grid `—` fallback. Commit `d169c62`.

## 7. Coverage notes

- Producer/contract are well covered: `tests/test_regime_stale.py` (stale flag,
  `age_days` numeric, no-cache branches) and `tests/test_api_contract.py:252-300`
  (cached serve, NaN→null, stale flag).
- **Renderer coverage:** previously uncovered — the mock fixture now carries
  `regime.metadata.generated_at` and `vintage.regime` (added `d169c62`; detail in
  the added-coverage bullet below).
- The tooltip prose itself is pinned by `breadth-ai-valuation.spec.mjs:209-228`.
- **Renderer coverage added** `d169c62`: `regime-report-date.spec.mjs` asserts the
  report stamp renders and the generic `.vintage-note` is suppressed even with
  `vintage.regime` present, the stale override renders the amber banner alongside
  the report stamp, and the absent-grid `—` fallback.
