# Portfolio rename input — match width to span (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Portfolio rename input — match width to span (2026-09-06)

**Status:** confirmed + fixed.

**Bug:** entering rename mode for a portfolio visibly shifted the
pencil icon ✎, totals ($X (+Y)), and close button ✕ ~25-30px to the
LEFT.  The span had `flex: 1` (grew to fill available header space);
the input had `field-sizing: content` (sized to text only).  The
input was narrower than the span was, so the elements to its right
shifted left.

**Fix:** `static/js/portfolio.js startEditForPid` now measures the
span's box width via `getBoundingClientRect()` BEFORE swapping in the
input and sets `inp.style.minWidth = ${spanWidth}px`.  The input box
matches the span's outer edge exactly, so the pencil / totals /
close button keep their position.  The plain `min-width: 8ch` CSS
floor (added in commit `55400a9`) stays as the accessibility floor
for a 1-2 char name.

**Why JS rather than CSS:** CSS `field-sizing: content` doesn't
expose a "match a sibling" mode; the alternatives are `width:
100%` (stretches beyond span when the flex container has extra space),
`width: max-content` (returns the input's intrinsic 20-char width
~160px), or `width: fit-content` (caps at container width but
doesn't match span).  Measuring in JS is the only way to get an
exact match without re-introducing the `flex: 1` stretch behavior
that the prior fix in commit `4716e02` was trying to avoid.

**Trade-off:** the input is now wide (~500-1000px on desktop) for a
3-char name like "IRA", whereas pre-fix it was ~74px content-sized.
The visual benefit (no shift) outweighs the compactness cost.

**Regression coverage:** `tests/frontend/portfolio-name-input.spec.mjs`
asserts the actual no-shift property (pencil / totals / close button
x-position unchanged between span and input states, with 1px slack
for sub-pixel rendering) plus the structural anti-reverts (`flex:
0 0 auto`, `field-sizing: content`, `min-width` not "160px").
Red-green verified with the fix reverted.




