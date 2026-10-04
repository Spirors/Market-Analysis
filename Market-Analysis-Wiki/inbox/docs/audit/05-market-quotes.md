# Section 05 — Market Quotes (indices / commodities / rates)

**Status:** `COMPLETE` (deep audit 2026-09-27; 05-A/B/C/D/E/F all fixed)
**Priority:** 8 of 9
**Last updated:** 2026-09-27

**Covers (raw parts):** `indices` (`index.html:62-105` band), `commodities`,
`rates`. **Renderers:** `renderIndices` (`static/js/cards.js` ~`:241-269`),
`renderCommodities` (~`:276-321`), `quotesTable`/`renderQuotes` (~`:226-238`).
**Backend:** `app/market.py` (`build_market_snapshot`, `build_futures_snapshot`,
`_quote_snapshot`), `app/spot.py` (`build_spot_snapshot`), assembled in
`app/service.py` (`refresh_market`).
**Evidence:** static + grep recon of the three renderers, the producers, the
fixtures and the tests. No runtime probe needed.

---

## 1. Purpose

Three structurally simple quote tables: a merged spot-vs-futures **indices**
table, a grouped **commodities** spot/futures table, and a **rates** table of
Treasury yields. Together they are the app's "what are prices doing" surface.

## 2. Data path (verified)

```
indices:     market.build_market_snapshot() → "indices"      (market.py:311, as_of :310)
           + market.build_futures_snapshot() → "index_futures" (market.py:380, as_of :379)
             → service.refresh_market (service.py:177-178, 212-213) → dashboard payload
             → renderIndices (cards.js:710 → :248)

commodities: spot.build_spot_snapshot() → "commodities_map"  (spot.py:255-259, as_of :250)
           + market.py:314 ("commodities") + market.py:381 (futures commodities)
             → service.py:217 (spot_snap — NO vintage stamp), :225, :231-232
             → renderCommodities (cards.js:712 → :282)

rates:       market.py:313 ("rates") → service.py:224
             → renderQuotes (cards.js:711/:725 → :236 → quotesTable :226)
```

Freshness: only **rates** carries a vintage stamp (`CARD_VINTAGE_KEY.rates =
"market"`, `cards.js:523-536`). indices/commodities render a footer
`asofNote(futures.as_of || data.as_of)`, where `futures.as_of` is just
`_now_iso()` at snapshot build (`market.py:379`) — **not** an exchange/FRED/LBMA
source time.

## 3. Findings

1. **`DATA` · P2 — 05-A · rates shown under a "Price" header with no unit.**
   `quotesTable` hard-coded a `Price` column for percent yields. **FIXED**
   (`4fbb73e`): the header is parameterised and rates pass `Yield (%)`.

2. **`DATA` · P2 — 05-B · null handling diverged across the three cards.**
   indices already showed an explicit `—` per cell; commodities **dropped the
   row** when both sides were null (`cards.js:301`) and could drop a whole group
   (`:314`); rates **dropped the row** on a null quote (`:230`) even though
   `market.rates` carries the key with a `null` value. Two tooltips claimed
   *"Failed fetches show as null"* — false for both. **User decision
   2026-09-27: always show the row with `—`.** **FIXED** `5e4cbba`.

3. **`DATA`/`TOOLTIP` · P2 — 05-C · the indices and rates tooltips are
   byte-identical and both mis-describe the card.** They say
   `"Quotes + daily change, derived from close history (yfinance fast_info is
   broken). Failed fetches show as null."` — the indices card actually pairs
   **spot vs E-mini futures**, and the rates card shows **Treasury yields as %**.
   Neither states ②interpretation, ③what changes it, or ⑤as-of. *Folded into
   05-B for the false clause.* **FIXED** `1432d13`: all three entries (indices,
   rates, commodities) rewritten to the 5-point standard.

4. **`DATA` · P2 — 05-D · the indices/commodities "As of" stamp means the wrong
   thing (open decision).** It is `_now_iso()` at snapshot build
   (`market.py:379`), i.e. *when the app fetched*, not the source date — while
   `spot.as_of` (`spot.py:250`) and per-row `source_date` exist and are never
   read. *Why:* for a daily FRED/LBMA close, "as of now" overstates freshness.
   **RESOLVED** `1432d13`: the commodities foot shows the spot source date when
   known, else the fetch time; indices keep the fetch time (live quotes).

5. **`DATA` · P3 — 05-E · `spot.attribution` and per-row `source_date` are
   promised but never rendered.** `config.py:77-78` and `spot.py:260-262` say
   attribution is "rendered at the foot of the card" and per-row `source_date`
   labels carry provenance; `grep attribution|source_date static/` → **0 hits**.
   *Why:* a stated provenance guarantee that the UI does not honour. **FIXED**
   `1432d13`: attribution and the source date render at the commodities card foot.

6. **`ARCHITECTURE` · P3 — 05-F · `cov["futures"]` is computed but never
   displayed.** `service.py:113-117` counts it; no `SECTION_CARDS` key maps to
   `futures` (`cards.js:485-491`). Probably intentional — worth confirming.
   **FIXED** `9cc83be`: dropped.

## 4. Tooltip 5-point gap (before 05-B/C)

| Card | ① measures | ② interpret | ③ what changes it | ④ source | ⑤ as-of |
|---|---|---|---|---|---|
| indices | ✗ | ✗ | ✗ | ⚠ | ✗ |
| commodities | ⚠ | ✗ | ✗ | ✅ | ✗ |
| rates | ⚠ | ✗ | ✗ | ⚠ | ✗ |

## 5. Fixes completed

- [x] **FIX-05-A** `DATA` P2 — rates value column labelled `Yield (%)`
      (`cards.js` `quotesTable` + both call sites). Commit `4fbb73e`.
- [x] **FIX-05-B** `DATA` P2 — null policy applied + false tooltip clauses
      corrected. Commit `5e4cbba`.
- [x] **FIX-05-C** `TOOLTIP` P2 — indices/rates/commodities tooltips rewritten to
      the 5-point standard. Commit `1432d13`.
- [x] **FIX-05-D/E** `DATA` P3 — commodities foot shows the spot source date when
      known (else fetch time) and renders `spot.attribution`. Commit `1432d13`.
- [x] **FIX-05-F** `ARCHITECTURE` P3 — dead `cov["futures"]` dropped. Commit
      `9cc83be`.

## 6. Tracked TODOs / open decisions

- [x] **DECISION 05-D** — **RESOLVED** (user, 2026-09-27): source date when
      known, else fetch time. Commit `1432d13`.
- [x] **DECISION 05-E** — **RESOLVED** (user, 2026-09-27): render
      `spot.attribution` + the source date at the card foot. Commit `1432d13`.
- [x] **DECISION 05-F** — **RESOLVED** (user, 2026-09-27): drop `cov["futures"]`.
      Commit `9cc83be`.
- [x] Tooltip copy rewritten to the 5-point standard. Commit `1432d13`.

## 7. Coverage notes

- `rates-yield-labels.spec.mjs` covers the 05-A header; `global-refresh.spec.mjs`
  covers card chrome. **Nothing** asserts null→`—` cells, row-drop behaviour, the
  commodities card, the real-spot column, or the `asof` footer.
- The shared fixture had no null entries and no `spot` key, so the
  `commodities_map` path was never exercised in the frontend; 05-B adds per-test
  null overrides.
- Producer side is well covered: `tests/test_spot.py` (`:405` failed spot row
  keeps `last: null`), `tests/test_market_cache.py` (all-null snapshots not
  cached).
- **Renderer coverage added** `1432d13`: `commodities-provenance.spec.mjs` asserts
  the source-date foot note and the attribution line, the compact date range when
  source dates differ, and the fetch-time fallback when `spot` is absent.
