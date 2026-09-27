# Next session — resume prompt

Paste the block below into a fresh session (or say: *"read
`docs/audit/next-session.md` and execute it"*).

---

```text
Continue the Market Analysis repo audit. This is a multi-session effort; the app
section audit and the wiki/retrieval audit are complete in the parts listed below.

START HERE — the canonical state (AGENTS.md does not mention this audit; treat
its silence as stale):
- docs/audit/README.md      — the canonical audit state. Sections that matter now:
                              §4 priority order, §7 fix policy, §8 verification,
                              §10 test baseline, §11 commits, §12 status board,
                              §13 open backlog, §14 session log.
- docs/audit/00-shell-and-tooltips.md, 01-risk.md, 04-indicators.md, 08-events.md
                            — deep section files (findings, line refs, what landed).
- docs/audit/wiki.md        — wiki/retrieval audit. Status COMPLETE: the three
                              parked decisions are resolved (see §6).

PROJECT RULES: follow AGENTS.md (auto-loaded). Load-bearing here: you are the
ONLY writer to the vault and to user-data files; sub-agents are read-only and
must NOT read the vault (pass wiki slices inline in their prompts); tests must
never touch live user data (tests/conftest.py autouse fixture redirects it); one
logical change per commit, scope-prefixed, never amend; data/events.json is
pipeline-owned — never stage or commit it.

GOAL: loop through the audit until its in-scope work is done, one bounded task at
a time, updating the docs as you go.

ALREADY DONE (do not re-do):
- Wiki decisions closed: session end owns the `.vault-meta/bm25` rebuild
  (AGENTS.md + session-memory-protocol.md), corpus noise accepted/documented,
  rerank stays lexical-only. Durable page in the vault.
- Fixes landed: 01-A..01-I (risk), 00-A/C/D/E/F (shell/tooltip), 08-A/B/C/P/T
  (events), 03-A (regime tooltip), 04-A/04-B (breadth labels), 05-A (rates unit).
- Test hygiene: the 3 stale baseline specs are repaired; news-row-chips repaired.
  **The frontend suite is fully green: 169 passed / 0 failed (verified 2026-09-27).**

WORK QUEUE (this order unless README says otherwise):
1. Remaining open backlog in README §13, by priority then P-level:
   07-A, 07-B, 07-C, 07-D, 07-E  (07-portfolio — needs bounded runtime probes),
   02-A (02-ai-sentiment: no on-card as-of), 06-A (06-bottleneck inline titles — light).
   00-B stays DEFERRED (refresh-error surface is a design decision).
2. Deep audits still pending (create <section>.md only when you actually do one):
   07-portfolio, 03-regime, 02-ai-sentiment, and 06-bottleneck (light pass only —
   prior art commit ff9fc12; do not re-report its findings).
3. Cross-section decisions (README §13): serve-or-drop the dead `GET /api/regime`;
   delete the dead `.section-refresh` scaffolding; de-duplicate `COOLDOWN_SECONDS`;
   timezone-aware `_to_iso`; unify null handling across the market cards.
4. Test hygiene left: add a modal focus-trap regression spec (FIX-00-E shipped
   without one).

FOR EACH TASK:
- Method: static code + existing specs first. Use agent-browser only as a bounded
  probe for a concrete suspected defect, and record the probe in the section file.
- Classify every finding BUG|TOOLTIP|UX|ACCESSIBILITY|DATA|PERFORMANCE|
  ARCHITECTURE|TEST|DESIGN|IDEA × P0–P3, always with a why and a file:line.
- Fix inline only if small, low-risk, localized, testable and behaviour-preserving
  (README §7). Otherwise document it in the backlog. STOP AND ASK if it needs a
  product/design decision rather than guessing.
- Verify: focused test → `cd tests/frontend; npx playwright test` → compare against
  the baseline in README §10 (currently 169 passed / 0 failed) → record it.
- Commit per README §11: `docs(audit): <section>` for docs, `fix(<scope>): …` /
  `feat(<scope>): …` for code — never mixed.
- Same pass: update README §12 status board, §13 backlog, §14 log.

ENVIRONMENT TRAPS (learned across sessions):
- Playwright's webServer binds port 8123 — run at most ONE browser suite at a
  time and reap it after (Get-NetTCPConnection -LocalPort 8123 -State Listen must
  show nothing). Tell parallel lanes NOT to run Playwright; the Orchestrator runs
  the single suite after they land.
- Never drive a CLI through a redirected-pipe wrapper (it hangs). Redirect output
  to a file under C:\Users\Spirors\AppData\Local\Temp\opencode\ and read that file.
- From pwsh, `wsl -d Ubuntu-22.04 -u root bash -lc "…"` swallows `$VAR` — inline
  full paths instead of using shell variables.
- Vault writes need WSL as root with an explicit `--vault`. Write through a
  `claude-obsidian.transaction.v1` bundle: build it, `transaction inspect`, then
  `transaction apply --approved-plan-sha256 <inspect's approval_sha256>`. Never use
  host Write/Edit for vault files. Non-root writes fail with CORRUPT_RUNTIME_STATE.
- Retrieval: rebuild at session end with
  `contextual-prefix.py --vault <vault> --all --no-llm` then
  `bm25-index.py --vault <vault> build`; query read-only with
  `retrieve.py --vault <vault> "<query>" --top 5 --no-rerank`. The navigation hubs
  (`index`/`hot`/`log`) and `sources/_retired/**` pollute results by design.
- The suite is green: a new failure is now a REAL regression, not baseline drift.

WIKI SYNC: per the user's decision, update the wiki AS each README task is
tackled, not in one batch. docs/audit/README.md stays canonical; the wiki gets
discoverability pointers and durable decisions only — never duplicated status
tables or TODOs.

DONE WHEN: README §13's open backlog is empty or every remaining item is
explicitly DEFERRED with a reason; all statuses are COMPLETE / FIXED-PARTIAL /
DEFERRED / EXCLUDED; and the frontend suite matches the recorded baseline
(169 passed / 0 failed) with no new failures.
```
