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
| `00-shell-and-tooltips.md` | header, `#bands`, reorder, `#confirmOverlay`, `#tagPopover`, `tooltip.js`, `CARD_TOOLTIPS` | `main.js`, `layout.js`, `tooltip.js`, `cards.js:538-610` | `/api/refresh`, `/api/meta` | INVENTORIED |
| `01-risk.md` | `risk`, `fragility` | `cards.js:15` | `/api/dashboard` → `risk` | INVENTORIED |
| `02-ai-sentiment.md` | `ai-sentiment` | `cards.js:172` | `/api/dashboard` → `ai_sentiment` | INVENTORIED |
| `03-regime.md` | `regime` | `cards.js:100` | `/api/dashboard` → `regime` | INVENTORIED |
| `04-indicators.md` | `indicators`, `breadth`, `breadth-ai` | `cards.js:150`, `:419`, `:423` | `/api/dashboard` → `indicators` | INVENTORIED |
| `05-market-quotes.md` | `indices`, `commodities`, `rates` | `cards.js:239`, `:273`, `:689` | `/api/dashboard` → `market` | INVENTORIED |
| `06-bottleneck.md` | `bottleneck` | `bottleneck.js` | `/api/bottleneck/*` | INVENTORIED |
| `07-portfolio.md` | `portfolio` | `portfolio.js`, `tickerTable.js` | `/api/portfolios*` | INVENTORIED |
| `08-events.md` | `events` | `events.js` | `/api/events*` | INVENTORIED |

A dedicated `<section>.md` file is created only once that section receives a
meaningful (deep) audit. Until then its shallow status lives here, in this table.

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

**This session's deep batch:** `00`, `01`, `08`. All others end the session as
`INVENTORIED` with explicit tracked TODOs here so the next session resumes
without reconstructing context.

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

This session's `00`/`01`/`08` audits are **static-first** (no runtime probes
unless a lane flags one).

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

Unrelated bugs discovered outside the active section are recorded here in the
backlog, not chased mid-section.

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
  labelled "prior art (`ff9fc12`)". Unresolved prior tasks may be surfaced as
  clearly labelled **inherited work**.

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
| `00-shell-and-tooltips` | INVENTORIED | deep audit in progress (this session) |
| `01-risk` | INVENTORIED | deep audit in progress (this session) |
| `02-ai-sentiment` | INVENTORIED | tracked TODO: deep audit |
| `03-regime` | INVENTORIED | tracked TODO: deep audit |
| `04-indicators` | INVENTORIED | tracked TODO: deep audit |
| `05-market-quotes` | INVENTORIED | tracked TODO: deep audit |
| `06-bottleneck` | INVENTORIED | light pass only; prior art `ff9fc12` |
| `07-portfolio` | INVENTORIED | tracked TODO: deep audit |
| `08-events` | INVENTORIED | deep audit in progress (this session) |

---

## 13. Cross-section findings and backlog

_Cross-section findings and the consolidated P0–P3 backlog are accumulated here
as lanes report. Entries are added only from reconciled lane results._

### Tracked TODOs

- Deep audit pending: `02-ai-sentiment`, `03-regime`, `04-indicators`,
  `05-market-quotes`, `07-portfolio`.
- Verify suspected dead endpoint `GET /api/regime` (`app/api.py:445`) — defined
  but apparently never called by the frontend.

### Inherited work (labelled)

_None yet — see §9 for the `06-bottleneck` prior-art rule._

---

## 14. Session log

| Date | Session | Work |
|---|---|---|
| 2026-09-26 | bootstrap | Created this index; verified test baseline (157/4/0); section map from recon; deep batch `00`/`01`/`08` dispatched |
