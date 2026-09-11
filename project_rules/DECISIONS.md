# Decisions

Durable, one-way-door(ish) decisions and confirmed root causes. Append new
entries; don't delete old ones even if later superseded — mark them
superseded instead, so the history of *why* stays intact. Newest at the
bottom.

Each entry is a **pointer** here — title, date, status, one-sentence
summary, and a link. The verbose detail (code snippets, test breakdowns,
verification matrices, file:line references) lives in
`archive/decisions/<slug>.md`. Decisions do not rotate; they accumulate.
Status / decision / rationale / rule stay inline so this file is scannable
at session start; open the archive file when implementing or debugging.

The entries below were pulled out of `AGENTS.md`'s "Key quirks" and
"Recent activity" sections during the `docs/` split-out — they were
always true, just harder to scan in prose form.

---

## Market data: yfinance only, no secondary fallback (2026-08-23)

**Summary:** The former Stooq CSV fallback was removed because Stooq now serves a

**Archive:** Full text in `archive/decisions/market-data-yfinance-only-no-secondary-fallback-2026-08-23.md`.

---

## Hidden launchers: `wscript.exe` + VBS, not `pythonw.exe` (undated)

**Summary:** `pythonw.exe` (the GUI-subsystem Python launcher) tries to detach from the

**Archive:** Full text in `archive/decisions/hidden-launchers-wscript-exe-vbs-not-pythonw-exe-undated.md`.

---

## Commodities spot pricing: FRED + Minted Metal, not Yahoo quotes (undated)

**Summary:** Yahoo's `fast_info` is broken in current `yfinance` versions, so real

**Archive:** Full text in `archive/decisions/commodities-spot-pricing-fred-minted-metal-not-yahoo-quotes-undated.md`.

---

## Risk gauge design: divided signals = healthy, unanimous = fragility (undated)

**Summary:** In the archived `ai_market_sentiment_gauge.html`, a card's `col` is fixed

**Archive:** Full text in `archive/decisions/risk-gauge-design-divided-signals-healthy-unanimous-fragility-undated.md`.

---

## Frozen reference files are not touched, ever (undated)

**Summary:** The four `ai_*.html` files at repo root are frozen reference material from a

**Archive:** Full text in `archive/decisions/frozen-reference-files-are-not-touched-ever-undated.md`.

---

## Hard-rule propagation: `project-rules` skill, not AGENTS.md alone (undated)

**Summary:** `AGENTS.md` auto-injects into the parent orchestrator's system prompt but

**Archive:** Full text in `archive/decisions/hard-rule-propagation-project-rules-skill-not-agents-md-alone-undated.md`.

---

## Why Phase 1 ran ahead of Phase 0 (2026-09-06)

**Summary:** The roadmap's own rule is "don't start a Phase N+1 item while a Phase N

**Archive:** Full text in `archive/decisions/why-phase-1-ran-ahead-of-phase-0-2026-09-06.md`.

---

## OPEN — tickerTable.js shared-component persistence (2026-09-05)

**Status:** confirmed + defensively fixed.

**Summary:** Investigation: per-section keys (`pfSort.{section}`, `pfVisible.{section}`,

**Archive:** Full text in `archive/decisions/open-tickertable-js-shared-component-persistence-2026-09-05.md`.

---

## Shared component rebuilds controls subtree — listeners must be re-wired (2026-09-06)

**Status:** confirmed + fixed.

**Summary:** In `static/js/tickerTable.js`, `drawControls()` rebuilds the entire

**Archive:** Full text in `archive/decisions/shared-component-rebuilds-controls-subtree-listeners-must-be-re-wired-2026-09-06.md`.

---

## Portfolio name input must size to content, not fill the header (2026-09-06)

**Status:** confirmed + fixed. **Superseded refinement:** 2026-09-06 entry below — `min-width: 160px` had a layout-shift bug for SHORT names (e.g. "IRA", 3 chars), since the fixed pixel floor was wider than the rendered title. Replaced with `field-sizing: content` + `min-width: 8ch`.

**Summary:** Pre-fix `.pf-name-input` had `flex: 1; min-width: 0;` which stretched the

**Archive:** Full text in `archive/decisions/portfolio-name-input-must-size-to-content-not-fill-the-header-2026-09-06.md`.

---

## Portfolio name input — use `field-sizing: content`, not a pixel floor (2026-09-06)

**Status:** confirmed + fixed. Supersedes the `min-width: 160px` fix above.

**Summary:** Regression coverage: `tests/frontend/portfolio-name-input.spec.mjs` +2

**Archive:** Full text in `archive/decisions/portfolio-name-input-use-field-sizing-content-not-a-pixel-floor-2026-09-06.md`.

---

## Stuck process on test launch — root cause + runtime fix (2026-09-06)

**Status:** confirmed + fixed. Runtime backstop in `app/lifecycle.py`; CLI flag `--auto-reap` + env var `MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S` documented in `project_rules/RUNBOOK.md`.

**Summary:** - `write_server_pid_file()` — records pid / parent_pid / started at

**Archive:** Full text in `archive/decisions/stuck-process-on-test-launch-root-cause-runtime-fix-2026-09-06.md`.

---

## Portfolio mutations must patch the cached dashboard payload (2026-09-06)

**Status:** confirmed + fixed (commit `b45858e`).

**Summary:** Pre-fix `app/portfolio.py` mutations (create/delete/rename portfolio,

**Archive:** Full text in `archive/decisions/portfolio-mutations-must-patch-the-cached-dashboard-payload-2026-09-06.md`.

---

## Per-portfolio scope must use composite keys, not nested Maps (2026-09-06)

**Status:** confirmed + fixed (commit `1fafbc1`).

**Summary:** Pre-fix `static/js/watchColors.js` used a single Map keyed by symbol

**Archive:** Full text in `archive/decisions/per-portfolio-scope-must-use-composite-keys-not-nested-maps-2026-09-06.md`.

---

## Every `[data-card]` in index.html must also appear in CARD_BAND (2026-09-06)

**Status:** confirmed + fixed (commit `6825c0f`).

**Summary:** Pre-fix `static/js/layout.js:14-30` `CARD_BAND` map was missing the

**Archive:** Full text in `archive/decisions/every-data-card-in-index-html-must-also-appear-in-card-band-2026-09-06.md`.

---

## validate_symbol must distinguish "yfinance unavailable" from "no profile" (2026-09-06)

**Status:** confirmed + fixed (commit `a2c793a`).

**Summary:** Pre-fix `app/earnings.py:68-89` `validate_symbol()` made two

**Archive:** Full text in `archive/decisions/validate-symbol-must-distinguish-yfinance-unavailable-from-no-profile-2026-09-06.md`.

---

## Earnings cache-miss path must not trigger a full universe rebuild (2026-09-06)

**Status:** confirmed + fixed (commit `80d0fef`).

**Summary:** Pre-fix `app/earnings.py:add_ticker` (lines 304-345) fell through to

**Archive:** Full text in `archive/decisions/earnings-cache-miss-path-must-not-trigger-a-full-universe-rebuild-2026-09-06.md`.

---

## Rename input must not bubble clicks to header (2026-09-06)

**Status:** confirmed + fixed (commit `974d988`).

**Summary:** Pre-fix `static/js/portfolio.js:200-207` header click handler's

**Archive:** Full text in `archive/decisions/rename-input-must-not-bubble-clicks-to-header-2026-09-06.md`.

---

## Card-level totals must refresh after any sub-table mutation (2026-09-06)

**Status:** confirmed + fixed (commit `8f3a82e`).

**Summary:** Pre-fix `static/js/portfolio.js:289-305` tickerTable callbacks for

**Archive:** Full text in `archive/decisions/card-level-totals-must-refresh-after-any-sub-table-mutation-2026-09-06.md`.

---

## Phase 2 audit — stale-on-reload cluster classification (2026-09-06)

**Status:** audit complete; classification decided; refactor pass landed in commit `b45858e`. This entry exists so a future session doesn't re-derive the classification from scratch.

**Summary:** 1. **Dashboard-cache staleness** (the actual cluster). Pre-fix

**Archive:** Full text in `archive/decisions/phase-2-audit-stale-on-reload-cluster-classification-2026-09-06.md`.

---

## Phase 2 audit — earnings `validate_symbol` path diff (2026-09-06)

**Status:** root cause confirmed; fix landed in the same commit (per the SESSION_LOG of 2026-09-06).

**Summary:** Portfolio enrichment (works for NVDA, AAPL, …):

**Archive:** Full text in `archive/decisions/phase-2-audit-earnings-validate-symbol-path-diff-2026-09-06.md`.

---

## Earnings watchlist section removed (2026-09-06)

**Status:** confirmed + removed.

**Summary:** - `app/earnings.py` (530 lines) — `add_ticker`, `remove_ticker`,

**Archive:** Full text in `archive/decisions/earnings-watchlist-section-removed-2026-09-06.md`.

---

## Portfolio rename input — match width to span (2026-09-06)

**Status:** confirmed + fixed.

**Summary:** confirmed + fixed.

**Archive:** Full text in `archive/decisions/portfolio-rename-input-match-width-to-span-2026-09-06.md`.

---

## Portfolio columns restored + per-portfolio state (2026-09-07)

**Status:** confirmed + shipped (commits `75b7c70` + `a8b60d2`).

**Summary:** | Column | Source |

**Archive:** Full text in `archive/decisions/portfolio-columns-restored-per-portfolio-state-2026-09-07.md`.

---

## AGENT-WORKFLOW-PROMPT.md removed (2026-09-07)

**Status:** removed.

**Summary:** The original session-start workflow template at

**Archive:** Full text in `archive/decisions/agent-workflow-prompt-md-removed-2026-09-07.md`.

---

## project-rules skill generalised for separate publication (2026-09-07)

**Status:** shipped; the skill is now a portable, project-agnostic core ready to be published as its own repo.

**Summary:** - Dropped three project-specific sections (Card behavior + tooltip,

**Archive:** Full text in `archive/decisions/project-rules-skill-generalised-for-separate-publication-2026-09-07.md`.

---

## Portfolio add/delete latency fix (2026-09-07)

**Status:** confirmed + shipped (commit pending; red-green verified against `audit-2026-09-07.md` P0 root cause). Audit doc reproduced the finding end-to-end (min/avg/max over 5 trials with mocked yfinance on N=10 holdings: 23.1 / 29.9 / 54.2 ms — confirming the ~3 s user- visible lag is entirely from yfinan...

**Summary:** 1. **`_patch_dashboard_cache` re-enriched all symbols on a 1-symbol

**Archive:** Full text in `archive/decisions/portfolio-add-delete-latency-fix-2026-09-07.md`.

---

## Next earnings date extraction — yfinance 1.6.0 returns datetime.date, not datetime.datetime (2026-09-07)

**Status:** confirmed + shipped (red-green verified). User-reported follow-up to the P0 fix: portfolio `next_earnings` column rendered as "—" for every holding.

**Summary:** ed = cal.get("Earnings Date")

**Archive:** Full text in `archive/decisions/next-earnings-date-extraction-yfinance-1-6-0-returns-datetime-date-not-datetime-datetime-2026-09-07.md`.

---

## Audit-2026-09-07 follow-up closure -- P3/P4/P5/P6 (2026-09-07)

**Summary:** Closed the remaining audit-2026-09-07 follow-ups this session (3 commits:

**Archive:** Full text in `archive/decisions/audit-2026-09-07-follow-up-closure-p3-p4-p5-p6-2026-09-07.md`.

---

## renderBody must clear portfolioTables Map before innerHTML rebuild (2026-09-07)

**Status:** confirmed + durable rule.

**Summary:** // static/js/portfolio.js:218-229

**Archive:** Full text in `archive/decisions/renderbody-must-clear-portfoliotables-map-before-innerhtml-rebuild-2026-09-07.md`.

---

## Diagnostic scripts MUST redirect data/portfolios.json to a temp dir (2026-09-07)

**Status:** confirmed + durable rule (data-loss incident).

**Summary:** 1. **gitignored = no safety net.** `data/*` is in `.gitignore` with

**Archive:** Full text in `archive/decisions/diagnostic-scripts-must-redirect-data-portfolios-json-to-a-temp-dir-2026-09-07.md`.

---

## Portfolio reorder: dict key order, not a separate `order` field (2026-09-07)

**Summary:** The portfolio reorder feature (move up / move down chevrons) persists

**Archive:** Full text in `archive/decisions/portfolio-reorder-dict-key-order-not-a-separate-order-field-2026-09-07.md`.

---

## Mass expand/collapse: renderHeaderControls() must follow renderBody() (2026-09-07)

**Summary:** `renderHeaderControls()` and `renderBody()` rebuild two separate

**Archive:** Full text in `archive/decisions/mass-expand-collapse-renderheadercontrols-must-follow-renderbody-2026-09-07.md`.

---

## Frozen reference snapshots (retrofit-extracted from AGENTS.md) (2026-09-08)

**Summary:** `archive/ai_*.html` reference snapshots are frozen and

**Archive:** Full text in `archive/decisions/frozen-reference-snapshots-retrofit-extracted-from-agents-md-2026-09-08.md`.

---

## Bottleneck category user prefs live in `data/bottleneck_prefs.json` (2026-09-08)

**Status:** confirmed + shipped.

**Summary:** Bottleneck user prefs (order + renames) live in `data/bottleneck_prefs.json`; the canonical `BOTTLENECK_CATEGORIES` constant is read-only and applied at serve time.

**Archive:** Full text in `archive/decisions/bottleneck-category-user-prefs-live-in-data-bottleneck-prefs-json-2026-09-08.md`.

---

## Test isolation: autouse `tests/conftest.py` redirects every user-data path (2026-09-08)

**Status:** confirmed + shipped.

**Summary:** New autouse `_isolate_data_files` fixture in `tests/conftest.py` monkeypatches every module-level user-data path to `tmp_path`, so a test that forgets isolation can never corrupt the user's real files.

**Archive:** Full text in `archive/decisions/test-isolation-autouse-conftest-py-redirects-every-user-data-path-2026-09-08.md`.

---

## Scheduled tasks + VBS launcher — incident surface + anti-patterns (2026-09-08)

**Status:** docs audit closed. Runbook now names the 3 tasks + recovery steps; `tests/test_scheduler.py` adds `launch.vbs` regression coverage to mirror the existing `scheduler.vbs` tests.

**Summary:** Phase 2 #7 docs audit. Three scheduled tasks (`MarketAnalysis-DailyRefresh` 09:00, `MarketAnalysis-NewsRefresh` every 4 h, `MarketAnalysis-EventsCommit` 17:00) launch via `wscript.exe scheduler.vbs` (WindowStyle=0, do-not-wait) — see `archive/decisions/hidden-launchers-wscript-exe-vbs-not-pythonw-exe-undated.md`. The desktop shortcut uses the sibling pattern via `launch.vbs`. Gap closed: RUNBOOK.md now documents the task table + InteractiveToken logged-off limitation + recovery procedure for a stuck scheduled refresh, plus an explicit anti-patterns list (notebook launches without `--auto-reap`, `Start-Process`/`nohup`/`pythonw`) so the "stuck launch" incident can't recur via a different code path than the Phase 0 fix.

**Archive:** Full text in `archive/decisions/scheduled-tasks-vbs-launcher-incident-surface-anti-patterns-2026-09-08.md`.

---

## tickerTable.js section gating must mirror _assertValidSection, not collapse to a single string (2026-09-08)

**Status:** confirmed + fixed. ReorderEnabled was a stale strict equality (`section === "portfolio"`) that silently no-op'd for every per-portfolio tickerTable instance (which pass `section: "portfolio.<pid>"`). ▲/▼ buttons + "↺ Default order" button missing from every portfolio for an unknown length of time.

**Summary:** Bug surfaced via user report "I don't see it in the front-end". `cards.js:793` help text advertised both features; the renderer hid them. Same anti-pattern class as the 2026-09-05 shared-component persistence decision: silent collapse of per-entity state into a single hardcoded key. Fix: widen `reorderEnabled` to mirror `_assertValidSection`, add boundary-disable on row buttons (matches portfolio-card / bottleneck / layout-card pattern), give the action column an explicit width (table-layout: fixed + 3 buttons overflowed silently), and add `tests/frontend/portfolio-holdings-reorder.spec.mjs` (7 tests).

**Archive:** Full text in `archive/decisions/tickertable-js-section-gating-must-mirror-assertvalidsection-not-collapse-to-single-string-2026-09-08.md`.

---

## Agent terminal servers: `Start-Process` + manual reap is a trap — use Playwright `webServer` or VBS, never bypass the runbook (2026-09-08)

**Status:** confirmed mistake, captured for future sessions.

**Summary:** During the 2026-09-08 holdings-reorder fix session, I bypassed `RUNBOOK.md` §"Anti-patterns" and launched a static server with `Start-Process python -m http.server 8123 ...` because Playwright's `webServer` block hadn't auto-started fast enough. Then the reap failed with "Access is denied" 22× because `Get-NetTCPConnection` `TimeWait` entries have `OwningProcess = 0` (System Idle Process, can't be stopped by regular users). The runbook already says `Start-Process` is wrong; the new lesson is (a) when the harness auto-start fails, debug the harness, don't bypass it — use a foreground `python -m http.server ... & PID=$!; npx playwright test ...; kill $PID` one-shot if needed; (b) reap filters must drop PID 0 (`Where-Object OwningProcess -gt 0`).

**Archive:** Full text in `archive/decisions/agent-terminal-servers-start-process-and-manual-reap-is-a-trap-2026-09-08.md`.

---

## News heuristic expansion — noun-heavy bearish + AI capex coverage (2026-09-09)

**Status:** shipped. Five keyword lists expanded; AI list de-duplicated across `app/config.py` and `app/store.py`. Regression test for the 2026-09-09 oil-headline mis-classification added.

**Summary:** Bag-of-words direction tagging in `app/news.py:185` silently mis-tagged noun-heavy bearish stories because `BEARISH_TERMS` only carried verbs (miss/plunge/crash/tariff/warning). The MarketWatch "Oil's surge back above $100 fuels fresh inflation fears" headline hit BULLISH on "surge" and BEARISH on 0 → bullish. Fix: add the missing nouns (`inflation/inflationary/stagflation/fear/fears/concern/concerns/disruption/disruptions/disrupted/shock/shocks/shocked`), policy verbs (`taper/tighten/warn/slowdown`), conditions (`weakness/strain/stagnation/contagion`), and analyst-action phrases (`guidance cut/estimates cut`). BULLISH_TERMS gets price-action verbs (`jump/climb/rise/gain/advance`) and catalysts (`approval/deal/partnership/rebound/optimism/breakthrough/lift`). MACRO_TERMS gets the rest of rates/credit/FX/labor/commodities/surveys. MICRO_TERMS gets forecasts/EPS/EBITDA/margins/FCF/SEC filings. AI_NEWS_KEYWORDS (single canonical list in `app/config.py`) gains frontier-model labs, hardware vendors, cloud providers, training/inference concepts, networking vendors, power tailwind, specific accelerator products — and `app/store.py:_is_ai_text` now references `config.AI_NEWS_KEYWORDS` so the timeline auto-tag and the AI capex-cycle gauge stay in sync.

**Archive:** Full text in `archive/decisions/news-heuristic-expansion-noun-heavy-bearish-ai-capex-coverage-2026-09-09.md`.

---

## AI gauge lookback window = 30 days (2026-09-09)

**Status:** shipped. Config + tooltip + analysis docstring + tests + a one-shot retag of 21 RSS events in the window.

**Summary:** The AI capex-cycle gauge reads AI-tagged events from the last `config.NEWS_LOOKBACK_DAYS` days of `data/events.json` (see `app/service.py:_recompute_ai_sentiment` and `app/ai_sentiment.py:compute_ai_news_sentiment`). The window was 60 days; the user had previously asked for 30 (one month) and for the window to be stated explicitly in the gauge's tooltip. This session landed both: `app/config.py:343 NEWS_LOOKBACK_DAYS = 30`, and `static/js/cards.js` `CARD_TOOLTIPS["ai-sentiment"]` now spells out the window, the composite-score formula (avg cohort 3m ROC × 2.0 + beneficiaries−spenders ROC × 1.5 + news × 0.3, capped at ±100), and the verdict cutoffs (±60/±20 mirrored below zero). `app/analysis.py:_events_tone` docstring and the `events_last_60d` weight-key were renamed to `events_last_30d`; the synthesis bullet ("Event flow (last N days)") auto-adapts. Two test files updated to match. After the change, the gauge drops 30-60-day-old events from its news leg — slightly less recall on chronic stories, but the gauge reacts faster to regime shifts and isn't dominated by stale noise from April–June.
**Archive:** Full text in
`archive/decisions/ai-gauge-lookback-window-30-days-2026-09-09.md`.

---

## News `user_edited` lock — preserve manual edits across RSS refreshes (2026-09-10)

**Status:** confirmed + shipped (commit `4734cc9`).

**Summary:** New `user_edited: bool` field on every event row; set to `True`
by `update_event_tags()` and short-circuits `upsert_events()` to refresh
only `updated_at`. Older events default `False` via `_build_event_payload`.

**Archive:** Full text in
`archive/decisions/news-user-edited-lock-2026-09-10.md`.

---

## Cross-module imports in the news stack — never add a `?v=…` query to one side without the other (2026-09-10)

**Status:** confirmed mistake, captured for future sessions. Same
anti-pattern class as the 2026-09-05 tickerTable.js shared-component
persistence decision and the 2026-09-08 holdings-reorder "silent
collapse to single string" decision.

**Summary:** During the news-overhaul build, an early draft added a
`?v=20260910` query to `events.js → cards.js` while `cards.js →
events.js` stayed unversioned and `main.js` pinned `?v=20260905c` on
its own `cards.js` import. The JS spec creates a fresh module record
per URL, so the version mismatch silently duplicated both modules:
`initEvents` (in events.js instance A) registered click listeners
against one `eventsCache`, while `renderNews` (in events.js instance B
because cards.js's versioned import resolved to a new module) wrote
to a different `eventsCache`. Symptom: clicking the Month button read
`eventsCache.length === 0` even though `renderNews` had just set it to
6 — events vanished from the dropdown. Fix: import without a version
so the URL resolves to the same module record; pin the cache-bust only
at the entry-point script tag in `index.html`. The rule of thumb:
**for any pair of modules that import each other, both import URLs
must be identical (either both versioned with the same query, or
both unversioned)** — a mismatch is a silent split-state bug.

**Archive:** Full text in
`archive/decisions/news-cross-module-import-versioning-2026-09-10.md`.

---

## News section overhaul — Week/Month toggle + user-edit lock + AI gauge auto-refresh (2026-09-10)

**Status:** shipped (commit `4734cc9`). Two DECISIONS pointers above
capture the standalone rules; this entry is the umbrella for the
feature itself.

**Summary:** News timeline gains a Week/Month grouping toggle (both
views, persisted per browser); a `user_edited` lock prevents RSS
refreshes from clobbering manual tag edits; the AI capex-cycle gauge
auto-refreshes after a manual AI tag via a new `ai_sentiment` field in
the `POST /api/events/tags` response (defensively wrapped in
try/except so a market-data outage returns `null` rather than 500-ing
the tag save). TDD: 5 backend tests + 7 Playwright tests, all
red-then-green.

**Archive:** Full text in
`archive/decisions/news-section-overhaul-week-month-user-edit-ai-gauge-2026-09-10.md`.

---

## News dimension-edit endpoint — manual fix for heuristic mis-classifications (2026-09-11)

**Status:** confirmed + shipped (commit `fa2c976`, follow-up to `4734cc9`).

**Summary:** New `POST /api/events/dimensions` endpoint + `store.update_event_dimensions()`
function. Body is `{link, category?, actor?, direction?, region?}` — only
named fields are updated, `null` clears. Validates each value against
`_DIMENSION_VALUES` (raises `ValueError` → HTTP 400). Arms `user_edited`
on any change so the override survives RSS refreshes. Frontend popover
branches: fixed-dimension pills show a `<select>` of valid values + Remove;
user / `ai` tags keep the free-text rename popover.

**Archive:** Full text in
`archive/decisions/news-dimension-edit-endpoint-2026-09-11.md`.

---

## AI capex-cycle gauge does NOT auto-refresh on tag edits (2026-09-11)

**Status:** confirmed + shipped (commit `fa2c976`). Reverts the auto-refresh
behavior introduced in `4734cc9` after the user clarified they wanted the
gauge to stay stable while curating tags — Refresh is the only trigger.

**Summary:** Removed `service._recompute_ai_sentiment(...)` call from
`POST /api/events/tags` and the `renderAISentiment(resp.ai_sentiment)`
call from `events.js:applyTagUpdate`. The gauge still updates when the
user clicks the global Refresh button (`/api/dashboard` → `_enrich` →
`_recompute_ai_sentiment` reads the current `events.json`).

**Archive:** Full text in
`archive/decisions/news-ai-gauge-no-auto-refresh-2026-09-11.md`.

---

## AI Valuation (Beneficiary) introduced (2026-09-10)

**Status:** confirmed + shipped (commits `339624e` / `6d67bef` / `8c2a932` / `4c2fd90`).

**Summary:** Per-ticker forward-PE cache (12h on-disk TTL, beneficiary cohorts only) feeds the BREADTH - AI Proxies hover tooltip and the AI capex-cycle gauge as a +25 score shift when median PE ≥ 30×; valuation stretch is euphoria (push score UP toward Euphoric / fragility setup), not distress.

**Archive:** Full text in
`archive/decisions/ai-valuation-beneficiary-introduced-2026-09-10.md`.

---

## Portfolio holdings reorder persistence — backend + frontend (2026-09-11)

**Status:** confirmed + shipped (commits `9f6eac1` / `4392797` / `b0e9789`).

**Summary:** `POST /api/portfolios/<pid>/holdings/reorder` + `app.portfolio.reorder_holdings` mirrors the existing portfolios/bottleneck reorder pattern (dict-key insertion order + `save_portfolios` + `_patch_dashboard_cache`); ▲/▼ clicks now POST optimistically with revert-on-error and grey out with a "Reset to default order" tooltip when the view is in a column-header sort.

**Archive:** Full text in
`archive/decisions/portfolio-holdings-reorder-persistence-2026-09-11.md`.

---

## Per-section refresh cooldowns — Portfolio 15 min, Breadth — AI 30 min (2026-09-11)

**Status:** confirmed + shipped (commits `5e00482` / `040c409` / `1254bb7`).

**Summary:** `app.config.REFRESH_SECTION_COOLDOWNS = {"portfolios": 900, "indicators": 1800}` gates `refresh_market()` on the cached `vintage` stamp in `data/dashboard.json`; sections within their cooldown keep the cached data and add their card key (`"portfolio"` or `"breadth_ai"`) to a new `cooldown_skip` list in the payload; the frontend renders a `cached Xm` pill in the affected card h2 and the global `#refreshBtn` hover tooltip shows `"Last refresh: X min ago — Next refresh available in: N min"`.

**Archive:** Full text in
`archive/decisions/per-section-refresh-cooldowns-2026-09-11.md`.

---
