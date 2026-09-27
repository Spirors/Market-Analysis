# Section 06 — Bottleneck (editor / forms light pass)

**Status:** `FIXED-PARTIAL` (editor/forms + tooltip passes 2026-09-27; 06-A..06-H
fixed; 06-I..06-O P3 tracked)
**Priority:** 9 of 9
**Last updated:** 2026-09-27

**Covers (raw parts):** the bottleneck editor/forms region — `bottleneck.js`
`:723-1396` (editor `:723-904`, render/refresh `:906-1095`, panels/handlers/
delegation `:1126-1396`), plus its markup suppliers `:305-330`, `:347-375`,
`:425-441`, `:445-529`, `:571-721`.
**Backend:** `/api/bottleneck/*` (`static/js/api.js:278-382`).
**Prior art:** commit `ff9fc12` (10 findings + the SSRF fix). This pass covers
`TOOLTIP`, `UX`, `ACCESSIBILITY`, copy/labels, destructive-action safety and
regressions only — not the scoring/topic logic.
**Evidence:** static + grep recon of the editor, the handlers, the panel markup
and the specs. No runtime probe needed.

---

## 1. Purpose

The editor/forms half of the Bottleneck card: topic create/edit, agent generate,
import/export, the job review panel, and the topic-row actions. It is the app's
most form-heavy surface and the one area the earlier bug audit did not review.

## 2. Findings

1. **`TOOLTIP` · P2 — 06-A · the native `title=` tooltips are gone. FIXED**
   (`95bb4c2`, "Option B" triage). Redundant titles deleted (tri-state flags,
   Generate/Delete buttons, topic chips, the research link); the informative ones
   now use the shared `attachTooltip` through a focusable trigger with
   `aria-describedby` — the metric explanation, the 40-day ROC as-of, the
   provenance hashes, the disabled-Generate reason, and the momentum badge.
   `grep title=` in `bottleneck.js` is now 0. *Why:* the section no longer carries
   two tooltip mechanisms, and the remaining info is keyboard/AT reachable.

2. **`BUG` · P2 — 06-B · a failed draft apply was silently swallowed. FIXED**
   (`6772f6b`). `setPanelMsg` (`:1137`) matched `.bn-panel`/`.bn-editor` but not the
   review panel (`.bn-job.review`, `:681`), and `applyDraft`'s `finally` calls
   `render()` which rebuilds the panel — so the `catch` message was written into a
   node that no longer existed. The review box now carries `data-bn-msg`, the
   selector includes `.bn-job [data-bn-msg]`, and the error is written *after* the
   final render. *Why:* an apply failure reported nothing to the user.

3. **`BUG` · P2 — 06-C · a job-poll re-render wiped the New-topic name and
   Generate theme. FIXED** (`6772f6b`). `captureUnsavedInput` (`:1017-1032`)
   snapshotted only the editor and the Import textarea; `newTopicName`/`genTheme`
   are now captured and re-bound (`:464`, `:486`), reset on a fresh `openPanel`
   (`:1144-1145`). *Why:* typed text vanished on a background poll.

4. **`ACCESSIBILITY` · P2 — 06-D · panel validation/error messages were not
   announced. FIXED** (`6772f6b`). The six `.bn-panel-msg` boxes now carry
   `role="status"`. *Why:* client-side validation and API errors were silent to
   screen readers.

5. **`BUG`/`UX` · P2 — 06-E · an unparsable underdog ceiling is silently dropped.**
   `:863-864` `const parsedCeiling = parseCeiling(...); if (parsedCeiling != null) …`
   — invalid text is ignored, then overwritten by the stored value on the next
   structural re-render, with no message. The spec at `bottleneck.spec.mjs:603`
   pins a mocked server 400 the real client path cannot produce. **FIXED**
   `bf66de5`: an unparsable ceiling is caught client-side with a message; the spec
   now asserts no request is sent.

6. **`A11Y` · P2 — 06-F · no focus management anywhere in the editor.**
   `bottleneck.js` has zero `.focus()` calls: opening a panel doesn't focus it,
   closing doesn't restore the trigger, and `render()` replaces
   `#bottleneckBody.innerHTML` so structural removes and the delete confirm drop
   focus to `document.body`. The delete confirm (`:323-326`, `:1339-1349`) is an
   inline pair, not a dialog (no `aria-modal`, no Escape) — unlike the events
   modal (`events.js:599-628`). **FIXED** `bf66de5`: panels focus on open and
   restore the trigger on close; the delete confirm defaults to Cancel and Escape
   cancels. (Full dialog/`aria-modal` semantics remain for the 06-A DOM pass.)

7. **`A11Y` · P2 — 06-G · unlabelled inputs.** Layer name (`:759`), evidence
   claim/source/URL (`:771-773`), the tier `<select>` (`:774`), and the stock
   ticker/name (`:791-792`) are placeholder-only or label-less; repeated
   `aria-label="Remove …"` buttons (`:760`, `:777`, `:793`) don't carry the
   layer/ticker value. **FIXED** `bf66de5`: inputs got accessible names and
   repeated remove buttons name their row.

8. **`UX` · P2 — 06-H · Cancel/Discard discard work with no unsaved-changes guard.**
   `cancel-edit` (`:1338`) and `close-panel` (`:1319`) drop the draft silently; the
   job "Discard" (`:717`) permanently dismisses (`rememberDismissedJob`, cap 50)
   with no confirmation or undo, though it reads reversible. **FIXED** `bf66de5`:
   inline guards before discarding a dirty panel or permanently dismissing a job.

9. **`DATA`/`UX` · P3 — 06-I · an evidence row with only a URL/tier is dropped
   silently on Save** (`:899` `.filter((ev) => ev.claim || ev.source)`).
   *Document.*

10. **`UX` · P3 — 06-J · copy drift.** One action is "Dismiss" (`:588`) / "Discard"
    (`:717`); "Cancel" carries four meanings (panel close, draft discard, delete
    abort, job abort); Generate is "Generate topic…" / "Generate one…" / "Generate";
    "stock cards" vs the "anchors/underdogs" section heads. *Document.*

11. **`UX` · P3 — 06-K · a poll failure leaves the last "running" state on screen**
    (`:1044-1048` stops polling but the panel keeps rendering the stale status).
    *Document.*

12. **`UX` · P3 — 06-L · clipboard copy is a silent no-op where
    `navigator.clipboard` is undefined** (`:1321`, no `else`). *Document.*

13. **`A11Y` · P3 — 06-M · section titles are `<div>`/`<span>`, not headings**
    (`.bn-panel-title`, `.bn-ed-section-head`), so a long form has no heading
    navigation. *Document.*

14. **`A11Y` · P3 — 06-N · a disabled Generate button carries its reason only in
    `title=`** (`:357`, `:437`) — unfocusable and hover-suppressed in some browsers
    (mitigated by the visible `.bn-gen-off` hint). *Document.*

15. **`UX` · P3 — 06-O · raw model jargon as reader copy** (`:182` renders
    `upstream`/`downstream` as the card's "Role"). *Document.*

## 3. Fixes completed

- [x] **FIX-06-B** `BUG` P2 — a failed apply surfaces its error in the review
      panel. Commit `6772f6b`.
- [x] **FIX-06-C** `BUG` P2 — New-topic name + Generate theme survive a poll
      re-render. Commit `6772f6b`.
- [x] **FIX-06-D** `ACCESSIBILITY` P2 — panel message boxes announce
      (`role="status"`). Commit `6772f6b`.
- [x] **FIX-06-E** `BUG`/`UX` P2 — an unparsable underdog ceiling is caught
      client-side with a message; no request is sent. Commit `bf66de5`.
- [x] **FIX-06-F** `A11Y` P2 — panels focus on open and restore the trigger on
      close; the delete confirm defaults to Cancel and Escape cancels. Commit
      `bf66de5`.
- [x] **FIX-06-G** `A11Y` P2 — inputs got accessible names; repeated remove
      buttons name their row. Commit `bf66de5`.
- [x] **FIX-06-H** `UX` P2 — inline guards before discarding a dirty panel or
      permanently dismissing a job. Commit `bf66de5`.
- [x] **FIX-06-A** `TOOLTIP` P2 — native `title=` removed/migrated to
      `attachTooltip` affordances; no `title=` remains. Commit `95bb4c2`.

## 4. Tracked TODOs / open decisions

- [ ] **06-I..06-O** `DATA`/`UX`/`A11Y` P3 — evidence silent-drop; copy drift;
      stale "running" after a poll failure; clipboard fallback; heading semantics;
      disabled-button tooltip; raw role jargon.

## 5. Coverage notes

- Frontend: `tests/frontend/bottleneck.spec.mjs` — plus the guards for 06-A..06-H
  (the editor interaction/a11y describe block: focus, described tooltips, guards).
- Not covered: the evidence silent-drop (06-I), and the 06-I..06-O P3 items.
- Not covered: client-side required checks, the ceiling silent-drop (06-E), the
  evidence silent-drop (06-I), focus behaviour (no `toHaveFocus`/Escape assertions),
  roles/labels, and `remove-*`/`add-*` structural actions.
- Backend (`tests/test_api_bottleneck.py`, `tests/test_bottleneck_topics.py`) covers
  the server contract, not the UI layers above.
- Suite state is recorded in `README.md` §10.
