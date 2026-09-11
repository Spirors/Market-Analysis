## 2026-09-11 — Portfolio holdings reorder persistence + per-section refresh cooldowns

**Summary:** Six commits across two parallel lanes. The Portfolio section's
holdings ▲/▼ reorder now persists to `data/portfolios.json` (was
session-only) and is greyed out when the view is in a column-header sort
(non-default order). The Portfolio and Breadth — AI proxies sections gain
per-section refresh cooldowns (15 min / 30 min) gated on the cached
`vintage` stamp; a refresh within the cooldown keeps the section's cached
data and surfaces a "cached Xm" badge + a "next refresh in N min" tooltip
on the global Refresh button.

### Backend lane (2 commits)

1. `9f6eac1` — `feat(portfolio): backend holdings reorder endpoint + tests`.
   New `app.portfolio.reorder_holdings(pid, order)` mirrors
   `reorder_portfolios`: validates that `order` is a permutation of the
   current non-cash holdings' symbols (no additions, removals, duplicates),
   mutates the holdings list in place, preserves the cash row at the end,
   `save_portfolios(state)` then `_patch_dashboard_cache(state)`. New
   `POST /api/portfolios/{pid}/holdings/reorder` endpoint maps
   `ValueError → 400` and `KeyError → 404`. 14 new backend tests (10 in
   `test_portfolio.py`: permutation/duplicate/missing-symbol/cash
   preservation/persistence; 4 in `test_api_contract.py`: round-trip,
   400, 404, cash preservation).

2. `5e00482` — `feat(refresh): backend per-section refresh cooldowns +
   tests`. New `app/config.py` constants:
   `PORTFOLIO_REFRESH_COOLDOWN_S = 900`, `BREADTH_AI_REFRESH_COOLDOWN_S
   = 1800`, `REFRESH_SECTION_COOLDOWNS = {"portfolios": 900,
   "indicators": 1800}` (the "breadth-ai" card reads `vintage.indicators`
   per `CARD_VINTAGE_KEY`, so the indicators cooldown drives the
   breadth-ai skip). `app.service.refresh_market()` loads the cached
   `data/dashboard.json` at the top, derives `_in_cooldown(vintage_key)`
   from each section's cached `vintage` stamp, and skips the indicators
   or portfolios computation when within cooldown (reuses the cached
   payload data + preserves the cached `vintage` stamp so the next
   cooldown check sees the same age). Unrelated sections (risk,
   bottleneck, ai_sentiment) still run. The returned payload gains a
   `cooldown_skip: list[str]` field, always present, `[]` when nothing
   skipped. 6 new tests in `tests/test_service_cooldown.py` (config
   constants, portfolio cooldown, indicators cooldown, outside cooldown,
   unrelated sections run, cold cache).

### Frontend lane (4 commits)

3. `4392797` — `feat(portfolio): frontend holdings reorder persistence`.
   New `static/js.api.reorderHoldings(pid, order)` (mirror of
   `reorderPortfolios`). `tickerTable.js:moveRow` now POSTs the new
   symbol order (cash rows filtered out) optimistically, reverts on
   error via `setStatus(msg, "bad")`. `portfolio.js` wires the new
   `onReorder` callback. 3 new Playwright tests (POST round-trip, revert
   on failure, cash-row omission from the POST body).

4. `b0e9789` — `fix(portfolio): grey-out ▲/▼ when not in default order`.
   `tickerTable.js:drawBody` adds a `reorderBlocked = sort.key !==
   "default"` condition: when true, all ▲/▼ buttons render with the
   `disabled` attribute + tooltip `"Reset to default order (↺) before
   reordering rows"`. `moveRow` gains a defensive `sort.key !== "default"`
   guard (defense in depth — the button is already disabled in the UI).
   3 new Playwright tests (disabled when sorted, re-enabled after ↺
   reset, no-op on force-click in non-default order).

5. `040c409` — `feat(refresh): cooldown tooltip + section age badges`.
   New `static/js.cards.applyCooldownBadge(section, data)` reads
   `data.cooldown_skip` + the section's `vintage[section]` stamp and
   renders a small `cached Xm` pill in the affected card's h2 (Portfolio
   uses `vintage.portfolios`; Breadth — AI proxies uses
   `vintage.indicators`). The pill carries a title tooltip `"Last
   refreshed X min ago — next refresh in N min"`. Cooldown constants
   (900s / 1800s) live in `cards.js` next to the badge code. New CSS
   rule `.cov-cooldown` (muted `--sub` colour, hairline border,
   `font-size: 9px`) added to `static/style.css` — separate from the
   existing `.cov-badge` to avoid semantic confusion (coverage vs data
   freshness). `static/js.main` adds hover/unhover wiring on
   `#refreshBtn`: on hover, the `title` is set to a live `"Refresh
   dashboard. Last refresh: X min ago. Next refresh available in: N
   min"` string; on unhover, restored to the static `"Refresh"`. 4 new
   Playwright tests in a new `refresh-cooldown.spec.mjs` (portfolio
   badge, breadth-ai badge, badge hidden when empty, refresh button
   tooltip). `mock-dashboard.mjs` extended with `cooldown_skip` +
   per-section vintage keys.

6. `1254bb7` — `docs(refresh): note cooldown + reorder behaviour in card
   tooltips`. `static/js.cards.CARD_TOOLTIPS["portfolio"].text` and
   `["breadth-ai"].text` gain one sentence each describing the
   refresh-cooldown behaviour. `portfolio.text` also notes that ▲/▼
   reorder now persists to `data/portfolios.json`.

### Verification

- `python -m pytest tests/test_service_cooldown.py tests/test_portfolio.py
  tests/test_api_contract.py` → **104 passed** (10 new portfolio + 4 new
  api_contract + 6 new service_cooldown + existing). 6.0s.
- `npx playwright test --config=tests/frontend/playwright.config.mjs
  tests/frontend/portfolio-holdings-reorder.spec.mjs
  tests/frontend/refresh-cooldown.spec.mjs` → **17 passed**. 6.4s.
- Pre-existing failures observed in the broader suite (NOT caused by
  this change):
  - `tests/test_service_coverage.py::test_recompute_ai_sentiment_filters_ai_only`
    — timing tolerance too tight (5s vs measured 12–14s).
  - `tests/test_portfolio_cache_sync.py` — pre-existing hang on the
    network-enrichment path; not addressed here (out of scope).
  - `tests/frontend/global-refresh.spec.mjs:63` "news rows carry region
    pill, source-weight badge, relevance chip" — `events.js` not
    modified by this change; failure pre-existed per the prior session's
    HANDOFF baseline (5 pre-existing failures documented).

### Files touched (16)

**Backend (7):** `app/api.py`, `app/portfolio.py`, `app/config.py`,
`app/service.py`, `tests/test_api_contract.py`, `tests/test_portfolio.py`,
`tests/test_service_cooldown.py` (new).

**Frontend (9):** `static/js/api.js`, `static/js/tickerTable.js`,
`static/js/portfolio.js`, `static/js/cards.js`, `static/js/main.js`,
`static/style.css`, `tests/frontend/portfolio-holdings-reorder.spec.mjs`,
`tests/frontend/refresh-cooldown.spec.mjs` (new),
`tests/frontend/mock-dashboard.mjs`.

### Operational notes

Both lanes ran in parallel via the Background Job Board. No
agent-spawned servers were left running. `data/events.json` was NOT
modified by this session (scheduler-owned per `RUNBOOK.md` §"Commit
conventions").

### Decision pointers

See `project_rules/DECISIONS.md` →
- "Portfolio holdings reorder persistence — backend + frontend (2026-09-11)"
- "Per-section refresh cooldowns — Portfolio 15 min, Breadth — AI 30 min (2026-09-11)"

### Archive

Full text in
`archive/sessions/2026-09-11-portfolio-reorder-persistence-refresh-cooldowns.md`.
