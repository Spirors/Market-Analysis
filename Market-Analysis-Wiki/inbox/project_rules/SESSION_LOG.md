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
> (currently 10 ΓÇö the skill default; the prior 5-entry override was
> reverted in commit `38bf801` because the retrofit to hybrid layout
> shrunk each pointer to ~6 lines, making the more aggressive rotation
> unnecessary), the oldest pointer is dropped ΓÇö the archive file is
> the source of truth.

---

## 2026-09-08 ΓÇö Phase 2 #7 closed: scheduler + VBS launcher docs audit

**Summary:** Docs audit closed. RUNBOOK.md gains a "Scheduled tasks
(3-task setup)" section (task table + InteractiveToken logged-off
limitation + 4-step "stuck scheduled refresh" recovery procedure) and
an "Anti-patterns ΓÇö launch paths that bypass the runtime backstop"
section enumerating wrong launch paths (notebook without
`--auto-reap`, `Start-Process` / `nohup` / `pythonw`) and the
explicit warning that `--auto-reap <n>` on a scheduled refresh would
kill it mid-run because `scheduler.vbs` returns `False` = do-not-wait.
`tests/test_scheduler.py` gains 4 `launch.vbs` tests mirroring the
existing `scheduler.vbs` coverage (file exists, `shell.Run` + `, 0,
False`, no `pythonw`, sets `CurrentDirectory` via
`GetParentFolderName(WScript.ScriptFullName)`). New DECISIONS.md
pointer + archive file
`archive/decisions/scheduled-tasks-vbs-launcher-incident-surface-anti-patterns-2026-09-08.md`.

**Archive:** Full text in
`archive/sessions/2026-09-08-phase-2-7-scheduler-vbs-launcher-docs-audit.md`.

---

## 2026-09-08 ΓÇö feat(bottleneck): up/down reorder + rename pencil

**Summary:** Bottleneck section gains interactive controls mirroring the Portfolio section's move/rename pattern: per-category Γåæ / Γåô chevrons + Γ£Ä rename pencil. Backend persistence in `data/bottleneck_prefs.json`; canonical `BOTTLENECK_CATEGORIES` constant is never mutated. 2 new API endpoints, 18 backend tests + 13 Playwright tests.

**Archive:** Full text in `archive/sessions/2026-09-08-feat-bottleneck-up-down-reorder-rename-pencil.md`.

---

## 2026-09-08 ΓÇö Test isolation: autouse `tests/conftest.py` redirects every user-data path

**Problem.** Test isolation was a per-test responsibility. 18 of 23
test files had no isolation setup, and the module-level path
constants (`PORTFOLIOS_PATH = config.DATA_DIR / "portfolios.json"`
at `app/portfolio.py:95`, etc.) are evaluated at import time ΓÇö so
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
autouse's values ΓÇö the autouse is the safety net that catches tests
that forget to set up isolation.

### Files

- `tests/conftest.py` (new ΓÇö autouse `_isolate_data_files` fixture)
- `.opencode/skills/project-rules/SKILL.md` (new Core rule "Test isolation")
- `project_rules/TESTING.md` (new "Test isolation ΓÇö never touch the
  user's data" section explaining the pattern + how to add a new path)
- `AGENTS.md` (added "Test isolation" to the Hard rules pointers list)
- `project_rules/DECISIONS.md` (new pointer entry)
- `project_rules/archive/decisions/test-isolation-autouse-conftest-py-redirects-every-user-data-path-2026-09-08.md`
  (new ΓÇö full rationale, mistakes-to-avoid, verification)

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

- Module-level path constants are bound at import time ΓÇö the autouse
  must patch each importing module's bound name separately, NOT just
  `config.DATA_DIR`. This is the failure mode that motivated the rule.
- Read-only assets (`static/`, `archive/`) are intentionally NOT
  redirected ΓÇö only state a test could mutate.
- When adding a new user-data path, add the monkeypatch line to
  `_isolate_data_files` in the same change. The fixture is the
  contract; an unpatched new path is a silent regression.

---

## 2026-09-07 ΓÇö Audit follow-up closure: P3/P4/P5/P6 (3 commits)

**Summary:** Closed the remaining audit-2026-09-07 follow-ups. P0 (perf) and the

**Archive:** Full text in `archive/sessions/2026-09-07-audit-follow-up-closure-p3-p4-p5-p6-3-commits.md`.

---

## 2026-09-07 ΓÇö Front-end nuclear renderBody fix (audit-2026-09-07 P0 follow-up)

**Summary:** User reported that add/delete holding felt fast but add/delete/rename

**Archive:** Full text in `archive/sessions/2026-09-07-front-end-nuclear-renderbody-fix-audit-2026-09-07-p0-follow-up.md`.

---

## 2026-09-07 ΓÇö Mass expand/collapse fix + portfolio move up/down

**Summary:** Two changes to the Portfolio card: (1) fix `.pf-toggle-all` label stuck on "Γû╝ all" by adding a `renderHeaderControls()` call after `renderBody()`, (2) add per-row Γåæ / Γåô chevrons that swap with the neighbor and POST to `/api/portfolios/reorder`. 431 backend tests pass (+10 new reorder tests); Playwright 73 pass / 20 fail (pre-existing baseline). 2 commits land the work.

**Archive:** Full text in `archive/sessions/2026-09-07-mass-expand-collapse-fix-and-portfolio-move-up-down.md`.

---

## 2026-09-08 ΓÇö Holdings row reorder + "Γå║ Default order" restored (silent-disabled-at-runtime bug)

**Summary:** User reported "I don't see it in the front-end" for the
holdings Γû▓/Γû╝ row reorder and the "Γå║ Default order" button. Root cause:
`static/js/tickerTable.js:166` had `reorderEnabled = section === "portfolio"`
but every per-portfolio instance is created with
`section: "portfolio.<pid>"` (`portfolio.js:559`), so the check was
always FALSE. Both buttons were silently absent from every portfolio
ΓÇö the help text in `cards.js:793` advertised the feature, the renderer
hid it. Same anti-pattern class as the 2026-09-05 shared-component
persistence decision: silent collapse of per-entity state into a
single hardcoded key. Fix: widen `reorderEnabled` to mirror
`_assertValidSection`, add boundary-disable on row buttons (matches
portfolio-card / bottleneck / layout-card pattern), give the action
column an explicit 90px width (`table-layout: fixed` + 3 buttons
overflowed silently), and add
`tests/frontend/portfolio-holdings-reorder.spec.mjs` (7 tests). Net
Playwright delta vs. baseline: +7 passing, -7 failing. Python: 424
passed, 0 failed.

**Archive:** Full text in `archive/sessions/2026-09-08-holdings-row-reorder-and-default-order-restored-silent-disabled-at-runtime-bug.md`.

---

## 2026-09-08 ΓÇö Captured: Start-Process + PID-0 reap mistake (operational discipline)

**Summary:** During the same session I bypassed
`RUNBOOK.md` ┬º"Anti-patterns" by launching the static test server with
`Start-Process` (because Playwright's `webServer` block hadn't
auto-started in time). The reap then failed with "Access is denied"
22├ù because `Get-NetTCPConnection` `TimeWait` entries report
`OwningProcess = 0` (System Idle Process) and PID 0 can't be stopped
by a regular user. Captured both as a decision entry so a future
session that hits the same time-pressure moment reads "the
runbook is not 'sometimes wrong'" instead of repeating the bypass.
Rule of thumb: (a) debug the harness when its auto-start fails, don't
bypass it ΓÇö for static servers, run server + test in one foreground
bash call with a captured PID; (b) reap filters must drop PID 0
(`Where-Object OwningProcess -gt 0`).

**Archive:** Full text in `archive/sessions/2026-09-08-captured-start-process-and-pid-0-reap-mistake-operational-discipline.md`.


---

## 2026-09-09 ΓÇö News heuristic keyword expansion (bullish/bearish/macro/micro/AI)

**Summary:** Expanded all five keyword lists in the news classifier to close
gaps exposed by the MarketWatch oil-headline mis-classification (tagged
"bullish" when the summary was unambiguously bearish).

- `app/news.py` `BULLISH_TERMS` (+): price-action verbs (`jump/climb/rise/gain/advance`),
  catalysts (`approval/deal/partnership/rebound/optimism/breakthrough/lift`),
  shareholder returns (`dividend hike`, `dividend increase`).
- `app/news.py` `BEARISH_TERMS` (+): inflation lexicon (`inflation/inflationary/stagflation`,
  `fear/fears`, `concern/concerns`, `disruption/disruptions/disrupted`,
  `shock/shocks/shocked`), policy verbs (`taper/tapering`, `tighten/tightening`,
  `warn/warns/warned`, `slowdown/slowing`), conditions (`weakens/weakening/weakness`,
  `strain/strained`, `stagnant/stagnation`, `contagion`), analyst-action
  phrases (`guidance cut`, `estimates cut`).
- `app/news.py` `MACRO_TERMS` (+): real rates (`breakeven/breakevens`, `real yield`),
  swaps, commodities beyond oil (`gold/silver/crude/brent/wti/natural gas`),
  FX (`dollar/dxy/greenback/currency`), broader central-bank umbrella,
  surveys (`ism/pmi`), consumption (`retail sales/consumer spending`),
  labor (`wage/labor market`), fiscal (`shutdown/government shutdown`),
  liquidity/balance-sheet plumbing, QE.
- `app/news.py` `MICRO_TERMS` (+): forecasts (`forecast`), per-share metrics
  (`eps/ebitda`), margins/cash flow (`margin/gross margin/free cash flow/fcf`),
  analyst coverage, corp actions (`delisting/lawsuit`), SEC filings
  (`10-k/10-q/8-k`).
- `app/config.py` `AI_NEWS_KEYWORDS` (+): frontier-model labs and families
  (`openai/anthropic/chatgpt/gpt/claude/gemini/llama/mistral/deepseek/llm/llms`),
  hardware vendors (`intel/arm/asml/micron/hynix/western digital/sandisk`),
  cloud providers (`aws/azure/gcp/oracle cloud`), training/inference
  concepts (`neural network/machine learning/deep learning/transformer/
  foundation model/rag/fine-tuning/agentic/copilot`), memory/storage
  (`ssd/nand/nand flash`), networking vendors (`arista/cisco/palo alto`),
  power tailwind (`power demand/grid/nuclear/small modular reactor/smr`),
  specific accelerator products (`blackwell/hopper/h100/h200/b200/mi300/
  mi400/rubin/grace/bluefield`), `genai/generative ai`.
- **De-dup**: removed `_AI_TAG_KEYWORDS` from `app/store.py`; `_is_ai_text`
  now references `config.AI_NEWS_KEYWORDS` directly. Edits to one place
  flow to both the timeline auto-tag and the AI capex-cycle gauge.

**Tests added** (`tests/test_news_analyze.py`,
`tests/test_ai_sentiment.py`, `tests/test_store.py`):

- Regression for the oil/$100 headline: `_direction()` now returns `bearish`
  on the full title + summary (bear hits 6 vs bull hits 2).
- New `_direction` cases: `recession concerns`, `shock + disruptions`,
  `taper + tightening`, `fda approves ... shares jump`, `rebound on optimism`,
  `breakthrough partnership deal`.
- New `_category` cases: `breakevens`/`real yields`, `central banks + gold + dollar`,
  `wti crude`, `dxy climbs`, `ism pmi`, `retail sales`, `government shutdown`,
  `wage growth`, `eps/fcf`, `analyst forecast`, `delisting + lawsuit`,
  `10-k margin pressure`.
- New `_is_ai_text` coverage tests for the expanded AI keyword list (model
  families, hardware vendors, cloud providers, training concepts, power/grid).
- New end-to-end test: a "OpenAI GPT-5 release drives datacenter capex"
  headline gets the `ai` tag on insert.
- New canonical-keyword-list test: store's `_is_ai_text` follows
  `config.AI_NEWS_KEYWORDS` (no frozen duplicate).

**Verification:** Targeted (`tests/test_news_analyze.py` +
`tests/test_ai_sentiment.py` + `tests/test_store.py`): 116 passed.
Full suite excluding `tests/test_portfolio_cache_sync.py` (pre-existing
infrastructure hang unrelated to this change, also hangs on the
git-stashed baseline): 439 passed, 1 warning in 122.79s.
`tests/test_portfolio_cache_sync.py` in isolation: 5 passed both before
and after this change.

**Files touched:** `app/news.py`, `app/config.py`, `app/store.py`,
`tests/test_news_analyze.py`, `tests/test_ai_sentiment.py`,
`tests/test_store.py`. Changelog: `data/logs/summary-2026-09-09.md`.

**Decision pointer:** See `project_rules/DECISIONS.md` ΓåÆ
"News heuristic expansion (2026-09-09)".


---

## 2026-09-09 ΓÇö AI gauge lookback window = 30 days + tooltip + re-tag

**Summary:** Three connected changes the user asked for together.

1. **AI gauge tooltip now states the lookback window explicitly** ΓÇö
   `static/js/cards.js` `CARD_TOOLTIPS["ai-sentiment"]` previously said
   "Reads AI-tagged events from data/events.json ..." but never mentioned
   the lookback, weights, or score formula. The info icon (Γä╣) on the AI
   gauge card header now shows the full text including the NEWS_LOOKBACK_DAYS
   window, the composite-score formula (avg cohort ROC ├ù 2.0 + spread ├ù 1.5 +
   news ├ù 0.3, capped at ┬▒100), and the verdict cutoffs (┬▒60/┬▒20, mirrored
   below zero) plus the const names (`NEWS_LOOKBACK_DAYS`,
   `AI_SENTIMENT_VERDICT_CUTOFFS`) so a future reader can grep for them.

2. **`NEWS_LOOKBACK_DAYS` 60 ΓåÆ 30** ΓÇö `app/config.py:343` and the
   `app/analysis.py` docstring / `_events_tone` comment + the
   `events_last_60d` weight-key dict + the AI Analysis synthesis bullet
   text + the two test files (`test_analysis_golden.py`,
   `test_service_coverage.py`) all updated to 30 days / `events_last_30d`.
   The synthesis weight (1.0) and the +0.5 / ΓêÆ0.5 bias for bullish/bearish
   net tone are unchanged ΓÇö only the *window* narrowed. The 30-day window
   matches the user's prior request and keeps the gauge responsive to
   regime shifts without stale events (e.g. AprilΓÇôJune noise) dominating.

3. **Re-classified 21 RSS events from the last 30 days** using the
   `d4a41a2` heuristic expansion. Spotlight changes (full diff in
   `data/logs/summary-2026-09-09.md`):
   - The triggering MarketWatch oil/$100 headline ΓÇö `direction: bullish ΓåÆ
     bearish` (the bug `d4a41a2` fixed).
   - "Salesforce's stock rockets 20%" ΓÇö `bearish ΓåÆ bullish`
     (`rockets`/`soar`/`gain` now in BULLISH_TERMS).
   - "US borrowing costs hit fresh highs over inflation fears" ΓÇö `neutral
     ΓåÆ bearish` (inflation/fears now in BEARISH_TERMS).
   - "Investors worried about rising bond yields" ΓÇö `neutral ΓåÆ bullish`.
   - "With Warsh running the Fed, should bond investors be worried?" ΓÇö
     `neutral ΓåÆ bearish` (worried maps to `concern` family).
   - "Kevin Warsh gets what every Fed chair hopes for: a bond market
     that ... " ΓÇö `neutral ΓåÆ bearish` (bond yields ΓåÆ inflation/worried).
   - "AI chip stocks were riding high. Here's why Micron ... " ΓÇö
     `composite_importance 8.28 ΓåÆ 9.66` (new AI keyword coverage).
   - 14 other reclassifications on inflation/concern/AI-headline stories.
   **Seed events (3)** in the 30-day window (`Cargo vessel attacked in
   Strait of Hormuz`, `Third ADNOC vessel attacked`, `UAE says two more
   ADNOC vessels attacked`) were NOT auto-overwritten per the news-filter
   skill rule that seed events are hand-curated; the proposed heuristic
   changes are logged in the changelog for review.
   **`data/events.json` not committed from this session** ΓÇö owned by
   the `MarketAnalysis-EventsCommit` scheduled task per `RUNBOOK.md`
   ┬º"Commit conventions". The scheduler's next 17:00 run will pick up
   the diff.

**Verification:**
- `tests/test_news_analyze.py` + `tests/test_ai_sentiment.py` +
  `tests/test_store.py` + `tests/test_analysis_golden.py` +
  `tests/test_service_coverage.py`: 151 passed (incl. the two updated
  tests for the 30-day window).
- Post-retag spot-check: oil headline now `direction: bearish`. AI-tagged
  events in last 30 days: 14, mix of bullish/neutral/bearish as expected
  from the underlying stories.

**Files touched (this session, this entry):** `app/config.py`,
`app/analysis.py`, `static/js/cards.js`,
`tests/test_analysis_golden.py`, `tests/test_service_coverage.py`.
`data/events.json` updated on disk but not committed from interactive
session. `data/logs/summary-2026-09-09.md` gets the bulk-retag entry.

**Decision pointer:** See `project_rules/DECISIONS.md` ΓåÆ
"AI gauge lookback window = 30 days (2026-09-09)".


---

## 2026-09-10 ΓÇö News section overhaul: Week/Month toggle + user-edit lock + AI gauge auto-refresh

**Summary:** Three coordinated features shipped as one commit
(`4734cc9`):

1. **Week/Month grouping toggle** on the news timeline. Both views,
   persisted per browser via new `tlGroupingMode` + `tlSelectedMonth`
   localStorage keys (the legacy `tlSelectedWeek` is untouched). The
   toggle is a segmented control inside the existing `.tl-toolbar`;
   the period dropdown adapts its label (`Timeline week` Γåö `Timeline
   month`) and options to the active mode. Generic
   `buildGroups(items, mode)` replaces `buildWeekGroups`; month buckets
   use `YYYY-MM`; the undated bucket is preserved.
2. **`user_edited` lock** on news events. New `bool` field on every
   row, set to `True` by `update_event_tags()`. Once set,
   `upsert_events()` skips overwrite entirely on RSS refresh (only
   `updated_at` is touched) ΓÇö manual tag edits now survive both manual
   and scheduled refreshes. Auto-AI-tag still applies on insert for new
   rows; user edits win on existing rows.
3. **AI capex-cycle gauge auto-refresh after a manual AI tag.** The
   `POST /api/events/tags` response gains a recomputed `ai_sentiment`
   payload. Defensive `try/except` around `service._recompute_ai_sentiment`
   so a transient market failure returns `ai_sentiment: null` rather
   than 500-ing the tag save. The frontend re-renders only when the
   edit actually touched `"ai"` (cheap `O(1)` check on the `add` /
   `remove` arrays).

**Architecture / bug highlight.** During the build, an early draft
added a `?v=20260910` query to the `events.js ΓåÆ cards.js` import.
The JS spec creates a fresh module record per URL, so the version
mismatch silently duplicated both modules: `initEvents` ran in one
instance and `renderNews` wrote `eventsCache` in another. Symptom:
click handler read `eventsCache.length === 0` while `renderNews` had
set it to 6. Fix: import without a version (single module record);
pin the cache-bust only at the entry-point script tag in
`index.html`. Recorded as a new DECISIONS entry so future
cross-module imports avoid the same pitfall.

**Files touched (9):** `app/api.py` (+14 / ΓêÆ2), `app/store.py` (+34
/ ΓêÆ12), `static/index.html` (+8), `static/js/cards.js` (+3 / ΓêÆ2),
`static/js/events.js` (+~130 / ΓêÆ~30), `static/style.css` (+32),
`tests/test_api_contract.py` (+21), `tests/test_store.py` (+84),
`tests/frontend/news-grouping.spec.mjs` (new, +171).
`data/events.json` updated on disk but NOT committed from this
session ΓÇö scheduler-owned per `RUNBOOK.md` ┬º"Commit conventions".

**Tests:** TDD throughout. 5 backend tests (4 in `test_store.py`:
`test_update_event_tags_sets_user_edited_flag`,
`test_upsert_events_skips_overwrite_when_user_edited`,
`test_upsert_events_overwrites_normal_event` regression guard,
`test_user_edited_default_false_for_unmodified_events`; 1 in
`test_api_contract.py`: `test_events_tags_returns_ai_sentiment`) and
7 Playwright tests (`news-grouping.spec.mjs`: defaults, click-Month,
filter-by-month, switch-back-restores-week, month-persistence,
mode-persistence, AI-gauge-rerender-on-tag) ΓÇö all written red, watched
fail, then made green. Backend: 443 passed in 121.91s. Frontend news
section: 7/7 passing. Full frontend suite has 22 remaining failures
that are pre-existing (HEAD without my changes had 116 failures,
so this is a net improvement ΓÇö see "Notes for the next session" in
HANDOFF.md).

**Operational notes.** Static-server lifecycle per `RUNBOOK.md`
step 2 (foreground form, captured PID, `Stop-Process` in `finally`).
Playwright's `webServer` block silently didn't auto-start on Windows
in this session; the foreground workaround was used without leaving
an orphan. The next 17:00 scheduled refresh will pick up the new
`user_edited=True` rows on disk from any earlier tag edits.

**Decision pointers:** See `project_rules/DECISIONS.md` ΓåÆ
"News `user_edited` lock ΓÇö preserve manual edits across RSS refreshes
(2026-09-10)", "Cross-module imports in the news stack ΓÇö never add a
`?v=ΓÇª` query to one side without the other (2026-09-10)", and
"News section overhaul ΓÇö Week/Month toggle + user-edit lock + AI gauge
auto-refresh (2026-09-10)".

**Archive:** Full text in
`archive/sessions/2026-09-10-news-section-overhaul-week-month-user-edit-ai-gauge.md`.


---

## 2026-09-11 ΓÇö News overhaul follow-ups: editable tags + no AI-gauge auto-refresh

**Summary:** Two corrections to the news section overhaul (commit `4734cc9`),
shipped as commit `fa2c976`:

1. **Every pill on a news row is now editable for manual fix.** The user
   reported that fixed-dimension pills (category / actor / direction /
   region) were inert ΓÇö only user / `ai` tags had a popover. The fix:
   the popover now branches on tag type. Fixed-dimension pills show a
   `<select>` of valid values for that dimension (+ a "(clear)" option
   to null it out) and a Remove button; user / `ai` tags keep the
   existing free-text rename input + Remove. Saving a dimension override
   POSTs to the new `/api/events/dimensions` endpoint
   (`store.update_event_dimensions()`), which validates the value
   against `_DIMENSION_VALUES` and arms the `user_edited` lock so the
   override survives both manual and scheduled RSS refreshes. Region pill
   moved from the row metadata strip into the regular pill line so it
   shares the same popover as the other dimensions (no more duplication
   of region info).

2. **AI capex-cycle gauge does NOT auto-refresh on tag edits.** The
   user clarified that adding the `ai` tag to a news event should not
   flip the gauge ΓÇö only the global Refresh button should trigger the
   recompute. The fix: removed the `_recompute_ai_sentiment` call from
   `POST /api/events/tags` (and the corresponding `ai_sentiment` field
   from the response), and removed the `renderAISentiment(resp.ai_sentiment)`
   call from `events.js:applyTagUpdate`. The gauge still updates when
   the user clicks Refresh (`/api/dashboard` ΓåÆ `_enrich` ΓåÆ
   `_recompute_ai_sentiment` reads the current `events.json`).

**Files touched (8):** `app/api.py` (+28 / ΓêÆ15), `app/store.py`
(+76 / ΓêÆ2), `static/index.html` (+8), `static/js/api.js` (+16),
`static/js/events.js` (+~80 / ΓêÆ~40), `static/style.css` (+20),
`tests/test_api_contract.py` (+90), `tests/test_store.py` (+85),
`tests/frontend/news-grouping.spec.mjs` (+147).

**Tests:** TDD throughout. 8 new backend tests in `test_store.py`
(`update_event_dimensions`: set field, clear with null, multi-field,
`user_edited` lock arms, unknown link 404, unknown field 400, invalid
value 400, empty-dict no-op); 9 new tests in `test_api_contract.py`
(replaced the obsolete `test_events_tags_returns_ai_sentiment` with
`test_events_tags_does_not_recompute_ai_sentiment` using a spy on
`service._recompute_ai_sentiment` to confirm zero calls; 8 new tests
for `/api/events/dimensions`); 5 new Playwright tests in
`news-grouping.spec.mjs` (every pill clickable, fixed-dimension
popover shape with `(clear)` option, dimension arms `user_edited`
lock, user-added tag popover shape, AI gauge does NOT auto-refresh).

**Verification:**
- `python -m pytest tests/ -k "not portfolio_cache_sync and not thirteenf and not service_coverage" -q`
  ΓåÆ **459 passed** in 119.64s (was 443, net +16)
- `npx playwright test tests/frontend/news-grouping.spec.mjs` ΓåÆ **12 passed** in 4.9s
  (was 7, net +5)

**Operational notes.** All changes flow through the established
Playwright harness (foreground server, captured PID, `Stop-Process` in
`finally`). No orphan processes left running. `data/events.json` NOT
committed ΓÇö scheduler-owned per `RUNBOOK.md` ┬º"Commit conventions".

**Decision pointers:** See `project_rules/DECISIONS.md` ΓåÆ
"News dimension-edit endpoint ΓÇö manual fix for heuristic mis-classifications
(2026-09-11)" and "AI capex-cycle gauge does NOT auto-refresh on tag edits
(2026-09-11)".

**Archive:** Full text in
`archive/sessions/2026-09-11-news-overhaul-followups-editable-tags-no-auto-ai-gauge.md`.

---

## 2026-09-10 ΓÇö UI-cleanup leftovers from earnings-watchlist removal

**Summary:** Two stale-UI bug fixes the user spotted after the
2026-09-06 earnings-watchlist section removal. Both are 1ΓÇô2 line edits to
`static/js/cards.js`, catching the frontend copy up to the backend
contract that already changed five days earlier.

1. **Risk Divergence tooltip signal count 9 ΓåÆ 8.**
   `static/js/cards.js:752` `CARD_TOOLTIPS["risk"].text` said "Aggregates
   9 cross-asset signals" but `app/config.py:224` `RISK_SIGNAL_TOTAL = 8`
   (and `app/risk.py:479-488` registers 8 strategies). The 9th signal
   (`_signal_valuation` / valuation stretch) was dropped in the
   earnings-watchlist cleanup on 2026-09-06
   (`archive/decisions/earnings-watchlist-section-removed-2026-09-06.md`).
   The badge in the card header correctly shows "7/8" (8 total
   strategies, 1 of which returned no data this run), but the tooltip
   text still claimed 9 ΓÇö fixed in place.

2. **AI capex-cycle gauge dead Valuation cell removed.**
   `static/js/cards.js:209` rendered `<span>Valuation
   <b>${escapeHtml(ai.valuation?.note || "ΓÇö")}</b></span>`, but
   `app/ai_sentiment.py` `compute_ai_sentiment` no longer returns a
   `valuation` key ΓÇö `compute_valuation_flag` was removed in the same
   2026-09-06 cleanup (forward-PE references went with the earnings
   cache). The cell always rendered a permanent dashline. Removed the
   `<span>`; `ai-gauge-meta` now shows Score / Beneficiaries vs Spenders /
   News, matching the three live signals the backend actually emits.
   CSS (`.ai-gauge-meta` flexbox with `flex-wrap`) is content-agnostic,
   so removing one span just re-flows the row.

**No backend changes. No new tests.** Bug surface is a 2-line UI delta
that's verifiable by inspection ΓÇö the existing frontend tests continue
to mock `ai_sentiment` payloads with `valuation: { note: "" }` and pass
unmodified (the mocked field is now unused on the production path too).

**Files touched (1):** `static/js/cards.js` (-1 / +1).

**Decision pointer:** See `project_rules/DECISIONS.md` ΓåÆ
"Earnings watchlist section removed (2026-09-06)" ΓÇö the rationale and
the blast radius of that cleanup; this entry is the frontend catch-up.

---

## 2026-09-10 ΓÇö AI Valuation (Beneficiary): per-ticker forward-PE cache, BREADTH hover, gauge score shift

**Summary:** Re-introduces a forward-PE valuation signal for the AI
capex-cycle gauge and the BREADTH - AI Proxies chart, replacing the dead
`compute_valuation_flag` that was removed in the 2026-09-06
earnings-watchlist cleanup. New shape: per-ticker PE cache (12h on-disk
TTL), `valuation` summary on the AI gauge output, BREADTH hover tooltip
with PE/cohort-median/stretch annotation, and a +25 score shift when
median beneficiary cohort PE ΓëÑ 30├ù.

### Architecture

Four feature commits in this sequence:

1. `339624e` ΓÇö `app/ai_valuation.py` (new): cache I/O (`load_cache`,
   `save_cache` ΓÇö atomic `tempfile.mkstemp + os.replace`, mirrors
   `app/changelog.py:114-127`), yfinance fetch
   (`fetch_beneficiary_pe` ΓÇö beneficiary cohorts only, excludes
   `"Capex Spenders"`), `compute_valuation` summary
   (`{median_pe, stretched, note, per_ticker_pe, fetched_at, cache_ttl_hours}`).
   `app/config.py:228-235` adds `AI_VALUATION_STRETCH_PE = 30.0`,
   `AI_VALUATION_SCORE_SHIFT = 25.0`, `AI_VALUATION_CACHE_TTL_HOURS = 12`,
   `AI_VALUATION_CACHE_PATH = DATA_DIR / "ai_valuation.json"`. Cache
   file added to `data/.gitignore`. `tests/conftest.py` autouse fixture
   gains one monkeypatch line (per the test-isolation hard rule ΓÇö
   module-level path constants are bound at import time, so the patch
   targets `ai_valuation._CACHE_PATH`, not `config.AI_VALUATION_CACHE_PATH`).

2. `6d67bef` ΓÇö Frontend BREADTH hover (Tasks 3+4 combined in one commit
   because both touch `static/js/cards.js` for the same feature): the
   `_renderBarChart` helper gains a `tooltipCallbacks` option; the
   `breadthAIChart` registers a custom `label` callback that emits
   `TICKER ΓÇö fwd PE ├ù├ù├ù├ù (cohort median ├ù├ù├ù├ù; stretch ΓëÑ 30├ù)`. The
   `ai-gauge-meta` row re-introduces a `Valuation (Beneficiary)` cell
   with the median PE and a `┬╖ stretched` / `┬╖ ok` trailing tag.
   `CARD_TOOLTIPS["ai-sentiment"]` gains a one-line addendum mentioning
   `AI_VALUATION_SCORE_SHIFT=25` when median PE ΓëÑ 30├ù.

3. `8c2a932` ΓÇö Mock payload backward-compat: `tests/frontend/mock-dashboard.mjs`
   default mock gains a `valuation: { median_pe: 35.0, stretched: true, ... }`
   field; seven existing frontend spec files update their inline
   `ai_sentiment` mocks to the new shape (mechanical, no test logic
   change).

4. `4c2fd90` ΓÇö Backend gauge integration: `app/ai_sentiment.py`
   `compute_ai_sentiment(snapshot, events, valuation=None)` ΓÇö when
   `valuation.stretched` is True, `score += config.AI_VALUATION_SCORE_SHIFT`
   (the verdict is re-classified AFTER the shift so the verdict reflects
   the final score). Returns `valuation: { median_pe, stretched, note }`
   so the frontend can render the new cell. `app/service.py`
   `_recompute_ai_sentiment` calls `ai_valuation.fetch_beneficiary_pe()`
   ΓåÆ `ai_valuation.compute_valuation()` ΓåÆ passes `valuation=` to
   `compute_ai_sentiment`. No new endpoints; existing `/api/dashboard`
   path picks it up via `_enrich ΓåÆ _recompute_ai_sentiment`.

### Plan, tests, verification

- Plan: `docs/superpowers/plans/2026-09-10-ai-valuation-breadth-hover.md`
  (1152 lines; per-task bite-sized TDD steps; user opted to skip the
  design doc and proceed straight to planning+implementation per the
  brainstorming skill's architectural path).
- Backend tests: `tests/test_ai_valuation.py` (new) ΓÇö 18 tests
  (cache hit/miss/expired/atomic-write/round-trip, yfinance fetch with
  mocked `yf.Ticker`, skip-spenders, skip-invalid-PE, partial failure,
  force-refresh, compute_valuation median/stretched/empty/threshold/
  per-ticker/cache-ttl). `tests/test_ai_sentiment.py` ΓÇö 4 new
  integration tests (stretched ΓåÆ +25; not-stretched ΓåÆ no shift;
  missing ΓåÆ no shift; output includes valuation dict).
- Frontend tests: `tests/frontend/breadth-ai-valuation.spec.mjs` (new) ΓÇö
  7 tests (2 BREADTH hover, 3 AI gauge meta cell, 1 score +25 verification,
  1 tooltip text). Note: the Playwright harness here intentionally
  blocks the Chart.js CDN, so the hover tests verify payload shapes and
  DOM rendering rather than canvas tooltip hover behavior ΓÇö same
  constraint that shaped other frontend specs in this repo.
- **Verification:** `python -m pytest tests/ -k "not thirteenf and not
  service_coverage and not portfolio_cache_sync" -q` ΓåÆ **481 passed**
  (was 459, net +22). `cd tests/frontend && npx playwright test` ΓåÆ
  **122 passed / 5 failed** (the 5 failures are pre-existing baseline:
  bottleneck-move, dash-layout-survives-reload ├ù2, global-refresh,
  portfolio-star-scope star persistence ΓÇö none caused by this change).

### Design rationale (recap from the brainstorming phase)

- **Stretch-only (not two-sided):** user explicitly chose to ignore the
  cheap-side signal; high PE = euphoria penalty (push score UP toward
  Euphoric / fragility setup), not distress. Original implementation's
  ΓêÆ15 penalty was backwards direction (high PE ΓåÆ "broken"); the new
  design has high PE ΓåÆ "euphoric".
- **Beneficiary cohorts only:** Capex Spenders (MSFT/GOOGL/AMZN/META/ORCL)
  are demand-side; their PE reflects the broader market, not the AI
  trade. Including them dilutes the median and weakens the signal.
- **Label `Valuation (Beneficiary)` in the UI** makes the cohort scope
  explicit so a future reader doesn't wonder why spenders aren't counted.
- **On-disk cache with 12h TTL** mirrors the deleted earnings-cache
  pattern; first refresh after expiry re-fetches ~65 Ticker.info calls
  (~60-90s), subsequent refreshes within 12h are instant.
- **The Bug #1 follow-up's "removed dead Valuation cell" was a stopgap.**
  This entry reverses that removal and replaces it with a live,
  data-driven cell ΓÇö completing the cleanup cycle that started on
  2026-09-06.

### Decision pointer

See `project_rules/DECISIONS.md` ΓåÆ "AI Valuation (Beneficiary)
introduced (2026-09-10)" ΓÇö full rationale, cohort-scope decision
rationale, mistakes-to-avoid, verification matrix.

### Files touched (8 files, 17 in the diff stat)

- `app/ai_valuation.py` (new, 181 lines)
- `app/ai_sentiment.py` (+20 / ΓêÆ5)
- `app/config.py` (+9)
- `app/service.py` (+5 / ΓêÆ1)
- `app/indicators.py` (added cohort_median_pe wiring per self-review fix)
- `static/js/cards.js` (+37 / ΓêÆ1)
- `tests/conftest.py` (+2 / ΓêÆ1)
- `tests/test_ai_valuation.py` (new, 196 lines)
- `tests/test_ai_sentiment.py` (+65)
- `tests/frontend/breadth-ai-valuation.spec.mjs` (new, 191 lines)
- `tests/frontend/mock-dashboard.mjs` (+38 / ΓêÆ4)
- `tests/frontend/portfolio.spec.mjs` (+3 / ΓêÆ3)
- `tests/frontend/bottleneck-move.spec.mjs` (+1 / ΓêÆ1)
- `tests/frontend/bottleneck-rename.spec.mjs` (+1 / ΓêÆ1)
- `tests/frontend/portfolio-holdings-reorder.spec.mjs` (+1 / ΓêÆ1)
- `tests/frontend/portfolio-header-collapse.spec.mjs` (+2 / ΓêÆ2)
- `tests/frontend/portfolio-move.spec.mjs` (+1 / ΓêÆ1)
- `tests/frontend/portfolio-star-scope.spec.mjs` (+1 / ΓêÆ1)
- `data/.gitignore` (+1)
- `docs/superpowers/plans/2026-09-10-ai-valuation-breadth-hover.md` (new, 1152 lines)

`data/events.json` was NOT modified by this session (scheduler-owned).
The Bug #1 follow-up entry earlier today removed the dead cell in
`static/js/cards.js`; this entry reverses that removal and replaces it
with a live, data-driven implementation.


---

## 2026-09-11 ΓÇö Portfolio holdings reorder persistence + per-section refresh cooldowns

**Summary:** Six commits across two parallel lanes. The Portfolio section's
holdings Γû▓/Γû╝ reorder now persists to `data/portfolios.json` (was
session-only) and is greyed out when the view is in a column-header sort
(non-default order). The Portfolio and Breadth ΓÇö AI proxies sections gain
per-section refresh cooldowns (15 min / 30 min) gated on the cached
`vintage` stamp; a refresh within the cooldown keeps the section's cached
data and surfaces a "cached Xm" badge + a "next refresh in N min" tooltip
on the global Refresh button.

### Backend lane (2 commits)

1. `9f6eac1` ΓÇö `feat(portfolio): backend holdings reorder endpoint + tests`.
   New `app.portfolio.reorder_holdings(pid, order)` mirrors
   `reorder_portfolios`: validates that `order` is a permutation of the
   current non-cash holdings' symbols (no additions, removals, duplicates),
   mutates the holdings list in place, preserves the cash row at the end,
   `save_portfolios(state)` then `_patch_dashboard_cache(state)`. New
   `POST /api/portfolios/{pid}/holdings/reorder` endpoint maps
   `ValueError ΓåÆ 400` and `KeyError ΓåÆ 404`. 14 new backend tests (10 in
   `test_portfolio.py`: permutation/duplicate/missing-symbol/cash
   preservation/persistence; 4 in `test_api_contract.py`: round-trip,
   400, 404, cash preservation).

2. `5e00482` ΓÇö `feat(refresh): backend per-section refresh cooldowns +
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

3. `4392797` ΓÇö `feat(portfolio): frontend holdings reorder persistence`.
   New `static/js.api.reorderHoldings(pid, order)` (mirror of
   `reorderPortfolios`). `tickerTable.js:moveRow` now POSTs the new
   symbol order (cash rows filtered out) optimistically, reverts on
   error via `setStatus(msg, "bad")`. `portfolio.js` wires the new
   `onReorder` callback. 3 new Playwright tests (POST round-trip, revert
   on failure, cash-row omission from the POST body).

4. `b0e9789` ΓÇö `fix(portfolio): grey-out Γû▓/Γû╝ when not in default order`.
   `tickerTable.js:drawBody` adds a `reorderBlocked = sort.key !==
   "default"` condition: when true, all Γû▓/Γû╝ buttons render with the
   `disabled` attribute + tooltip `"Reset to default order (Γå║) before
   reordering rows"`. `moveRow` gains a defensive `sort.key !== "default"`
   guard (defense in depth ΓÇö the button is already disabled in the UI).
   3 new Playwright tests (disabled when sorted, re-enabled after Γå║
   reset, no-op on force-click in non-default order).

5. `040c409` ΓÇö `feat(refresh): cooldown tooltip + section age badges`.
   New `static/js.cards.applyCooldownBadge(section, data)` reads
   `data.cooldown_skip` + the section's `vintage[section]` stamp and
   renders a small `cached Xm` pill in the affected card's h2 (Portfolio
   uses `vintage.portfolios`; Breadth ΓÇö AI proxies uses
   `vintage.indicators`). The pill carries a title tooltip `"Last
   refreshed X min ago ΓÇö next refresh in N min"`. Cooldown constants
   (900s / 1800s) live in `cards.js` next to the badge code. New CSS
   rule `.cov-cooldown` (muted `--sub` colour, hairline border,
   `font-size: 9px`) added to `static/style.css` ΓÇö separate from the
   existing `.cov-badge` to avoid semantic confusion (coverage vs data
   freshness). `static/js.main` adds hover/unhover wiring on
   `#refreshBtn`: on hover, the `title` is set to a live `"Refresh
   dashboard. Last refresh: X min ago. Next refresh available in: N
   min"` string; on unhover, restored to the static `"Refresh"`. 4 new
   Playwright tests in a new `refresh-cooldown.spec.mjs` (portfolio
   badge, breadth-ai badge, badge hidden when empty, refresh button
   tooltip). `mock-dashboard.mjs` extended with `cooldown_skip` +
   per-section vintage keys.

6. `1254bb7` ΓÇö `docs(refresh): note cooldown + reorder behaviour in card
   tooltips`. `static/js.cards.CARD_TOOLTIPS["portfolio"].text` and
   `["breadth-ai"].text` gain one sentence each describing the
   refresh-cooldown behaviour. `portfolio.text` also notes that Γû▓/Γû╝
   reorder now persists to `data/portfolios.json`.

### Verification

- `python -m pytest tests/test_service_cooldown.py tests/test_portfolio.py
  tests/test_api_contract.py` ΓåÆ **104 passed** (10 new portfolio + 4 new
  api_contract + 6 new service_cooldown + existing). 6.0s.
- `npx playwright test --config=tests/frontend/playwright.config.mjs
  tests/frontend/portfolio-holdings-reorder.spec.mjs
  tests/frontend/refresh-cooldown.spec.mjs` ΓåÆ **17 passed**. 6.4s.
- Pre-existing failures observed in the broader suite (NOT caused by
  this change):
  - `tests/test_service_coverage.py::test_recompute_ai_sentiment_filters_ai_only`
    ΓÇö timing tolerance too tight (5s vs measured 12ΓÇô14s).
  - `tests/test_portfolio_cache_sync.py` ΓÇö pre-existing hang on the
    network-enrichment path; not addressed here (out of scope).
  - `tests/frontend/global-refresh.spec.mjs:63` "news rows carry region
    pill, source-weight badge, relevance chip" ΓÇö `events.js` not
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
modified by this session (scheduler-owned per `RUNBOOK.md` ┬º"Commit
conventions").

### Decision pointers

See `project_rules/DECISIONS.md` ΓåÆ
- "Portfolio holdings reorder persistence ΓÇö backend + frontend (2026-09-11)"
- "Per-section refresh cooldowns ΓÇö Portfolio 15 min, Breadth ΓÇö AI 30 min (2026-09-11)"

### Archive

Full text in
`archive/sessions/2026-09-11-portfolio-reorder-persistence-refresh-cooldowns.md`.


---

## 2026-09-11 ΓÇö Portfolio follow-up fixes: live prices always refresh + reorder survives collapse+expand

**Summary:** One commit (`bfb118f`) addressing two follow-up bugs from the
morning's session (`9f6eac1` / `5e00482` / `4392797` / `b0e9789` / `040c409`
/ `1254bb7`). The cooldown logic added that morning was over-aggressive for
the Portfolio section ΓÇö it blanked the live-price columns on every
in-cooldown refresh ΓÇö and the Γû▓/Γû╝ reorder only persisted in the backend
because the closure variable `p.holdings` was never updated by the
optimistic swap.

### Bug 1 ΓÇö Live prices blank after refresh (Portfolio section)

**Symptom (user-reported):** "Cache data got wiped when refreshed and now I
have to wait till cooldown is over." Clarification via clarifying questions:
portfolios + holdings still visible, but the live-price columns (Last price /
Total value / Daily % / 7-day % / 30-day % / 52W high) all showed "ΓÇö".

**Root cause:** `app/service.py:refresh_market` (the morning's lane-1 code)
gated `enrich_portfolios` on the cooldown. When in cooldown, the cached
`portfolios` was reused. But the cache is patched structurally via
`_patch_dashboard_cache` (`app/portfolio.py:25-68`) ΓÇö it carries the user's
`symbol / shares / total_cost` (and any other fields set by mutations) but
NOT the live-price enrichment (`last_price / pct_daily / pct_7d / pct_30d /
high_52w / sector / marketcap / forward_pe / forward_peg /
next_earnings`). The frontend rendered all of those as "ΓÇö".

**Fix:** Remove the portfolio cooldown skip. Always run `enrich_portfolios`
for the portfolios section. Keep the cooldown for the `breadth_ai` /
`indicators` section (the user only complained about portfolio, and
breadth-ai has its own price-cohort data path that benefits from the
cooldown).

**Why this is safe (and why the cooldown was over-engineered for
portfolios):**
- `enrich_portfolios` calls `get_info_snapshot` per symbol ΓÇö but that's
  `lru_cache`-backed with a 5-min TTL (`_INFO_CACHE_BUCKET_S = 300`), so
  the second call within a 15-min window hits the cache.
- The bulk `quote_snapshot` + `histories_bulk` are single HTTP calls to
  yfinance ΓÇö comparable to the cost of `_enrich` recomputing the rest of
  the dashboard.
- Within a 15-min window, the "savings" was at most 1 saved HTTP call
  per 15 min. Not worth blanking prices.

**Files touched:**
- `app/service.py:refresh_market` ΓÇö removed the `_in_cooldown("portfolios")`
  branch; unconditional `enrich_portfolios` call. The `cooldown_skip`
  field stays in the payload (the `"portfolio"` entry will just never be
  appended now).
- `static/js/cards.js:CARD_TOOLTIPS["portfolio"]` ΓÇö removed the
  "15-minute refresh cooldown" sentence.

**Tests:**
- `tests/test_service_cooldown.py`:
  - DELETED `test_refresh_market_respects_portfolio_cooldown` (no longer
    applies; the new behaviour is that portfolio enrichment always runs).
  - ADDED `test_refresh_market_always_enriches_portfolios_regardless_of_cooldown`
    ΓÇö seeds the cache with a fresh `vintage["portfolios"]` so
    `_in_cooldown("portfolios")` would return True if it were called.
    Runs `refresh_market`. Asserts `result["portfolios"]` has live prices
    (the same `last_price` the mocked `enrich_portfolios` returns).
    Asserts `"portfolio"` is NOT in `cooldown_skip`. Mocks
    `enrich_portfolios` to spy on whether it was called.
  - KEPT all breadth-ai cooldown tests (unchanged).
- `tests/frontend/refresh-cooldown.spec.mjs`:
  - DELETED `test("Portfolio card shows 'cached Xm' badge when
    cooldown_skip includes portfolio")` ΓÇö badge no longer shows for
    portfolio.
  - ADDED `test("Portfolio prices are not blank after refresh")` ΓÇö mocks
    `/api/dashboard` with portfolios that have `last_price` set. Clicks
    the global refresh. Asserts the rendered holdings show the price.
  - KEPT all breadth-ai tests.

### Bug 2 ΓÇö Γû▓/Γû╝ reorder resets on collapse+expand (Portfolio section)

**Symptom (user-reported):** "Also holding position is persistent only
after refresh button (position is probably persistent in the backend).
(action such as collasping portfolio reset position in frontend)."
Confirmed: the reorder IS persistent on the backend (clicking the global
Refresh button restores the new order), but collapse + expand in the
frontend shows the OLD order.

**Root cause:** In `static/js/portfolio.js:renderHoldingsTable` (the
morning's lane-2 code), the `onReorder` callback was wired as:

```js
onReorder: async (order) => {
  await API.reorderHoldings(pid, order);
},
```

It POSTed the new order to the backend but did NOT mutate `p.holdings`
(the closure variable that the next `renderBody()` reads from).
`tickerTable.js:moveRow` only mutated the `tickerTable.data.rows` array
in memory; that array is destroyed when the next `renderBody()` clears
`portfolioTables` (line 239) and recreates a fresh `tickerTable` instance
on collapse+expand. The fresh instance reads `p.holdings`, which still
held the OLD order because nothing had propagated the swap up to
`portfolioData.portfolios[pid].holdings`.

**Fix:** Update `onReorder` in `static/js/portfolio.js:renderHoldingsTable`
to mirror the new order in both the closure's `p.holdings` AND the
module-level `portfolioData.portfolios[pid].holdings` before the POST.
Cash row stays at the end. The backend POST is unchanged.

**Files touched:**
- `static/js/portfolio.js:renderHoldingsTable` ΓÇö `onReorder` callback
  now rebuilds `p.holdings` from the new symbol order, updates
  `portfolioData.portfolios[pid].holdings`, calls `renderGrandHeader()`
  (totals might have changed in some edge case), then POSTs.

**Tests:**
- `tests/frontend/portfolio-holdings-reorder.spec.mjs`:
  - ADDED `test("Γû▓/Γû╝ reorder persists across collapse + expand")` ΓÇö
    mock `reorderHoldings` to succeed. Set up a portfolio with holdings
    [NVDA, AAPL, MSFT]. Expand the portfolio. Click Γû▓ on AAPL. Collapse.
    Expand. Assert holdings are now [AAPL, NVDA, MSFT] (the new order,
    not the original).
  - ADDED `test("Γû▓/Γû╝ reorder preserves the cash row position across
    collapse + expand")` ΓÇö same shape with a cash row, verifying cash
    stays at the end.

### Verification

- `python -m pytest tests/test_service_cooldown.py tests/test_portfolio.py
  tests/test_api_contract.py` ΓåÆ **104 passed** in 6.84s.
- `npx playwright test --config=tests/frontend/playwright.config.mjs
  tests/frontend/portfolio-holdings-reorder.spec.mjs
  tests/frontend/refresh-cooldown.spec.mjs` ΓåÆ **19 passed** in 7.1s.

### Files touched (6)

`app/service.py`, `static/js/cards.js`, `static/js/portfolio.js`,
`tests/test_service_cooldown.py`, `tests/frontend/refresh-cooldown.spec.mjs`,
`tests/frontend/portfolio-holdings-reorder.spec.mjs`.

### Decision pointer

See `project_rules/DECISIONS.md` ΓåÆ
"Portfolio enrichment always runs (no cooldown skip) ΓÇö 2026-09-11".

### Archive

Full text in
`archive/sessions/2026-09-11-followup-fix-prices-collapse-reorder.md`.



---

# 2026-09-13 — Wiki-centric architecture adopted

**Summary:** Adopted `github.com/AgriciDaniel/claude-obsidian` as the
project's knowledge-base tool; ingested all 99 sources from
`project_rules/*.md`, `project_rules/archive/**/*.md`, `docs/logs/*.md`,
and `docs/superpowers/{plans,specs}/*.md` into the
`Market-Analysis-Wiki/` vault; restructured to a wiki-centric
architecture where source documents live at
`Market-Analysis-Wiki/raw/<dir>/<file>.md` (preserving the original
directory structure) and `AGENTS.md` is the only canonical rules
file (no separate `project-rules` skill).

## What shipped

**Phase 0 — Environment check.** WSL confirmed available
(`docker-desktop` default). The docker-desktop WSL distro has no
Python or bash, so Ubuntu 22.04 was installed via
`wsl --install -d Ubuntu-22.04 --no-launch` (admin required for WSL
install). Python 3.12.13 was installed via
`apt-get install python3.12 python3.12-venv` from the deadsnakes PPA.

**Phase 1 — Install and adopt.**
- Cloned `AgriciDaniel/claude-obsidian` to
  `C:\Users\Spirors\AppData\Local\Temp\opencode\claude-obsidian`
  (scratch location, NOT inside the vault — per the product's design
  that the source clone is not the vault).
- Adopted the existing vault via
  `python3.12 claude-obsidian.py adopt` (not `init` — the vault
  already existed with `.obsidian/` config). Approval SHA
  `d8af041ccc0f0b8d05870990868cac6e51c4eb05092d6ba2041517d8261cd08e`;
  applied 11 foundation files: `.claude-obsidian.json`,
  vault-local `.gitignore`, `.obsidian/snippets/vault-colors.css`,
  `.raw/.manifest.json`, `inbox/.gitkeep`, `wiki/{hot,index,log,overview}.md`,
  `wiki/meta/ledgers/{claim,source}-ledger.json`.
- Installed OpenCode integration via
  `bash scripts/setup-multi-agent.sh --host opencode --apply`
  (Git Bash on Windows — the bash script is POSIX-portable). 15
  skill symlinks created at `~/.config/opencode/skills/<name>`:
  autoresearch, canvas, defuddle, obsidian-bases, obsidian-markdown,
  save, think, wiki, wiki-cli, wiki-fold, wiki-ingest, wiki-lint,
  wiki-mode, wiki-query, wiki-retrieve. The 8 pre-existing
  skills were left untouched — installer's `--check` confirmed no
  conflicts.
- **WSL metadata workaround:** added
  `[automount] options = "metadata"` to `/etc/wsl.conf` and ran
  `wsl --shutdown`. Without this, `os.chmod()` is a no-op on
  `/mnt/c` and the adopt apply fails with `RESULT_DRIFT` (file
  created at mode 0o511 instead of the expected 0o600).

**Phase 2 — Organize sources.** The original plan was
`mklink /J` junctions from `Market-Analysis-Wiki/inbox/` to
`project_rules/` and `docs/`, but `capture.py` rejects junctions
(`SOURCE_SYMLINK` check — WSL sees Windows reparse points as
symlinks). The decision was to drop junctions and stage physical
copies into `inbox/`. 99 files copied: 9 from `project_rules/`
root, 26 from `archive/sessions/`, 47 from `archive/decisions/`,
17 from `docs/{logs,superpowers}/`. The `.gitignore` line
`Market-Analysis-Wiki/inbox/` was added.

**Phase 3 — Initial ingest.**
- `capture apply` with approval SHA
  `ab30cfa7c64a0e8f2cdb961bd7cee48c8adae6caa4f9dc6d1fbb6d7f7ad53062`
  created 99 content-addressed captures at
  `.raw/captured/<sha>.md`. Idempotency verified: re-running the
  plan produced `would_change: 0, skipped: 99, status: noop`.
- `transaction inspect` then `transaction apply` with approval SHA
  `9e7c2b70b87c5406c471fc019b9f1083bf59da2cc89f9d3b043f1df15de21e4b`
  wrote 102 vault files: 99 source pages at
  `wiki/sources/<slug>.md`, plus updated `wiki/{index,log,hot}.md`.
  `source_manifest_updates` on the bundle populates
  `.raw/.manifest.json` — do NOT write
  `wiki/meta/ledgers/source-ledger.json` directly (the engine
  manages it).
- **Wiki-ingest scope:** 4 parallel background explorer subagents
  read the 99 originals and produced source-page drafts as JSON.
  Groups: docs (17), project_rules root (9), archive/sessions (26),
  archive/decisions (47). Orchestrator aggregated the drafts,
  built the transaction bundle, applied via `transaction apply`.
  No concept/entity pages created — the wiki-ingest
  compilation-value gate filtered them out (most sources are
  point-in-time records, not durable synthesis).
- **Acceptance:** 5 sample SHA-256s matched pre-ingest values;
  HANDOFF wiki page shows the full citation chain
  (original_path + original_sha256 + stored_path); re-capture plan
  shows `would_change: 0` on all 99 items.

**Phase 4 — AGENTS.md Wiki section.** Added `## Wiki` between
`## Skills` and `## See also`, pointing at `wiki-ingest`,
`wiki-query`, `wiki-lint`, and noting the WSL requirement for
vault writes. Added `Wiki knowledge-base sync` bullet to the
hard-rules list.

**Phase 5 — Wiki-centric restructure.** User redirected
mid-phase from "strip Bootstrap/Retrofit" to: inline all Core
rules into AGENTS.md; move `project_rules/` and `docs/` to
`Market-Analysis-Wiki/raw/` preserving structure; remove
`.opencode/skills/project-rules/` entirely.
- `community-plugins.json` is already `[]` — no `karpathywiki`
  entry to remove (no-op).

## Architectural decisions

- **Wiki is canonical, raw/ is the working markdown store.**
  Future edits go to `Market-Analysis-Wiki/raw/<dir>/<file>.md`,
  then `wiki-ingest` folds the changes into
  `wiki/sources/<slug>.md`. Captures in `.raw/captured/<sha>.md`
  are immutable by content address — they only grow (or stay
  constant) as sources change.
- **Hard-rules live in AGENTS.md, not a separate skill.**
  Trade-off: every session reads ~390 lines upfront (vs ~141
  before). Per the Documentation Hygiene rule, this is acceptable
  for a "read in full, every time" file.
- **WSL is the only path that writes to the vault.** Native
  Windows fails closed (`os.name == "nt"` →
  `UNSUPPORTED_PLATFORM`). Read-only queries (capture plan,
  contract verify, doctor) work natively.

## Verification

- `python3.12 doctor --vault ...` → `ok: true`, all checks pass.
- Capture re-plan: `would_change: 0, skipped: 99, status: noop`
  (idempotent on unchanged sources).
- 5/5 sample originals verified SHA-256-unchanged after the entire
  ingest pipeline.

## Files touched (this session)

- **Created (vault):** `Market-Analysis-Wiki/{.claude-obsidian.json,
  .gitignore, .obsidian/snippets/vault-colors.css, .raw/.manifest.json,
  inbox/.gitkeep, wiki/{hot,index,log,overview}.md, wiki/meta/ledgers/
  {claim,source}-ledger.json, wiki/sources/<99 files>, .raw/captured/
  <99 files>, raw/{project_rules,docs}/<all files>}`
- **Modified:** `AGENTS.md` (rewritten, ~141 → ~390 lines,
  hard-rules inlined + paths updated), `.gitignore`
  (`Market-Analysis-Wiki/inbox/` added), `Market-Analysis-Wiki/raw/
  project_rules/HANDOFF.md` (this session's state appended),
  `Market-Analysis-Wiki/raw/project_rules/SESSION_LOG.md`
  (this entry)
- **Removed from repo (now in wiki only):** `project_rules/` (9 + 73
  archive files), `docs/` (18 files),
  `.opencode/skills/project-rules/` (skill + templates)

## Decision pointer

See `Market-Analysis-Wiki/raw/project_rules/DECISIONS.md` →
"Wiki-centric architecture adopted — originals relocated to
`Market-Analysis-Wiki/raw/`, hard-rules inlined in AGENTS.md,
`project-rules` skill removed (2026-09-13)".

## Notes for the next session

- **Don't run `wiki-query` until after wiki-lint passes.**
  wiki-lint is deterministic; wiki-query reads the same graph.
- **`source_manifest_updates` not direct ledger writes.** When
  building transaction bundles for ingest, use the
  `source_manifest_updates` field — the engine writes
  `.raw/.manifest.json` and the wiki/meta/ledgers/{source,claim}-
  ledger.json files from there. Writing the ledger JSON directly
  triggers `INVALID_PROVENANCE_LEDGER` because source IDs must be
  `src-<digest[:20]>` (not raw SHA-256) and each entry needs an
  `origin: {kind, locator}` object.
- **`os.chmod()` is a no-op on `/mnt/c` without `metadata` in
  `/etc/wsl.conf [automount] options`.** Any future WSL-based
  tooling that touches the vault needs this config.
- **The vault is `.gitignore`d by omission, not by an explicit
  rule.** Future agents should keep it that way. The whole
  `Market-Analysis-Wiki/` is local to this machine.

## Archive

Full text in
`archive/sessions/2026-09-13-wiki-centric-architecture-adopted.md`.
