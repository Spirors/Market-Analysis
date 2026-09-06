# Decisions

Durable, one-way-door(ish) decisions and confirmed root causes. Append new
entries; don't delete old ones even if later superseded — mark them
superseded instead, so the history of *why* stays intact. Newest at the
bottom.

The entries below were pulled out of `AGENTS.md`'s "Key quirks" and "Recent
activity" sections during the `docs/` split-out — they were always true,
just harder to scan in prose form.

---

## Market data: yfinance only, no secondary fallback (2026-08-23)

The former Stooq CSV fallback was removed because Stooq now serves a
JavaScript bot-wall to non-browser clients. There is currently no secondary
source for market data — failed fetches surface as `null` and are never
cached. Do not silently re-add a scraping-based fallback without confirming
it can survive non-browser access long-term; that's the exact failure mode
that killed Stooq.

## Hidden launchers: `wscript.exe` + VBS, not `pythonw.exe`

`pythonw.exe` (the GUI-subsystem Python launcher) tries to detach from the
parent console on startup; when that detach leaves OS console-handle state
inconsistent, `pythonw` silently aborts before binding. The working pattern
is `wscript.exe <vbs-script> python args...` with the VBS setting
`shell.Run "python args", 0, False` (`WindowStyle=0` = `SW_HIDE`, `False` =
don't wait). Used by both `launch.vbs` (desktop shortcut) and
`scheduler.vbs` (Windows Task Scheduler tasks). If a third hidden launcher
is ever needed, copy this pattern — do not reintroduce `pythonw.exe`.

## Commodities spot pricing: FRED + Minted Metal, not Yahoo quotes

Yahoo's `fast_info` is broken in current `yfinance` versions, so real
cash-market spot for the Commodities card comes from FRED public CSV
(energy) and Minted Metal public JSON (precious metals) instead, mapped
back onto the matching Yahoo futures ticker so the renderer doesn't need to
know the source family.

## Risk gauge design: divided signals = healthy, unanimous = fragility

In the archived `ai_market_sentiment_gauge.html`, a card's `col` is fixed
for layout; the signed `weight` is what moves the needle. `app/risk.py`
encodes the same intuition in code rather than layout: divided signals
across the 9 cross-asset inputs are healthy, unanimous optimism is the
fragility signal (RED fires on consensus optimism, not just bad numbers).
The gauge's ~70 events are also part of the news timeline seed
(`app/seed_data.py`), with direction mapped from its bear/neutral/bull
columns. Keep this framing in mind before "fixing" `app/risk.py` to fire on
raw bearishness — unanimous bearishness is not the RED trigger, unanimous
*optimism* is.

## Frozen reference files are not touched, ever

The four `ai_*.html` files at repo root are frozen reference material from a
prior project (they seeded the analysis framework and design system). Do not
modify them regardless of what else is being refactored.

## Hard-rule propagation: `project-rules` skill, not AGENTS.md alone

`AGENTS.md` auto-injects into the parent orchestrator's system prompt but
**not** into OMO-slim subagent sessions (`@fixer`, `@explorer`, `@oracle`,
`@designer`, etc.). Handing the rules through the dispatch prompt is the
only reliable cross-context path. The pattern:

1. Hard rules live in `.opencode/skills/project-rules/SKILL.md`.
2. `AGENTS.md` "During Work" instructs the orchestrator to invoke that
   skill (`skill` tool) before any subagent dispatch and include the
   output in the subagent's prompt string.
3. Subagents receive the rules as immediate task context, not as static
   background.

Keep the skill and AGENTS.md's "Hard rules" section in sync — they are
deliberately the same content in two places, because the skill survives
subagent dispatch while AGENTS.md survives session restart.

## Why Phase 1 ran ahead of Phase 0 (2026-09-06)

The roadmap's own rule is "don't start a Phase N+1 item while a Phase N
item is open," but the Phase 1 docs split (commits `52e5b92`, `8583711`)
went in while Phase 0 still had open bugs. The reason: Phase 0's open
bugs (`stuck-process`, `tickerTable.js` cross-section state) need durable
root-cause records that survive context resets, and the session-start
read-order + `docs/DECISIONS.md` + `docs/HANDOFF.md` + `docs/SESSION_LOG.md`
are exactly that mechanism. Diagnosing Phase 0 bugs without those docs in
place would re-introduce the "rediscover the failed approach the hard
way" failure mode. The Phase 0 work itself is still untouched and remains
the top of the next-actions list.

---

---

## OPEN — tickerTable.js shared-component persistence (2026-09-05) — CLOSED 2026-09-06

**Status:** confirmed + defensively fixed.

Investigation: per-section keys (`pfSort.{section}`, `pfVisible.{section}`,
`pfOrder.{section}`) are correctly namespaced in `static/js/tickerTable.js`.
The `column_order` / `column_visibility` backend storage in `app/api.py`'s
`columns_put` is also correctly keyed per-section (`state["column_order"][section]`).
The bug class warned about by AGENT-WORKFLOW-PROMPT.md §3b — "shared
component loses per-section namespacing" — did NOT occur; the refactor was
done correctly.

**Defensive fix:** `static/js/tickerTable.js` now exports a `VALID_SECTIONS`
allowlist (`["earnings", "portfolio"]`) and `_assertValidSection()` runs at
the top of every load/save helper plus `createTickerTable()`. An undefined
or unknown `section` prop throws immediately with a message pointing at
this rule, instead of silently templating `pfSort.undefined` /
`pfVisible.null` and dropping every preference change.

**Rule for future extractions:** "Shared UI components must take their
persistence key as a required prop, validated against an allowlist; never
let a shared component default or hardcode a storage key." Adding a new
section to `VALID_SECTIONS` requires a paired regression test in
`tests/frontend/section-position.spec.mjs` covering the new key.

Regression coverage: `tests/frontend/section-position.spec.mjs` (7 tests)
verifies Earnings/Portfolio isolation across all three persistence
channels (Sort / Visible / Order), reload round-trip, and that no bare
`pfOrder` / `pfVisible` / `pfSort` (no section suffix) keys exist.

## Shared component rebuilds controls subtree — listeners must be re-wired (2026-09-06)

**Status:** confirmed + fixed.

In `static/js/tickerTable.js`, `drawControls()` rebuilds the entire
`controlsSel` subtree via `el.innerHTML = ...` on every column reorder,
header sort, and reset-sort. The pre-fix `render()` entry point called
`drawControls(); wireAddInput(); drawBody()` — `wireAddInput()` was wired
ONCE. After the first column reorder, the freshly-created
`.tt-input` / `.tt-add-btn` had no event listeners, and the Add button
silently did nothing.

**Fix:** `wireAddInput()` now runs at the end of `drawControls()`. Every
controls rebuild re-attaches the input/button listeners. Listeners
attach to fresh DOM nodes; the discarded elements (and their listeners)
are GC'd naturally — no leak.

**Rule for future shared components:** "Any shared component that
rebuilds a subtree containing interactive elements (inputs, buttons)
must re-wire those elements' listeners inside the rebuild path — not
rely on a one-shot setup call. Event delegation on a stable container
is the safer alternative if the rebuild happens often."

Regression coverage: `tests/frontend/watchlist-add.spec.mjs` (8 tests)
covers the add flow under: initial render, column reorder, header sort,
visibility toggle, multiple back-to-back reorders, Enter-key, and
input-validation (disabled when empty / whitespace-only).

## Portfolio name input must size to content, not fill the header (2026-09-06)

**Status:** confirmed + fixed.

Pre-fix `.pf-name-input` had `flex: 1; min-width: 0;` which stretched the
inline rename input to ~87% of `.pf-pf-header` width on a typical desktop
layout (measured at 1027 / 1184 px). The surrounding empty space inside
the header was too narrow to hit, so users couldn't easily click outside
the input to blur/commit it.

**Fix:** `static/style.css` switches `.pf-name-input` to
`flex: 0 0 auto; width: auto; min-width: 160px; max-width: 100%`. The
input now sizes to its content while staying usable on narrow headers
(mobile / sidebar collapse).

**Rule for inline-rename / inline-edit inputs in flex containers:**
"Don't default to `flex: 1` for transient edit inputs — size to content
so the surrounding container area remains clickable for the
click-outside-to-blur UX pattern users expect."

Regression coverage: `tests/frontend/portfolio-name-input.spec.mjs` (3
tests) asserts the input width ratio stays under 50% of header width,
plus the single-line + click-outside-to-blur + Enter-saves UX behaviors.

## Stuck process on test launch — root cause + runtime fix (2026-09-06)

**Status:** confirmed + fixed in this session. Runtime backstop shipped in
`app/lifecycle.py`; CLI flag `--auto-reap` and the matching env var
`MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S` documented in `docs/RUNBOOK.md`.

**Trigger observed:** an interactive session launched `python run.py
--open-browser` at 14:20 local on 2026-09-06 to test a dashboard change.
The session ended before the documented reap step (runbook §Step 3). The
python child stayed bound to `127.0.0.1:8000` for 54+ minutes until a
later session noticed `Test-NetConnection -Port 8000 = True` while
`Get-Process python` returned the orphaned PID.

**Root cause:** the `launch-test-reap` cycle is documented in `AGENTS.md`
and `docs/RUNBOOK.md` but enforcement is purely procedural — an agent that
forgets to reap (or whose turn ends before the reap step) leaks a
python.exe with no runtime backstop. The previous scheduler fix
(`cc7f476`) made the *launch* side reliable (pythonw ban, lockfile,
PID-liveness check) but did not address the *reap* side.

**Fix (runtime backstop):** `app/lifecycle.py` provides:

- `write_server_pid_file()` — at startup, record this process's PID,
  parent PID, and start time under `data/server.pid`. Rewritten on every
  launch so a stale entry never blocks the next session. Lets the next
  session locate (and `Stop-Process`) a stray instance immediately.
- `remove_server_pid_file()` — best-effort cleanup on `/api/shutdown`
  and via `atexit`. Refuses to unlink a file belonging to a different
  PID so we never silently hide a previous orphan.
- `start_auto_reap_watchdog(timeout_after_parent_dead_s)` — daemon
  thread that polls the launching parent PID via
  `app.lockfile._pid_alive` and calls `os._exit(0)` once the parent has
  been gone for the configured grace period. Default 0 = disabled, so
  desktop launches (where the parent is `wscript.exe` which dies only
  when python exits) are unaffected. Agent terminal launches pass
  `--auto-reap 60` (or set the env var) so a forgotten reap turns into
  "agent reaps itself" once the launching shell exits.

**Runbook additions (see `docs/RUNBOOK.md`):**

- Agent terminal launches must use `python run.py --auto-reap 60` (or
  set `$env:MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S=60`). The number is
  the grace period after the parent process dies — 60s is enough that a
  normal interactive session is never affected, low enough that a leaked
  server doesn't linger.
- Desktop `.lnk` launches leave `--auto-reap` at 0 (default). The
  server's normal lifecycle is `launch.vbs` (waits) → python → browser
  → `/api/shutdown` → exit, with `wscript.exe` as python's parent for
  the whole session. The watchdog would never see the parent die during
  a normal user session.

**Regression test:** `tests/test_lifecycle.py` (13 tests) and
`tests/test_run.py` (6 new tests) cover the watchdog, the pid-file
helpers, the CLI flag, the env var fallback, the atexit cleanup, and
the `/api/shutdown` pid-file cleanup. Red-green verified: with the
fix reverted, `test_shutdown_endpoint_removes_server_pid` fails.

## Portfolio mutations must patch the cached dashboard payload (2026-09-06)

**Status:** confirmed + fixed (commit `b45858e`).

Pre-fix `app/portfolio.py` mutations (create/delete/rename portfolio,
add/edit/remove holding, add/edit/remove cash row) all wrote
`data/portfolios.json` correctly but never touched
`data/dashboard.json`. `service.get_dashboard` (app/service.py:283)
served the cached `dashboard.json` (with its embedded `portfolios`
sub-tree) until `QUOTE_TTL` expired or the in-page Refresh button
forced a full rebuild. Net effect: every portfolio mutation appeared
to silently fail until a manual Refresh, and the only "delete" that
"worked" was a phantom delete via stale cache + retry that produced a
404. The 44 stray "Test*" portfolios in `data/portfolios.json` were
the visible residue of this bug.

The reference pattern is `app/earnings.py:254-266` (add_ticker) and
`:283-291` (remove_ticker): after mutating `data/watchlist.json`,
patch `data/cache/earnings.json` in place via `store.save_json`. The
Portfolio module now follows the same shape with a new
`_patch_dashboard_cache(state)` helper (app/portfolio.py) called
after every `save_portfolios(state)`.

**Rule for future mutations:** Any new mutation function added to
`app/portfolio.py` MUST call `_patch_dashboard_cache(state)` after
saving, or it will re-introduce this exact bug. Extending the
regression test in `tests/test_portfolio_cache_sync.py` is the
mechanical reminder.

**Helper semantics:** best-effort — wraps the whole patch in a
`try/except` that silently returns on any failure. A failed patch
means the user sees stale data until QUOTE_TTL expires (same as
pre-fix), never a hard error. The patch updates
`cached["portfolios"]` with the freshly-enriched
(`enrich_portfolios` + `enrich_portfolios_with_earnings`) state and
bumps `vintage["portfolios"]` so the per-card "As of" stamp reflects
the mutation time.

## Per-portfolio scope must use composite keys, not nested Maps (2026-09-06)

**Status:** confirmed + fixed (commit `1fafbc1`).

Pre-fix `static/js/watchColors.js` used a single Map keyed by symbol
only for the Portfolio section's star state. Starring NVDA in
"Fidelity Main" also starred NVDA in "Fidelity Roth IRA" because the
Map was shared across every portfolio. Same bug class as the Phase 0
tickerTable.js per-section key bug (commit 94442b6 follow-ups) but
on a different axis: portfolio-id vs section.

The fix uses composite `"<pid>::<sym>"` keys in the SAME flat Map,
not a nested `Map<pid, Map<sym, color>>` structure. The composite-key
approach keeps the localStorage serialization flat, stays compatible
with the existing `saveWatchColors` / `loadSection` infrastructure,
and means the storage key (`pfWatchColors`) is unchanged — only the
value shape evolved.

**Rule for future per-section per-entity scope:** When adding
per-(section, entity) persistence (e.g. per-portfolio, per-strategy,
per-watchlist), use a composite key inside the same Map rather than
a nested Map. Define the composite key format in `watchColors.js`
(or its successor), expose `get*(entity, key)` / `set*(entity, key,
value)` helpers, and keep the internal key shape private to that
module.

**Per-section opt-in:** the `SECTIONS` config table now carries a
`keyBy` field (`"symbol"` for Earnings, `"portfolio"` for Portfolio).
When adding a third section that needs a different scope axis (e.g.
per-strategy, per-watchlist), add a new `keyBy` value and a parallel
set of helpers — don't extend the existing two.

## Every `[data-card]` in index.html must also appear in CARD_BAND (2026-09-06)

**Status:** confirmed + fixed (commit `6825c0f`).

Pre-fix `static/js/layout.js:14-30` `CARD_BAND` map was missing the
`"portfolio"` entry. The `<section data-card="portfolio">` was added
to `static/index.html` in commit `1589aaf` but the layout map was
never updated. `persistLayoutFromDOM()` (layout.js:124) saved layouts
containing `"portfolio"` (it's in the DOM), but `applyLayoutOnLoad()`'s
guard at line 78 silently rejected any saved layout containing an
unknown card id. Every F5 reverted to HTML source order with no error
or warning.

**Root cause family:** This is the same shape of bug as the Phase 0
tickerTable.js cross-section state bug — two consumers (here: persist
vs apply) where one allows an item and the other rejects it silently.
The fix made the persistence side filter to only known cards (now
both sides agree on the allowlist). For tickerTable.js the defensive
fix was `VALID_SECTIONS` allowlist + `_assertValidSection()` guard;
for layout.js the existing `known` Set check at line 78 was already
correct, it was just incomplete — the data side needed updating.

**Rule for new dashboard cards:** Any new `<section data-card="...">`
added to `static/index.html` MUST be added to `CARD_BAND` in
`static/js/layout.js:14-30` in the same change. There is now a
regression test (`tests/frontend/dash-layout-survives-reload.spec.mjs`)
that checks `CARD_BAND` includes every `[data-card]` in
`index.html` — extending either side without the other will fail the
test.

## validate_symbol must distinguish "yfinance unavailable" from "no profile" (2026-09-06)

**Status:** confirmed + fixed (commit `a2c793a`).

Pre-fix `app/earnings.py:68-89` `validate_symbol()` made two
sequential yfinance calls (`_yf_info` and `_validate_by_history`
fallback). Both wrappers caught exceptions silently with
`except Exception: return {}` / `return []`. On rate-limit (very
common when validating several tickers in quick succession), both
calls failed and the user saw "invalid symbol" when the real problem
was "yfinance unavailable."

**Two-axis fix:**
1. Distinguish network errors from genuinely-invalid symbols in the
   `reason` field so the frontend can show a meaningful error.
2. Don't make two sequential yfinance calls when one suffices — the
   first call's sparse-info check (`_CONFIRMATION_FIELDS`:
   exchange/currency/quoteType/regularMarketPrice) accepts symbols
   even without `longName`, so the history fallback is rarely needed.
   Reducing 2 calls per validation to ~1 reduces rate-limit pressure.

**Plus a retry-with-1s-backoff** on transient network errors
(`requests.exceptions` family, `yfinance.YFRateLimitError`), and a
60s TTL `lru_cache` to absorb bursts (e.g. validating 5 tickers in a
row calls yfinance 5× in 30 seconds today — cached, it's 5 in 60+
seconds).

**Rule for any future yfinance wrapper:** Network errors must be
distinguishable from "yfinance returned empty." `_yf_info` now
returns `(dict, error_str)` so callers can branch on `error_str`.
The next wrapper that needs a "transient, retry once" path should
use `_yf_info_with_retry()` as the template.

**LSP note:** The 12 new mocked tests in `tests/test_earnings.py`
intentionally call `validate_symbol(None)` to verify the empty-input
path. The function signature `def validate_symbol(sym: str)` types
`sym` as `str` but the runtime handles `None` via `(sym or "").strip()`
— the test exercises that defensive behavior. LSP flags this as a
type mismatch; the runtime is correct. A future cleanup could
broaden the signature to `sym: str | None`, but it's a cosmetic
change, not a correctness fix.
