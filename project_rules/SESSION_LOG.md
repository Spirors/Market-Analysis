# Session Log

Append-only. Newest entry at the bottom. This file is git-tracked -- unlike
`data/logs/summary-YYYY-MM-DD.md`, which is gitignored and local-only per
`AGENTS.md`. Use this file for anything that needs to survive across
machines or a fresh checkout; keep using the existing `data/logs/` changelog
for its original local-daily-changelog purpose.

> Hybrid layout: the **latest entry is in full** (so the session-start
> read per AGENTS.md is one click deep), **older entries are pointers**
> with full text in `archive/sessions/<slug>.md` (one file per session).
> Once this file exceeds `{{SESSION_LOG_ROTATION_ENTRIES}}` entries
> (currently 5 for this project; updated 2026-09-08), the oldest pointer
> is dropped — the archive file is the source of truth.

---

## 2026-09-08 — feat(bottleneck): up/down reorder + rename pencil

Bottleneck section gains interactive controls mirroring the Portfolio
section's established patterns:

**Backend:**
- New `app/bottleneck_prefs.py` — persistence layer for user overrides
  (order + renames) in `data/bottleneck_prefs.json`. The canonical
  `BOTTLENECK_CATEGORIES` constant is never mutated; prefs are applied
  at serve time.
- `app/bottleneck.py` — `bottleneck_read()` now calls `_apply_prefs()`
  which layers user order + renames on top of the ranked output.
  `category_original` field added to each category dict so the frontend
  can track canonical names after renames.
- 2 new API endpoints in `app/api.py`: `POST /api/bottleneck/categories/reorder`
  and `PUT /api/bottleneck/categories/{name}?new_name=...`.
- Cache-patching pattern mirrors `portfolio._patch_dashboard_cache()`.

**Frontend:**
- `static/js/cards.js` — `renderBottleneck()` enhanced with rename
  pencil (✎), move-up/down (↑/↓) buttons, inline rename input
  (`_startEditForCategory`), and reorder helper (`_moveBottleneckCategoryBy`).
  Module-level `bottleneckData` tracks categories with canonical names.
- `static/js/api.js` — 2 new fetch helpers: `reorderBottleneckCategories`
  and `renameBottleneckCategory`.
- `static/style.css` — `.bn-rename-btn`, `.bn-move-up`, `.bn-move-down`,
  `.bn-name-input` styles mirroring the portfolio `.pf-*` counterparts.

**Tests:**
- `tests/test_bottleneck_prefs.py` — 18 backend tests covering prefs
  persistence, reorder validation, rename validation, `bottleneck_read`
  integration, and API endpoint contracts.
- `tests/frontend/bottleneck-move.spec.mjs` — 7 Playwright tests for
  reorder (boundary state, swap, stopPropagation, reload persistence,
  single-category, chained swaps).
- `tests/frontend/bottleneck-rename.spec.mjs` — 6 Playwright tests for
  rename (inline input, Enter saves, Escape cancels, blur empty restores,
  stopPropagation, reload).

**Docs:**
- `project_rules/API.md` — 2 new endpoints documented.
- `project_rules/DECISIONS.md` — decision about prefs storage location
  and rationale.

### Files changed

- `app/bottleneck_prefs.py` (new)
- `app/bottleneck.py` (modified — `_apply_prefs`, `category_original` field)
- `app/api.py` (modified — 2 new endpoints)
- `static/js/cards.js` (modified — enhanced `renderBottleneck`)
- `static/js/api.js` (modified — 2 new fetch helpers)
- `static/style.css` (modified — new control styles)
- `tests/test_bottleneck_prefs.py` (new)
- `tests/frontend/bottleneck-move.spec.mjs` (new)
- `tests/frontend/bottleneck-rename.spec.mjs` (new)
- `project_rules/API.md` (modified)
- `project_rules/HANDOFF.md` (modified)
- `project_rules/SESSION_LOG.md` (this entry)
- `project_rules/DECISIONS.md` (modified)
- `project_rules/ROADMAP.md` (modified)

---

## 2026-09-08 — Test isolation: autouse `tests/conftest.py` redirects every user-data path

**Problem.** Test isolation was a per-test responsibility. 18 of 23
test files had no isolation setup, and the module-level path
constants (`PORTFOLIOS_PATH = config.DATA_DIR / "portfolios.json"`
at `app/portfolio.py:95`, etc.) are evaluated at import time — so
patching `config.DATA_DIR` alone does NOT update the bound name. A
test that forgot to patch the right layer would silently write to
the real `data/portfolios.json`: no exception, no warning, the test
passes, the user loses their portfolios.

**Decision.** Add a new Core rule "Test isolation" to
`.opencode/skills/project-rules/SKILL.md` and enforce it with an
autouse pytest fixture in a new `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def _isolate_data_files(monkeypatch, tmp_path):
    monkeypatch.setattr(portfolio, "PORTFOLIOS_PATH", tmp_path / "portfolios.json")
    monkeypatch.setattr(bottleneck_prefs, "_PREFS_PATH", tmp_path / "bottleneck_prefs.json")
    monkeypatch.setattr(store, "SUPPRESSED_PATH", tmp_path / "suppressed_sources.json")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "REGIME_DIR", tmp_path / "regime")
    monkeypatch.setattr(config, "EVENTS_PATH", tmp_path / "events.json")
    monkeypatch.setattr(config, "ANALYSIS_DB_PATH", tmp_path / "analysis.db")
    monkeypatch.setattr(changelog, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(store, "_READY", False)
    monkeypatch.setattr(store, "_analysis_repo", None)
    yield
```

pytest applies autouse fixtures before per-test fixtures, so tests
that already declare `tmp_portfolios` / `tmp_store` / etc. override the
autouse's values — the autouse is the safety net that catches tests
that forget to set up isolation.

### Files

- `tests/conftest.py` (new — autouse `_isolate_data_files` fixture)
- `.opencode/skills/project-rules/SKILL.md` (new Core rule "Test isolation")
- `project_rules/TESTING.md` (new "Test isolation — never touch the
  user's data" section explaining the pattern + how to add a new path)
- `AGENTS.md` (added "Test isolation" to the Hard rules pointers list)
- `project_rules/DECISIONS.md` (new pointer entry)
- `project_rules/archive/decisions/test-isolation-autouse-conftest-py-redirects-every-user-data-path-2026-09-08.md`
  (new — full rationale, mistakes-to-avoid, verification)

### Verification

- `python -m pytest tests/test_portfolio.py tests/test_bottleneck_prefs.py tests/test_api_contract.py`:
  **101 passed** in ~62 s.
- `python -m pytest tests/test_validation.py tests/test_changelog.py tests/test_lifecycle.py tests/test_store.py tests/test_portfolio_cache_sync.py tests/test_dashboard_equivalence.py tests/test_lockfile.py`:
  exit=0.
- `python -m pytest tests/ -k "not thirteenf and not service_coverage"`:
  exit=0 (full suite minus the two known-skip files per `AGENTS.md`).
- Pre-existing per-test fixtures (`tmp_portfolios` in
  `tests/test_portfolio.py:9-12`, `tmp_store` in
  `tests/test_api_contract.py:29-35`) override the autouse without
  conflict; their explicit values take precedence as expected.

### Notes for the next session

- Module-level path constants are bound at import time — the autouse
  must patch each importing module's bound name separately, NOT just
  `config.DATA_DIR`. This is the failure mode that motivated the rule.
- Read-only assets (`static/`, `archive/`) are intentionally NOT
  redirected — only state a test could mutate.
- When adding a new user-data path, add the monkeypatch line to
  `_isolate_data_files` in the same change. The fixture is the
  contract; an unpatched new path is a silent regression.

---

## 2026-09-07 — P0 add/delete latency fix shipped

**Summary:** Applied the P0 fix sketched in `docs/logs/audit-2026-09-07.md`. Two

**Archive:** Full text in `archive/sessions/2026-09-07-p0-add-delete-latency-fix-shipped.md`.

---

## 2026-09-07 — Earnings date column fix (user-reported follow-up to P0)

**Summary:** After the P0 perf fix shipped, the user reported that the portfolio

**Archive:** Full text in `archive/sessions/2026-09-07-earnings-date-column-fix-user-reported-follow-up-to-p0.md`.

---

## 2026-09-07 — Audit follow-up closure: P3/P4/P5/P6 (3 commits)

**Summary:** Closed the remaining audit-2026-09-07 follow-ups. P0 (perf) and the

**Archive:** Full text in `archive/sessions/2026-09-07-audit-follow-up-closure-p3-p4-p5-p6-3-commits.md`.

---

## 2026-09-07 — Front-end nuclear renderBody fix (audit-2026-09-07 P0 follow-up)

**Summary:** User reported that add/delete holding felt fast but add/delete/rename

**Archive:** Full text in `archive/sessions/2026-09-07-front-end-nuclear-renderbody-fix-audit-2026-09-07-p0-follow-up.md`.

---

## 2026-09-07 — Mass expand/collapse fix + portfolio move up/down

User reported two issues on the Portfolio card: a bug ("Mass expand
and collapse does not work") and a feature ("Moving portfolio up and
down"). Investigated, designed, implemented, tested, committed.

### Bug: mass expand/collapse label was stuck

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

### Feature: move portfolio up/down

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

### Files

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

### Verification

- `python -m pytest tests/`: **431 passed** in 50 s (up from 421 —
  the +10 reorder tests). No regressions.
- `npx playwright test`: **73 passed / 20 failed** in 14 s. 20
  failures match the pre-existing baseline (tooltip × 9 +
  shutdown-listener × 8 environmental + 3 audit-noted). My 11
  new tests (4 mass-toggle + 7 move) all pass.
- `python -c "from app import api"`: OK.
- `node -c static/js/portfolio.js`: no syntax errors.
- `node -c static/js/api.js`: no syntax errors.

### Decisions

Two new durable entries in `project_rules/DECISIONS.md`:
- "Portfolio reorder: dict key order, not a separate `order`
  field" — the design choice + the (small) caveat about JSON
  spec compliance.
- "Mass expand/collapse: renderHeaderControls() must follow
  renderBody()" — the lesson from the bug + the future-test rule.

### Commits

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


