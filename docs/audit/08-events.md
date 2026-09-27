# Section 08 — Events (news timeline)

**Status:** `AUDITED` (deep static audit complete; runtime probes not yet run)
**Priority:** 3 of 9
**Last updated:** 2026-09-26

**Covers (raw parts):** `events` card (`index.html:144-179`) — Week/Month
segmented control, period `<select>`, seed-only checkbox, the legacy tag chipset
(`#tlFilters`) and the Region/Weight/Topic chipsets, the row pills that open
`#tagPopover`, the `+ tag` inline form, Remove/Hide-source actions, and the
shared confirm modal as used here.

**Backend:** `app/api.py:141-228` (`/api/events*`); data plumbing in
`data.events` (`cards.js:696`); dedupe/store in `app/news.py` + `app/store.py`.
**Evidence:** static review of `events.js`, `style.css`, `index.html`,
`global-refresh.spec.mjs`, `app/api.py`, `app/news.py`, `app/store.py`.

---

## 1. Purpose

The filtered news timeline: groups ingested/curated market events into
week/month buckets, layers tag + region/weight/topic chips + a seed-only toggle,
and lets the user correct mis-classified tags through a popover. It is also the
surface where the stale "news-row chips" baseline failure lives.

## 2. User workflow

Pick Week/Month → pick a period → stack chips (legacy tag chips, then
Region/Source-weight/Topic) + Seed-only → click a row pill to fix a dimension or
rename/remove a tag → optionally Remove event / Hide source (confirm modal) →
global Refresh to recompute the AI gauge.

## 3. Current controls / interactions

Week/Month segmented (`index.html:151-154`) · period `<select>` (`:156`) ·
seed checkbox (`:159`) · chipsets `#tlRegionChips/#tlWeightChips/#tlTopicChips`
(`:163-176`) · legacy `#tlFilters` (`:177`) · row pills → `#tagPopover`
(`:206-223`) · `+ tag` inline form · ✕ Remove / hide source · confirm modal
(`:189-198`).

## 4. Current tooltips

| Where | Location | vs the 5-point standard |
|---|---|---|
| Card info button (shared `attachTooltip`) | `cards.js:583-586`, wired `:597+` | (1) ✓ · (2) partial — no band definitions, no Critical≥9 · (3) partial — no refresh cadence · (4) ✓ · **(5) ✗** |
| Source-weight badge `title=` | `events.js:420` | Raw number only; no band/scale |
| Relevance chip `title=` | `events.js:424` | Scale 0–10 ✓ · band meaning ✗ |
| `+ tag` / Remove / hide source `title=` | `events.js:432,446,447` | Action labels only |

**Convergence unmet:** 5 inline `title=` remain here, and the card tooltip
drops interpretation bands and freshness (finding 11).

## 5. Bugs / correctness findings

1. **`BUG` · P2 — `showEventError` is out of scope in the popover.**
   `events.js:777` defines it as a `const` *inside* the `#newsBody` click
   handler, but `bindTagPopoverOnce` calls it from `:669` and `:686`. A failed
   tag rename/remove/dimension save throws `ReferenceError` instead of showing
   the inline error. *Why:* a failed save looks like a silent no-op.
   **Inline-safe** — hoist `showEventError` to module scope.

2. **`BUG` · P3 — unstable tie ordering.** `events.js:324` returns `-1` for
   equal `published`, overriding the backend's stable link tiebreak
   (`store.py:186-196`), so same-timestamp rows can reshuffle. *Why:* row order
   changes between renders for no reason. **Inline-safe** — compare `link` as a
   secondary key.

3. **`BUG`/`TEST` · P1 — the "news-row chips" baseline failure is a STALE TEST,
   not a product bug.** `global-refresh.spec.mjs:64` asserts
   `.tl-meta .pill.region` count 1, but the implementation moved region out of
   `.tl-meta` into the tag line (`events.js:414-417`) and now renders it as an
   editable `.tl-tags .pill.region` (`:391-396`). Region still renders — only the
   selector lags the refactor. **Track-only** (one-line selector change, no
   product change). *This is one of the 4 baseline failures; see `README.md` §10.*

## 6. UX / clarity findings

4. **`UX` · P3 — misleading empty state.** A truly empty timeline shows "No
   events match the selected filters." (`events.js:377`), conflating "no data"
   with "filtered out". *Why:* the two need different user actions.

## 7. Accessibility findings

5. **`ACCESSIBILITY` · P1 — tag pills are keyboard-inaccessible.** The pills are
   `<span data-act="tag-edit">` with no `tabindex`/`role`/keydown handler
   (`events.js:391-396`); the only keydown delegate handles `.tag-add-input`
   (`:866-875`). `.pill-clickable:focus-visible` (`style.css:980`) is dead intent
   — a span cannot focus. *Why:* keyboard users cannot open the tag editor at
   all. **Track-only** — render pills as `<button>`, or add
   `tabindex="0" role="button"` + Enter/Space.

6. **`ACCESSIBILITY` · P2 — chip focus is lost and tag chips lack a pressed
   state.** Every toggle rebuilds the row via `innerHTML`
   (`events.js:229-238`, `:261-265`), destroying the focused button; the legacy
   tag chips never set `aria-pressed` (region/weight/topic do, `:263`). *Why:*
   keyboard focus jumps away after each filter click and state is not announced.
   **Track-only** — restore focus by `data-key` after re-render; add
   `aria-pressed`.

7. **`ACCESSIBILITY` · P2 — no live region.** `#weekBadge` (`index.html:157`)
   updates but is not `aria-live`, and filter changes re-render `#newsBody`
   silently. *Why:* screen-reader users get no confirmation the filter applied.
   **Inline-safe** — add an `aria-live="polite"` status span.

8. **`ACCESSIBILITY` · P3 — `.chip` lacks `focus-visible`** (`style.css:367-381`),
   unlike `.tl-mode-btn` (`:363`).

## 8. Other technical findings

9. **`DATA` · P3 — timezone / as-of honesty.** RSS timestamps are stored
   UTC-naive (`news.py:383-390` `_to_iso` emits no `Z`/offset) but
   `new Date("…T00:00:00")` parses as **local** (`events.js:181-188`), while
   `.tl-date` shows the raw UTC slice (`:404`) and the header/card as-of is ET.
   East-of-UTC users can see a week-label/date disagreement. *Why:* it breaks
   the cross-view consistency rule. **Track-only** — cross-section (shared
   `_to_iso`; the AI-gauge lookback in `store.py:612-613` compares the same
   strings).

10. **`DATA` · P3 — dedupe is lossy and order-dependent.** The cross-source
    merge (`store.py:81-86`, gated `:346-351`) can merge two genuinely distinct
    same-titled items within 2 days, and misses the same story when wording
    diverges. Deterministic but not guaranteed. *Why:* duplicates or accidental
    merges erode trust. **Track-only** — document; optionally require a shared
    rare token.

11. **`TOOLTIP` · P2 — standard gap.** Add to the card tooltip: weight bands
    (high ≥1.1 / med 0.9–1.1 / low <0.9), relevance bands (crit ≥9 / high ≥7 /
    med ≥4), the Critical≥9 rule, and
    `NEWS_REFRESH_INTERVAL_HOURS = 4`.

12. **`DESIGN` · P3 — dead CSS/comment from the region move.**
    `style.css:1373-1375`, `:1392`, `:1396-1405` still describe/colour
    region-in-`.tl-meta`, and `events.js:455-460` is a garbled duplicated
    comment.

## 9. Suggested improvements

- Land the two tiny isolated fixes now: hoist `showEventError` (F1) and fix the
  comparator (F2).
- Do the a11y cluster as one pass: pills → buttons + focus restoration (F5, F6)
  + live region (F7) + `.chip` focus-visible (F8).
- Roll tooltip convergence (F11) into the shared-component direction.
- Correct the stale spec selector (F3).

## 10. Fixes completed

Verified 2026-09-26; the frontend suite moved **157/4 → 158/3** (FIX-08-T turned
the stale "news-row chips" failure green; the other 3 fail at baseline too).

- [x] **FIX-08-A** `BUG` P2 — `showEventError` hoisted to module scope (`events.js:498`). Commit `a143f11`.
- [x] **FIX-08-B** `BUG` P3 — comparator tie-breaks equal `published` on `link` (`events.js:326-334`). Commit `c883c3c`.
- [x] **FIX-08-C** `ACCESSIBILITY` P2 — sr-only `#tlStatus` (`role="status" aria-live="polite"`) updated on every filter change (`index.html:158`, `events.js:387-397`). Commit `82fd50e`.
- [x] **FIX-00-E** `ACCESSIBILITY` P1 — modal records the invoker, cycles Tab/Shift+Tab, restores focus on close (`events.js:516-557,572-595`). Commit `6b1ae3b`.
- [x] **FIX-00-F** `ACCESSIBILITY` P3 — `#tagPopover` is `role="dialog" aria-label="Edit tag"` and returns focus to the source pill (`index.html:207`, `events.js:606-621`). Commit `6bd6e53`.
- [x] **FIX-08-T** `TEST` P1 — stale selector updated to `.tl-tags .pill.region` (`global-refresh.spec.mjs:64`). Commit `854d01c`.
- [x] **FIX-08-P** `ACCESSIBILITY` P1 — tag pills are now `role="button" tabindex="0"`
      with an Enter/Space branch in the `#newsBody` keydown delegate that forwards
      to the existing click branch (single-fire); the popover's focus-restore now
      lands on the pill, and `.chip:focus-visible` gives the filter chips a focus
      ring (`events.js:413-421,928-949`, `style.css:394-397`). Commit `8fbc301`.
- [x] **FIX-08-Q** `BUG` **P1** — a document-level "Enter = confirm" branch
      fired before the focused button's activation, so **Enter on the focused
      Cancel button ran the destructive confirm** (deleting the event) while
      Space cancelled. The override is removed; native button activation makes
      Enter and Space both act on the focused control, Escape stays global
      (`events.js:575-583`). Two regression tests added to
      `modal-focus-trap.spec.mjs`. Commit `aaebdb0`.

## 11. Tracked TODOs

**Applied (see §10):** FIX-08-A, FIX-08-B, FIX-08-C, FIX-08-P, and the stale-spec
repair FIX-08-T.

**Track-only / follow-up:**
- [ ] Restore chip focus after the `innerHTML` re-render (`data-key` lookup); add `aria-pressed` to the legacy tag chips
- [ ] Split "no data" vs "no filter match" empty states
- [x] ~~Timezone-aware ISO / ET formatting (cross-section, shared `_to_iso`)~~ — done (`47c8b6a`): `Z` end-to-end, legacy-tolerant reads
- [ ] Document dedupe merge tolerance
- [ ] Remove dead region-in-`.tl-meta` CSS and the garbled comment
- [x] ~~Converge the row's native `title=` onto `attachTooltip`~~ — done (`fe40eed`): the 2 informational chips (source weight, finance relevance) migrated to focusable triggers; 3 redundant titles deleted. Stale gauge-recompute comment dropped (`9d76447`).

**Runtime probes (Q6 bounded):**
- [ ] Tab to a row pill; confirm it is unreachable (F5)
- [ ] Post-chip-toggle focus position (F6)
- [ ] Force a 500 from `/api/events/dimensions`; confirm the `ReferenceError` (F1)

## 12. Verification notes

**Baseline verdicts (feed `README.md` §10):**

- **"news-row chips" → stale test, not a regression.** Product behavior is
  correct; region renders as an editable `.tl-tags .pill.region`. Only the
  assertion selector lags.
- **The two "dash-layout" failures are out of section-08 scope** but share the
  same staleness pattern: both fixtures include a removed card `"earnings"`
  (`dash-layout-survives-reload.spec.mjs:118,155`) absent from `CARD_BAND`
  (`layout.js:26-40`), so `applyLayoutOnLoad` returns `applied:false`. Route to
  the layout finding (`00-shell-and-tooltips`, finding 2).
- **"portfolio-star-scope"** belongs to `07-portfolio`; verdict pending that
  section's audit.

No runtime walkthrough run; no files modified during the audit. Applied fixes
are verified via `README.md` §8.
