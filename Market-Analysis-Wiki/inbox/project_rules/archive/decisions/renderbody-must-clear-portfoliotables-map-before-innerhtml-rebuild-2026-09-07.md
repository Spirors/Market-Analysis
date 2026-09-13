# renderBody must clear portfolioTables Map before innerHTML rebuild (2026-09-07)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## renderBody must clear portfolioTables Map before innerHTML rebuild (2026-09-07)

**Status:** confirmed + durable rule.

**Context:** Patch C (the audit-2026-09-07 follow-up front-end fix) made
`renderHoldingsTable(slot, p)` early-return + reuse the existing
tickerTable instance via `existing.refresh({rows})` when one is already
in the `portfolioTables` Map (`static/js/portfolio.js:423-428`). This
preserves the user's current sort state and debounced edit timers
across add/remove holding mutations — the original "nuclear rebuild"
threw all of that away on every click.

**Failure mode discovered during red-green verification:** the
`tests/frontend/portfolio.spec.mjs` star cycling tests
("clicking a star cycles the color and tints the row", line 578 +
"right-clicking a starred row clears the watch", line 595) went red
with Patch C alone. Root cause: a star click triggers
`renderBody()` which does `el.innerHTML = html` and rebuilds every
`.pf-pf` div from scratch — including the `.pf-pf-body` slots. The
`portfolioTables` Map, however, still held tickerTable instances
bound to the now-DETACHED old slots. When `renderHoldingsTable`
ran for the expanded portfolios and called `existing.refresh({rows})`
on the orphaned tickerTable, the refresh updated the detached DOM
(no longer in the document). The NEW slot was never populated —
so the user clicked a star and saw their holdings table disappear.

**Fix:** `renderBody()` must call `portfolioTables.clear()`
immediately before the `el.innerHTML = html` assignment (and before
the empty-state placeholder branch). The cleared Map ensures
`renderHoldingsTable` falls through to the "first-time render" path
and creates a fresh tickerTable bound to the new slot.

```js
// static/js/portfolio.js:218-229
if (!portfolios.length) {
  portfolioTables.clear();        // <-- detached-slot guard
  el.innerHTML = `<div class="pf-empty">…</div>`;
  renderGrandHeader();
  return;
}
…
portfolioTables.clear();          // <-- detached-slot guard
el.innerHTML = html;
```

**Red-green verification:**

| Test                                                      | Pre-fix  | Patch C alone (no clear) | Patch C + clear |
|-----------------------------------------------------------|----------|---------------------------|------------------|
| `portfolio.spec.mjs:578` star cycles color                | PASS     | FAIL (NVDA row missing)  | PASS             |
| `portfolio.spec.mjs:595` right-click clears watch         | PASS     | FAIL (NVDA row missing)  | PASS             |
| `tickerTable-instance-preservation.spec.mjs` (2 new tests)| —        | PASS                      | PASS             |
| `portfolio-targeted-render.spec.mjs` (3 new tests)        | —        | PASS                      | PASS             |

**Rule (durable):** any function that wipes `#portfolioBody` via
`el.innerHTML = ...` (currently only `renderBody`) MUST call
`portfolioTables.clear()` first. A Map-of-DOM-handles outliving the
DOM it points to is the silent-failure class — the function returns
without error, the user sees an empty section. The fix
(`portfolioTables.clear()`) is one line, but the failure mode
only surfaces via UI tests, not via Python backend tests. New
sections sharing the `portfolioTables` Map must follow the same
discipline.


