---
type: meta
title: Wiki Log
status: evergreen
created: 2026-09-13
updated: 2026-09-25
tags:
  - meta
  - log
---

# Wiki Log

Newest completed operations appear first.

## 2026-09-25 - feat(bottleneck): $3B underdogs + named research stages

- Operation: `session-end-20260925-serenity-underdog-and-stages` (save).
- Two commits, `992efec..db148e7`. `992efec`: `UNDERDOG_CEILING_DEFAULT` $10B ->
  $3B (the skill's own headroom threshold, `references/methodology.md:334`), the
  core/extended conviction tier removed end to end (at a $3B ceiling it collided
  with `CORE_TIER_MAX = $3B`, leaving `extended` unreachable), and the underdog
  definition — "emerging stocks with great potential" — stated verbatim in the
  per-topic note and the `cards.js` help text. `db148e7`: a generation job
  persists an ordered four-stage list (`refresh_skill`, `read_lens`, `draft`,
  `warm_metrics`) with per-stage status + note; only `draft` is fatal; the metrics
  warm is bounded at 20s; legacy stage-less jobs still render.
- Behaviour change: stage 1 now runs the `npx` skill refresh inside a generation
  run, where before the refresh was reachable only from `POST /skill/refresh`.
- Verified: backend 633 (+ 13 lifecycle), Playwright 143 with the 4 known
  pre-existing failures, bottleneck spec 20; each commit also tested alone. Live
  against the real app: the four stages rendered and advanced, `refresh_skill`
  came back `done` (npx really ran), a degraded run showed `draft: failed` +
  `warm_metrics: skipped`, and a hand-created topic stored
  `underdog_ceiling = 3000000000` with the chip reading `≤ $3B` and 0 tier pills.
- Corrected: `agent-browser screenshot` **is** verified — it saved a PNG. The
  prior "unverified" note came from three redirected-pipe wrapper hangs, not the
  tool. `AGENTS.md` updated.
- Open: a real generation currently fails on the token budget
  (`finish_reason='length'`, empty content; `MAX_TOKENS = 8000` against a ~136 KB
  lens) — pre-existing, not from these commits, but it blocks the happy path. A
  terminal failure also hides the four-stage list. Both are recorded on the
  decision page.

## 2026-09-25 - docs(agents): trim AGENTS.md to the WHAT/WHY/HOW shape

- Operation: `session-end-20260925-agents-trim` (save).
- `AGENTS.md` 222 -> 189 lines. Each hard rule is one line stating the rule
  followed by a `Detail:` pointer to the vault page carrying its rationale and
  worked examples — a decision page where one exists, `project_rules__RUNBOOK`
  where the rationale is operational (commit hygiene, file ownership, wiki sync).
  No rule was weakened or dropped; only the prose moved.
- Pointers are repo-root-relative and all 18 resolve, verified by script along
  with the file's factual claims (100 source pages, 52 decisions). A first pass
  wrote them as `wiki/...`, which dangled — cheap lesson: a pointer-resolution
  check catches this class of error in one run.
- Closed: the `AGENTS.md` split watch opened when the file crossed its 200-line
  threshold. Its own Documentation-hygiene rule required proposing the split in
  the same session, which this completes.

## 2026-09-25 - chore(tools): install agent-browser, keep Playwright as the gate

- Operation: `session-end-20260925-browser-tooling` (save).
- `agent-browser` 0.38.1 + Chrome 154.0.8037.57 installed globally. The local
  `.agents/skills/agent-browser/SKILL.md` was already present but is only a
  discovery stub, so it pointed at a CLI that did not exist; it is live now.
- Decision: **Playwright stays the front-end regression gate** (18 specs) and
  `agent-browser` takes the exploratory pass it cannot do. Recorded in `AGENTS.md`
  with its verification status. Relevant caveat found while checking: the
  Playwright `webServer` is a static `python -m http.server` and the specs mock
  every endpoint, so the suite never exercises the real backend — a live
  `agent-browser` pass is the only browser check that does.
- Verified live against the real app: `agent-browser open` loads it, and
  `/api/bottleneck/topics` serves the new payload in process
  (`framework: serenity-aleabitoreddit`, `topics: 0`, `generation.enabled: true`).
- Not verified: `screenshot` / `snapshot` end-to-end. Three attempts hung in the
  PowerShell wrapper, not the tool — redirected-pipe handle inheritance from the
  spawned Chrome, plus a truncating `Select-Object -First` truncation. All three
  leaked processes, which were reaped and confirmed clean (0 processes, 0
  listeners). The trap is now a Process hygiene rule in `AGENTS.md`.
- Also corrected: `AGENTS.md` claimed 95 source pages / `### decision (47)`
  (now 100 / 52) and did not mention that vault writes need root under WSL.
- Open: `AGENTS.md` is 222 lines and a split is proposed; `agent-browser`'s
  screenshot path needs one in-lane confirmation.

## 2026-09-25 - docs(wiki): record the bottleneck API/agent contract and the delegation finding

- Operation: `session-end-20260925-bottleneck-contract` (save).
- Follow-up to the entry below, after auditing the driving plan file against the
  vault: three things it carried were not yet durable, and one vault page was
  stale.
- New decision pages: the Bottleneck section's route table, error mapping, job
  semantics, agent endpoint/limits/cost and the tiering evidence; and the finding
  that a poisoned agent-model binding is inherited by child sessions, so a session
  in that state cannot delegate and must be replaced rather than retried.
- Callout added to `sources/project_rules__API.md`: this page documents the
  **deleted** `/api/bottleneck/categories/*` routes and also predates the removal
  of the `thirteenf` and `ai_analysis` dashboard keys (commit `8dedc18`), so its
  route and payload-key lists are historical for those areas. The second of those
  predates this session.
- Corrections: `AGENTS.md` still claimed 95 live source pages and
  `### decision (47)`; now 100 and 52. `wiki/hot.md` records that vault writes must
  run as **root** under WSL, because `.vault-meta/transactions/` holds root-owned
  mode-700 state dirs from earlier sessions and the engine reads that directory
  before it can start.
- Retired: the driving plan file `HANDOFF-bottleneck-section.md` is deleted; its
  phase table and skill-refresh command were already superseded by the decision
  pages.
- Decisions: 50 -> 52. Verification: lint introduces no new findings (the 2 dead
  links are pre-existing prefix-style wikilinks in the two `_retired/` pages).

## 2026-09-25 - feat(bottleneck): topic-driven chokepoint section (10 commits, a40c85e..099e932)

- Operation: `session-end-20260925-bottleneck-topics` (save).
- Replaced the section's 5 hardcoded categories and their reorder/rename prefs
  with user-authored **topics**: a demand driver, its upstream constraining
  layers, and downstream per-stock thesis cards. Added 13 routes
  (`/api/bottleneck/topics` CRUD + import/export, generate, job poll/cancel,
  apply, skill status/refresh); `GET /topics` is the front-end's single render
  call.
- New: `app/bottleneck_topics.py` (topic store), `app/topic_agent.py` (in-app
  drafting agent — the app's only keyed path and only child-process spawn site),
  `static/js/bottleneck.js`, `tests/test_bottleneck_topics.py`,
  `tests/test_topic_agent.py`, `tests/test_api_bottleneck.py`,
  `tests/frontend/bottleneck.spec.mjs` (18 tests).
- Deleted: `BOTTLENECK_CATEGORIES`, `app/bottleneck_prefs.py` + its 2 routes and
  tests, the old renderer, its 2 endpoint clients and their 2 Playwright specs.
  `data/bottleneck_prefs.json` left on disk, not migrated (precedent: `8dedc18`).
- Skill: the vendored `w-y-p/serenity-aleabitoreddit-skill` is deleted (10
  files); upstream `yan-labs/serenity-aleabitoreddit` is installed into
  `.agents/skills/` and gitignored (upstream `license: null`), with
  `skills-lock.json` tracking provenance. Footer link re-pointed.
- Config: `OPENCODE_GO_API_KEY` in a gitignored `.env` plus a committed
  `.env.example`. Every keyed path degrades to null; the app runs without it.
- Four cross-view divergence defects were found and fixed during the build: two
  PE sources, a frozen copy served for a live value, a render-path fetch on a
  second cache key, and a header badge reading the dashboard while the body read
  the topics payload. All four are the same shape; the fixes are recorded as a
  durable decision.
- Verification: backend 620 passed + 13 lifecycle passed as a separate invocation
  (`test_lifecycle.py`'s watchdog truncates a single-process run, as documented);
  frontend Playwright 141 passed / 4 pre-existing failures (news-row chips,
  portfolio-star-scope, dash-layout x2). Live OpenCode Go smoke test: HTTP 200 on
  `deepseek-v4.1-flash`, envelope captured before the agent hardened on it.
- Decisions: 47 -> 50. Three new decision pages; the category-prefs decision is
  annotated superseded in the index.
- Deviations worth carrying forward: the skill CLI needs `-a universal --copy -y`
  to run non-interactively; `skills-lock.json` is tracked and was rewritten by the
  CLI; the agent's `skill_snapshot` hash is a different scheme from the lockfile's
  `computedHash`.
- Not committed: the plan file `HANDOFF-bottleneck-section.md` (untracked).

## 2026-09-25 - refactor(dashboard): remove AI Analysis Run Log + Superinvestors 13F (8dedc18)

- Operation: `session-end-20260925-remove-analysis-13f` (save).
- Removed two dashboard sections the user reported as hardly used: the
  "AI Analysis · Run Log" card and the "Superinvestors · 13F" card. Recon
  showed they were a closed pair - nothing surviving consumed `ai_analysis`
  or `thirteenf` (the analysis engine was 13F's only other consumer) - so
  both backends were removed wholesale.
- Deleted `app/analysis.py` (deterministic weighted-vote synthesis),
  `app/thirteenf.py` (SEC EDGAR 13F), the `analysis_runs` SQLite run-log in
  `app/store.py`, `GET /api/analysis/history`, `ANALYSIS_DB_PATH`,
  `THIRTEENF_TTL` and `SUPERINVESTORS`; stripped the service
  refresh/coverage/enrich wiring and the frontend renderers, layout
  registries, error routing, tooltips and dead CSS.
- Preserved the legacy `news.db` -> `events.json` migration in `store.py`
  (events path untouched). Left on disk (persisted/derived data, not
  deleted per the user's choice): `data/analysis.db`,
  `data/thirteenf_snapshot.json`. Regenerated the stale
  `data/dashboard.json` oracle so its top-level keys match the new payload.
- Verification: backend 526 passed + 13 lifecycle passed (a single-process
  full-suite run truncates on a pre-existing `test_lifecycle.py` watchdog
  `os._exit` after ~60s - unrelated); frontend Playwright 134 passed / 6
  pre-existing failures (bottleneck-move x2, news-row chips,
  portfolio-star-scope, dash-layout x2 - the last pair already broken by
  the earlier earnings-card removal). Commit 8dedc18: 23 files, +48/-1518.
- Follow-up: `static/style.css.orig` is a stale tracked backup that still
  contains the deleted `.tf-holdings` / `.ana-*` rules - left in place
  (pre-existing; separate logical change).

## 2026-09-23 - fix(dashboard): stop HTTP 500 on non-finite floats (4af86f1)

- Operation: `session-end-20260923-dashboard-nan-500` (save).
- Bug: GET /api/dashboard answered HTTP 500 ("Failed to load dashboard:
  HTTP 500" in the UI). Starlette's JSONResponse serialises with
  allow_nan=False, so one NaN anywhere in the payload raised
  `ValueError: Out of range float values are not JSON compliant: nan`
  and took down the entire response. The regime detector emits NaN for
  all 38 component values (current_ratio, sma_6m/12m, roc_3m/12m,
  crossover.gap_pct) when its price source is unavailable
  (`treasury_data_available: false`) - 6 of 189 reports on disk, all 5
  from 2026-09-23. That report was embedded in the cached
  `data/dashboard.json`, so every load 500'd; `/api/regime` broke the
  same way.
- Fix: new `store.json_safe()` recursively maps NaN/Infinity -> None (the
  project's "no data" sentinel; the UI already renders null as an em
  dash). Applied at both JSON-serving boundaries: `service._enrich()`
  (covers the dashboard, including a NaN already baked into the cache)
  and `regime.get_regime()` (covers `/api/regime`). `store.save_json()`
  now sanitises too, so our own caches never persist invalid JSON again.
  Composite score/zone preserved - only genuinely missing values become
  null.
- Tests: +4 regression tests (store.json_safe unit, save_json
  non-finite, `/api/dashboard` with a NaN-bearing cached payload,
  `/api/regime` with a NaN-bearing detector report). Verified against the
  real server: both endpoints 200, strict JSON parse (System.Text.Json)
  clean, no standalone NaN token. Backend suite 564 passed; the 4
  pre-existing test_portfolio_cache_sync failures (the same NaN
  ValueError) drop to a single flaky worker crash.
- Root-cause note for future coverage: the NaN originates in the
  third-party macro-regime-detector skill (pinned in skills-lock.json),
  so the fix sanitises at our serve boundary rather than patching the
  skill. test_portfolio_cache_sync is network-dependent (real yfinance
  calls) and flaky under xdist.

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
