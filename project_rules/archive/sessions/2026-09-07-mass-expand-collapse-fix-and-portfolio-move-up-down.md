# 2026-09-07 — Mass expand/collapse fix + portfolio move up/down

User reported two issues on the Portfolio card: a bug ("Mass expand
and collapse does not work") and a feature ("Moving portfolio up and
down"). Investigated, designed, implemented, tested, committed.

## Bug: mass expand/collapse label was stuck

`static/js/portfolio.js:657-663` — the `.pf-toggle-all` click handler
updated the `expanded` set and called `renderBody()`, but never
called `renderHeaderControls()`. The bodies correctly toggled
collapsed/expanded, but the "▼ all" / "▲ all" label was stuck on
"▼ all" forever after the first click because the controls
container was never re-rendered. To the user the button looked
unresponsive because the only feedback surface (the label) never
changed.

Fix: one extra `renderHeaderControls()` call in the click handler.
The function is cheap (rebuilds a small div + re-attaches 2
handlers) and `allExpanded` is correctly recomputed from the post-
click `expanded` set, so the label flips to "▲ all" after expand
and back to "▼ all" after collapse.

## Feature: move portfolio up/down

New per-row `↑` / `↓` chevrons in each portfolio header (between
the pencil rename and the totals). The first row's `↑` and the
last row's `↓` render `disabled` so the boundary is visually
obvious. click → swap-with-neighbor → POST to
`/api/portfolios/reorder` → re-render so the new boundary disabled-
state takes effect.

State model: persist the order via the existing dict key order
in `data/portfolios.json`. Python's `json` and JS's `JSON` both
preserve the sequence; the frontend's `Object.values(portfolios)`
walks the new order without extra plumbing. No new schema field,
no migration. Considered adding a top-level `order: [pid, ...]`
field but rejected (it would be a second source of truth alongside
the dict key order, and would need migration for any existing
portfolios.json). Durable decision recorded in DECISIONS.md.

API: `POST /api/portfolios/reorder` body `{ order: [pid, ...] }`.
The new order must be a permutation of the current pids (no adds,
removes, duplicates). Empty order is allowed only when there are
zero portfolios. Server validates, rebuilds the dict, patches the
dashboard cache, returns `{ order: [...] }`. On 400 the frontend
surfaces the server's `detail` via alert.

Wired in both the `renderBody` path (full rebuild) and the
`_wirePortfolioHeader` path (targeted insert). `stopPropagation`
mirrors the delete / pencil behavior so clicking a chevron doesn't
collapse the portfolio. Defensive checks in `_movePortfolioBy`
bail silently on stale clicks (concurrent delete or disabled-
button race) and surface server errors via alert.

## Files

- `app/portfolio.py` — `reorder_portfolios(order)` (34 lines).
- `app/api.py` — `POST /api/portfolios/reorder` route (20 lines).
- `static/js/api.js` — `reorderPortfolios(order)` client (17 lines).
- `static/js/portfolio.js` — `buildPortfolioHTML(p, position)`,
  `_movePortfolioBy(pid, direction)`, chevron click handlers in
  `renderBody` + `_wirePortfolioHeader`, `renderPortfolioInsert`
  passes position, plus the one-line `renderHeaderControls()` call
  in the toggle-all handler.
- `static/style.css` — `.pf-move-up` / `.pf-move-down` rules
  (hover + disabled states, matches existing `.pf-caret` visual
  treatment).
- `tests/test_portfolio.py` — 10 reorder backend tests
  (swap, round-trip, data-preservation, rejects missing /
  duplicate / omitted / non-list / empty-when-non-empty inputs,
  reorder-then-delete no-corruption).
- `tests/frontend/portfolio-mass-toggle.spec.mjs` — 4 tests
  (label flips on expand, flips back on collapse, mixed state
  expands the missing one, label survives reload).
- `tests/frontend/portfolio-move.spec.mjs` — 7 tests
  (boundary disabled-state, up/down swap, stopPropagation, reload
  persistence, single-portfolio both-disabled, chained swaps).

## Verification

- `python -m pytest tests/`: **431 passed** in 50 s (up from 421 —
  the +10 reorder tests). No regressions.
- `npx playwright test`: **73 passed / 20 failed** in 14 s. 20
  failures match the pre-existing baseline (tooltip × 9 +
  shutdown-listener × 8 environmental + 3 audit-noted). My 11
  new tests (4 mass-toggle + 7 move) all pass.
- `python -c "from app import api"`: OK.
- `node -c static/js/portfolio.js`: no syntax errors.
- `node -c static/js/api.js`: no syntax errors.

## Decisions

Two new durable entries in `project_rules/DECISIONS.md`:
- "Portfolio reorder: dict key order, not a separate `order`
  field" — the design choice + the (small) caveat about JSON
  spec compliance.
- "Mass expand/collapse: renderHeaderControls() must follow
  renderBody()" — the lesson from the bug + the future-test rule.

## Commits

2 commits land the work (per the "one logical change per commit"
rule, even though both changes touched the same file):

- `d35431b fix(portfolio): mass expand/collapse label updates after click`
- `8b6a65e feat(portfolio): move portfolio up/down via per-row chevrons`

This session's docs commit lands third.

Working tree at session end: `data/events.json` has unstaged
scheduler timestamp updates (scheduler-owned, ignore per
project-rules). 2 feature commits + 1 docs commit. Static server
reaped at end of session; user's FastAPI server (PID 7604) left
running per the runbook's "never leave a server running for the
user" rule.
