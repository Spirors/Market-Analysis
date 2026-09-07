# Decisions

Durable, one-way-door(ish) decisions and confirmed root causes. Append
new entries; don't delete old ones even if later superseded — mark
them superseded instead, so the history of *why* stays intact. Newest
at the bottom.

> AGENT: this file is the project's "what we decided and why" record.
> Every durable choice (chose library X over Y, picked storage shape
> Z, ruled out approach W because it broke under load) belongs here
> the moment you confirm it. The standard entry shape is:

```
## Title (YYYY-MM-DD)

**Status:** confirmed + implemented (commit `<sha>`).

**Problem:** 1-2 sentences on what was wrong / what was needed.

**Decision:** 1-2 sentences on what was chosen.

**Why:** the rationale, especially the "mistakes to avoid" framing
so a future session doesn't re-derive the same conclusion (or worse,
re-derive it wrong).
```

A `**Regression coverage:**` line is a useful addition when the
decision is the kind where a future refactor could silently regress
it (see `project_rules/RUNBOOK.md` § commit hygiene for the broader
rule on regression tests).

Once the file accumulates a few real entries, periodically revisit
and merge *only* entries that are genuinely duplicates — the file
is supposed to be scannable, not a wall of near-duplicates.
