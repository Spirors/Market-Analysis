# Fix Log — What Happened and What's Left

**Date:** 2026-08-22 · **Branch:** `fix/review-errors` · **Status:** all confirmed errors fixed & verified ✅

This is the plain-language version of what happened. The technical detail lives in `docs/improvement-review.md` (remaining work) and in git history.

---

## The story

1. A full review of every section of the app found ~30 issues: real bugs, fragile designs, and improvement ideas.
2. Each high-stakes claim was independently re-checked against the code before anything was touched — 8 were confirmed as-is, 2 were corrected (less severe than first thought).
3. You asked to fix **only the errors**, on a separate branch, one commit per fix, skipping anything that needs your sign-off.
4. Three specialists fixed the errors in parallel (analysis engines / data layer / frontend), each running the test suite before every single commit. One leftover bug (`bottleneck.py`) was fixed directly afterward.
5. **Result: 17 commits, zero regressions.** Tests: 9/9 passing before and after. JavaScript syntax check passes. All modules import cleanly.

---

## What was fixed (17 commits)

### Analysis engines — the numbers you see are now trustworthy

| What was wrong | What it means | Fix |
|---|---|---|
| The "valuation stretch" signal could never fire | It compared a list's median against its own top-quartile — mathematically almost impossible. Risk signal #9 and the AI gauge's −15 penalty were dead code doing nothing. | Now uses a simple absolute rule: stretched when median forward PE ≥ 30× (`451b1b8`) |
| "Median" wasn't the median | For even-sized lists it picked the upper-middle value, slightly skewing PE readings. | Uses the real statistical median (`e91ebea`) |
| RED alert could never trigger on bad-data days | The RED rules demanded "5 bullish signals" even when only 3 signals had data. Exactly when data is patchy — often during market stress — the alarm was silent. | Gates now scale with how many signals actually reported (`8e25b08`) |
| Crashes on impossible prices | A zero/negative price would crash log-math in correlation and volatility code instead of being skipped. | Non-positive closes are now treated as missing (`d7b3d4d`) |
| Confidence scores were understated | A hand-typed constant said weights total 15; they actually total 14 — confidence got capped too early at exactly the wrong boundary. | Total is now computed from the weight table so it can't drift again (`52e5f51`) |
| Crash risk on malformed dates | A non-text date value would raise an uncaught error in the synthesis engine. | Both date-parsing sites handle it safely (`ee3dbfe`) |

### Data layer — outages no longer poison the dashboard

| What was wrong | What it means | Fix |
|---|---|---|
| Failed downloads were cached as if real | If Yahoo hiccuped, empty results were stored and served for 24 hours — breadth/risk/momentum silently went blank and looked like "no signal". The single worst integrity bug found. | Failed fetches are never cached; next call retries (`ce66f0d`) |
| An EDGAR outage wiped 13F data for 20 days | A failed rebuild overwrote the good cached snapshot with an empty one. | Last good snapshot is kept when a rebuild fails (`cb5c36c`) |
| News fetch could hang forever | The RSS download had no timeout — the only network call in the app without one. Also, articles with no date skipped the 48-hour window entirely, and undated items got stamped with a fabricated "now". | 15-second timeout; undated entries dropped; fabricated timestamps removed (`8d1bd16`) |
| Database housekeeping ran on every operation | Schema checks (including table-drop migration logic) executed on nearly every read/write — wasteful lock churn against the scheduled task, and a loud warning now fires before any destructive migration. | Initialization runs once per process; JSON writes are atomic (temp file + rename) so a crash can't leave torn files; undated events can no longer be wrongly merged as duplicates (`dd0959e`) |
| Concurrent page loads triggered duplicate refreshes | Opening the dashboard in two tabs launched two full ~1-minute refreshes racing each other (and the 09:00 scheduled task). | A lock ensures one refresh at a time; latecomers reuse its result (`b7b30eb`) |
| Regime detector crashes weren't contained | Missing files or OS errors escaped and could kill a refresh. | Handled like other failures — serve cached report (`3c0f03c`) |

### API — input is now checked

| What was wrong | What it means | Fix |
|---|---|---|
| Deleting an event with no arguments "succeeded" | Returned 200 while doing nothing. | Returns a proper 400 error (`aa79b6d`) |
| Any garbage string could be added as a ticker | Invalid symbols persisted forever, failed silently on every rebuild, and were used in cache filenames where a `/` or `..` could write outside the cache folder. | Tickers are validated before adding (with a human-readable reason on rejection) and sanitized before touching filenames (`490017d`) |

### Frontend — the dashboard no longer lies after refreshes

| What was wrong | What it means | Fix |
|---|---|---|
| `javascript:` links from news feeds could execute | Link text was escaped, but the link *address* wasn't checked — a malicious feed headline could run script when clicked (stored XSS). | Only http/https links become clickable; everything else renders as plain text (`3de3172`) |
| Older data could overwrite newer data | Rapid refreshes raced each other; a slow stale response could repaint a card with old numbers, and the header timestamp desynced from card contents. Errors also always appeared in the Risk card no matter which section failed, and failed actions gave zero feedback. | Every fetch carries a generation token — stale responses are discarded; HTTP errors are detected; errors render in the correct card; failed add/remove/delete actions show inline messages (`05d4c6d`) |
| Zero prices were dropped, NaN kept | Bottleneck momentum filters discarded valid 0.0 closes but kept NaN values. | Filter keeps zeros, drops NaN (`85979c8`) |

---

## Choices made on your behalf (flagged for review)

- **PE stretch threshold = 30×** — the broken quartile logic needed *some* number. Change `VALUATION_STRETCH_PE` in `app/risk.py` if you want a different band.
- **RED gate formula = max(3, 60% of live signals)** — restores alarms under partial data. Tunable in `app/risk.py`.
- **Undated news = dropped, not kept** — strictest reading of your "no backlog, no fabrication" rule.
- **Validation pattern = `[A-Z0-9.^=-]{1,10}`** — covers normal tickers incl. `^VIX`, `BRK.B`, `BTC-USD`, `GC=F`.
- **Full-dashboard failures still show in the Risk card** — that spot doubles as the whole-page error area; only single-card failures were rerouted.

## Skipped on purpose (needs your decision)

See **§2 "Parked"** in `docs/improvement-review.md`. Short version: things that would change analysis outputs (breadth double-count of SMH+SOXX, verdict semantics, missing-vs-zero handling), add features (regime expiry), change infrastructure (cross-process locking, WAL mode), or decide security posture (endpoint auth). Plus one unverified suspicion worth a manual look: whether the Stooq ticker mapping actually produces valid Stooq codes.

Suggested improvements (module split, tests, UI polish, accessibility, etc.) were deliberately **not** implemented — they remain listed in the review doc.

---

## How to review & merge

```powershell
git log --oneline main..fix/review-errors   # the 17 fix commits
git diff main...fix/review-errors --stat    # files touched
python -m pytest tests/ -q                  # 9 passed
python run.py                               # try the dashboard
```

Merge when satisfied: `git checkout main && git merge fix/review-errors`
