---
type: source
title: "Session Log — Append-Only Session History"
status: imported
imported_at: 2026-09-13
original_path: "inbox/project_rules/SESSION_LOG.md"
original_sha256: "8ee7ea30da9f4ba4746fbba67292ba8e8220a1d6a10d2ddc2327a19da42d529d"
stored_path: ".raw/captured/8ee7ea30da9f4ba4746fbba67292ba8e8220a1d6a10d2ddc2327a19da42d529d.md"
source_kind: "session-log"
tags:
  - source
  - session-log
---

# Session Log — Append-Only Session History

Hybrid session log — latest entry in full, older entries as pointers to archive/sessions/<slug>.md. Append-only. Git-tracked (unlike data/logs/summary-YYYY-MM-DD.md which is gitignored and local-only). The latest entry covers 2026-09-11 portfolio follow-up fixes (live prices always refresh, reorder survives collapse+expand). Rotation threshold is 10 entries (SESSION_LOG_ROTATION_ENTRIES).

## Citation

- **Original:** `inbox/project_rules/SESSION_LOG.md`
  - SHA-256: `8ee7ea30da9f4ba4746fbba67292ba8e8220a1d6a10d2ddc2327a19da42d529d`
- **Captured:** `.raw/captured/8ee7ea30da9f4ba4746fbba67292ba8e8220a1d6a10d2ddc2327a19da42d529d.md`

## Key claims

- Hybrid layout: latest entry in full so session-start read is one click deep; older entries are ~6-line pointers with full text in archive/sessions/<slug>.md.
  - *Evidence:* "Hybrid layout: the **latest entry is in full** (so the session-start read per AGENTS.md is one click deep), **older entries are pointers** with full text in `archive/sessions/<slug>.md`"
- Rotation threshold reverted to 10 entries (from prior 5) because hybrid pointers shrank to ~6 lines each.
  - *Evidence:* "Once this file exceeds `{{SESSION_LOG_ROTATION_ENTRIES}}` entries (currently 10 — the skill default; the prior 5-entry override was reverted in commit `38bf801`"
- Every session documents test verification counts: the 2026-09-11 followup session reported 104 passed backend + 19 passed frontend.
  - *Evidence:* "Backend: 104 passed. Frontend: 19 passed (15 portfolio-holdings-reorder + 4 refresh-cooldown)."
- The test isolation autouse fixture was introduced on 2026-09-08 to redirect all module-level user-data paths to tmp_path.
  - *Evidence:* "Add a new Core rule "Test isolation" to `.opencode/skills/project-rules/SKILL.md` and enforce it with an autouse pytest fixture in a new `tests/conftest.py`"

## Concepts

- `session-continuity`
- `hybrid-layout`
- `append-only-log`
- `test-isolation`
- `changelog-conventions`

## Entities

- `tests/conftest.py`
- `.opencode/skills/project-rules/SKILL.md`
- `project_rules/DECISIONS.md`
- `archive/sessions/`
- `data/logs/`
- `app/news.py`
- `app/store.py`
- `app/config.py`
