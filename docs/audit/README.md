# Market Analysis — Per-Section Audit

**This file is the canonical audit state and the resume point.** The wiki
(`Market-Analysis-Wiki/wiki/hot.md` and `index.md`) only *points here*. Never
duplicate status tables, findings, priorities, or TODOs into the wiki — that
would create two competing sources of truth.

An active, multi-session audit of every user-facing section of the app. The goal
is a per-section picture of *what the section does*, *how its tooltips read*,
and *what is broken or improvable* — with small, safe fixes applied inline and
everything larger tracked for a later session.

---

## 1. Scope and lenses

The app is a single page: 13 `<section class="card">` cards in three generated
bands (Sentiment / Stats / News), reorderable per browser. Most cards render from
`GET /api/dashboard`; portfolio, bottleneck, events and meta use their own
endpoints.

Every finding is classified on two axes and must state **why** it matters.

**Type:** `BUG` · `TOOLTIP` · `UX` · `ACCESSIBILITY` · `DATA` · `PERFORMANCE` ·
`ARCHITECTURE` · `TEST` · `DESIGN` · `IDEA`

**Priority:** `P0` serious correctness / data-loss / security · `P1` important
broken behavior · `P2` meaningful usability or correctness improvement ·
`P3` polish / optional

Not every observation must become a change. `IDEA` items are allowed but must
justify their value; this is not a speculative feature backlog.

**Lens coverage per section:** bugs/broken behavior · tooltip quality · UX
clarity, labels, copy · accessibility · data correctness and cross-view
consistency · performance · architecture/maintainability · test gaps ·
improvements discovered during the audit.

Visual redesign is **flagged as a `DESIGN` task**, never implemented here.

---

## 2. Section map

Nine audit units. Raw card ids are listed so findings map back to implementation
quickly.

| Audit file | Raw card ids / parts | Renderer(s) | Data | Status |
|---|---|---|---|---|
| `00-shell-and-tooltips.md` | header, `#bands`, reorder, `#confirmOverlay`, `#tagPopover`, `tooltip.js`, `CARD_TOOLTIPS` | `main.js`, `layout.js`, `tooltip.js`, `cards.js:538-610` | `/api/refresh`, `/api/meta` | AUDITED |
| `01-risk.md` | `risk`, `fragility` | `cards.js:15` | `/api/dashboard` → `risk` | AUDITED |
| `02-ai-sentiment.md` | `ai-sentiment` | `cards.js:172` | `/api/dashboard` → `ai_sentiment` | INVENTORIED |
| `03-regime.md` | `regime` | `cards.js:100` | `/api/dashboard` → `regime` | INVENTORIED |
| `04-indicators.md` | `indicators`, `breadth`, `breadth-ai` | `cards.js:150`, `:419`, `:423` | `/api/dashboard` → `indicators` | INVENTORIED |
| `05-market-quotes.md` | `indices`, `commodities`, `rates` | `cards.js:239`, `:273`, `:689` | `/api/dashboard` → `market` | INVENTORIED |
| `06-bottleneck.md` | `bottleneck` | `bottleneck.js` | `/api/bottleneck/*` | INVENTORIED (light pass) |
| `07-portfolio.md` | `portfolio` | `portfolio.js`, `tickerTable.js` | `/api/portfolios*` | INVENTORIED |
| `08-events.md` | `events` | `events.js` | `/api/events*` | AUDITED |

A dedicated `<section>.md` file is created only once that section receives a
meaningful (deep) audit. Until then its shallow findings live in §13 here.

---

## 3. Audit depth status

| Status | Meaning |
|---|---|
| `INVENTORIED` | Shallow pass complete (purpose, controls, tooltip inventory, obvious findings) |
| `AUDITED` | Deep static audit complete |
| `RUNTIME-VERIFIED` | One or more findings confirmed through bounded runtime probes |
| `FIXED-PARTIAL` | Safe findings fixed; remaining work tracked |
| `COMPLETE` | Audit complete and no unresolved in-scope work |
| `DEFERRED` | Intentionally postponed |
| `EXCLUDED` | Repository rule or explicit scope exclusion |

---

## 4. Priority order

Ordered by dependency and impact, **not** alphabetically. Do not reshuffle to
make numbering sequential.

1. `00-shell-and-tooltips` — shared infrastructure; every other section's tooltip findings depend on it
2. `01-risk` — the app's headline verdict, highest P0/P1 impact
3. `08-events` — highest defect yield (known-red specs live here)
4. `07-portfolio` — persistence/scope complexity + a known-red spec
5. `04-indicators` — shared payload, cross-view consistency risk
6. `03-regime` — dashboard consumer
7. `02-ai-sentiment` — dashboard consumer
8. `05-market-quotes` — structurally simplest, expect low yield
9. `06-bottleneck` — light TOOLTIP/UX/A11Y/regression pass only (prior art, see §9)

**Session 2026-09-26 deep batch:** `00`, `01`, `08` (all `AUDITED`). The rest end
the session `INVENTORIED` with tracked TODOs in §13.

---

## 5. Tooltip standard

Every meaningful card/data tooltip should answer, where applicable:

1. **What it measures**
2. **How to interpret it** — scale, colors, directionality, thresholds
3. **What causes it to change**
4. **Data source**
5. **As-of / freshness**

Do not force all five fields when one is genuinely irrelevant — but the audit
must **explicitly note missing context** rather than accepting a vague one-line
description.

**Two mechanisms exist and must converge:**

- (a) the global `attachTooltip` component (`static/js/tooltip.js`), driven by
  centralized `CARD_TOOLTIPS` (`static/js/cards.js:538-591`) on card-header info
  buttons;
- (b) scattered native `title=` attributes inline in widgets.

Converge (b) onto (a) for consistent appearance, keyboard support, Escape
dismissal, focus behavior, ARIA semantics, and maintainability. Migrate inline
only when clearly bounded and behavior-preserving; document anything needing
DOM restructuring, event-ownership changes, or unusual dynamic lifecycle as a
tracked TODO. **Do not keep both systems long-term without documenting why a
specific case must remain native.**

---

## 6. Evidence and runtime probes

Default evidence is static code reading plus existing tests/specs. Use
`agent-browser` **only** as a bounded probe when a concrete suspected defect
exists, static behavior conflicts with a spec, user-visible behavior is
ambiguous from code, or interaction state cannot be inferred statically.

No full runtime walkthrough of every section. A probe is targeted, recorded in
the relevant section file, and stopped once the question is answered.

The session's `00`/`01`/`08` audits were **static-first**; the pending probes are
listed per section file.

---

## 7. Fix policy

Fix inline only when the change is small, clearly understood, low-risk,
localized, easy to test, and unlikely to alter unrelated behavior. A tiny safe
fix may naturally touch a test plus its implementation — the distinction is
**complexity/risk, not file count**.

Document instead of fixing when the issue involves significant cross-section
behavior, backend or data-model changes, concurrency, security-sensitive
behavior, large refactors, unclear intended behavior, or a change needing a
product/design decision.

Unrelated bugs discovered outside the active section are recorded in §13, not
chased mid-section.

---

## 8. Verification protocol

For every implemented fix:

1. Add or update a focused test where practical.
2. Run the relevant focused test first.
3. Run the frontend regression suite (`cd tests/frontend; npx playwright test`).
4. Compare against the verified baseline in §10.
5. Record the result in the section file (and update §13).

---

## 9. Exclusions

- **`archive/ai_*.html` — frozen snapshots, fully excluded.** Not audited, not
  modified, no section files, and their problems are not app findings. Frozen by
  repository rule.
- **`06-bottleneck` — prior art.** Already bug-audited in commit `ff9fc12` (10
  findings plus an SSRF fix). This audit covers it for `TOOLTIP`, `UX`,
  `ACCESSIBILITY`, copy/labels, regressions introduced after that audit, and
  anything outside the earlier audit's scope only. Overlapping findings are
  labelled "prior art (`ff9fc12`)". Unresolved prior tasks appear as clearly
  labelled **inherited work** in §13.

---

## 10. Verified test baseline

- **Command:** `cd tests/frontend && npx playwright test`
  (config `tests/frontend/playwright.config.mjs`; `webServer` is
  `python -m http.server 8123 --bind 127.0.0.1` with all `/api/*` mocked)
- **Result (first verified run):** 161 tests — **157 passed / 4 failed / 0 skipped**
- **Verified:** 2026-09-26

The 4 failures are **pre-existing baseline failures**. Future sessions must not
classify them as regressions:

| # | Spec | Failure |
|---|---|---|
| 1 | `dash-layout-survives-reload.spec.mjs:115` | `applyLayoutOnLoad` does not accept a layout containing portfolio |
| 2 | `dash-layout-survives-reload.spec.mjs:147` | card order does not persist after full page reload |
| 3 | `global-refresh.spec.mjs:62` | news rows missing region pill / source-weight badge / relevance chip |
| 4 | `portfolio-star-scope.spec.mjs:146` | star state does not persist across reload independently |

### Baseline failure verdicts (from this audit)

- **#3 "news-row chips" → STALE TEST, not a product bug.** The refactor moved
  region from `.tl-meta` to the tag line; the pill still renders (now editable)
  as `.tl-tags .pill.region` (`events.js:391-396`). Only the selector
  (`global-refresh.spec.mjs:64`) lags. See `08-events.md`.
- **#4 "portfolio-star-scope" → STALE TEST, not a product bug.** Composite
  per-portfolio keys are implemented (`watchColors.js:58-73`,
  `portfolio.js:543-551,800-816`). `pfExpanded` persists, so both portfolios are
  already **expanded** after reload; the spec's two caret clicks then *collapse*
  them and `renderBody` skips holdings tables (`portfolio.js:304-309`), leaving
  no `.earn-star`. Subtests 1 & 3 start collapsed and pass. See §13.
- **#1/#2 "dash-layout" ×2 → stale fixture over a REAL product bug.** Both
  fixtures include a removed card `"earnings"` absent from `CARD_BAND`, so
  `applyLayoutOnLoad` returns `applied:false`. That is the *correct* consequence
  of an over-strict rule: `layout.js:76` discards the **entire** saved order if
  any id is unknown (see §13 cross-section #6). Fix the tolerance (FIX-00-C) and
  the fixture.

> Incidental drift: the 2026-09-25 wiki log quoted 141 passed / 4 failed. The
> failing set is identical; the tree now has more passing tests. If the baseline
> changes during later recon, update this section with the newly verified
> baseline rather than assuming the old count still holds.

---

## 11. Commit conventions

- `docs(audit): bootstrap section audit` — this file.
- `docs(audit): <section>` — one commit per completed/deeply-audited section file.
- `fix(<scope>): <description>` / `feat(<scope>): <description>` — applied fixes,
  **never** bundled into a `docs(audit)` commit. Each carries its focused test
  where practical.

---

## 12. Status board

| Section | Status | Notes |
|---|---|---|
| `00-shell-and-tooltips` | AUDITED | 10 findings; 6 inline-safe fixes queued |
| `01-risk` | AUDITED | **P0 found**; backend fixes in progress |
| `02-ai-sentiment` | INVENTORIED | tracked TODO: deep audit |
| `03-regime` | INVENTORIED | tracked TODO: deep audit |
| `04-indicators` | INVENTORIED | tracked TODO: deep audit (1× DATA P1 open) |
| `05-market-quotes` | INVENTORIED | tracked TODO: deep audit |
| `06-bottleneck` | INVENTORIED | light pass done; prior art `ff9fc12` |
| `07-portfolio` | INVENTORIED | tracked TODO: deep audit (runtime-probe needed) |
| `08-events` | AUDITED | a11y cluster open; stale spec identified |

---

## 13. Cross-section findings and backlog

### Cross-section findings

1. **Tooltip system split is systemic.** Inline `title=` counts found: events 5,
   bottleneck 17, portfolio ~8 (+`tickerTable`/`watchColors`), shell reorder 26.
   None meet the 5-point standard; many sit on non-focusable `<span>`s, so they
   are hover-only and unreachable by keyboard/SR. Convergence is one effort.
2. **As-of / freshness (point 5) is the most-missing standard field** — present
   only as a separate vintage stamp on some cards, absent from the tooltip copy.
3. **Null/unavailable handling diverges** across market cards: indices show an
   explicit "—", commodities drop the row, `quotesTable` drops the row while its
   tooltip claims nulls are shown. One `DATA` decision, several call sites.
4. **Timezone-naive ISO** originates in the shared `news.py:_to_iso` (no `Z`),
   so events display can disagree by timezone and the AI-gauge lookback compares
   the same naive strings — the fix must be cross-section.
5. **Dead endpoint `GET /api/regime`** (`app/api.py:445`) — no frontend caller;
   pinned only by `tests/test_api_contract.py`. Serve-or-drop decision.
6. **Layout tolerance bug** (`layout.js:76`) discards an entire saved order on
   any unknown id and mis-places cards missing from `order` (`layout.js:80-83`).
   This underlies the "dash-layout" baseline failures and would reshuffle a saved
   layout after any future card addition.
7. **Dead `.section-refresh` scaffolding** still wired in `api.js`, `layout.js`,
   `main.js` although the control cannot render; `COOLDOWN_SECONDS` is duplicated
   (`cards.js:613-616`, `main.js:49`).
8. **Same-metric naming collisions.** Positive: risk breadth % and the Indicators
   breadth % are the same `pct_above_ma` universe and agree. Negative: the
   breadth *card* labels "share above 50DMA" while plotting distance-from-MA
   (`04`), and VIX reads "vol normal" in Risk vs "unknown" in Indicators (`01`).
9. **`fragility` names a non-existent `valuation` dependency** (`cards.js:589`);
   `risk.flip_conditions` is computed and documented but never rendered.

### Backlog (consolidated)

| ID | Type | Pri | Section | Summary | Status |
|---|---|---|---|---|---|
| 01-A | BUG/DATA | **P0** | 01 | zero-coverage risk renders a confident GREEN | FIX IN PROGRESS |
| 01-B | BUG/UX | P1 | 01 | all-neutral tape reads GREEN | ready |
| 01-C | DATA | P1 | 01 | VIX `unknown` rendered "vol normal" / `None` | ready |
| 01-D | TOOLTIP | P1 | 01 | risk tooltip omits half the verdict logic | ready |
| 01-E | TOOLTIP | P1 | 01 | flip strings contradict their thresholds | ready |
| 01-F | TOOLTIP/DATA | P1 | 01 | false `valuation` dependency | ready |
| 00-A | ACCESSIBILITY | P1 | 00 | injected ⓘ inside `h2` pollutes heading name | ready |
| 00-E | ACCESSIBILITY | P1 | 00/08 | confirm modal: no focus trap / restore | ready |
| 08-P | ACCESSIBILITY | P1 | 08 | tag pills keyboard-inaccessible | track-only |
| 08-T | TEST | P1 | 08 | "news-row chips" stale spec selector | ready (test) |
| 04-A | DATA | P1 | 04 | breadth card label vs plotted metric contradiction | tracked |
| 04-B | DATA | P1 | 04 | indicators text vs breadth bars disagree (same name) | tracked |
| 07-A | DATA | P2 | 07 | column sort saved but never restored | tracked |
| 07-B | DATA | P2 | 07 | server column prefs write-only (never read) | tracked |
| 07-C | ACCESSIBILITY | P2 | 07 | star clear requires right-click | tracked |
| 07-D | ACCESSIBILITY | P2 | 07 | sortable `th` click-only; Columns button no `aria-expanded` | tracked |
| 07-E | TOOLTIP | P2 | 07 | `cards.js:580` self-contradicts persistence | tracked |
| 03-A | TOOLTIP | P1 | 03 | regime tooltip fails 3 of 5 points | tracked |
| 02-A | TOOLTIP | P2 | 02 | AI gauge: no on-card as-of | tracked |
| 05-A | DATA | P2 | 05 | rates shown in a "Price" column with no % unit | tracked |
| 06-A | TOOLTIP | P2 | 06 | 17 inline `title=`; none meet 5-point | tracked |

(Full detail, evidence and line refs live in the deep section files and, for
`INVENTORIED` sections, in this session's lane outputs.)

### Tracked TODOs — next session

- **Deep audit pending:** `07-portfolio` (needs runtime probes for 07-A/07-C/07-D),
  `04-indicators` (runtime chart/mobile), `05-market-quotes` (null/stale payloads),
  `03-regime`, `02-ai-sentiment`, and `06-bottleneck` editor/forms (light pass only).
- **Cross-section decisions:** serve-or-drop `/api/regime`; tolerant layout merge;
  delete dead `.section-refresh` scaffolding; de-duplicate `COOLDOWN_SECONDS`;
  timezone-aware `_to_iso`; unify null handling across market cards.
- **Tooltip convergence:** finish (b)→(a) across events/bottleneck/portfolio/
  shell; add a `setText`/live-update member to `attachTooltip`; add the
  as-of/freshness point to `CARD_TOOLTIPS`.
- **Test hygiene:** refresh the stale selectors (#3/#4) and the dash-layout
  fixture once FIX-00-C lands; add a modal focus-trap regression spec.

### Inherited work (labelled, from `ff9fc12`)

- No unresolved prior-art findings were newly surfaced; the `06-bottleneck`
  editor/forms area (`bottleneck.js:730+`) remains unreviewed by the earlier
  audit and is carried forward as a this-audit TODO, not a re-report.

---

## 14. Session log

| Date | Session | Work |
|---|---|---|
| 2026-09-26 | bootstrap | Created this index; verified test baseline (157/4/0); section map from recon; deep batch `00`/`01`/`08` dispatched |
| 2026-09-26 | audit | `00`, `01`, `08` deep-audited and committed; baseline verdicts recorded (3 stale specs, 1 real layout bug); `P0` risk fix dispatched |
