# project-rules skill generalised for separate publication (2026-09-07)

Full text of the entry from `project_rules/DECISIONS.md`
(retrofit 2026-09-08: this file is the single source of truth for
the verbose detail; the live file holds only the pointer).

---

## project-rules skill generalised for separate publication (2026-09-07)

**Status:** shipped; the skill is now a portable, project-agnostic
core ready to be published as its own repo.

**Why:** the skill was originally designed for this project and grew
project-specific sections (Card tooltip / Risk gauge / Commodities
spot pricing). Once the project had its own decisions documented in
\project_rules/DECISIONS.md\, the skill no longer needed to carry
those sections - it could focus on the universal principles that
apply to any repo.

**What changed:**

- Dropped three project-specific sections (Card behavior + tooltip,
  Risk-gauge design, Commodities spot pricing). Their anti-pattern
  lessons are preserved here in DECISIONS.md; new repos adopt the
  skill without inheriting THIS repo's implementation details.
- Stripped repo-specific anchors from the universal sections
  (Server lifecycle no longer names pythonw.exe / wscript.exe /
  port 8000; Data integrity drops the yfinance / SEC EDGAR / Stooq
  specifics; Shared UI components drops the tickerTable.js example).
  Each rule now states the principle only.
- Added a Bootstrap section: on invocation in a fresh repo, the
  agent reads \	emplates/\, substitutes placeholders, and writes
  AGENTS.md + the five \project_rules/*.md\ seed files. No script
  required - the agent does the copy-paste from the shipped templates.
- Added \	emplates/\ directory with 6 placeholder-laden seed files
  + a README that documents the set and the placeholder map.
- Replaced repo-specific defaults in the Initialisation table
  (\Spirors/Market-Analysis\, \Market Analysis Tool\,
  \python run.py\) with obvious placeholder values so the published
  version doesn't bake in this repo's specifics.

**What did NOT change:**

- The universal rules themselves (Data integrity, Frozen files,
  Commit hygiene, Shared components, File ownership, Session
  continuity, Process hygiene) - same principles, same enforcement
  expectations, just with the project-specific examples stripped.
- This repo's project-specific rules - they still apply here, they
  just live in \project_rules/DECISIONS.md\ instead of the skill.

**Rule for future skill edits:** when adding a rule to the skill,
ask: does this apply to ANY project, or only to projects with this
specific feature? If only to a feature, document it in this repo's
DECISIONS.md instead. The skill stays portable by staying generic.


