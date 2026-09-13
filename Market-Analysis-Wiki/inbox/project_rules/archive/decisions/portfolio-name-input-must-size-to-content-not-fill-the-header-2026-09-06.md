# Portfolio name input must size to content, not fill the header (2026-09-06)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Portfolio name input must size to content, not fill the header (2026-09-06)

**Status:** confirmed + fixed. **Superseded refinement:**
2026-09-06 entry below — `min-width: 160px` had a layout-shift bug
for SHORT names (e.g. "IRA", 3 chars), since the fixed pixel floor was
wider than the rendered title. Replaced with `field-sizing: content`
+ `min-width: 8ch`.

Pre-fix `.pf-name-input` had `flex: 1; min-width: 0;` which stretched the
inline rename input to ~87% of `.pf-pf-header` width on a typical desktop
layout (measured at 1027 / 1184 px). The surrounding empty space inside
the header was too narrow to hit, so users couldn't easily click outside
the input to blur/commit it.

**Fix (commit `4716e02`, refined `974d988`):** `static/style.css` switched
`.pf-name-input` to `flex: 0 0 auto; width: auto; min-width: 160px;
max-width: 100%`. The input sizes to its content while staying usable on
narrow headers (mobile / sidebar collapse).

**Rule for inline-rename / inline-edit inputs in flex containers:**
"Don't default to `flex: 1` for transient edit inputs — size to content
so the surrounding container area remains clickable for the
click-outside-to-blur UX pattern users expect."

Regression coverage: `tests/frontend/portfolio-name-input.spec.mjs` (3
tests) asserts the input width ratio stays under 50% of header width,
plus the single-line + click-outside-to-blur + Enter-saves UX behaviors.

