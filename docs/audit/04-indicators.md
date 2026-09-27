# Section 04 — Indicators (+ Breadth cards)

**Status:** `FIXED-PARTIAL` (deep recon done 2026-09-26; two `DATA` P1 fixes landed)
**Priority:** 5 of 9
**Last updated:** 2026-09-26

**Covers (raw parts):** `indicators` card (`index.html:95-110`), the two chart
cards `breadth` (`index.html:103-109`) and `breadth-ai` (`index.html:115-121`).
**Backend:** `app/indicators.py` (`pct_above_ma`, `compute_indicators`), payload
via `/api/dashboard` → `indicators`; assembled in `app/service.py:179-191`.
**Evidence:** static + targeted grep recon of `static/js/cards.js`,
`static/index.html`, `app/indicators.py`, `app/config.py`, `tests/`.

---

## 1. Purpose

One payload (`indicators`) feeds two presentations: the `Indicators` card's
text/KV rows (aggregate readings such as breadth %, VIX, yields) and the two
breadth chart cards (per-symbol bars). It is the shared-payload section where a
cross-view consistency defect is most likely.

## 2. Data path (verified)

```
app/indicators.py:pct_above_ma (:112-141)
  → compute_indicators (:254-289)
      breadth_core   = pct_above_ma(indices ∪ sectors)   # INDICES 4 (config.py:40-45)
      breadth_sectors= pct_above_ma(sectors)             # SECTORS 12 (config.py:124-137)
      "breadth": { breadth_pct, detail[sym] = { above, close, ma, pct_from_ma } }
  → app/service.py:185-191 (cached, vintage key "indicators")
  → GET /api/dashboard (static/js/api.js:58)
  → renderIndicators(data.indicators)  cards.js:708  ← aggregate numbers
  → renderBreadthSectorsChart(...)     cards.js:713  ← per-symbol bars
```

Both renderers read the **same** `data.indicators.breadth` object and share the
`indicators` vintage/cooldown, so staleness cannot diverge between them.

## 3. Findings

1. **`DATA` · P1 — 04-A · the breadth card labelled the metric it does not plot.**
   The card headline claimed the *aggregate share above the 50DMA*
   (`index.html:105`), and both breadth tooltips said "Share of … trading above
   their 50-day moving average" (`cards.js:577`, `:581`), while the renderer
   plots each symbol's **signed distance from its own 50DMA**
   (`cards.js:360-363,391` from `pct_from_ma`; dataset `"% from 50DMA"`
   `:408`; y-axis `"distance from 50DMA (%)"` `:415`). The chart's own inner
   labels were already correct — the outer label was the contradiction. The
   no-Chart.js fallback (`cards.js:422`) was worse: it printed `breadth_pct` —
   a *different quantity* — as if it were the chart's metric. *Why:* the card a
   user reads first described a number the card never shows.

2. **`DATA` · P1 — 04-B · two cards presented different quantities under one name.**
   The `Indicators` row "Breadth — Sectors & Indices (% > 50DMA)"
   (`cards.js:168`) shows `breadth_pct` (aggregate share, 0–100), while the
   breadth card's bars show signed per-symbol distance. Same payload key, same
   "Breadth" name, irreconcilable visually (e.g. `68%` vs `+5.0 / −2.3`).
   *Why:* the cross-view consistency rule; a reader reasonably assumes the bar
   chart aggregates to the headline number.
   **Note:** the audit's original hypothesis ("different universe") is *not*
   what the recon found — the universe is identical (`indices ∪ sectors` for
   both renderers). The divergence is **aggregation**, not universe.

3. **`DATA` · P3 — sectors-only figures are computed and served but never shown.**
   `breadth_sectors` / `breadth_indices` are produced (`indicators.py:258,289`)
   and pinned by `tests/test_indicators.py:354-365`, yet grepping `static/` for
   them returns zero hits. Either render them (the tooltip's "sector"
   wording suggests intent) or drop them. *Not fixed — product call.*

## 4. Fixes completed

- [x] **FIX-04-A / FIX-04-B** `DATA` P1 — every breadth label now describes what
      is plotted: `index.html:105` headline → "distance from 50-day MA"; both
      `CARD_TOOLTIPS` entries rewritten (signed distance, sign convention, real
      universe `4 indices + 12 sector ETFs`, and a pointer to the Indicators row
      for the aggregate share); the no-Chart.js fallback now labels its number
      "aggregate share (Chart.js unavailable)". The aggregate share keeps its
      home on the Indicators row, which resolves the name collision.
      New `tests/frontend/breadth-labels.spec.mjs` (4 tests) guards the labels —
      previously there was **zero** frontend coverage for them.
      Commit `5bf3b1f`.

## 5. Tracked TODOs

- [ ] `DATA` P3 — decide render-vs-drop for `breadth_sectors` / `breadth_indices`.
- [ ] Reconcile the `breadth` tooltip's `deps` (`["sector histories", "index histories"]`)
      with wherever the histories are actually sourced.
- [ ] Runtime probe (still open): mobile/narrow-width chart legibility for the
      three chart cards.

## 6. Verification notes

- Suite after the fix: **167 tests / 167 passed / 0 failed** (the 3 stale
  `dash-layout` ×2 and `portfolio-star-scope` specs were repaired in the
  test-hygiene pass `99907a7` — see `README.md` §10).
- No computed value, payload shape, or backend file changed.
- Threshold/enumeration claims in the new tooltip copy were checked against the
  code, not invented (distances are the plotted `pct_from_ma`; the "4 indices +
  12 sector ETFs" universe is `config.py:40-45,124-137`).
