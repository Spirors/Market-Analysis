# Improvements Log — What Happened and What It Means

**Date:** 2026-08-22 · **Branch:** `improvements/review-2026-08-22` · **Status:** all 8 approved improvements done ✅ (+1 bonus bug caught)

Plain-language version of this round. The earlier bug-fix round is described in `docs/fix-log-2026-08-22.md` (already on `main`). Technical detail: `docs/improvement-review.md`.

---

## The story

You approved the eight *suggested improvements* from the review. They were implemented on this branch by specialist agents working in two waves — structural changes first, then the features that build on them, with the new test suites written last so they lock in the final behavior. Every commit passed the full test suite before it was made.

**Result: 16 commits. Tests went from 9 to 61, all passing in about a second, no internet needed.**

---

## What changed, in human terms

### 1. The math now lives in one place (`800fc87`)
The same calculations (momentum, market breadth, VIX-vs-average) were hand-copied in four different files. They agreed today, but nothing stopped them from drifting apart tomorrow. Now there is one copy of each formula in `app/indicators.py`, and everyone else borrows it. A randomized comparison of old-vs-new math across ~10,000 cases showed **zero differences** — same numbers, less code.

### 2. Settings moved to the settings file (`9242ef6`)
About two dozen tuning numbers (risk thresholds, AI-gauge weights, timeouts, lookback windows, ticker lists) were buried inside code files. They all now live in `app/config.py` with clear names and unchanged values — so tweaking the tool no longer means hunting through logic.

### 3. The bottleneck card got faster (`dcfa675`)
On a cold start, that card used to fetch up to ~55 tickers one-by-one during page builds. All of its tickers are now pulled in one bulk batch with everything else. The safety-net fallback remains, but normal builds never hit it.

### 4. You can now see when data is degraded (`d958b08`)
Before: if Yahoo was down, cards quietly went blank and looked like "nothing happening." Now every card knows how many of its inputs are alive, and shows a small muted "7/9"-style badge **only when something is missing**. Healthy dashboard = unchanged look.

### 5. Each card can show its own timestamp (`7a9139a`)
Cards used to imply everything came from the same moment. Each section now carries its own "As of HH:MM" stamp, so mixed-age data is honest and visible.

### 6. Scheduled tasks are safer (`d017b7a`, `04b08cf`)
Log files now rotate daily and anything older than 30 days deletes itself (new `--logfile-prefix` option). A slow refresh gets 4 hours instead of being killed at 1. Installing a task can no longer delete the old one and then fail. And the docs now say plainly: these tasks don't run while you're logged off Windows.

### 7. The frontend is finally organized (`ff02650`, `7846ec6`, `87305e6`)
The 1,366-line `app.js` monolith became 8 small modules under `static/js/`. Card labels now come from the backend (`GET /api/meta`) instead of a hand-maintained copy in JavaScript — if the endpoint ever fails, the built-in fallback is identical. **One visible side effect:** seven abbreviated names now show their proper full names (e.g., "Semis" → "Semiconductors", "Dow" → "Dow Jones"). Everything else looks and behaves exactly as before.

### 8. Regression tests: 51 new checks (`b40a88d`, `51f2aac`, `c11f1a6`, `b677dc4`, `22792f6`)
Five test suites now guard the things that broke before: the synthesis engine's scoring math, the risk engine's alarm rules (including "alarms still work when data is sparse"), database integrity, cache behavior ("failures are never cached"), and the API endpoints. All run offline in ~1 second.

---

## Bonus: the new tests immediately caught a real bug (`5c7602a`)

While being tested, the confidence scorer turned out to have a misordered condition: the "very low data coverage → cap confidence at 35%" rule could never trigger — those runs were capped at 55 instead. Same disease as the dead valuation signal fixed last round: a rule that exists but never fires. Fixed, test un-skipped, suite green.

**What you'll notice:** on days when very few engines have data, the stated confidence will now be more conservative (35-ish instead of 55-ish). That's the rule working as designed.

---

## Choices made on your behalf

- **Full ticker names** replace seven abbreviations (side effect of serving labels from config).
- **Badges/stamps are deliberately near-invisible** when everything is healthy — they only appear when something needs attention.
- **Log retention = 30 days**, execution limit = 4 hours.
- **Restart note:** a dev server started before these changes was still running on port 8000 during testing — restart `python run.py` to see the new frontend.

## Still parked (unchanged — needs your decision)

Resolved 2026-08-23: every parked item was decided and implemented on `parked/review-2026-08-23`, one commit each — see `docs/park-log.md`.

---

## How to review & merge

```powershell
git log --oneline main..improvements/review-2026-08-22   # the 16 commits
git diff main...improvements/review-2026-08-22 --stat    # files touched
python -m pytest tests/ -q                               # 61 passed
python run.py                                            # try the dashboard
```

Merge when satisfied: `git checkout main && git merge improvements/review-2026-08-22`
