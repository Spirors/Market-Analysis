# Session Log

Append-only. Newest entry at the bottom. This file is git-tracked —
unlike the local daily changelog (typically `{{DATA_DIR}}/logs/summary-YYYY-MM-DD.md`,
gitignored). Use this file for anything that needs to survive across
machines or a fresh checkout; use the local daily changelog for its
quick local-audit purpose.

> Older logs in archive/session-log-archive.md (once entries accumulate
> past ~10, the older ones rotate to that file).

---

## YYYY-MM-DD — Project initialised via `project-rules` skill

- Ran the `project-rules` skill's bootstrap procedure against this
  repo to scaffold `AGENTS.md` + `project_rules/`.
- Substituted placeholders: `{{REPO_NAME}}`, `{{REPO_DISPLAY_NAME}}`,
  `{{DATA_DIR}}`, `{{SERVER_COMMAND}}`, `{{FROZEN_HTML_DIR}}`.
- Next session: start filling in the placeholder sections in each
  generated file as the project develops — the first durable decision
  is the first `## YYYY-MM-DD — …` entry in `project_rules/DECISIONS.md`,
  the first `## YYYY-MM-DD — …` entry in `project_rules/SESSION_LOG.md`
  after this bootstrap entry, and the first update to
  `project_rules/HANDOFF.md`.
