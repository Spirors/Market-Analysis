# Next session — resume prompt

Paste the block below into a fresh session (or say: *"read
`docs/audit/next-session.md` and execute it"*).

---

```text
Continue the Market Analysis repo audit. This is a multi-session effort; a full
app-section audit and a wiki audit are already complete and committed.

START HERE — the canonical state (AGENTS.md will tell you to read wiki/hot.md;
it does NOT yet mention this audit, so treat it as stale):
- docs/audit/README.md      — app audit index. Sections that matter now:
                              §4 priority order, §7 fix policy, §8 verification,
                              §10 test baseline, §11 commits, §12 status board,
                              §13 open backlog + tracked TODOs.
- docs/audit/00-shell-and-tooltips.md, 01-risk.md, 08-events.md — completed
                              deep section files (findings, line refs, what landed).
- docs/audit/wiki.md        — wiki/retrieval audit; §6 has 3 parked decisions.

PROJECT RULES: follow AGENTS.md (auto-loaded). Load-bearing ones here: you are the
ONLY writer to the vault and to user-data files; sub-agents are read-only and must
NOT read the vault (pass wiki slices inline in their prompts); tests must never
touch live user data (tests/conftest.py autouse fixture redirects it); one logical
change per commit, scope-prefixed, never amend; data/events.json is pipeline-owned
— never stage or commit it.

GOAL: loop through the audit until its in-scope work is done, one bounded task at
a time, updating the docs as you go.

WORK QUEUE (this order unless README says otherwise):
1. Resolve the 3 parked wiki decisions in docs/audit/wiki.md §6 — cheapest, and
   index freshness is a P1: nothing currently rebuilds the retrieval index after a
   vault write, so it silently goes stale.
2. Open backlog fixes in README §13, by priority then P-level: 01-E, 00-D, 08-P,
   then 04-A/04-B, 03-A, 07-A…07-E, 02-A, 05-A, 06-A.
3. Deep audits still pending (create <section>.md only when you actually do one):
   07-portfolio (needs bounded runtime probes), 04-indicators, 05-market-quotes,
   03-regime, 02-ai-sentiment, and 06-bottleneck editor/forms (light pass only —
   prior art commit ff9fc12; do not re-report its findings).

FOR EACH TASK:
- Method: static code + existing specs first. Use agent-browser only as a bounded
  probe for a concrete suspected defect, and record the probe in the section file.
- Classify every finding BUG|TOOLTIP|UX|ACCESSIBILITY|DATA|PERFORMANCE|
  ARCHITECTURE|TEST|DESIGN|IDEA × P0–P3, always with a why and a file:line.
- Fix inline only if small, low-risk, localized, testable and behaviour-preserving
  (README §7). Otherwise document it in the backlog. STOP AND ASK if it needs a
  product/design decision rather than guessing.
- Verify: focused test → `cd tests/frontend; npx playwright test` → compare against
  the baseline in README §10 (currently 158 passed / 3 failed) → record in the
  section file.
- Commit per README §11: `docs(audit): <section>` for docs, `fix(<scope>): …` /
  `feat(<scope>): …` for code — never mixed.
- Same pass: update README §12 status board, §13 backlog, §14 log.

ENVIRONMENT TRAPS (learned this session):
- Playwright's webServer binds port 8123 — run at most ONE browser suite at a time,
  and reap it after (Get-NetTCPConnection -LocalPort 8123 must show nothing).
- Never drive a CLI through a redirected-pipe wrapper (it hangs). Redirect output to
  a file under C:\Users\Spirors\AppData\Local\Temp\opencode\ and read that file.
- From pwsh, `wsl -d Ubuntu-22.04 -u root bash -lc "…"` swallows `$VAR` — inline
  full paths instead of using shell variables.
- The two dash-layout specs re-implement applyLayoutOnLoad in-page with a stale
  mirrored CARD_BAND, and portfolio-star-scope assumes expanded→collapsed; all
  three are STALE SPECS, not product bugs (README §10). Repair them deliberately as
  test hygiene — never weaken an assertion to make a failure disappear.
- Vault writes need WSL as root with an explicit --vault; non-root writes fail with
  CORRUPT_RUNTIME_STATE. Retrieval is already built in .vault-meta/bm25: rebuild with
  contextual-prefix.py --all --no-llm then bm25-index.py build; query read-only with
  retrieve.py --vault <vault> "<query>" --top 5 --no-rerank.

WIKI SYNC: per the user's decision, update the wiki AS each README task is tackled,
not in one batch. docs/audit/README.md stays canonical; the wiki gets discoverability
pointers and durable decisions only — never duplicated status tables or TODOs.

DONE WHEN: README §13's open backlog is empty or every remaining item is explicitly
DEFERRED with a reason; all statuses are COMPLETE / FIXED-PARTIAL / DEFERRED /
EXCLUDED; and the frontend suite matches the recorded baseline with no new failures.
Close with a short report of what landed, what remains, and what you chose not to fix.
```
