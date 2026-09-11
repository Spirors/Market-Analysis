# Per-section refresh cooldowns — Portfolio 15 min, Breadth — AI 30 min (2026-09-11)

## Problem

The Portfolio and Breadth — AI proxies sections were both fetching
fresh data on every click of the global `#refreshBtn`. The Portfolio
section's enrichment (`enrich_portfolios`) does up to N+1 HTTP calls
(one bulk history + one `Ticker.info` per unique symbol). With ~10
holdings that's 10–15 s of yfinance traffic on every refresh click.
The Breadth — AI proxies section's `indicators.breadth_ai` depends
on per-cohort histories; a click flood wastes the user's yfinance
rate-limit budget and adds nothing the user can act on within the
15-min / 30-min windows the data is structurally stable in.

The user asked: "the refresh button should only trigger a fetch when
the last refresh is >= 15 min ago for Portfolio and >= 30 min ago for
Breadth — AI proxies".

## Decision

Three coordinated commits (one backend, two frontend):

1. **`5e00482` — `feat(refresh): backend per-section refresh cooldowns + tests`**
   New `app/config.py` constants:
   - `PORTFOLIO_REFRESH_COOLDOWN_S = 15 * 60  # 15 minutes`
   - `BREADTH_AI_REFRESH_COOLDOWN_S = 30 * 60  # 30 minutes`
   - `REFRESH_SECTION_COOLDOWNS: dict[str, int] = {"portfolios":
     900, "indicators": 1800}` — keyed by **vintage key** (the key
     in `data["vintage"]`), not by card key. The mapping
     `breadth-ai` card → `vintage["indicators"]` follows the
     existing `CARD_VINTAGE_KEY` convention in `static/js.cards`
     (the Breadth — AI proxies card displays the indicators
     section's vintage stamp).

   `app.service.refresh_market()` modified to gate sections:
   - At the top, load `cached = store.load_json(config.DATA_DIR /
     "dashboard.json") or {}` and derive `cached_vintage`.
   - `_in_cooldown(vintage_key)` parses `cached_vintage[vintage_key]`
     as ISO and returns `now - parsed < REFRESH_SECTION_COOLDOWNS.get(key, 0)`.
   - **Indicators branch**: when `_in_cooldown("indicators")` is True,
     reuse `cached["indicators"]` and copy `cached_vintage["indicators"]`
     into the new `vintage["indicators"]`. Append `"breadth_ai"` to
     `skipped`.
   - **Portfolios branch**: when `_in_cooldown("portfolios")` is True,
     reuse `cached["portfolios"]` and copy `cached_vintage["portfolios"]`
     into the new `vintage["portfolios"]`. Append `"portfolio"` to
     `skipped`.
   - The market snapshot (`market.build_market_snapshot`) ALWAYS runs
     — risk, bottleneck, ai_sentiment, indices, rates, commodities
     all need it. Only indicators / portfolios computations are
     skippable.
   - Result gains `"cooldown_skip": skipped` field (always present,
     `[]` when nothing skipped).

2. **`040c409` — `feat(refresh): cooldown tooltip + section age badges`**
   - `static/js.cards.applyCooldownBadge(section, data)` reads
     `data.cooldown_skip` + the section's `vintage[section]` stamp and
     renders a small `<span class="pill neutral cov-cooldown">cached Xm</span>`
     pill in the affected card's h2 (Portfolio uses `vintage.portfolios`;
     Breadth — AI proxies uses `vintage.indicators`).
   - The pill carries a `title` tooltip `"Last refreshed X min ago —
     next refresh in N min"` (N = max(0, ceil(cooldown - elapsed)) / 60).
   - Cooldown constants (900 / 1800) live in `cards.js` next to the
     badge code. **Intentional duplication** with `app.config` — the
     two are independent code paths (server gate vs client tooltip).
     Any change to one must change the other; the test isolation
     fixture does not help here because the constants are not user-data.
   - New CSS rule `.cov-cooldown` (muted `--sub` colour, hairline
     border, `font-size: 9px`) in `static/style.css`. Separate from
     `.cov-badge` to avoid semantic confusion (coverage = "how many
     data sources are live"; cooldown = "how fresh is the data").
   - `static/js.main` adds hover/unhover wiring on `#refreshBtn`:
     on hover, `title` is set to `"Refresh dashboard. Last refresh:
     X min ago. Next refresh available in: N min"` (X from
     `dashboardData.as_of`; N = MAX across all cooldowned sections,
     so the "next refresh" is when ALL sections can move forward
     together); on unhover, restored to static `"Refresh"`.

3. **`1254bb7` — `docs(refresh): note cooldown + reorder behaviour in card tooltips`**
   `static/js.cards.CARD_TOOLTIPS["portfolio"].text` and
   `["breadth-ai"].text` gain one sentence each describing the
   refresh-cooldown behaviour. `portfolio.text` also notes that ▲/▼
   reorder now persists to `data/portfolios.json` (cross-link to
   the portfolio reorder persistence decision).

## Rationale

- **Why reuse the existing `vintage` dict instead of a separate
  `data/refresh_state.json`:** the cached dashboard payload already
  carries `vintage: dict[str, str]` populated by `refresh_market` as
  each section's computation completes. Adding a separate file would
  duplicate state and create a sync bug surface ("which timestamp is
  authoritative?"). The `vintage` dict is the single source of truth
  for "how old is this section's data?" and adding a new section to
  the cooldown map is a 1-line config change.
- **Why skip the section's computation, not just the section's
  HTTP fetch:** the cooldown's whole point is to save cycles on
  expensive yfinance calls (the per-symbol `Ticker.info` /
  `get_histories_bulk` paths inside `enrich_portfolios` and
  `indicators.compute_indicators`). Skipping the computation
  entirely reuses the cached payload's already-computed data — no
  parse, no HTTP, no allocation. The cost is that the user sees
  stale prices for the cooldown window; that's the explicit UX
  trade-off the user asked for.
- **Why the cooldown map is keyed by vintage key, not card key:**
  `vintage["portfolios"]` and `vintage["indicators"]` are the only
  fields the backend reads. The frontend-facing `cooldown_skip`
  labels (`"portfolio"`, `"breadth_ai"`) are different from the
  backend vintage keys — `breadth_ai` is a frontend concept (the
  card name) that maps to the indicators vintage. The two spaces
  are kept separate so the backend doesn't need to know about
  card naming.
- **Why the frontend uses static `900` / `1800` constants instead of
  fetching from a `/api/config` endpoint:** the dashboard payload is
  small enough that duplicating two integer constants in `cards.js`
  is cheaper than a new endpoint + cache layer + sync story. The
  duplication is documented in HANDOFF.md "Notes for the next
  session". If the constants ever need to be runtime-tunable, the
  fix is to add them to the `cooldown_skip` payload (or a sibling
  field) and have `applyCooldownBadge` read them.
- **Why unrelated sections (risk, bottleneck, ai_sentiment) still
  run when indicators are in cooldown:** the cooldown is a per-section
  cost-saver, not a global throttle. Risk reads from the market
  snapshot directly (not from `indicators`); ai_sentiment reads from
  events + cohort snapshots; bottleneck reads from the snapshot.
  They share the same `market.build_market_snapshot` call but
  neither depends on `indicators.breadth_ai` (which is what the
  cooldown skips). The market snapshot is the only shared cost —
  and yfinance's snapshot endpoint is cheap compared to the
  per-symbol `Ticker.info` calls.

## Tests added

- `tests/test_service_cooldown.py` (new, 245 lines, 6 tests):
  - `test_config_reports_cooldown_constants`
  - `test_refresh_market_respects_portfolio_cooldown`
  - `test_refresh_market_respects_breadth_ai_cooldown`
  - `test_refresh_market_refreshes_outside_cooldown`
  - `test_refresh_market_runs_unrelated_sections_even_when_indicators_in_cooldown`
  - `test_cooldown_skip_empty_on_cold_cache`
- `tests/frontend/refresh-cooldown.spec.mjs` (new, 71 lines, 4 tests):
  - `test("Portfolio card shows 'cached Xm' badge when cooldown_skip includes portfolio")`
  - `test("Breadth-AI card shows 'cached Xm' badge when cooldown_skip includes breadth_ai")`
  - `test("Portfolio card hides the badge when cooldown_skip is empty")`
  - `test("Refresh button tooltip shows 'Last refresh' info on hover")`
- `tests/frontend/mock-dashboard.mjs` (+3 lines): `cooldown_skip`,
  `portfolios` / `indicators` vintage keys in `basePayload()` and
  `installMockDashboard()` defaults.

## Verification

- `python -m pytest tests/test_service_cooldown.py tests/test_portfolio.py
  tests/test_api_contract.py` → **104 passed** in 6.0s.
- `npx playwright test --config=tests/frontend/playwright.config.mjs
  tests/frontend/portfolio-holdings-reorder.spec.mjs
  tests/frontend/refresh-cooldown.spec.mjs` → **17 passed** in 6.4s.

## Mistakes to avoid

- Do NOT add a "force refresh" parameter to `POST /api/refresh` that
  bypasses the cooldown. The cooldown's purpose is to save cycles on
  expensive yfinance calls; a force-bypass makes the cooldown
  optional and the user will eventually hit yfinance rate limits
  again. If the user needs fresh data urgently, the cached `vintage`
  stamp is the freshness indicator — a 15-min-old price is fine for
  most decisions.
- Do NOT move the cooldown constants to a per-portfolio setting.
  The Portfolio section's data fetch cost is dominated by the
  holdings (not the portfolios), and the per-portfolio holdings cost
  is dominated by the unique-symbol set. A 15-min cooldown is the
  right granularity for the whole section.
- Do NOT skip `market.build_market_snapshot` when any section is in
  cooldown. The snapshot is what every other section consumes;
  skipping it would create empty risk / bottleneck / ai_sentiment
  payloads. The cost of the snapshot itself is one bulk yfinance
  download, which is cheap compared to per-symbol `Ticker.info`.
- Do NOT use a separate `data/refresh_state.json` file. The cached
  `vintage` dict is the single source of truth for section age; a
  separate file creates a sync bug surface.
