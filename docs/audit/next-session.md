# Next session — resume prompt

Paste the block below into a fresh session (or say: *"read
`docs/audit/next-session.md` and execute it"*).

---

```text
Continue the Market Analysis repo audit. Multi-session effort. The app-section
audit is deep-audited on all nine sections; the wiki/retrieval audit is COMPLETE.

START HERE — the canonical state:
- docs/audit/README.md      — canonical. §4 priority order, §7 fix policy,
                              §8 verification, §10 test baseline, §11 commits,
                              §12 status board, §13 backlog + open decisions,
                              §14 session log.
- Section files: 00-shell-and-tooltips.md, 01-risk.md, 02-ai-sentiment.md,
  03-regime.md, 04-indicators.md, 05-market-quotes.md, 07-portfolio.md,
  08-events.md. (06-bottleneck is a light pass only — no section file.)
- docs/audit/wiki.md        — wiki/retrieval audit, COMPLETE.

PROJECT RULES: follow AGENTS.md (auto-loaded). Load-bearing: you are the ONLY
writer to the vault and to user-data files; sub-agents are read-only and must NOT
read the vault (pass slices inline); tests must never touch live user data
(tests/conftest.py autouse fixture); one logical change per commit,
scope-prefixed, never amend; data/events.json is pipeline-owned — never stage or
commit it.

GOAL: the audit's in-scope work is essentially done. What remains is a short list
of DECISIONS the user must take, plus two small cleanups. Do not re-open settled
items.

ALREADY DONE (do not re-do): every fix in README §13 marked FIXED, including the
risk engine, shell/tooltip, events (incl. the P1 destructive-Enter bug), regime,
indicators/breadth, market quotes, portfolio (all five), AI sentiment, the
timezone-aware ISO change, and the wiki retrieval decisions. Test hygiene: the
three stale baseline specs are repaired and the modal focus-trap spec exists.
**The frontend suite is fully green: 198 passed / 0 failed (verified 2026-09-27).**

WORK QUEUE:
1. OPEN DECISIONS (ask the user — do not guess; see README §13):
   - 03-B/C/D — the regime card's authoritative timestamp: detector
     `metadata.generated_at` (honest report time) vs the refresh-time
     `vintage.regime` (currently shown) vs the file mtime (`age_days`). Related:
     should the regime card suppress the generic `.vintage-note`, and should
     `service._enrich` stamp `vintage["regime"]` on the serve path? Today the
     stale banner and the footer stamp can disagree on the same card.
   - 05-D — what the indices/commodities "As of" stamp should mean (fetch time,
     which it is today, vs the FRED/LBMA source date), and whether to surface
     `spot.as_of` / per-row `source_date`.
   - 05-E — render `spot.attribution` + `source_date` (promised in `config.py`
     and `spot.py` but never rendered), or drop the claims.
   - 05-F — keep or drop `cov["futures"]` (computed, never displayed).
2. SMALL CLEANUPS (no decision needed):
   - Test hygiene: 12 out-of-scope frontend specs still carry stale mock keys
     (`column_order`/`column_visibility`) and two keep a dead `PUT .../columns/`
     branch. Harmless; remove them.
   - `IDEA` P3 — the unused `initialSort` option plumbing in `tickerTable.js`.
   - `UX` P3 — give the regime component grid an explicit `—` fallback when
     `component_scores` is absent.
3. 06-bottleneck: 06-A (17 inline `title=`) is DEFERRED — full convergence needs
   DOM restructuring (11 hover-only spans; 3 chips inside one focusable button;
   2 tests pin native titles). Only run it if the user wants a @designer pass.

FOR EACH TASK: static code + existing specs first; classify every finding
BUG|TOOLTIP|UX|ACCESSIBILITY|DATA|PERFORMANCE|ARCHITECTURE|TEST|DESIGN|IDEA ×
P0–P3 with a why and a file:line; fix inline only if small, low-risk, localized,
testable and behaviour-preserving (README §7); otherwise document it. STOP AND ASK
for product/design decisions. Verify: focused test → `cd tests/frontend; npx
playwright test` → compare against README §10 (198 passed / 0 failed). Commit per
README §11. Same pass: update README §12/§13/§14.

ENVIRONMENT TRAPS:
- Playwright's webServer binds port 8123 — ONE browser suite at a time; reap it
  after (Get-NetTCPConnection -LocalPort 8123 -State Listen must show nothing).
  Tell parallel lanes NOT to run Playwright; the Orchestrator runs the suite.
- Never drive a CLI through a redirected-pipe wrapper. Redirect output to a file
  under C:\Users\Spirors\AppData\Local\Temp\opencode\ and read that file.
- From pwsh, `wsl -d Ubuntu-22.04 -u root bash -lc "…"` swallows `$VAR` — inline
  full paths. Also: pwsh treats backticks as escapes, so put scripts with
  backticks in a file rather than `python -c`.
- Vault writes need WSL as root with an explicit `--vault`, through a
  `claude-obsidian.transaction.v1` bundle (build → inspect → apply with the
  inspect's `approval_sha256`). Never host-Edit a vault file.
- Retrieval: rebuild at session end (`contextual-prefix.py --all --no-llm`, then
  `bm25-index.py build`); query read-only via `retrieve.py --top 5 --no-rerank`.
  Navigation hubs and `sources/_retired/**` pollute results by design.
- The suite is green: a new failure is now a REAL regression.

WIKI SYNC: docs/audit/README.md stays canonical; the wiki gets discoverability
pointers and durable decisions only.

DONE WHEN: README §13's open decisions are answered or explicitly DEFERRED, the
two cleanups are done or tracked, all statuses are COMPLETE / FIXED-PARTIAL /
DEFERRED / EXCLUDED, and the frontend suite matches 198 passed / 0 failed.
```
