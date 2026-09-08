# Decisions

Durable, one-way-door(ish) decisions and confirmed root causes. Append
new entries; don't delete old ones even if later superseded — mark
them superseded instead, so the history of *why* stays intact. Newest
at the bottom.

> AGENT: this file is the project's "what we decided and why" record.
> Every durable choice (chose library X over Y, picked storage shape
> Z, ruled out approach W because it broke under load) belongs here
> the moment you confirm it.

## File layout (pointer index + per-decision archive)

This file is a **pointer index** — each entry is title, date, status,
one-sentence summary, and a link. The verbose detail (code snippets,
test breakdowns, verification matrices, file:line references) lives in
`archive/decisions/<slug>.md`. Decisions do not rotate; they accumulate.

The standard entry shape here (live file) is:

```
## Title (YYYY-MM-DD)

**Status:** confirmed + implemented (commit `<sha>`) | superseded by ...

**Summary:** one sentence capturing what was decided + why.

**Archive:** Full text in `archive/decisions/<slug>.md`.

---
```

The full entry in `archive/decisions/<slug>.md` follows the longer
shape below:

```
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

## How to add a new entry

1. Decide the title and date (today, in `YYYY-MM-DD`).
2. Generate the slug: lowercase the title, replace non-alphanumeric
   with `-`, strip leading/trailing `-`, append `-<date>` (e.g.
   `validate-symbol-uses-yfinance-bulk-2026-09-08`).
3. Write the full entry into `archive/decisions/<slug>.md` with the
   Problem / Decision / Why shape.
4. Add the pointer to this file (live index) with Status, Summary,
   and the Archive link. Place the pointer in chronological position
   (newest at the bottom).

Once the live file accumulates a few real entries, periodically revisit
and merge *only* entries that are genuinely duplicates — the live
file is supposed to be scannable, not a wall of near-duplicates.
