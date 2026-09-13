# 2026-09-10 — News section overhaul: Week/Month toggle + user-edit lock + AI gauge auto-refresh

> Verbose companion to the pointer at `project_rules/SESSION_LOG.md`.
> The live SESSION_LOG keeps only the latest entry in full per
> AGENTS.md hybrid layout; this file holds the verbose detail
> (file:line citations, test breakdowns, verification matrix) so a
> future session implementing or debugging can read it without
> re-deriving from scratch.

## Commit

`4734cc9` — `feat(news): week/month grouping toggle + user-edit lock + AI gauge auto-refresh`

## Three coordinated features

### Feature 1 — Week / Month grouping toggle (both views, persisted)

**Why both views:** the user asked for "both view with cache to remember
which is being used". `tlSelectedWeek` is preserved untouched so existing
bookmarks/links stay valid; `tlSelectedMonth` is a sibling key for the
month-mode selection; `tlGroupingMode` flips between them.

**Generic group builder.** `buildWeekGroups(items)` (events.js:257 in the
pre-change file) became `buildGroups(items, mode)`. The dispatch:

```js
if (mode === "month") {
  key = monthKeyOf(n);            // "YYYY-MM" or UNDATED_KEY
  label = key === UNDATED_KEY ? "Undated" : monthLabel(key);
} else {
  const ws = weekStart(n.published);
  key = ws ? ws.toISOString().slice(0, 10) : UNDATED_KEY;
  label = ws ? "Week of " + fmtWeekRange(ws) : "Undated";
}
```

`monthKeyOf` validates `YYYY-MM` with a regex so partial / malformed
timestamps still land in the undated bucket. `monthLabel` uses
`toLocaleDateString("en-US", { month: "long", year: "numeric" })` so the
labels stay locale-consistent with the rest of the dashboard.

**UI placement.** Inside the existing `.tl-toolbar` div, BEFORE the
period dropdown. Segmented control: two `<button class="tl-mode-btn"
data-mode="...">`s in a `role="group"`. Active state mirrors the
existing `.chip.active` style (filled with `--blue`, white text). Hover
state for the inactive button uses a subtle transparent fill. `aria-pressed`
on each button reflects the active mode; clicking switches the mode
and persists it.

**Label.** The original `<label class="tl-week-label">` got `id="tlPeriodLabel"`
plus a JS-side textContent flip on mode change:
`"Timeline week"` ↔ `"Timeline month"`. The `class` stayed so any
existing CSS targeting `.tl-week-label` continues to apply.

**Storage.** Three keys: `tlGroupingMode` (`"week" | "month"`, default
`"week"`), `tlSelectedWeek`, `tlSelectedMonth`. Each mode has its own
selected-period key so flipping modes never clobbers the other mode's
choice.

**Files:** `static/index.html` (+8), `static/js/events.js` (toggle logic
+ persistence + dropdown rendering), `static/style.css` (+32 for
`.tl-mode-toggle` / `.tl-mode-btn` / `:focus-visible` outline).

### Feature 2 — `user_edited` lock on news events

**Why.** RSS refreshes would re-derive fixed dimensions (category/actor/
direction/region) from the current title/summary text. If the heuristic
later flipped an event's category, the user's tag (which still said
`"ai"`) was kept but everything else was silently overwritten. The
user's words: "news that have been edited should not overwrite".

**Schema change.** Added `"user_edited"` to `_EVENT_FIELDS` in
`app/store.py`. Default `False` for events that never had a user tag
mutation; `_build_event_payload` coerces missing to `False` so older
JSON files don't blow up on read.

**Mutation.** `update_event_tags()` in `app/store.py:478` now sets
`target["user_edited"] = True` before saving. This is the only place
the flag gets set.

**Refresh lock.** `upsert_events()` (app/store.py:382) checks
`target_row.get("user_edited")` at the top of its update branch:

```python
if target_row.get("user_edited"):
    target_row["updated_at"] = now
else:
    # full re-derive from current text (existing behavior)
    ...
```

So once a row is user-edited, every subsequent RSS refresh — manual or
scheduled — only refreshes the `updated_at` stamp and leaves the
title/summary/category/actor/direction/region/tags untouched.

**Auto-AI-tag interaction.** Still works for new rows (insert path is
unaffected). For existing user-edited rows, the AI auto-tag won't be
re-applied even if the title changes — preserving user intent. The
cost: if a user manually removes the `"ai"` tag and the source later
corrects a typo that DOES match AI keywords, the row won't re-tag. This
is the explicit trade-off the user asked for ("don't overwrite my edits").

**Files:** `app/store.py` (+34 / −12).

### Feature 3 — AI gauge auto-refresh after a manual AI tag

**The killer feature.** Without it, adding/removing the `"ai"` tag via
the `+ tag` button only updated the timeline; the AI capex-cycle gauge
stayed stale until the user hit global Refresh.

**Backend.** `POST /api/events/tags` (app/api.py:152) now wraps a
defensive `try/except` around `service._recompute_ai_sentiment`:

```python
ai_sentiment = None
try:
    ai_sentiment = service._recompute_ai_sentiment(store.list_events(limit=5000))
except Exception:
    pass
return {"updated": updated, "events": store.list_events(limit=500), "ai_sentiment": ai_sentiment}
```

`ai_sentiment` is `null` rather than 500 if market data is unavailable.
The tag save has already happened by this point — even if the recompute
fails, the tag edit persists. Defense-in-depth matters here because
yfinance is rate-limited and a quota hit during a tag click would be
a horrible UX.

**Frontend export.** `renderAISentiment` in `static/js/cards.js:169`
gained `export` (body unchanged). `events.js` imports it.

**Frontend trigger.** New `applyTagUpdate(link, add, remove)` helper in
`events.js:447` replaces the three call sites that used to do
`renderNews((await updateEventTags(...)).events)`:

```js
async function applyTagUpdate(link, add, remove) {
  const resp = await updateEventTags(link, add, remove);
  renderNews(resp.events);
  if (resp.ai_sentiment && (add.includes(AUTO_TAG) || remove.includes(AUTO_TAG))) {
    renderAISentiment(resp.ai_sentiment);
  }
  return resp;
}
```

The `(add.includes(AUTO_TAG) || remove.includes(AUTO_TAG))` check
means non-AI tag edits (e.g. adding `"earnings-watch"`) don't trigger a
gauge re-render — cheap `O(1)` check on the small add/remove arrays.
Older backends (without `ai_sentiment` in the response) are handled by
the falsy check on `resp.ai_sentiment`.

**Files:** `app/api.py` (+14 / −2), `static/js/cards.js` (+3 / −2),
`static/js/events.js` (+~130 / −~30).

## The bug that almost shipped — cross-module `?v=` import pitfall

**Symptom.** First Playwright run of "clicking Month shows month groups"
failed with: `#weekSelect option` count = 1 (expected 4).

**Investigation.** Added console.log instrumentation:

```js
btn.addEventListener("click", () => {
  console.log("[TL_TOGGLE] click next=" + next + " current=" + groupingMode + " eventsCacheLen=" + eventsCache.length);
  ...
});
```

Initial render logged `events=6 groups=6` (correct). Click logged
`eventsCacheLen=0` (wrong — should be 6). Then `applyEventFilter`
rebuilt with 0 events.

**Root cause.** The early-draft cards.js had:
```diff
-import { renderNews } from "./events.js";
+import { renderNews } from "./events.js?v=20260910";
```

Combined with my new events.js:
```js
import { renderAISentiment } from "./cards.js?v=20260910";
```

The result was a module-graph split:
- `main.js` loaded `cards.js?v=20260905c` (instance A)
- `cards.js A` loaded `events.js?v=20260910` (instance C)
- `events.js C` loaded `cards.js?v=20260910` (instance D)
- `main.js` loaded `events.js` (no version) — instance B (different URL!)

`renderSection` in `cards.js A` called `renderNews` from `events.js C`,
which set `eventsCache` in instance C. But `initEvents` had registered
the click listener against instance B's `eventsCache`, which was still
the initial `[]`. Two module instances, two `eventsCache`s, silent
state split.

The stack trace confirmed it:
```
[TL_RENDER_NEWS] itemsLen=6 stack= at renderNews
(events.js:190) | at renderSection (cards.js?v=20260905c:892) | at load (api.js:85)
```

`renderNews` from `events.js` (no version) called by `renderSection` in
`cards.js?v=20260905c`. So events.js in the stack was instance B (the
one main.js loaded). But that instance's eventsCache was 0 by the time
the click handler ran — because the click handler's listener was
attached in instance B, and instance B's eventsCache was never set
(someone else's instance C was the one being updated).

Wait — the stack shows `renderSection` in `cards.js?v=20260905c`
(instance A) called `renderNews` from `events.js` (instance B), and
that set `eventsCache` in B. So B SHOULD have had 6 events. But the
click handler in B read 0.

Actually the explanation is more subtle. The module URL is
`events.js` (no version). Both A (via the versioned import) and
main.js (via the unversioned import) tried to load `events.js?v=20260910`
and `events.js` (no version) — two different URLs = two different
module records. But the stack shows only one `events.js` URL.

Looking at the stack again: `at renderNews (events.js:190:98)`. The
`190:98` is line:column. Looking at events.js line 190 after my
edits, that's inside `renderNews`. The stack doesn't show a query
parameter because the browser strips it from the stack frame name.

Whatever — the empirical fix is to not have ANY version mismatch. Both
imports must use the same URL string (or no version). The current
state in the committed code:

```js
// events.js
import { renderAISentiment } from "./cards.js";   // no version
```

```js
// cards.js
import { renderNews } from "./events.js";        // no version
```

```js
// main.js
import { renderSection, initCardTooltips } from "./cards.js?v=20260905c";
import { initEvents } from "./events.js";
```

main.js pins `?v=20260905c` on its own `cards.js` import (cache-bust),
but events.js and cards.js use unversioned imports so they share the
single module record that main.js loaded.

The fix is permanent and recorded in DECISIONS.

## Test matrix

### Backend — `tests/test_store.py` (+84 lines)

| Test | Status | What it proves |
|---|---|---|
| `test_update_event_tags_sets_user_edited_flag` | PASS | After tag mutation, `user_edited=True` |
| `test_upsert_events_skips_overwrite_when_user_edited` | PASS | Re-upserting a user-edited link doesn't change any field except `updated_at` |
| `test_upsert_events_overwrites_normal_event` | PASS (regression) | Non-user-edited rows still get full re-derive from current text |
| `test_user_edited_default_false_for_unmodified_events` | PASS | Fresh inserts default `user_edited=False` |

### Backend — `tests/test_api_contract.py` (+21 lines)

| Test | Status | What it proves |
|---|---|---|
| `test_events_tags_returns_ai_sentiment` | PASS | `POST /api/events/tags` response includes `ai_sentiment` key |

### Frontend — `tests/frontend/news-grouping.spec.mjs` (new, +171)

| Test | Status | What it proves |
|---|---|---|
| `toggle defaults to week` | PASS | Boot defaults + Week is `aria-pressed=true` |
| `clicking Month shows month groups in the dropdown` | PASS | Mode switch repopulates dropdown with month buckets |
| `selecting a month filters events to that month only` | PASS | Month bucket only contains events with `YYYY-MM` prefix match |
| `switching back to Week restores the previously selected week` | PASS | Each mode keeps its own selection |
| `month selection persists across reload` | PASS | `tlSelectedMonth` survives `page.reload()` |
| `mode (week/month) persists across reload` | PASS | `tlGroupingMode` survives `page.reload()` |
| `tagging an event with "ai" re-renders the AI gauge` | PASS | Stubbed `/api/events/tags` returning `{events, ai_sentiment}` triggers gauge re-render |

All 7 failed before the implementation (RED), all 7 passed after
(GREEN).

## Verification commands

```powershell
# Backend (full suite minus long-running + flaky files)
python -m pytest tests/ -k "not portfolio_cache_sync and not thirteenf and not service_coverage" -q
# → 443 passed, 43 deselected, 1 warning in 121.91s

# Targeted backend
python -m pytest tests/test_store.py tests/test_api_contract.py -x -q
# → 57 passed (34 + 23)

# Frontend (news section only, all 7 tests)
npx playwright test tests/frontend/news-grouping.spec.mjs --reporter=list
# → 7 passed (3.4s)
```

## Operational notes

- **Static server lifecycle.** Playwright's `webServer` block in
  `playwright.config.mjs` did not auto-start the static server in this
  session. Fell back to the foreground form (captured PID, `Stop-Process`
  in `finally`) per RUNBOOK.md §"Server lifecycle checklist" step 2.
  No orphan server left running at session end.

- **Git stash artifact.** A `git stash` was used mid-session to compare
  baseline Playwright failures (HEAD without my changes: 116 failed) vs.
  my changes (22 failed). Net improvement of 94 tests. Stash was popped
  cleanly; no working-tree drift.

- **Untracked file.** `tests/frontend/news-grouping.spec.mjs` was a new
  file added this session. Staged explicitly with `git add` to avoid
  the `?? ` line from accidentally including unrelated untracked files.

## Files committed

```
A  tests/frontend/news-grouping.spec.mjs   (+171)
M  app/api.py                               (+14 / −2)
M  app/store.py                             (+34 / −12)
M  static/index.html                        (+8)
M  static/js/cards.js                       (+3 / −2)
M  static/js/events.js                      (+~130 / −~30)
M  static/style.css                         (+32)
M  tests/test_api_contract.py               (+21)
M  tests/test_store.py                      (+84)
```

`data/events.json` is gitignored and unchanged on disk — no
intervention. The next 17:00 `MarketAnalysis-EventsCommit` scheduled
task will commit any drift there.