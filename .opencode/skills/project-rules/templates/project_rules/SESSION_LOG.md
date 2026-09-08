# Session Log

Append-only. Newest entry at the bottom. This file is git-tracked —
unlike the local daily changelog (typically `{{DATA_DIR}}/logs/summary-YYYY-MM-DD.md`,
gitignored). Use this file for anything that needs to survive across
machines or a fresh checkout; use the local daily changelog for its
quick local-audit purpose.

> Hybrid layout: the **latest entry is in full** (so the session-start
> read per AGENTS.md is one click deep), **older entries are pointers**
> with full text in `archive/sessions/<slug>.md` (one file per session).
> Once this file exceeds `{{SESSION_LOG_ROTATION_ENTRIES}}` entries,
> the oldest pointer is dropped — the archive file is the source of truth.

---

## YYYY-MM-DD — Project initialised via `project-rules` skill

This is the bootstrap entry — it sits as the first session and stays in
full. Every subsequent entry follows the same shape.

- Ran the `project-rules` skill's bootstrap procedure against this
  repo to scaffold `AGENTS.md` + `project_rules/`.
- Substituted placeholders: `{{REPO_NAME}}`, `{{REPO_DISPLAY_NAME}}`,
  `{{DATA_DIR}}`, `{{SERVER_COMMAND}}`, `{{FROZEN_HTML_DIR}}`,
  `{{DOC_LINE_THRESHOLD}}`, `{{SESSION_LOG_ROTATION_ENTRIES}}`.
- Next session: start filling in the placeholder sections in each
  generated file as the project develops — the first durable decision
  is the first `## YYYY-MM-DD — …` entry in `project_rules/DECISIONS.md`,
  the first `## YYYY-MM-DD — …` entry in `project_rules/SESSION_LOG.md`
  after this bootstrap entry, and the first update to
  `project_rules/HANDOFF.md`.

## File layout (hybrid)

This file: pointer index, with the latest entry in full. Archive:
per-session files.

```
## YYYY-MM-DD — <Title>           (latest entry — full text inline)

<full prose, sections, code snippets, test results, commits, etc.>

---

## YYYY-MM-DD — <Title>           (older entry — pointer)

**Summary:** one sentence capturing what happened this session.

**Archive:** Full text in `archive/sessions/<slug>.md`.

---
```

`archive/sessions/<slug>.md` holds the full verbose text of the older
session (same shape as the inline entry above).

## How to add a new entry

1. Decide the title and date (today, in `YYYY-MM-DD`).
2. Write the entry inline at the bottom of this file as the new "latest"
   entry — full text.
3. The previously-latest entry gets converted to a pointer: extract a
   one-sentence summary, then move the full text to
   `archive/sessions/<date>-<slug>.md` and replace the inline entry
   with the pointer shape.
4. If the live file now exceeds `{{SESSION_LOG_ROTATION_ENTRIES}}`
   entries, drop the oldest pointer (the archive file stays).

When extracting the summary from the previously-latest entry, the
first substantive paragraph is usually enough — the archive file
holds everything else.

## Rotation thresholds

- `{{SESSION_LOG_ROTATION_ENTRIES}}` — how many entries (latest full +
  older pointers) this live file may carry before the oldest pointer
  is dropped. Suggested default: 10. Lower (e.g. 5) for projects with
  very verbose sessions.
- `{{DOC_LINE_THRESHOLD}}` — separate threshold (default 200) that
  flags oversized files for a documentation-hygiene split. SESSION_LOG
  rotates by entry count, not line count.
