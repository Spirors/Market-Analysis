# Market Analysis — Per-Section Audit

**This file is the canonical audit state and the resume point.** The wiki
(`Market-Analysis-Wiki/wiki/hot.md` and `index.md`) only *points here*. Never
duplicate status tables, findings, priorities, or TODOs into the wiki — that
would create two competing sources of truth.

An active, multi-session audit of every user-facing section of the app. The goal
is a per-section picture of *what the section does*, *how its tooltips read*,
and *what is broken or improvable* — with small, safe fixes applied inline and
everything larger tracked for a later session.

**Companion:** `docs/audit/wiki.md` — the wiki audit (is the vault a retrievable
memory, or just organized Markdown?). Separate artifact, same taxonomy.

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
| `04-indicators.md` | `indicators`, `breadth`, `breadth-ai` | `cards.js:150`, `:419`, `:423` | `/api/dashboard` → `indicators` | FIXED-PARTIAL |
| `05-market-quotes.md` | `indices`, `commodities`, `rates` | `cards.js:239`, `:273`, `:689` | `/api/dashboard` → `market` | INVENTORIED |
| `06-bottleneck.md` | `bottleneck` | `bottleneck.js` | `/api/bottleneck/*` | INVENTORIED (light pass) |
| `07-portfolio.md` | `portfolio` | `portfolio.js`, `tickerTable.js` | `/api/portfolios*` | FIXED-PARTIAL |
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
- **Session-start baseline:** 161 tests — **157 passed / 4 failed / 0 skipped**
- **Current baseline (2026-09-27):** 169 tests — **169 passed / 0 failed**.
  FIX-08-T repaired the stale "news-row chips" selector (157/4 → 158/3); pass 1
  added 2 focused specs, FIX-04-A/B added 4 (`breadth-labels.spec.mjs`),
  FIX-05-A added 2 (`rates-yield-labels.spec.mjs`), and the three remaining stale
  fixtures were corrected in the test-hygiene commit `99907a7`. **No baseline
  failures remain.**
- **Verified:** 2026-09-27 (full Playwright run on the clean tree, `169 passed /
  0 failed`, 1.1m)

**All four baseline failures were stale specs — none was a product regression.**
Every one is now repaired, and future sessions should treat a reappearance as a
genuine regression:

| # | Spec | Failure | Repair |
|---|---|---|---|
| 1 | `global-refresh.spec.mjs:62` | "news rows carry region pill" selector lagged the region move | FIX-08-T `854d01c` |
| 2 | `dash-layout-survives-reload.spec.mjs:115` | in-page mirror accepted only a layout containing portfolio | test hygiene `99907a7` |
| 3 | `dash-layout-survives-reload.spec.mjs:147` | mirrored order did not persist after reload | test hygiene `99907a7` |
| 4 | `portfolio-star-scope.spec.mjs:146` | reload test assumed collapsed portfolios | test hygiene `99907a7` |

### Baseline failure verdicts (from this audit)

- **"news-row chips" → STALE TEST, now REPAIRED.** The refactor moved region from
  `.tl-meta` to the tag line; the pill renders (and is editable) as
  `.tl-tags .pill.region` (`events.js:391-396`). Selector updated (FIX-08-T,
  `854d01c`) — the spec passes. See `08-events.md`.
- **"portfolio-star-scope" → STALE TEST, not a product bug.** Composite
  per-portfolio keys are implemented (`watchColors.js:58-73`,
  `portfolio.js:543-551,800-816`). `pfExpanded` persists, so both portfolios are
  already **expanded** after reload; the spec's two caret clicks then *collapse*
  them and `renderBody` skips holdings tables (`portfolio.js:304-309`), leaving
  no `.earn-star`. Subtests 1 & 3 start collapsed and pass. **REPAIRED**
  (`99907a7`): an `expandAllPortfolios` normaliser now leaves already-expanded
  portfolios alone, so the independence assertion actually exercises both rows.
- **"dash-layout" ×2 → stale fixture over a REAL product bug.** Both fixtures
  include a removed card `"earnings"` absent from `CARD_BAND`, and the spec
  re-implements `applyLayoutOnLoad` in-page with a stale mirrored `CARD_BAND`, so
  it never exercises the real `layout.js`. The product-side over-strict rule is
  fixed (FIX-00-C, `472de74`); the mirrored `CARD_BAND` and the tolerant merge
  were refreshed in `99907a7` — not a regression.

> Drift history: the 2026-09-25 wiki log quoted 141/4; at session start the tree
> was 157/4 (more passing tests, same failing set); after the first fix pass it
> was 158/3, then 160/3, and after the test-hygiene repairs it is **167/0**. If
> the baseline changes again, update this section with the newly verified numbers
> rather than assuming the old count holds.

---

## 11. Commit conventions

- `docs(audit): bootstrap section audit` — this file.
- `docs(audit): <section>` — one commit per completed/deeply-audited section file.
- `fix(<scope>): <description>` / `feat(<scope>): <description>` — applied fixes,
  **never** bundled into a `docs(audit)` commit. Each carries its focused test
  where practical.
- **Wiki sync rule (user decision, 2026-09-26):** the wiki is updated **as each
  README task is tackled**, not batched up front. This file stays the canonical
  audit state; the wiki carries discoverability pointers and durable decisions
  only.

---

## 12. Status board

| Section | Status | Notes |
|---|---|---|
| `00-shell-and-tooltips` | FIXED-PARTIAL | FIX-00-A..I landed (00-G deps AT, 00-H/I dead-code + cooldown); track-only: remaining `CARD_TOOLTIPS` as-of |
| `01-risk` | FIXED-PARTIAL | 1× P0 + 2 backend + 5 presentation + FIX-01-E landed; track-only items remain |
| `02-ai-sentiment` | FIXED-PARTIAL | 02-A + 02-B **FIXED**; deep audit pending |
| `03-regime` | INVENTORIED | 03-A (tooltip) **FIXED**; deep audit still pending |
| `04-indicators` | FIXED-PARTIAL | 04-A/04-B (breadth labels) **FIXED**; `breadth_sectors` render-or-drop open |
| `05-market-quotes` | FIXED-PARTIAL | 05-A (rates column unit) **FIXED**; deep audit still pending |
| `06-bottleneck` | INVENTORIED | 06-A **DEFERRED** (user); light pass done; prior art `ff9fc12` |
| `07-portfolio` | FIXED-PARTIAL | 07-A **FIXED**; 07-C/07-D in progress; 07-B approved (delete server prefs); 07-E ready |
| `08-events` | FIXED-PARTIAL | 7 fixes landed incl. 08-Q (destructive Enter); chip focus-loss + timezone in progress |

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

### Fixed in this audit (26 fixes)

`01-A` `bb59e2f` · `01-B` `b7521d6` · `01-C` `19a33d4` · `01-D` `27c69fc` ·
`01-F` `2c6abf0` · `01-G` `c17df15` · `01-H` `4bfbee5` · `01-I` `ea3dfd7` ·
`01-E` `5b00879` ·
`00-A` `0e9d2bf` · `00-C` `472de74` · `00-D` `e0bd9db` · `00-E` `6b1ae3b` ·
`00-F` `6bd6e53` ·
`08-A` `a143f11` · `08-B` `c883c3c` · `08-C` `82fd50e` · `08-P` `8fbc301` ·
`08-T` `854d01c` · `03-A` `372ffd3` · `04-A`+`04-B` `5bf3b1f` · `05-A` `4fbb73e` ·
`00-B` `f4904ae` · `07-A` `6fb2622` · `02-A` `a00edac`.

Plus a test-hygiene commit `99907a7` (the three stale baseline specs).

The `P0` fix (`01-A`) and its two backend siblings altered an existing
green-path test; they landed with their test, and the frontend suite stayed at
157/4 through them. FIX-08-T later moved it to 158/3; the four fixes of the
second pass added 2 specs, giving **160/3** (see §10).

### Open backlog

| ID | Type | Pri | Section | Summary | Status |
|---|---|---|---|---|---|
| 01-E | TOOLTIP | P1 | 01 | flip strings contradict their thresholds | **FIXED** `5b00879` |
| 00-D | ARCHITECTURE | P2 | 00 | `attachTooltip` has no live-text API | **FIXED** `e0bd9db` |
| 00-G | ACCESSIBILITY | P2 | 00 | tooltip deps/data-source hidden from AT (`tooltip.js:42`) | **FIXED** `694f2bb` |
| 00-H | ARCHITECTURE | P2 | 00 | dead `.section-refresh` scaffolding; `refreshSection()` unreachable | **FIXED** `dbb8898` |
| 00-I | UX | P2 | 00 | duplicated `COOLDOWN_SECONDS`; cooldown label presented a max as a promise | **FIXED** `dbb8898` |
| 00-B | UX | P2 | 00 | refresh errors overwrite `#riskBody` | **FIXED** `f4904ae` |
| 08-P | ACCESSIBILITY | P1 | 08 | tag pills keyboard-inaccessible | **FIXED** `8fbc301` |
| 08-Q | BUG | P1 | 08 | Enter on the focused Cancel button runs the destructive confirm (deletes the event) | **FIXED** `aaebdb0` |
| 04-A | DATA | P1 | 04 | breadth card label vs plotted metric contradiction | **FIXED** `5bf3b1f` |
| 04-B | DATA | P1 | 04 | indicators text vs breadth bars disagree (same name) | **FIXED** `5bf3b1f` |
| 04-C | DATA | P3 | 04 | `breadth_sectors`/`breadth_indices` computed + served, never rendered | **FIXED** `7560635` |
| 03-A | TOOLTIP | P1 | 03 | regime tooltip fails 3 of 5 points | **FIXED** `372ffd3` |
| 07-A | DATA | P2 | 07 | column sort saved but never restored | **FIXED** `6fb2622` |
| 07-B | DATA | P2 | 07 | server column prefs write-only (never read) | **APPROVED**: localStorage wins, delete the server prefs (user, 2026-09-27) — in progress |
| 07-C | ACCESSIBILITY | P2 | 07 | star clear requires right-click | **APPROVED**: keep right-click, document the keyboard route (user, 2026-09-27) — in progress |
| 07-D | ACCESSIBILITY | P2 | 07 | sortable `th` click-only; Columns button no `aria-expanded` | in progress |
| 07-E | TOOLTIP | P2 | 07 | `cards.js:589` self-contradicts persistence | ready |
| 02-A | TOOLTIP | P2 | 02 | AI gauge: no on-card as-of | **FIXED** `a00edac` |
| 02-B | DATA | P2 | 02 | served `ai_sentiment.as_of` is always null while the cached copy has it (cache ≠ wire) | **FIXED** `80d9bd1` |
| 05-A | DATA | P2 | 05 | rates shown in a "Price" column with no % unit | **FIXED** `4fbb73e` |
| 06-A | TOOLTIP | P2 | 06 | 17 inline `title=`; none meet 5-point | **DEFERRED** (user, 2026-09-27) — needs a DOM/design pass; recon in the §14 notes |

(Full detail, evidence and line refs live in the deep section files and, for
`INVENTORIED` sections, in this session's lane outputs.)

### Tracked TODOs — next session

- **Deep audit done / remaining:** `04-indicators` and `07-portfolio` are deep-audited
  (section files exist). Still pending: `03-regime`, `02-ai-sentiment`,
  `05-market-quotes` (null/stale payloads), and `06-bottleneck` editor/forms
  (light pass only — 06-A is user-DEFERRED).
- **Cross-section decisions — all taken 2026-09-27:**
  - `/api/regime` → **DONE** `5a740ea` (route dropped, contract tests retargeted at `regime.get_regime()`).
  - Shell dead code → **delete** the unreachable `.section-refresh` wiring,
    **de-duplicate** `COOLDOWN_SECONDS`, and make the header cooldown label
    honest ("up to N min").
  - Timezone → **fix end-to-end** (in progress): `_to_iso` emits UTC with `Z`;
    parse and compare consistently.
  - Null handling → **always show the row with `—`** (never silently drop) and
    correct the tooltip copy.
  - `risk.flip_conditions` → **render** it under the thesis; refresh the stale
    `risk-divergence` SKILL.md (in progress).
  - Modal focus trap → **add** the missing regression spec.
  - `06-A` (bottleneck inline tooltips) → stays **DEFERRED** (needs a DOM/design
    pass).
  *(Tolerant layout merge is done — FIX-00-C.)*
- **Tooltip convergence:** finish (b)→(a) across events/bottleneck/portfolio/
  shell; add the as-of/freshness point to the remaining `CARD_TOOLTIPS` entries.
  *(The `attachTooltip` live-text member landed — FIX-00-D — and the Refresh
  button is now on the unified surface; the regime entry meets all 5 points —
  FIX-03-A.)*
- **Test hygiene:** *(`portfolio-star-scope` and both `dash-layout` mirrors are
  repaired — `99907a7`; the news-row-chips selector — FIX-08-T.)* **Still open:**
  add a modal focus-trap regression spec (`FIX-00-E` shipped without one).

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
| 2026-09-26 | fixes | 16 fix commits landed across `00`/`01`/`08`; frontend baseline 157/4 → **158/3**; remaining 6 sections `INVENTORIED` with the §13 backlog |
| 2026-09-26 | wiki | Separate wiki audit (`docs/audit/wiki.md`): retrieval index was never provisioned — built (156 chunks) and probe-tested (8/12 top-1); hub-page noise + freshness gap found |
| 2026-09-26 | wiki decisions | Closed the 3 parked wiki decisions (`wiki.md` §6): session end now owns the retrieval-index rebuild (`AGENTS.md` + `session-memory-protocol.md`), corpus noise accepted + documented, rerank stays lexical-only. Vault decision page + `index`/`log`/`hot`/`overview` updated in one `save` transaction |
| 2026-09-26 | backlog pass 1 | FIX-01-E `5b00879`, FIX-00-D `e0bd9db`, FIX-08-P `8fbc301`, FIX-03-A `372ffd3` landed (deep-audit order §4). Frontend suite re-verified **160 passed / 3 failed** (163 tests; the 3 are the known stale specs); risk focused tests 15 passed / 30 `-k "risk or regime"`. Retargeted the `refresh-cooldown` assertion rather than weakening it |
| 2026-09-26 | backlog pass 2 | `04-indicators` deep recon (`exp-1`) + FIX-04-A/FIX-04-B `5bf3b1f`: the breadth card headline/tooltips/fallback claimed the aggregate share while the chart plots per-symbol distance-from-MA; root cause is aggregation, not universe (the audit's hypothesis). Section file `04-indicators.md` created; labels now guarded by a new spec |
| 2026-09-27 | test hygiene | Repaired the 3 stale baseline fixtures `99907a7` (dash-layout mirror stale `CARD_BAND`/guard/removed id; star-scope expansion assumption). No `expect()` line edited. **Suite now 167 passed / 0 failed** — the audit's baseline is fully green |
| 2026-09-27 | backlog pass 3 | FIX-05-A `4fbb73e`: the Rates card labelled percent yields under a bare "Price" header; `quotesTable`'s value header is now parameterised (`Yield (%)` for rates only). Suite **169 passed / 0 failed** |
| 2026-09-27 | pass 5 | Landed: 02-B `80d9bd1`, 04-C `7560635`, 00-G `694f2bb`, 00-H/I `dbb8898`, 08-Q `aaebdb0` (destructive Enter on Cancel), /api/regime `5a740ea`, modal focus-trap spec `749d24e`. New P1 found by the spec lane: Enter on Cancel confirmed a delete |
| 2026-09-27 | decisions (11) | User decided: 02-B thread `as_of`; drop `/api/regime`; shell dead-code cleanup + honest cooldown label; fix timezone ISO end-to-end; null policy = always show `—`; render `flip_conditions` + refresh risk SKILL.md; drop `breadth_sectors`/`indices`; add modal focus-trap spec; deep-audit 05 + 03; 06-A stays deferred; deps AT-visibility only |
| 2026-09-27 | decisions + pass 4 | User decisions: 00-B header status banner; 07-B localStorage wins (delete server prefs); 07-C document-only; 06-A deferred. Landed: FIX-00-B `f4904ae`, FIX-07-A `6fb2622`, FIX-02-A `a00edac`. Suite **173 passed / 0 failed**. Deep recon completed for `07-portfolio` (section file created) and `02`/`06`; new finding 02-B (null `ai_sentiment.as_of` on the wire) |
