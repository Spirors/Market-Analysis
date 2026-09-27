# Section 00 — Shell and tooltips

**Status:** `AUDITED` (deep static audit complete; runtime probes not yet run)
**Priority:** 1 of 9
**Last updated:** 2026-09-26

**Covers (raw parts):** `header` (as-of stamp, Refresh), `#bands` + band heads,
the 26 card-reorder buttons, `#confirmOverlay` modal, `#tagPopover`,
`static/js/tooltip.js` (global `attachTooltip`), `static/js/cards.js:538-610`
(`CARD_TOOLTIPS` + `initCardTooltips`), boot wiring (`static/js/main.js`),
`static/js/layout.js`, `static/js/shutdown-listener.js`.

**Does not cover:** the content of any domain card (own section file).
**Evidence:** static review of `tooltip.js`, `layout.js`, `cards.js:520-675`,
`events.js:478-711`, `main.js`, `index.html`, `style.css`, and `tests/frontend`.

---

## 1. Purpose

Cross-cutting shell: page chrome, boot/wiring, the global tooltip component, and
the card-header info-button registry. It owns nothing domain-specific; it owns
*whether every card can explain itself* and *whether the chrome survives
re-render and reorder*.

## 2. User workflow

Load → header shows as-of + Refresh → 13 cards in Sentiment/Stats/News bands →
hover a card's ⓘ for its explanation → reorder via ↑/↓ → destructive news
actions hit the confirm modal → edit a news tag in the popover.

## 3. Current controls / interactions

Refresh button (`index.html:20`) · 26 reorder buttons (`index.html:30-147`) ·
13 ⓘ buttons injected at boot (`cards.js:597`) · generated band heads
(`layout.js:92`) · reset-layout link (`index.html:183`) · confirm modal
(`index.html:189`) · tag popover (`index.html:206`) · pagehide beacon
(`shutdown-listener.js`).

## 4. Current tooltips

| Location | Mechanism | Gaps vs the 5-point standard |
|---|---|---|
| `cards.js:538-591` (13 entries) | (a) `attachTooltip` | Strong on (1)(2)(3)(4). **(5) as-of is absent from the copy** — freshness only via the separate `.vintage-note`/header. The `deps` row is `aria-hidden` (`tooltip.js:42`), so (4) is invisible to AT. |
| `index.html:30-31`, 26 reorder buttons | (b) native `title=` | Only (1); no interpretation/cause/source/as-of. |
| `index.html:20` Refresh | (b) dynamic `title` | Text set on **mouseenter only** (`main.js:55-78`); no initial `title` in HTML; **keyboard focus gets nothing**. |
| `cards.js:650` cooldown badge | (b) `badge.title` | (1)(5) partial; duplicates the cooldown constants. |

**Coverage: complete.** `CARD_TOOLTIPS` has exactly 13 keys and all 13
`[data-card]` shells exist — no orphan in either direction. But the spec that
asserts this (`global-refresh.spec.mjs:25`) omits `portfolio` from its card list
(`:12-16`), so the card most in need of explanation is untested (finding 8).

## 5. Bugs / correctness findings

No P0/P1 shell correctness defects found. The refresh-error overwrite (finding
3) is the closest, classified `UX` because it is a surface/placement decision,
but it destroys rendered content and is worth treating with bug severity.

## 6. UX / clarity findings

1. **`UX` · P2 — global-refresh failure destroys the Risk card's rendered
   content.** `main.js:22-23` and `api.js:88` write the error string into
   `#riskBody`, replacing the rendered risk analysis (and its vintage stamp)
   until the next successful load. A transient network blip blanks the most
   important card. *Why it matters:* the highest-value card becomes less
   trustworthy than the rest. *(borderline `BUG`)*

2. **`UX` · P2 — saved layout is all-or-nothing and mis-orders newly added
   cards.** `layout.js:76` discards the *entire* saved order if any id is
   unknown (rename/removal silently resets the user's custom order);
   `layout.js:80-83` appends only listed cards, so a card absent from `order`
   (e.g. added later) is left at its old DOMy position — a simulation shows it
   lands **first**, not in place. *Why:* a future card addition reshuffles an
   unrelated saved layout.

## 7. Accessibility findings

3. **`ACCESSIBILITY` · P1 — the confirm modal has no focus trap and no focus
   restore.** `events.js:496-500` un-hides it and focuses Cancel, but Tab walks
   out to the page behind `#confirmOverlay` (whose `aria-modal="true"` therefore
   lies to AT), and on close focus drops to `<body>` instead of the invoking
   control. *Why:* keyboard/SR users lose their place and can act on hidden
   content. `layout.js` / `events.js` fix; **inline-safe**.

4. **`ACCESSIBILITY` · P1 — the injected ⓘ button pollutes every card heading's
   accessible name.** The button is appended *inside* the `h2` (`cards.js:607`)
   with `aria-label="About the … card"` (`:605`). A heading's name is computed
   from its contents, so AT announces "Risk divergence About the risk card"
   across all 13 headings. *Why:* it mis-names the element users navigate by.
   **Inline-safe** — move the button to a sibling of the `h2`, or name the `h2`
   explicitly via a wrapped `<span>` + `aria-labelledby`. Also unblocks the
   `aria-label` copy cleanup (card-id → human title).

5. **`ACCESSIBILITY` · P3 — `#tagPopover` lacks ARIA and focus restore.**
   `index.html:206` has no `role`/`aria-label`; `events.js:539-547` close does
   not return focus to the source pill; no focus trap. (Escape is handled,
   `events.js:700-703`.) *Defer to `08-events` reconciliation.*

6. **`ACCESSIBILITY` · P3 — `deps` pills are `aria-hidden`.** `tooltip.js:42`
   hides the dependency/source list from AT, dropping point (4) for
   screen-reader users. Consider an aria-visible "Depends on …" sentence.

## 8. Other technical findings

7. **`ARCHITECTURE` · P2 — duplicated cooldown constants + dead per-section
   refresh scaffolding.**
   - `COOLDOWN_SECONDS` is defined twice (`cards.js:613-616`, `main.js:49`) —
     drift risk; `main.js:70-76` admits it cannot see `cooldown_skip`, so "Next
     refresh in N min" is a best-guess maximum, not truth.
   - `.section-refresh` is extinct in the DOM (`global-refresh.spec.mjs:33`
     asserts count 0), yet `api.js:66-71/147-148`, `layout.js:10/184-197` and a
     `main.js:30-31` comment still wire it — `refreshSection()` is unreachable.
   - `cards.js:1248` references an "analysis ↻" that no longer exists.
   *Why:* the next contributor wires a control that can never render and trusts
   a stale comment. **Track-only.**

8. **`TEST` · P3 — the tooltip-coverage spec skips `portfolio`**
   (`global-refresh.spec.mjs:12-16`).

9. **`ARCHITECTURE` · P2 — the tooltip contract cannot express the Refresh
   button's tooltip.** `attachTooltip` builds its text once (`tooltip.js:98`)
   with no live-update API, so the freshness tooltip was forced onto a
   native-`title` hack that only fires on hover (`main.js:51-82`). *Why:* the
   one control needing a time-sensitive tooltip is the only one outside the
   unified system, and keyboard users get no freshness info.

10. **`IDEA` · P3 — band heads can duplicate.** `moveCard` swaps across bands
    (`layout.js:149-152`) while the header derives from `CARD_BAND`, so dragging
    a sentiment card into Stats yields two "Sentiment" headers. Likely
    intentional ("header travels with its card") — worth a one-line hint.
    *Not a change request.*

## 9. Suggested improvements

- Add an as-of/freshness sentence to each `CARD_TOOLTIPS` entry (point 5).
- Route the `.card-mv` `title=` and the cooldown `badge.title` through
  `attachTooltip` to finish the (b)→(a) convergence.
- Give `#asof` `role="status"` so refresh announcements reach AT.

## 10. Fixes completed

Verified 2026-09-26; the frontend suite was unchanged at **157/4** for these
changes (it later moved to 158/3 via `08-events` FIX-08-T).

- [x] **FIX-00-A** `ACCESSIBILITY` P1 — `initCardTooltips` wraps the `h2` in a `.card-head` row and appends the ⓘ button as a **sibling**, not a child; heading accessible names no longer include the button text (`cards.js:597-626`, `style.css:1258-1272`). Commit `0e9d2bf`.
- [x] **FIX-00-C** `UX` P2 — `applyLayoutOnLoad` filters unknown/malformed/duplicate ids instead of rejecting the whole saved order, and appends known-but-unlisted cards in `CARD_BAND` order (`layout.js:70-108`). Commit `472de74`. *(The two `dash-layout` specs stay red: they re-implement the logic in-page with a stale mirrored `CARD_BAND` — a test-hygiene follow-up, not a product regression.)*
- [x] **FIX-00-E** — modal focus trap/restore, landed in the events lane (`6b1ae3b`); see `08-events.md`.
- [x] **FIX-00-F** — tag popover ARIA/focus restore (`6bd6e53`); see `08-events.md`.
- [x] **FIX-00-D** `ARCHITECTURE` P2 — `attachTooltip` now accepts a string **or a
      provider function** (re-run on every open) and returns a `setText` handle;
      the header Refresh button moved onto the unified surface, so its
      freshness/cooldown copy shows on hover **and** keyboard focus, and the
      mouseenter-only native `title` hack is gone (`tooltip.js:98-131,174`,
      `main.js:46-77`). Focused spec added; the stale `refresh-cooldown`
      assertion was retargeted to the tooltip node, not weakened. Commit `e0bd9db`.

- [x] **FIX-00-B** `UX` P2 — a failed refresh no longer writes into `#riskBody`.
      One header status region (`#appStatus`) owns every load/refresh failure:
      soft ("still showing the last successful data") when a prior payload is on
      screen, hard when nothing has loaded; auto-cleared on the next success.
      `api.js` gained `showAppStatus`/`clearAppStatus` and dropped the per-card
      `renderSectionError`/`SECTION_ERROR_TARGETS` map, so no card body is ever
      overwritten. `#asof` gained `role="status"`; `.hdr-status` reserves its
      height so nothing shifts. `index.html:22-28`, `style.css:34-59`,
      `api.js:1-48,87-96,172-181`, `main.js:5,20-30`. Commit `f4904ae`.
- [x] **FIX-00-G** `ACCESSIBILITY` P2 — the tooltip `deps` row is no longer
      `aria-hidden`; it is a labelled `role="list"` with `role="listitem"`
      pills, so the data-source point (standard 4) is part of the tooltip's
      `aria-describedby` text (`tooltip.js:10-19,49-66`). Commit `694f2bb`.
- [x] **FIX-00-H** `ARCHITECTURE` P2 — the unreachable per-section refresh
      subsystem is gone (`refreshSection`, `SECTION_IDS`, `sectionGen`,
      `_setFeedback`, `_pulseCard`, `FEEDBACK_HOLD_MS`, `_resetSectionButtons`)
      from `api.js`/`layout.js`/`main.js`. Commit `dbb8898`.
- [x] **FIX-00-I** `UX` P2 — `COOLDOWN_SECONDS` is a single export in `api.js`
      (consumed by `main.js` and `cards.js`), and the header copy is honest:
      "Next refresh available in up to N min". Commit `dbb8898`.

## 11. Tracked TODOs

**Applied (see §10):** FIX-00-A, FIX-00-B, FIX-00-C, FIX-00-D.

**Still to dispatch (shell-only files):** none.

**Deferred to `08-events` reconciliation (shared `events.js`):**
- [x] ~~**FIX-00-E** `ACCESSIBILITY` P1 — modal focus trap + restore~~ — done (`6b1ae3b`)
- [x] ~~**FIX-00-F** `ACCESSIBILITY` P3 — `#tagPopover` ARIA + focus restore~~ — done (`6bd6e53`)

**Track-only / follow-up:**
- [x] ~~Remove dead `.section-refresh` scaffolding~~ — done, FIX-00-H (`dbb8898`)
- [x] ~~De-duplicate `COOLDOWN_SECONDS` and make the header label honest~~ — done, FIX-00-I (`dbb8898`)
- [ ] `TEST` P3 — add `portfolio` to the tooltip-coverage spec (this session's `00-TEST`)
- [x] ~~Add an as-of/freshness sentence to all 13 `CARD_TOOLTIPS` entries~~ — done (`2894c5e`)
- [x] ~~Make `deps` data-source point visible to AT~~ — done, FIX-00-G (`694f2bb`)
- [x] ~~Converge inline native `title=` onto `attachTooltip`~~ — done (`fe40eed`)

**Runtime probes (Q6 bounded) — resolved 2026-09-27:**
- [x] ~~heading accessible-name computation with ⓘ inside `h2`~~ — the ⓘ is a
      `.card-head` sibling, not inside the `h2` (spec-proven). The probe's premise
      was false, but the concern was real for the coverage/cooldown badges, which
      **were** appended inside the `h2` — fixed as `00-V` (`c589a95`): they now
      render in `.card-head` beside the `h2`. The same class for the portfolio
      grand total and the bottleneck badge is fixed as `00-W` (`739cc4c`).
- [x] ~~Tab escape from the open confirm modal~~ — covered by
      `modal-focus-trap.spec.mjs`.
- [x] ~~saved-order-with-extra-card layout~~ — covered by the tolerant merge
      (FIX-00-C) and `dash-layout-survives-reload.spec.mjs`.

## 12. Verification notes

Static only; no probes run and no files modified during the audit. Any applied
fix is verified via §8 of `README.md` (focused test → frontend suite → compare
against the 157/4/0 baseline).
