# Agent Workflow Kickoff Prompt

Paste this at the start of a session with your coding agent (opencode, Claude
Code, etc.) whenever you're about to do non-trivial work on a repo. Sections
marked **[PROJECT-SPECIFIC]** are the only parts you rewrite per project —
everything else is meant to be copy-pasted as-is.

Memory approach: plain, git-tracked Markdown files read in a fixed order at
session start/end (credit: r/opencodeCLI). No vector DB, no background
service, no embeddings — durable facts live in files you can diff and grep.

---

## Session Start

Read in this exact order before doing anything else:

1. `AGENTS.md` — hard rules, non-negotiable process
2. `README.md`
3. `ROADMAP.md` — current phase; only work inside it unless told otherwise
4. `docs/HANDOFF.md` — where the last session left off
5. latest entry in `docs/SESSION_LOG.md`
6. `docs/DECISIONS.md`
7. `docs/RUNBOOK.md` — exact operational procedures (launch/test/shutdown)

`ARCHITECTURE.md`, `API.md`, and `TESTING.md` are deliberately **not** in
this list — read them on demand when the task actually touches that area.
Keeping deep reference material out of the mandatory read keeps
session-start cost roughly flat even as the docs grow.

State your plan in 3–6 bullets before writing code. Wait for a go-ahead on
anything destructive (deleting files, rewriting shared modules, force-push,
schema changes).

## During Work

- Keep `docs/HANDOFF.md` aligned with current status and next actions as they
  change — don't wait until session end if something material shifts.
- Record durable decisions (architecture choices, "we tried X and it failed
  because Y", anything future sessions must not silently re-litigate) in
  `docs/DECISIONS.md` the moment you confirm them, not from memory later.
- Keep `docs/RUNBOOK.md` in sync with any change to operational commands
  (how to launch, test, shut down, deploy). If a command in the runbook is
  stale, fix the runbook in the same change — don't leave it to rot.

## Session End

- Update `docs/HANDOFF.md`:
  - `Last updated` timestamp (`YYYY-MM-DD HH:MM UTC`)
  - current state
  - top 3 next actions
  - blockers (if any)
- Append a new timestamped entry to `docs/SESSION_LOG.md`.
- Confirm no secrets were added to tracked files.
- Log the change per the project's existing changelog convention (check
  `AGENTS.md` — e.g. this project's `app.changelog.log_change`).

---

## 1. Non-negotiable process rules

These exist because violating them has already caused real incidents on this
project. Treat them as a hard gate, not a suggestion. The authoritative,
step-by-step version of these lives in `docs/RUNBOOK.md` — read it, don't
reconstruct it from memory.

| Don't | Do |
|---|---|
| Leave a server/process running "for the user to test" at the end of a turn | Kill anything you spawned; verify it's dead before ending the turn |
| Launch a real server just to sanity-check a route | Use an in-process test client (e.g. FastAPI `TestClient`) — no port binding, no orphan risk |
| Use `Start-Process`, `nohup`, `&`, or `Invoke-Expression`-based detached launches to "verify the server is up" | If a real running server is genuinely required (e.g. browser automation against the live UI), launch it hidden per `docs/RUNBOOK.md`, verify, then reap it explicitly |
| Assume "stealth mode" means anti-bot evasion | On this project, "stealth" launch = **no visible console window** for a local dev server (hidden-window launcher pattern), not fingerprint evasion. Anti-bot stealth only applies if you're adding browser automation against *third-party* sites |
| Bundle a refactor with a bug fix in one commit | One logical change per commit. Fix the bug, verify, commit. Refactor separately |
| Rediscover a failed approach the hard way | Check `docs/DECISIONS.md` first; log new findings there the moment you confirm them |

## 2. Refactor governance (use this whenever the project feels like it's "about to implode")

- **One extraction, one verification pass.** Before pulling shared logic out
  of two or more call sites into a common module, write down — in
  `docs/DECISIONS.md` or the PR description — exactly which state each
  caller currently persists independently (its own storage key, its own API
  param, its own default). Do this *before* extracting, not after something
  breaks.
- **Round-trip test every consumer after a shared-component extraction.**
  For each caller: change something → reload/reopen → confirm the same state
  comes back, for *that specific caller*, not just the one you tested by hand.
  Cross-contamination between callers sharing one component is the single
  most common bug class from this kind of refactor.
- **Don't touch frozen/reference files** unless explicitly told to (check
  `AGENTS.md` for any "frozen — do not modify" list before editing).
- **Log meaningful changes** using whatever changelog mechanism the project
  already has (check `AGENTS.md` before inventing your own).

## 3. [PROJECT-SPECIFIC] Open bugs for this pass — Market-Analysis

### 3a. Stuck process when launching the site to test
- The lifecycle rule is documented in `AGENTS.md` under "Local server
  lifecycle" — and should now be duplicated as an actual step-by-step
  checklist in `docs/RUNBOOK.md` so it's impossible to skim past.
- If you hit a hang despite following it, the likely culprits, in order:
  1. You used `pythonw.exe` directly instead of the `wscript.exe` + VBS
     `SW_HIDE` pattern (`launch.vbs` / `scheduler.vbs`) — see
     `docs/DECISIONS.md` for why `pythonw.exe` was already ruled out once.
  2. You verified against a real running server when `TestClient` would have
     sufficed.
  3. You started a server via `python run.py` (or a variant) and the turn
     ended before the reap step ran.
- Once fixed: record the concrete root cause in `docs/DECISIONS.md`, not just
  in the commit message — the goal is that the *next* session never
  re-diagnoses this from scratch.

### 3b. Section position not being saved
- Prime suspect: the recent shared `tickerTable.js` extraction (commit
  `914f406`, Earnings + Portfolio refactor). Before looking anywhere else:
  1. Confirm `column_order` / `column_visibility` are still read/written
     under **separate, section-specific keys** (`earnings` vs `portfolio`)
     after the extraction — not a single shared key the new component
     defaulted to.
  2. Confirm the dashboard card-order mechanism (`dashLayout` in
     `localStorage`, per `AGENTS.md`'s key quirks) wasn't accidentally
     touched by the same refactor — it's a *different* persistence
     mechanism from the per-section column prefs and easy to conflate.
  3. Reproduce with two sections open at once: reorder Earnings, reload,
     check Earnings *and* Portfolio. If Portfolio's order also changed or
     reset, that confirms cross-contamination from the shared component.
  4. Add a regression test per section so this can't silently regress again
     on the next shared-component change.
- Once fixed: add the finding to `docs/DECISIONS.md` — e.g. "shared UI
  components must take their persistence key as a required prop, never
  hardcode or default it" — so it governs future extractions, not just this
  one.

## 4. Why plain files instead of a memory plugin

Considered a vector-DB memory plugin (e.g. `opencode-mem`) and decided
against it for this project: it adds a background web server, an embedding
model download, and shard/migration management — another local process to
keep alive, which is the opposite of what you want while actively debugging
a process-lifecycle bug. The session-start/during/end file protocol above
gets you the same "don't re-explain yourself every session" benefit with
zero new moving parts, and it's fully git-diffable. Revisit this only if the
`docs/` files grow past what's skimmable, or you're juggling enough projects
that auto-capture's zero-effort recall starts paying for itself.

## 5. When AGENTS.md itself has grown too large

If `AGENTS.md` is pushing 400+ lines and mixing hard rules with reference
material, that's a contributor to "the project feels like it's imploding."
See `ROADMAP.md` Phase 1 for the proposed split — architecture/API/testing
reference move to their own docs, operational procedures move to
`docs/RUNBOOK.md`, and `AGENTS.md` itself shrinks to rules + the Session
Start/During/End protocol above.
