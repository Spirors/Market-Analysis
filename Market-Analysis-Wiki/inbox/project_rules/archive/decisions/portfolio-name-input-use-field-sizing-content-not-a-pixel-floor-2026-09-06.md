# Portfolio name input — use `field-sizing: content`, not a pixel floor (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Portfolio name input — use `field-sizing: content`, not a pixel floor (2026-09-06)

**Status:** confirmed + fixed. Supersedes the `min-width: 160px` fix above.

**Problem:** the previous `min-width: 160px` introduced a layout-shift
bug for SHORT names — "IRA" rendered at ~30px (title) but the input
stayed at 160px (fixed pixel floor), shoving pencil / totals / close
~130px right.

**Fix:** swap `min-width: 160px` for `field-sizing: content` plus
`min-width: 8ch` (character-width floor). Input sizes to its content
+ padding/border (~74px for "IRA" at 13px font). Supported Chrome 123+,
Firefox 122+, Safari 17.5+; older browsers fall back to intrinsic 20-char
size — same as the old behaviour, no regression.

**Why not `max(min-content, 8ch)` (original plan):** CSS `max()` doesn't
compose with `field-sizing: content` — the browser ignores the formula and
uses the content-sized width regardless. Once `field-sizing: content` is
the sizing mechanism, `min-width` is just a hard lower bound, not a
formula input.

**Rule:** for inline-rename / inline-edit inputs, use
`field-sizing: content` with `min-width: <ch>` as the usability floor
(NOT a fixed pixel value). Fixed pixel floors regress for SHORT values —
character widths scale with font size and are robust across name lengths.

Regression coverage: `tests/frontend/portfolio-name-input.spec.mjs` +2
tests (short-name width `<130px`, no pre-`4716e02` stretch). Both fail
on the reverted code; the existing 3 tests pass (they use "Fidelity
Main" where content > 160px and didn't catch the regression).


