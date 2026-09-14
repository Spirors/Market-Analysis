---
type: source
title: "Market Analysis Tool Phase Roadmap"
status: retired
imported_at: 2026-09-13
retired_at: 2026-09-13
superseded_by: "wiki/overview.md (migration history) + wiki/hot.md (active threads)"
original_path: "inbox/project_rules/ROADMAP.md"
original_sha256: "75e527b250a63913adfdd5e8c2d6cf9874a33c50b76d05b76154f4b854f9fd33"
stored_path: ".raw/captured/75e527b250a63913adfdd5e8c2d6cf9874a33c50b76d05b76154f4b854f9fd33.md"
source_kind: "roadmap"
tags:
  - source
  - roadmap
  - retired
---

# Market Analysis Tool Phase Roadmap

> [!deprecated] This umbrella page was retired 2026-09-13. Phase 0–2 are
> closed; Phase 3 is open-ended and the user pulls from it on request.
> Current state lives in [[wiki/overview.md]] (vault map and migration
> history) and [[wiki/hot.md]] (active threads). Captured source content
> is preserved below for historical reference.

Phase-level status tracker for the Market Analysis Tool. Documents Phase 0 (critical bug fixes — all closed), Phase 1 (documentation consolidation — closed), Phase 2 (refactor debt — closed), and Phase 3 (feature work — bottleneck reorder shipped, backlog open). The rule for agents is: do not start Phase N+1 items while Phase N items remain open.

## Citation

- **Original:** `inbox/project_rules/ROADMAP.md`
  - SHA-256: `75e527b250a63913adfdd5e8c2d6cf9874a33c50b76d05b76154f4b854f9fd33`
- **Captured:** `.raw/captured/75e527b250a63913adfdd5e8c2d6cf9874a33c50b76d05b76154f4b854f9fd33.md`

## Key claims

- Phase 0 closed: stuck-process lifecycle fix, section-position persistence, earnings watchlist add-button fix, portfolio name input sizing, session-continuity docs.
  - *Evidence:* "- [x] **Fix: stuck process on test launch.** Root cause + fix per `AGENT-WORKFLOW-PROMPT.md` §3a."
- Phase 3 is the active feature phase; bottleneck reorder + rename shipped as the first Phase 3 item.
  - *Evidence:* "- [x] **Bottleneck section reorder + rename (mirrors portfolio).** Per-category ↑ / ↓ chevrons and ✎ rename pencil"
- Frozen reference files (`ai_*.html`) and no-key data sources are explicit non-goals.
  - *Evidence:* "- Modifying the 4 archived `ai_*.html` reference files — frozen, per `AGENTS.md`."
- AGENTS.md was trimmed to under 150 lines by splitting docs into project_rules/ files.
  - *Evidence:* "Status: closed in commits `52e5b92` (docs split-out) + `8583711` (`project-rules` skill + AGENTS.md dispatch rule). `AGENTS.md` is now ~119 lines"

## Concepts

- `phase-tracking`
- `frozen-reference-files`
- `session-continuity`
- `documentation-consolidation`
- `refactor-debt`

## Entities

- `app/lifecycle.py`
- `app/portfolio.py`
- `static/js/tickerTable.js`
- `app/earnings.py`
- `static/style.css`
- `data/bottleneck_prefs.json`
- `project_rules/DECISIONS.md`
- `project_rules/RUNBOOK.md`
- `project_rules/HANDOFF.md`
- `project_rules/SESSION_LOG.md`
