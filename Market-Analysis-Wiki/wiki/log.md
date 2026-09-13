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

## 2026-09-13 — Initial ingest: 99 sources from project_rules/ + docs/

- Operation: `ingest-20260913-initial-99`
- Source count: 99 (9 project_rules root, 26 archive/sessions, 47 archive/decisions, 17 docs/)
- Wiki pages: 99 source pages at `wiki/sources/<slug>.md`
- Captures: 99 immutable snapshots at `.raw/captured/<sha>.md` (created by capture apply earlier)
- Source manifest: 99 entries added to `.raw/.manifest.json`
- Citations: every source page has original_path + original_sha256 + stored_path back to inbox/ + .raw/captured/.
