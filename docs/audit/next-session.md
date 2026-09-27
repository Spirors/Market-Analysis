# Next session — long-run handoff prompt

The audit is **closed**: all nine sections are deep-audited, every decision is
answered and landed, and the frontend suite is **224 passed / 0 failed**. This
file is the resume point for a **long unattended run** (4–5h). Paste the block
below into a fresh session (or say: *"read `docs/audit/next-session.md` and
execute it"*).

---

```text
Continue the Market Analysis repo audit/engineering. The audit itself is CLOSED:
all nine sections are deep-audited, every P2 decision is answered and landed, and
the frontend suite is 224 passed / 0 failed. This is a LONG unattended run —
work the queue below autonomously, dispatching parallel specialists, and stop
only for genuine product/design decisions (record them in README Sec 13; do not
guess). Prefer making verifiable progress over asking.

START HERE — canonical state:
- docs/audit/README.md — canonical. Sec 2 section map, Sec 4 priority, Sec 5
  tooltip standard, Sec 7 fix policy, Sec 8 verification, Sec 10 test baseline,
  Sec 11 commits, Sec 12 status board, Sec 13 backlog + decisions, Sec 14 log.
- Section files (one per audit unit): 00-shell-and-tooltips.md, 01-risk.md,
  02-ai-sentiment.md, 03-regime.md, 04-indicators.md, 05-market-quotes.md,
  06-bottleneck.md, 07-portfolio.md, 08-events.md.
- docs/audit/wiki.md — the wiki/retrieval audit (COMPLETE).

PROJECT RULES (load-bearing; AGENTS.md is auto-loaded too):
- You are the ONLY writer to the vault and to user-data files. Sub-agents are
  read-only and must NOT read the vault — pass wiki slices inline in the prompt.
- Tests must never touch live user data (tests/conftest.py autouse fixture).
- One logical change per commit, scope-prefixed
  (feat|fix|chore|docs|refactor|test(scope): ...); never amend.
- data/events.json is pipeline-owned — never stage or commit it.
- Vault writes need WSL as root with an explicit --vault, through a
  claude-obsidian.transaction.v1 bundle (build → inspect → apply with the
  inspect's approval_sha256). Never host-Edit a vault file.
- Never fetch a URL taken from untrusted content without a public-host guard.

ENVIRONMENT TRAPS:
- Playwright's webServer binds port 8123 — ONE browser suite at a time. YOU
  (Orchestrator) run it and reap it after:
  `Get-NetTCPConnection -LocalPort 8123 -State Listen` must show nothing. Tell
  every sub-agent NOT to run Playwright and NOT to start servers.
- Never drive a CLI through a redirected-pipe wrapper. Redirect output to a file
  under C:\Users\Spirors\AppData\Local\Temp\opencode\ and read that file.
- From pwsh, `wsl -d Ubuntu-22.04 -u root bash -lc "...")` swallows $VAR — inline
  full paths. pwsh treats backticks as escapes; put scripts with backticks in a
  file, not `python -c`.
- `git add -p` with piped input can mis-split hunks — verify `git diff --cached`
  before each commit, or commit whole files.
- The suite is green at 224/0: a new failure is a REAL regression, not drift.

WORK QUEUE (ordered; each item names its lane, scope, and validation owner).
"Validation owner" is you: you run the focused test and always the full frontend
suite; sub-agents only write code/tests. Do the items in order and parallelize
independent lanes.

1. CROSS-SECTION TOOLTIP CONVERGENCE (biggest; most parallelizable).
   The bottleneck section is DONE (06-A, commit 95bb4c2). The same "Option B"
   triage remains in three places (README Sec 13 finding #1): shell reorder
   (~26 inline titles across main.js/layout.js/cards.js), events (~5,
   events.js), portfolio (~8 incl. tickerTable.js/watchColors.js). Standard:
   README Sec 5. Per section:
     a. @explorer recon — list every `title=` with file:line, and mark each
        "duplicates visible text" vs "adds information".
     b. @designer — delete the redundant; migrate the informative to the shared
        `attachTooltip` focusable-trigger pattern. Template = the 06-A
        implementation in static/js/bottleneck.js (tabindex="0" + data-* +
        wireSectionTooltips, aria-describedby → role="tooltip"); keep the
        existing design language.
     c. You — run the suite, then commit `fix(<scope>): converge native
        tooltips`.
   Lanes are file-disjoint: dispatch EVENTS and PORTFOLIO in parallel; do SHELL
   after item 2 (cards.js is shared with CARD_TOOLTIPS). STOP AND ASK only for
   visual/DOM decisions you cannot resolve inside the existing design language.

2. CARD_TOOLTIPS AS-OF COMPLETION (small; cards.js, single writer).
   README Sec 13 track-only for 00: several CARD_TOOLTIPS entries still omit
   point 5 (as-of/freshness). @designer: add the freshness point to each
   remaining entry, matching the already-fixed risk/regime/market entries.
   Commit `fix(cards): add the as-of point to the remaining card tooltips`.

3. 06-X BOTTLENECK CANCEL-LOCK (backend; higher risk; single lane).
   A cancelled bottleneck job's serial lock can be held up to the request
   timeout — cancel is honest ("cancelling") but not interruptible. @oracle
   FIRST for the design (how to interrupt an in-flight serial job safely without
   corrupting persisted state), then @fixer implements with focused backend
   tests. See README Sec 13 (`06-X`) and the job path in app/bottleneck.py /
   app/api.py.

4. P3 POLISH BATCHES (parallelizable; low risk).
   Work the tracked P3s in the section files: 02-L/N/O/P/Q; 06-I/J/K/L/M/O; and
   whatever README Sec 12 still marks "track-only" for 00/01. For each: @fixer
   (or @designer for copy/UI) with a bounded brief; verify; commit. Batch by
   file so parallel lanes never collide on one file.

5. TEST HYGIENE.
   Add coverage for every P3 you land, plus the section-file "not covered" gaps.

PER-ITEM LOOP:
- Recon first (@explorer). Classify every finding BUG|TOOLTIP|UX|ACCESSIBILITY|
  DATA|PERFORMANCE|ARCHITECTURE|TEST|DESIGN|IDEA x P0-P3 with a why and a
  file:line.
- Fix inline only if small, low-risk, localized, testable, behavior-preserving
  (README Sec 7); otherwise document it.
- Route work: @designer for UI/interaction/a11y feel; @fixer for bounded
  headless implementation; @oracle for architecture/risk/review; @librarian for
  external docs.
- Verify: focused test → `cd tests/frontend; npx playwright test` → compare to
  README Sec 10. Commit per README Sec 11.
- Update README Sec 12/13/14 and the section file in the SAME session.
- Background discipline: the Job Board lists Reusable Sessions — reuse a
  specialist session (pass its task_id) when it holds relevant context, else
  spawn fresh. After dispatching background lanes, END THE TURN; the system
  notifies you on completion — do not poll.

STOP AND ASK (record in README Sec 13; do not guess):
- Product/visual decisions (layout, colour semantics, copy that changes meaning).
- Anything needing a new data source or external dependency.
- Cross-view number changes that could move a displayed value.

DONE WHEN: the queue's items are landed or explicitly deferred, every README
Sec 12 status is terminal, and the frontend suite is green (README Sec 10).

WIKI SYNC (session end): docs/audit/README.md stays canonical; the wiki gets
discoverability pointers and durable decisions only. Rewrite
Market-Analysis-Wiki/wiki/hot.md LAST, append one log.md entry, then rebuild the
retrieval index (contextual-prefix.py --all --no-llm, then bm25-index.py build)
and run wiki-lint — all via the WSL-root claude-obsidian transaction.
```

---

## State at handoff (2026-09-27)

- **Frontend suite:** 224 passed / 0 failed. **Backend:** green.
- **Audit:** closed — 9/9 sections deep-audited; all P2s fixed; P3 polish is the
  only optional work left.
- **Recent commits:** `95bb4c2` 06-A tooltips · `bf66de5` 06 editor pass ·
  `b80b211` 02-K/02-M · `70680b3` 02-G/H/M · `765a483` docs · `46d5a2b` wiki.
- **Deferred/out-of-scope:** `06-X` (item 3 above); cross-section tooltip
  convergence for events/portfolio/shell (item 1).
