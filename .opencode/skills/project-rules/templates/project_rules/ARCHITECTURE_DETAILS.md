# Architecture — module details

> AGENT: this file is the **optional** deep-dive companion to
> `project_rules/ARCHITECTURE.md`. The skill's Documentation hygiene
> rule ({{DOC_LINE_THRESHOLD}}-line self-check) splits ARCHITECTURE.md
> in two when it crosses the threshold — the verbose per-module
> "Module map" descriptions move here; the high-level overview (Stack,
> Section-to-code map, Backend module quick-reference, Known quirks)
> stays in ARCHITECTURE.md.

> AGENT: create this file **only** when `project_rules/ARCHITECTURE.md`
> crosses the {{DOC_LINE_THRESHOLD}}-line threshold AND you can't shrink
> it without losing information. The split is lossless — everything
> moves to its right home. After the split, edit `AGENTS.md` "See also"
> to list both files. See the project-rules skill's Core rules →
> Documentation hygiene section for the trigger rules.

## Module map

> AGENT: this section is the deep-dive per-module content that moved
> out of ARCHITECTURE.md. One paragraph per module: what it does, who
> calls it, cache layout notes, design rationale. Reference the matching
> `project_rules/DECISIONS.md` entry when a design choice has a durable
> decision recorded (especially for `**Why we did it this way**` style
> decisions).

- `{{MODULE_PATH}}` — {{ROLE}}. Called by {{CALLERS}}. Cached at
  `{{CACHE_PATH}}` with TTL `{{TTL}}` (see DECISIONS for why).
- ...

## (Optional) Sub-modules

> AGENT: for projects with deeply nested module hierarchies, add a
> sub-section here per top-level module that warrants its own map.
> Most projects skip this section — the main Module map is enough.
