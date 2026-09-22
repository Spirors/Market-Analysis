---
type: meta
title: Wiki Log
status: evergreen
created: 2026-09-13
updated: 2026-09-22
tags:
  - meta
  - log
---

# Wiki Log

Newest completed operations appear first.

## 2026-09-22 - fix(portfolio): register the missing rename route (534fd5f)

- Operation: `fix-20260922-portfolio-rename-route` (save).
- Bug: portfolio rename was broken in both the UI and the API.
  `app/portfolio.py` already had `rename_portfolio()` and
  `static/js/api.js` already sent `PUT /api/portfolios/{pid}?name=...`,
  but `app/api.py` never registered that route - the path existed only
  for DELETE, so FastAPI answered 405 Method Not Allowed. The inline
  pencil handler then alerted and re-rendered, silently reverting the
  name, which is why the change "did not work and did not persist".
- Fix: added `portfolios_rename()` to `app/api.py` (name as query param,
  400 on empty/whitespace name, 404 on unknown pid, no live-price
  enrichment because a rename touches only the name). Returns the same
  `{id, portfolio}` shape as POST /api/portfolios.
- Tests: three API-level regression tests in `tests/test_portfolio.py`
  (rename persists across GET, empty name -> 400, unknown pid -> 404).
  Backend suite: 106 passed.
- Root-cause note for future coverage: the gap was invisible to both
  existing layers - backend tests called `portfolio.rename_portfolio()`
  directly (bypassing HTTP routing) and the Playwright rename specs mock
  the PUT endpoint, so a route that was never registered passed both.
  HTTP-level tests are the layer that catches missing/dropped routes.

## 2026-09-14 - Project skills consolidated into .agents/skills (55d4080)

- Operation: `maint-20260914-project-skills-consolidation` (save).
- Moved the 4 project-authored domain skills (data-pull,
  financial-deep-research, news-filter, risk-divergence) from
  .opencode/skills/ to .agents/skills/ via git mv so OpenCode and Freebuff
  share one canonical skills home. Verified via opencode debug skill: all
  4 resolve from .agents/skills post-move; 19 skills total live there now
  (15 claude-obsidian + 4 domain). Empty .opencode/skills/ removed.
- skills-lock.json audit: it is the provenance manifest of the
  GitHub-sourced skill installer and tracks only the 8 third-party
  .agents/skills skills. The 15 claude-obsidian skills (managed via the
  sibling checkout, provenance in AGENTS.md) and the 4 project-authored
  domain skills deliberately stay out of it - no GitHub source to pin.
- Removed the empty untracked .slim/ runtime dir (slim skills recreate it
  on demand) and broadened the .gitignore rule from .slim/deepwork/ to
  .slim/ to keep future codemap/deepwork state out of the tree.

## 2026-09-14 - Global claude-obsidian skills removed; think migrated (233568b, 9355c72)

- Operation: `maint-20260914-global-skills-removed` (save).
- User-authorized cleanup: deleted the 15 redundant global copies under
  ~/.config/opencode/skills/ - the 14 migrated earlier plus think, the
  15th claude-obsidian skill initially misclassified as slim-managed (it
  is upstream and absent from the slim 8-skill manifest). think was copied
  project-locally first (byte-identical to the checkout), then all 15
  verified resolving to .agents/skills via opencode debug skill with the
  globals gone for real.
- oh-my-opencode-slim untouched: its 8 managed skills, plugins, and MCP
  grants stay global. context7/gh_grep are slim preset grants in
  ~/.config/opencode/oh-my-opencode-slim.json (librarian gets both;
  orchestrator gets gh_grep only); the servers are registered by the slim
  plugin, not by opencode.jsonc ("mcp": {} is empty).
- AGENTS.md skills bullet now lists the full set incl. think and the
  product root (sibling ../claude-obsidian), tightened back to the
  200-line threshold (8e28412). README Architecture section notes the
  bundled project-local skills (9355c72).

## 2026-09-14 - Session end: claude-obsidian skills migrated to project-local .agents/skills (862bcee)

- Operation: `session-end-20260914-skills-local-migration` (save).
- Migrated all 14 claude-obsidian skills (wiki, wiki-cli, wiki-ingest,
  wiki-fold, wiki-lint, wiki-mode, wiki-query, wiki-retrieve, save,
  autoresearch, defuddle, obsidian-bases, obsidian-markdown, canvas) from
  ~/.config/opencode/skills/ into .agents/skills/ as byte-identical copies
  including references/ and templates/ (verified drift-free against the
  durable product checkout, v2.2.0). oh-my-opencode-slim managed skills,
  plugins, and global MCP config untouched (no MCPs currently active).
- Verification: `opencode debug skill` resolves all 14 to
  .agents/skills/<name>/SKILL.md when the global copies are absent; while
  both exist OpenCode prefers the global copy (identical content, so
  behavior is unchanged). Read-only wiki-lint green: 104 pages, 101
  findings all pre-existing (archived-page frontmatter gaps + 2 retired
  dead links), none introduced by the migration. No absolute paths or
  Claude-Code-specific assumptions in the migrated skills.
- Freebuff reads .agents/skills/ natively (user-confirmed). AGENTS.md
  updated (9498500) to point at the project-local skills.

## 2026-09-14 - claude-obsidian clone relocated out of Temp

- Operation: `maint-20260914-relocate-obsidian-core` (save).
- Moved the product clone from the old AppData/Local/Temp/opencode location
  (ephemeral, subject to Windows temp cleanup) to the durable checkout at
  Documents/Main/GitHub/Spirors/claude-obsidian. Git checkout intact
  (32ac5a0, v2.2.0); no embedded absolute-path references; doctor ok from
  the new path (WSL root + explicit --vault unchanged). Session temp
  artifacts (pytest outputs, TestClient verify dirs) removed.
- hot.md updated with the durable path; Active Threads watch item cleared.

## 2026-09-14 - Session end: fix(ai-valuation) forward-PE re-wiring (1ba5288) + test repairs (47e5a7f)

- Operation: `session-end-20260914-ai-valuation-fwdpe-rewire` (save).
- Bug: BREADTH - AI Proxies hover intermittently missing FWD PE despite a
  fresh data/ai_valuation.json; Refresh seemed to trigger it. Root cause:
  PEs were wired only inside compute_indicators; cold start computed
  indicators before the PE cache existed, and the 30-min indicators cooldown
  re-served the PE-less payload on every refresh. Fix: indicators.wire_forward_pe
  (idempotent, drops unbacked PEs) called on compute, cooldown-reuse, and
  every serve (after the AI-gauge recompute that populates the cache).
  Commits: 1ba5288 (fix + regression tests), 47e5a7f (3 pre-existing test
  failures repaired, clean-tree verified).
- Verification: backend full suite green; frontend breadth-ai-valuation 7/7;
  live 62/71 tickers with forward_pe; AI gauge valuation repopulated.
- Changelog: data/logs/summary-2026-09-14.md 15:07:39 fix.

## 2026-09-13 — Layer 2 prune: 10 historical artifacts + 7 design specs/plans regrouped (+ corrections)

- Operation: `wiki-fold-20260913-history-regroup`
- Pre-check: grepped `app/`, `static/`, `tests/`, `AGENTS.md`, `README.md`, and
  the rest of the wiki for references to all 18 candidates (11 historical
  artifacts + 7 superpowers specs/plans). **Zero live references** anywhere.
- Removed 16 single-entry groups from `wiki/index.md`:
  - 9 historical: `audit (2)`, `fix-log (1)`, `improvements-log (1)`,
    `migration-guide (1)`, `park-log (1)`, `refactor-example (1)`,
    `refactor-metrics (1)`, `summary (1)`, `test-plan (1)`
  - 7 design-history: `ai-capex-design (1)`, `ai-capex-plan (1)`,
    `ai-valuation-plan (1)`, `news-overhaul-design (1)`,
    `news-overhaul-plan (1)`, `portfolio-design (1)`, `portfolio-plan (1)`
- Added 2 new groups:
  - `### history (10)` — one-time audits, refactor logs, prior state summaries
  - `### design-history (7)` — pre-ship design specs and implementation plans;
    the spec/plan annotation explicitly directs readers to `### decision (47)`
    for current guidance and the spec/plan only for design rationale
- **Correction (same session):** `ARCHITECTURE_DETAILS` was a
  misclassification in the first pass — it's a live companion to
  `ARCHITECTURE`, not a historical artifact. Moved out of history into
  `### architecture (2)`, with an inline annotation marking it as a
  companion to the module map.
- Source page count: unchanged at 95 (this is a regroup, not a delete).
- Reversible: re-splitting any of the tail groups into their original
  single-entry categories is a small edit if ever needed.

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
