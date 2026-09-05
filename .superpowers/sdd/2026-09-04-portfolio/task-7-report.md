# Task 7 Report — Portfolio renderer (portfolio.js + cards.js dispatch + HTML + CSS)

**Status:** DONE
**Commit:** `1589aaf`
**Date:** 2026-09-04

## Summary

portfolio.js + cards.js dispatch + HTML + CSS; node --check passed; Rulings 2 and 3 applied

## Changes

- `static/js/portfolio.js` (NEW): Portfolio card renderer with serenity-style expand/collapse per portfolio, editable Shares/Total cost cells (400ms debounce + immediate on Enter/blur), cash row with editable cost + value, per-portfolio totals footer, grand total in card header, expand/collapse all toggle, create/rename/delete portfolio, add/remove holding, add cash row with "cannot remove" alert.
- `static/js/cards.js`: Added `import { renderPortfolio }` and `case "portfolio": renderPortfolio(data)` in the dispatch table (both the specific case and the default/all-render branch).
- `static/index.html`: Inserted new `<section data-card="portfolio">` immediately before `<section data-card="earnings">`, with reorder controls, h2, controls div, and body div.
- `static/style.css`: Appended ~40 lines of `.pf-*` CSS rules for the portfolio section (controls, expand/collapse headers, editable inputs, cash row, totals row, empty state, grand total, add row, delete buttons). Uses existing theme variables (`--hair`, `--neutral-bg`, `--ink`, `--sub`, `--blue`, `--bear`).

## Verification

- `node --check static/js/portfolio.js`: passed (no syntax errors)
- `pctClassName` uses the clean 3-arm form (Ruling 2): **confirmed** — 3 arms: null → "muted", >0 → "pos", <0 → "neg"
- `createTickerTable` is NOT called from `renderHoldingsTable` (Ruling 3): **confirmed** — only appears in a comment explaining the ruling; all rendering uses `buildPortfolioTableHtml` + `wirePortfolioRowEvents`
- Portfolio card is inserted immediately before the earnings card in `static/index.html`: **confirmed** (line 143)
- `.pf-*` CSS rules appended to `static/style.css`: **confirmed** (23 rule blocks at bottom of file)
- No server launched (not required for this task)

## Fix round 1

**Date:** 2026-09-04

### Critical fix — Cash row + totals row appended to wrong parent

Cash and totals `<tr>` elements were appended to `tableEl` (a `<div class="pf-holdings-table">`) instead of the `<table>`'s `<tbody>`. This caused orphan table fragments outside the table structure.

**Change:** Lines 176-179 — replaced `tableEl.appendChild(...)` with `table.querySelector("tbody").appendChild(...)`.

### Important fix — Reuse `pctClassName` instead of duplicated inline logic

Both `renderGrandHeader` (line 102) and `renderBody` loop (line 119) inlined `const gainCls = t.gain > 0 ? "pos" : (t.gain < 0 ? "neg" : "muted")` instead of calling the already-defined `pctClassName(t.gain)`.

**Change:** Replaced both inline `gainCls` computations with `pctClassName(t.gain)`.

### Verification

- `node --check static/js/portfolio.js`: passed (no syntax errors)
- Minor findings (style.css .muted class, hardcoded rgba) intentionally not touched per instructions.

## Rulings Applied

- **Ruling 2 — `pctClassName(v)`:** Applied. Clean 3-arm version: `if (v == null) return "muted"; if (v > 0) return "pos"; if (v < 0) return "neg"; return "muted";`. The plan's convoluted version was NOT used.
- **Ruling 3 — No `createTickerTable` for per-portfolio table:** Applied. `renderHoldingsTable` creates a plain `<table>`, fills it with `buildPortfolioTableHtml(p)`, then wires events via `wirePortfolioRowEvents(table, p)`. The `createTickerTable` import was removed entirely from portfolio.js since it is not needed.
