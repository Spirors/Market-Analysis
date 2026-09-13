# Frozen reference snapshots (retrofit-extracted from AGENTS.md) (2026-09-08)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## Frozen reference snapshots (retrofit-extracted from AGENTS.md) (2026-09-08)

**Decision:** `archive/ai_*.html` reference snapshots are frozen and
must not be edited. Adapting them silently corrupts the design
system they encode.

**Rationale:** Universal rule from the `project-rules` skill Core
rules → Frozen files, applied to this project. The reference
snapshots are how the current UI was specified; modifying them
would rewrite the design history. Four files in scope today
(`archive/ai_market_cycle_diagram_v4.html`,
`archive/ai_market_sentiment_gauge.html`,
`archive/ai_market_positioning.html`,
`archive/ai_thesis_timeline.html`); each is the seed source for
analysis frameworks still in active use (e.g. the gauge seeded
`app/risk.py`, the timeline seeded `app/seed_data.py`).

**Mistakes to avoid:** Any refactor that conflicts with a frozen
file loses — find another way. If a new behavior conflicts with the
gauge's divided-signals-healthy framing, the refactor loses; if a
new card layout conflicts with the positioning snapshot's
information hierarchy, the refactor loses.

**Related:** If a new frozen directory is added in the future,
append it here with the same shape; do not edit `AGENTS.md` to
inline the directory listing. The skill already encodes the
universal "frozen files" rule; the project-specific directory
listing lives here so the hard-rule pointer in `AGENTS.md` stays
generic and re-points at `DECISIONS.md`.
