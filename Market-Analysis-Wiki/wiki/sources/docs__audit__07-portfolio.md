---
type: source
title: "Audit 07 — portfolio"
status: archived
created: 2026-10-04
updated: 2026-10-04
imported_at: 2026-10-04
source_kind: audit
original_path: "docs/audit/07-portfolio.md"
original_sha256: "eb5020e058ba757ce1a7f45c65c6ce4bd2cec06e7fa0bcead46e86a9038822e3"
stored_path: ".raw/captured/eb5020e058ba757ce1a7f45c65c6ce4bd2cec06e7fa0bcead46e86a9038822e3.md"
retired_from: "docs/audit/ (removed 2026-10-04; last repo commit 1e03a2e)"
tags:
  - source
  - audit
  - history
---

# Audit 07 — portfolio

> **Historical — not live state.** This is the finished app audit's section
> file, archived 2026-10-04 and retired from the repo. It described the code
> as of 2026-09-27 and is kept for reference only: do **not** treat it as
> current status or instructions. Live state is [[wiki/hot.md]]; the code is
> the source of truth.

# Section 07 — Portfolio

**Status:** `FIXED-PARTIAL` (deep recon 2026-09-27; all five findings 07-A..07-E fixed)
**Priority:** 4 of 9
**Last updated:** 2026-09-27

**Covers (raw parts):** `portfolio` card (`index.html:124-142`), `static/js/portfolio.js`,
the shared `static/js/tickerTable.js` (also used by the earnings/other tables),
and `static/js/watchColors.js` (star state).
**Backend:** `app/api.py` (`/api/portfolios*`), `app/portfolio.py`,
`app/service.py`; persistence in `data/portfolios.json` (+ the patched
`data/dashboard.json` cache).
**Evidence:** static + grep recon of the three JS modules, the portfolio
endpoints, and the portfolio specs. Runtime probes were **not** needed — every
finding was provable statically.

---

## 1. Purpose

A multi-portfolio holdings tracker: CRUD over `data/portfolios.json`, live-price
enrichment, per-portfolio column order/visibility, per-portfolio star (watch)
state, and a sortable holdings table. It is the section with the most persistence
surfaces, which is exactly where the audit's findings cluster.

## 2. Persistence map (verified)

| Key / field | Written by | Read by | Status |
|---|---|---|---|
| `localStorage["pfSort.portfolio.<pid>"]` | `tickerTable.js:79` | `loadSort` `:68` | **07-A — was dead** (short-circuited), now fixed |
| `localStorage["pfVisible.portfolio.<pid>"]` | `tickerTable.js:93` | `loadVisibility` `:82` | works |
| `localStorage["pfOrder.portfolio.<pid>"]` | `tickerTable.js:110` | `loadOrder` `:96` | works |
| `localStorage["pfWatchColors"]` (`<pid>::<sym>`) | `watchColors.js:39-43,72` | `watchColors.js:20-30` | works |
| `localStorage["pfExpanded"]` | `portfolio.js:114-117` | `portfolio.js:108` | works |
| `data/portfolios.json` → `column_order` / `column_visibility` | `api.py:434-436` (PUT) | **nothing** | **07-B — write-only dead data** |
| `data/portfolios.json` → holdings order | `portfolio.py:493` | `portfolio.js:575` | works (07-E truth source) |
| `data/dashboard.json` → `portfolios` | `portfolio.py:58-63` | `service.py:238` | prefs stripped from the payload |

## 3. Findings

1. **`DATA` · P2 — 07-A · column sort saved but never restored.**
   `saveSort` wrote `localStorage[pfSort.portfolio.<pid>]` on every sort change
   (`tickerTable.js:415-418`, `:321-323`, `:339-341`), but `tickerTable.js:175`
   is `let sort = initialSort || loadSort(section)` and the only caller passed a
   literal — `portfolio.js:568` `initialSort: { key: "default", dir: 1 }` — so
   `loadSort` was unreachable. Aggravator: `renderBody` clears
   `portfolioTables` (`portfolio.js:214,239`), destroying the instance, so the
   sort was lost after collapse/expand too, not only on reload. *Why:* the user's
   explicit sort silently reverted; a dead loader is worse than no loader.

2. **`DATA` · P2 — 07-B · server column prefs are write-only dead data.**
   The client `PUT`s to `/api/portfolios/columns/{section}` (`api.js:344-351`)
   → `api.py:409-437` → `data/portfolios.json`; no client ever reads it back
   (rendering uses localStorage). The backend documents this itself
   (`app/portfolio.py:99-102`). `GET /api/portfolios` returns the fields
   (`api.py:231-235`) but `portfolio.js:784` ignores them. *Why:* a silent lie —
   the app persists a preference it never honours.
   **Decided 2026-09-27 (user): localStorage is the source of truth; delete the
   server-side fields + the write-only route.**

3. **`ACCESSIBILITY` · P2 — 07-C · clearing a star requires a right-click.**
   Left-click cycles `amber → bull → bear` and can never clear
   (`watchColors.js:49-52`); `contextmenu` is the only clear path
   (`portfolio.js:807-818`). The star is a real `<button aria-pressed>`, so the
   ContextMenu key works — but nothing documents it. *Why:* an undocumented,
   mouse-only action.
   **Decided 2026-09-27 (user): keep right-click; document the keyboard route in
   the title/aria-label.**

4. **`ACCESSIBILITY` · P2 — 07-D · sortable `<th>` is click-only; the Columns
   button has no `aria-expanded`.** `<th>` (`tickerTable.js:371,374`) has no
   `tabindex`/`role`/`aria-sort`; the only sort handler is a click listener
   (`:415-421`). The Columns button (`:245`) never sets `aria-expanded`
   (toggle only flips a class, `:262-268`). The portfolio header already does
   it right (`portfolio.js:328`, `:252-254`) — the pattern exists in-file.

5. **`TOOLTIP` · P2 — 07-E · the portfolio `CARD_TOOLTIPS` entry contradicts
   itself.** `cards.js:589` says both *"▲/▼ reorder rows in the current view
   only"* and *"▲/▼ reorder rows persists to data/portfolios.json"* — the first
   is false: `onReorder` (`portfolio.js:602-619`) POSTs to
   `/api/portfolios/{pid}/holdings/reorder` (`portfolio.py:465-494`) and the
   order survives reload (`portfolio-move.spec.mjs:234`). Related stale
   comments: `tickerTable.js:12-13,205-206` claim session-only reorder; the ↻
   button's title promises "Reset to insertion order" while `resetSort()`
   (`:321-326`) clears only the sort.

## 4. Coverage matrix

| Finding | Existing tests | Verdict |
|---|---|---|
| 07-A | `portfolio-holdings-reorder.spec.mjs:183/:200/:437` (in-session only) | was **uncovered** — new spec added |
| 07-B | `test_portfolio.py:476/:498/:490/:524`; `portfolio.spec.mjs:312` | write path covered; read-back gap real |
| 07-C | `portfolio.spec.mjs:578/:595`; `portfolio-star-scope.spec.mjs:194` | right-click covered; keyboard gap |
| 07-D | only `portfolio-header-collapse.spec.mjs:337` (header, not Columns) | **no coverage** |
| 07-E | none | **no coverage** |

## 5. Fixes completed

- [x] **FIX-07-A** `DATA` P2 — removed the hard-coded `initialSort` so the
      factory consults `loadSort()`; nothing-saved still yields insertion order
      (`portfolio.js:568`). New spec covers the previously-dead restore path
      (`portfolio-holdings-sort-persist.spec.mjs`). Commit `6fb2622`.
- [x] **FIX-07-C** `ACCESSIBILITY` P2 — the star's `title` and new `aria-label`
      now name the symbol and state, describe the click/Enter/Space cycle, and
      give the clear route explicitly (right-click, Shift+F10, ContextMenu key).
      No handler behaviour changed (`watchColors.js:77-85`). Commit `ee193a4`.
- [x] **FIX-07-D** `ACCESSIBILITY` P2 — sortable `<th>` are focusable with
      Enter/Space parity and a live `aria-sort`; the Columns button carries
      `aria-expanded` on every open/close path plus `aria-controls` to a
      per-instance menu id (`tickerTable.js:43-46,172-174,250-254,270-278,
      313-323,386-397,434-451`). Commit `2a3dd26`.
- [x] **FIX-07-B** `DATA` P2 — the write-only server column prefs are gone:
      removed the PUT route, the `column_order`/`column_visibility` state
      fields and their default constants, the client call + its debounce, and
      the tests that pinned the dead path. localStorage is the sole source of
      truth; the PUT-firing spec now asserts localStorage persistence and zero
      server writes (`app/api.py`, `app/portfolio.py`, `static/js/api.js`,
      `portfolio.js`, `tickerTable.js`). Commit `a2c7df0`.
- [x] **FIX-07-E** `TOOLTIP` P2 — the portfolio tooltip no longer claims row
      reorder is "current view only" while also saying it persists; the two
      stale `tickerTable.js` comments and the ↻ button title (it resets the
      sort, not the manual order) are corrected (`cards.js:601`,
      `tickerTable.js:7-14,205-206,256`). Commit `669358c`.

## 6. Tracked TODOs

All five findings (07-A..07-E) are fixed. Remaining minor items:

- [x] ~~`IDEA` P3 — the now-unused `initialSort` option plumbing remains in
      `tickerTable.js`; harmless, remove only if the option is dropped for good.~~
      Removed — `e928717`.
- [x] ~~`TEST` P3 — 12 out-of-scope frontend specs still carry stale mock keys
      (`column_order`/`column_visibility`) and two keep a dead
      `PUT .../columns/` mock branch; harmless (the app ignores them), but worth
      a cleanup pass.~~ Cleaned — `0116dc5`.
- [x] ~~Portfolio native `title=` converged onto `attachTooltip`~~ — done
      (`fe40eed`): header/toolbar/cash-row/row-removal tooltips migrated;
      `tickerTable` ◀/▶ and the blocked ▲/▼ branch kept native (tooltip surface
      sits behind the Columns menu; disabled controls do not fire hover/focus);
      `watchColors` star kept native (its `title` is asserted equal to its
      `aria-label`).

## 7. Verification notes

- Static recon was sufficient; no runtime probe was needed for any of the five.
- Suite after FIX-07-A: verified together with the other lanes (see README §10).

## Citation

- **Original:** `docs/audit/07-portfolio.md` (retired from the repo 2026-10-04; last repo commit `1e03a2e`)
  - SHA-256: `eb5020e058ba757ce1a7f45c65c6ce4bd2cec06e7fa0bcead46e86a9038822e3`
- **Captured:** `.raw/captured/eb5020e058ba757ce1a7f45c65c6ce4bd2cec06e7fa0bcead46e86a9038822e3.md`
