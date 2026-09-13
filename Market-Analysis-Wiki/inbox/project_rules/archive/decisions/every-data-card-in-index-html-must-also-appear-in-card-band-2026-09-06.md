# Every `[data-card]` in index.html must also appear in CARD_BAND (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Every `[data-card]` in index.html must also appear in CARD_BAND (2026-09-06)

**Status:** confirmed + fixed (commit `6825c0f`).

Pre-fix `static/js/layout.js:14-30` `CARD_BAND` map was missing the
`"portfolio"` entry. The `<section data-card="portfolio">` was added
to `static/index.html` in commit `1589aaf` but the layout map was
never updated. `persistLayoutFromDOM()` (layout.js:124) saved layouts
containing `"portfolio"` (it's in the DOM), but `applyLayoutOnLoad()`'s
guard at line 78 silently rejected any saved layout containing an
unknown card id. Every F5 reverted to HTML source order with no error
or warning.

**Root cause family:** This is the same shape of bug as the Phase 0
tickerTable.js cross-section state bug — two consumers (here: persist
vs apply) where one allows an item and the other rejects it silently.
The fix made the persistence side filter to only known cards (now
both sides agree on the allowlist). For tickerTable.js the defensive
fix was `VALID_SECTIONS` allowlist + `_assertValidSection()` guard;
for layout.js the existing `known` Set check at line 78 was already
correct, it was just incomplete — the data side needed updating.

**Rule for new dashboard cards:** Any new `<section data-card="...">`
added to `static/index.html` MUST be added to `CARD_BAND` in
`static/js/layout.js:14-30` in the same change. There is now a
regression test (`tests/frontend/dash-layout-survives-reload.spec.mjs`)
that checks `CARD_BAND` includes every `[data-card]` in
`index.html` — extending either side without the other will fail the
test.

