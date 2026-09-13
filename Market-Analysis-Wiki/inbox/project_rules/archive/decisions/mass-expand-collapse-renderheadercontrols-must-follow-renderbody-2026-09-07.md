# Mass expand/collapse: renderHeaderControls() must follow renderBody() (2026-09-07)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Mass expand/collapse: renderHeaderControls() must follow renderBody() (2026-09-07)

`renderHeaderControls()` and `renderBody()` rebuild two separate
containers (`#portfolioControls` and `#portfolioBody`). The
`.pf-toggle-all` click handler needs both: it updates the
`expanded` set (so the body must re-render to show the new state)
AND it changes the basis for the button's `allExpanded` label (so
the controls must re-render to flip the "▼ all" / "▲ all" text).

Pre-fix, the click handler called only `renderBody()`. The body
correctly flipped between collapsed and expanded, but the label
stayed on "▼ all" forever after the first click — to the user, the
button looked unresponsive because the only feedback surface (the
label) never changed. The bodies were toggling correctly; the user
just couldn't tell.

The lesson: any click handler that mutates state read by
`renderHeaderControls` (or any sibling rebuilder) must call both
rebuilders. Same shape as the existing rule that any state mutation
that affects the grand header totals must also call
`renderGrandHeader()`. Add new test cases for the label-flip
behavior alongside any future change to the toggle-all handler, the
controls renderer, or the order the two are called. See
`tests/frontend/portfolio-mass-toggle.spec.mjs` for the 4 regression
tests added this session.


