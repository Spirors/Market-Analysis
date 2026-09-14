---
type: meta
title: Wiki Log
status: evergreen
created: 2026-09-13
updated: 2026-09-13
tags:
  - meta
  - log
---

# Wiki Log

Newest completed operations appear first.

## 2026-09-13 — Layer 1 prune: 4 umbrella pages retired

- Operation: `wiki-fold-20260913-umbrella-retire`
- Moved to `wiki/sources/_retired/` (preserves content, marks `status: retired` + `superseded_by:` in frontmatter + Obsidian deprecation callout):
  - `project_rules__HANDOFF.md` — superseded by [[wiki/hot.md]] + [[wiki/overview.md]]
  - `project_rules__DECISIONS.md` — superseded by `### decision (47)` in [[wiki/index.md]]
  - `project_rules__SESSION_LOG.md` — superseded by `### session (26)` in [[wiki/index.md]] + [[wiki/log.md]]
  - `project_rules__ROADMAP.md` — superseded by [[wiki/overview.md]] (migration history) + [[wiki/hot.md]] (active threads)
- `wiki/index.md`: removed 4 single-entry groups (`### decisions (1)`, `### handoff (1)`, `### roadmap (1)`, `### session-log (1)`); added `### retired (4)` group at the end of Sources with supersession mapping.
- Captures at `.raw/captured/<sha>.md` are immutable; this prune only restructures the live wiki source pages. Reversible by re-ingesting from the captures.
- Decisions and session count: 47 / 26 — unchanged.

## 2026-09-13 — Migration: wiki-native session memory adopted

- Operation: `migration-20260913-wiki-native-memory`
- Scope: `AGENTS.md` rewritten to wiki-native session protocol; `README.md` updated to point at the vault; `wiki/overview.md` expanded from a one-line stub; `wiki/meta/session-memory-protocol.md` created; `wiki/log.md` + `wiki/hot.md` updated.
- Behaviour change: session start now reads `wiki/hot.md` (was: `inbox/project_rules/HANDOFF.md` + `ROADMAP.md` + `DECISIONS.md` + `RUNBOOK.md`). The old inbox-based protocol is deprecated; `inbox/project_rules/` is preserved as a frozen archive.
- Decisions: remain as source pages under `wiki/sources/`, listed in `wiki/index.md` (47 entries, unchanged).

## 2026-09-13 — Initial ingest: 99 sources from project_rules/ + docs/

- Operation: `ingest-20260913-initial-99`
- Source count: 99 (9 project_rules root, 26 archive/sessions, 47 archive/decisions, 17 docs/)
- Wiki pages: 99 source pages at `wiki/sources/<slug>.md`
- Captures: 99 immutable snapshots at `.raw/captured/<sha>.md` (created by capture apply earlier)
- Source manifest: 99 entries added to `.raw/.manifest.json`
- Citations: every source page has original_path + original_sha256 + stored_path back to inbox/ + .raw/captured/.
