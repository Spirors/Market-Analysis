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
read-order + `project_rules/DECISIONS.md` + `project_rules/HANDOFF.md` + `project_rules/SESSION_LOG.md`
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

**Status:** confirmed + fixed. **Superseded refinement:**
2026-09-06 entry below — `min-width: 160px` had a layout-shift bug
for SHORT names (e.g. "IRA", 3 chars), since the fixed pixel floor was
wider than the rendered title. Replaced with `field-sizing: content`
+ `min-width: 8ch`.

Pre-fix `.pf-name-input` had `flex: 1; min-width: 0;` which stretched the
inline rename input to ~87% of `.pf-pf-header` width on a typical desktop
layout (measured at 1027 / 1184 px). The surrounding empty space inside
the header was too narrow to hit, so users couldn't easily click outside
the input to blur/commit it.

**Fix (commit `4716e02`, refined `974d988`):** `static/style.css` switched
`.pf-name-input` to `flex: 0 0 auto; width: auto; min-width: 160px;
max-width: 100%`. The input sizes to its content while staying usable on
narrow headers (mobile / sidebar collapse).

**Rule for inline-rename / inline-edit inputs in flex containers:**
"Don't default to `flex: 1` for transient edit inputs — size to content
so the surrounding container area remains clickable for the
click-outside-to-blur UX pattern users expect."

Regression coverage: `tests/frontend/portfolio-name-input.spec.mjs` (3
tests) asserts the input width ratio stays under 50% of header width,
plus the single-line + click-outside-to-blur + Enter-saves UX behaviors.

## Portfolio name input — use `field-sizing: content`, not a pixel floor (2026-09-06)

**Status:** confirmed + fixed. Supersedes the `min-width: 160px` fix above.

**Problem:** the previous `min-width: 160px` introduced a layout-shift
bug for SHORT names — "IRA" rendered at ~30px (title) but the input
stayed at 160px (fixed pixel floor), shoving pencil / totals / close
~130px right.

**Fix:** swap `min-width: 160px` for `field-sizing: content` plus
`min-width: 8ch` (character-width floor). Input sizes to its content
+ padding/border (~74px for "IRA" at 13px font). Supported Chrome 123+,
Firefox 122+, Safari 17.5+; older browsers fall back to intrinsic 20-char
size — same as the old behaviour, no regression.

**Why not `max(min-content, 8ch)` (original plan):** CSS `max()` doesn't
compose with `field-sizing: content` — the browser ignores the formula and
uses the content-sized width regardless. Once `field-sizing: content` is
the sizing mechanism, `min-width` is just a hard lower bound, not a
formula input.

**Rule:** for inline-rename / inline-edit inputs, use
`field-sizing: content` with `min-width: <ch>` as the usability floor
(NOT a fixed pixel value). Fixed pixel floors regress for SHORT values —
character widths scale with font size and are robust across name lengths.

Regression coverage: `tests/frontend/portfolio-name-input.spec.mjs` +2
tests (short-name width `<130px`, no pre-`4716e02` stretch). Both fail
on the reverted code; the existing 3 tests pass (they use "Fidelity
Main" where content > 160px and didn't catch the regression).


## Stuck process on test launch — root cause + runtime fix (2026-09-06)

**Status:** confirmed + fixed. Runtime backstop in `app/lifecycle.py`;
CLI flag `--auto-reap` + env var `MARKET_ANALYSIS_AUTO_REAP_PARENT_DEAD_S`
documented in `project_rules/RUNBOOK.md`.

**Trigger:** an interactive launch of `python run.py --open-browser`
on 2026-09-06 ended the turn before the reap step. The python child
stayed bound to `127.0.0.1:8000` for 54+ minutes until a later session
noticed `Test-NetConnection -Port 8000 = True`.

**Root cause:** `launch-test-reap` was purely procedural — no runtime
backstop. The previous scheduler fix (`cc7f476`) hardened the *launch*
side (pythonw ban, lockfile, PID liveness) but not the *reap* side.

**Fix (`app/lifecycle.py`):**

- `write_server_pid_file()` — records pid / parent_pid / started at
  startup under `data/server.pid`. Lets the next session locate a stray
  instance immediately.
- `remove_server_pid_file()` — best-effort cleanup on `/api/shutdown` +
  `atexit`. Refuses to unlink a foreign pid so a previous orphan isn't
  silently hidden.
- `start_auto_reap_watchdog(s)` — daemon thread polls parent PID via
  `app.lockfile._pid_alive` and `os._exit(0)` once the parent has been
  gone for the configured grace. Default 0 = disabled (desktop launches
  where parent is `wscript.exe`). Agent terminals pass `--auto-reap 60`
  so a forgotten reap becomes "agent reaps itself".

**Runbook additions (see `project_rules/RUNBOOK.md`):**

- Agent terminal launches MUST use `--auto-reap 60` (or the env var).
- Desktop `.lnk` launches leave `--auto-reap` at 0 (normal lifecycle is
  `launch.vbs` → python → browser → `/api/shutdown` → exit with
  `wscript.exe` as parent for the whole session).

Regression coverage: `tests/test_lifecycle.py` (13 tests) +
`tests/test_run.py` (6 new) cover the watchdog, pid-file helpers, CLI
flag, env-var fallback, atexit cleanup, `/api/shutdown` pid-file cleanup.
Red-green verified: with the fix reverted,
`test_shutdown_endpoint_removes_server_pid` fails.

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

## Earnings cache-miss path must not trigger a full universe rebuild (2026-09-06)

**Status:** confirmed + fixed (commit `80d0fef`).

Pre-fix `app/earnings.py:add_ticker` (lines 304-345) fell through to
`earnings_calendar()` (which fetches yfinance for EVERY ticker in the
universe, ~30-60 seconds) when `_cached_calendar()` returned None
(cache missing or beyond `EARNINGS_TTL`). The frontend's
`addEarningsSymbol` fetch at `static/js/api.js:199-203` has no
explicit timeout and just awaits — the user clicked Add, saw no
progress, hit F5, by then the rebuild completed and the ticker
appeared. The earlier `a2c793a` `validate_symbol` retry fix
couldn't help because validation succeeded; the hang was in the
post-validation cache-rebuild path.

This regression re-introduced the exact failure mode the earlier
"validate_symbol distinguishes network errors" decision
(`a2c793a`) was trying to prevent — a user-visible hang that masks
itself as a different bug (invalid symbol) when yfinance is slow.

**Fix:** When the cache is missing, build just the new ticker's
enriched row via `_enrich(sym, quotes)` and write a minimal cache
with just that ticker. `remove_ticker` similarly invalidates the
cache instead of rebuilding. The user's earnings watchlist is the
source of truth for what they care about; the full universe
rebuild is owned by the section's Refresh button + scheduled task.

**Rule for cache-patching helpers:** When patching a cache after a
mutation, don't fall through to a full rebuild if the cache is
missing. Either build the minimal affected state inline, or
invalidate and return what you have. A full rebuild should only
run from explicit user action (Refresh button) or the scheduled
task — never from an additive mutation's side-effect.

**Plus UX fix:** `static/js/tickerTable.js:402-411` `tryAdd` now
shows "Adding…" + disabled state on the Add button during the
request, so even if the request takes a few seconds the user gets
feedback. `finally` re-enables the button and resets the label.

## Rename input must not bubble clicks to header (2026-09-06)

**Status:** confirmed + fixed (commit `974d988`).

Pre-fix `static/js/portfolio.js:200-207` header click handler's
skip list was `.pf-rename-btn, .pf-del, .pf-caret, .pf-pf-totals` —
missing `.pf-name-input`. When the user clicked inside the rename
input, the click bubbled up to the header handler and toggled
collapse, destroying the input mid-rename. Same root cause family
as the earlier Phase 0 "shared component cross-section state" bug
but on a different axis (event bubbling vs shared state).

**Fix (defense in depth):**
1. Added `.pf-name-input` to the skip list at line 202.
2. Added `e.stopPropagation()` on the input's click/focus/keydown
   handlers as belt-and-suspenders.

Either alone would suffice; both together prevent the next variant
of the same bug (e.g. if someone adds another child element to the
header without updating the skip list).

**Rule for inline-edit controls inside clickable containers:** When
a click handler on a parent toggles state, every interactive
descendant (inputs, dropdowns) MUST either be in the parent's
explicit skip list OR call `stopPropagation` on its own events.
Belt-and-suspenders — both, never just one.

**Plus CSS fix:** `.pf-rename-btn` in `static/style.css:1223` was
inheriting `font-weight: 600` and `border-radius: 6px` from the
generic `.mini` class while overriding `padding` to `0 4px`,
producing an oversized button that pushed the header layout.
Rewrote to `flex: 0 0 auto; font-size: 14px; font-weight: normal;
opacity: 0.6` (full opacity on hover/focus) — icon-only button
that fits naturally inline with the rename input.

**Rule for icon-only buttons sharing a generic button class:** When
adding a new icon-only button to a layout, do NOT rely on a generic
button class (`.mini`, `.btn`, etc.) for the base. Either define
the icon button as its own class with all required properties
explicit, or scope the generic class's properties via a more
specific selector.

## Card-level totals must refresh after any sub-table mutation (2026-09-06)

**Status:** confirmed + fixed (commit `8f3a82e`).

Pre-fix `static/js/portfolio.js:289-305` tickerTable callbacks for
per-holding add/remove/edit mutated the local `p.holdings` closure
and returned rows for the per-table totals row to update — but
`renderGrandHeader()` (which paints the card-level "$X (+Y)" total)
was never called. Only the per-table totals row updated; the card
header stayed stale until the user triggered a full reload. Same
bug class as the earlier Phase 0 "dashboard cache stale after
mutation" (commit `b45858e`) but on a different layer: the
table-internal render fired, the card-internal render did not.

**Fix:** Added `renderGrandHeader()` calls after every addRow,
removeRow, editCell mutation so the card header totals refresh
synchronously with the per-table updates.

**Rule for any per-table mutation callback in a card with a
card-level aggregate (header total, footer count, etc.):** The
callback MUST also re-render the card-level aggregate after the
mutation. Don't rely on a top-level `refresh()` to cascade —
top-level refreshes only fire on explicit user action (Refresh
button, F5), and per-table mutations should be self-contained.

**Generalization:** This same pattern likely applies to other
sections (Bottleneck, Indicators, Breadth cards) that have a
header-level aggregate computed from a table body. Audit each
section's render functions for "table body updates but header
total doesn't" before shipping the Phase 2 codebase health audit.

---

## Phase 2 audit — stale-on-reload cluster classification (2026-09-06)

**Status:** audit complete; classification decided; refactor pass landed
in commit `b45858e`. This entry exists so a future session doesn't
re-derive the classification from scratch.

**Cluster observed:** add/delete a row inside a portfolio writes
server-side, but a plain reload shows stale state while the in-page
Refresh button brings it current. Same for whole-portfolio add/delete
and rename. Repro: add/delete row → `data/portfolios.json` reflects →
plain reload shows pre-mutation state → click Refresh → current.

**Classification — two separate issues, NOT the same root cause:**

1. **Dashboard-cache staleness** (the actual cluster). Pre-fix
   `app/portfolio.py` mutations wrote `data/portfolios.json` correctly
   but never touched `data/dashboard.json`. `service.get_dashboard`
   served the cached `dashboard.json` (with embedded `portfolios`
   sub-tree) until `QUOTE_TTL` expired. **Fixed by `b45858e`** — new
   `_patch_dashboard_cache(state)` helper called after
   `save_portfolios(state)` in all 9 mutation functions. Mirrors
   `app/earnings.py`'s existing `EARNINGS_CACHE_PATH` patching pattern.

2. **`tickerTable.js` shared-component state namespacing** (NOT this
   cluster). Per-section localStorage key bug class. Fixed in `94442b6`
   follow-ups via `VALID_SECTIONS` allowlist + `_assertValidSection()`.
   Different bug, different file, different surface.

**Refactor pass (Phase 2 #2) — already landed in `b45858e`.** The
unification the ROADMAP bullet called for is exactly what `b45858e`
does. Both modules now share the same pattern (write source-of-truth
JSON → patch cached payload → bump `vintage[<key>]` → best-effort
try/except). The 5-test regression suite in
`tests/test_portfolio_cache_sync.py` covers add/remove holding +
add/delete portfolio through TestClient — extend for any new mutation
type.

**Remaining debt surfaced by the audit (none blocking):**

- No `tickerTable.js`-style "shared component consumed by 2+ sections
  with independently-keyed persisted state" candidate beyond the
  existing per-portfolio star scoping (`getPortfolioWatchColor(pid,
  sym)`, commit `1fafbc1`). The audit bullet found no other candidates.
- Cache-invalidation shape is consistent across `earnings` and
  `portfolio`. Template for any future module:
  `save_<thing>(state)` → `_patch_<cache>_cache(state)` (reads cached
  payload, replaces sub-tree, bumps `vintage[<key>]`, writes via
  `store.save_json`, wrap in try/except so a failed patch degrades to
  "stale until QUOTE_TTL").

**Conclusion:** Phase 2 #1 + #2 effectively done — `b45858e` lands the
unification. No new commits required. Future sessions should treat the
existing `_patch_dashboard_cache(state)` helper as the template for any
new module's cache-invalidation logic.

---

## Phase 2 audit — earnings `validate_symbol` path diff (2026-09-06)

**Status:** root cause confirmed; fix landed in the same commit
(per the SESSION_LOG of 2026-09-06).

**Bug repro:** entering "NVDA" into the Earnings Watchlist Add field
returns "invalid symbol."

**Path diff — earnings vs portfolio yfinance surfaces:** the two call
paths hit *different* yfinance endpoints. Portfolio enrichment uses the
bulk-download surface (`yf.download`, documented in `app/market.py:97-98`
as "reliable in yfinance 1.6.0"). Earnings validation used the per-symbol
info surface (`yf.Ticker.info`), which is rate-limited independently of
symbol validity by Yahoo.

```
Portfolio enrichment (works for NVDA, AAPL, …):
  GET /api/dashboard → service._enrich → enrich_portfolios
    → market._quote_snapshot(symbols)
      → yf.download(symbols, period="7d", group_by="column")   [BULK]
  (app/portfolio.py:284, 361; app/market.py:94-130)

Earnings validation (fails for NVDA when Yahoo rate-limits):
  POST /api/earnings/watchlist → earnings.add_ticker
    → earnings.validate_symbol
      → _validate_uncached
        → _yf_info_with_retry → _yf_info
          → yf.Ticker(sym).info                                [PER-SYMBOL]
        → fallback: market.get_history(sym, days=5)
          → yf.download(symbol, period="5d")                   [BULK]
  (app/earnings.py:106-131, 56-89)
```

The pre-fix `validate_symbol` (`a2c793a` predecessor) called *both*
`Ticker.info` AND history in sequence and silently swallowed exceptions
in both wrappers, so a rate-limit hit both surfaces and produced
`valid: False`.

**Reproduction (mocked yfinance, no network):** four scenarios, `yf.Ticker`
+ `yf.download` both mocked, cache cleared between scenarios:

| Scenario | Ticker.info | yf.download | CURRENT result |
|---|---|---|---|
| A (live happy) | full dict | works | `valid=True, name="NVIDIA Corporation", sector="Technology"` |
| B (rate-limit) | empty | works | `valid=True, name="NVDA", sector=None` |
| C (full outage) | empty | empty | **`valid=False, reason="no yfinance profile and no price history found for NVDA"`** (THE BUG) |
| D (info only) | works | empty | `valid=True, name="NVIDIA Corporation", sector="Technology"` |

Scenario C reproduces the bug; B/D explain why it's intermittent (one
surface still working lets the fallback rescue). C fires when *both*
are rate-limited.

**Why `a2c793a` didn't stick:** earlier fix added retry-with-1s-backoff
+ 60s LRU around `Ticker.info`, but kept `Ticker.info` as PRIMARY.
Retrying a fundamentally-flaky call just delays the user's verdict by
1s. The right shape of fix is to validate existence the same way
portfolio already does successfully — not add retry/error-handling
around a flaky call.

**Fix:** `_validate_uncached` now uses `market.get_history(sym, days=5)`
(bulk-download, same as portfolio) as PRIMARY. `Ticker.info` becomes
SECONDARY (no retry). Same verdicts in every scenario, but the common
rate-limit case (B) now succeeds without depending on the fallback
rescue, and the full-outage case (C) is still caught. Removed
`_yf_info_with_retry`; kept the `_yf_info` `(dict, error_str)` shape
so "yfinance unavailable" vs "symbol genuinely not found" still
surfaces to the user.

**Regression coverage:** new tests in `tests/test_earnings.py` mock
`market.get_history` + `yf.Ticker` independently — no network, no rate
limit dependency. All four scenarios + `add_ticker` + `add_holding`
paths.

---

## Earnings watchlist section removed (2026-09-06)

**Status:** confirmed + removed.

**Scope chosen:** strip everything except `validate_symbol` (which
`portfolio.add_holding` still uses to reject invalid symbols). Rejected
"UI only" and "UI + keep backend enrichment" — both would have left a
thin backend wrapper for a section nobody used.

**What was removed:**

- `app/earnings.py` (530 lines) — `add_ticker`, `remove_ticker`,
  `earnings_calendar`, `earnings_force_refresh`, `_enrich`, `_ai_rec`,
  `_ticker_calendar`, `cached_payload`, `_has_usable_prices`, the
  watchlist/removed JSON helpers, and the `EARNINGS_CACHE_PATH`
  filesystem artifact.
- `app/validation.py` (NEW, ~155 lines) — extracted `validate_symbol`
  + its dependencies (`_yf_info`, `_validate_uncached`,
  `_validate_cached`, `_cache_bucket`, `_TICKER_RE`,
  `_CONFIRMATION_FIELDS`). This module is the small footprint that
  survives the removal.
- `app/api.py` — four endpoints gone (`GET /api/earnings`,
  `GET /api/earnings/validate`, `POST /api/earnings/watchlist`,
  `DELETE /api/earnings/watchlist`) plus the `with_earnings` query
  param on `GET /api/portfolios`.
- `app/portfolio.py` — `enrich_portfolios_with_earnings` and the
  `_EARNINGS_FIELDS` constant are gone. `add_holding` calls
  `validation.validate_symbol` directly.
- `app/config.py` — `EARNINGS_TTL`, `EARNINGS_UNIVERSE`,
  `VALUATION_STRETCH_PE`, `AI_SENTIMENT_VALUATION_PENALTY` are gone.
  `RISK_SIGNAL_TOTAL` adjusted from 9 to 8. `EARNINGS` as a
  `FINANCE_KEYWORDS` string stays (still a finance-relevance signal
  for news classification).
- `app/service.py` — `refresh_earnings`, the `earnings` payload field,
  the `earnings` coverage entry, and the earnings arg passed through
  `compute_risk` / `compute_ai_sentiment` are gone.
- `app/risk.py` — `_valuation_stretched` and `_signal_valuation` are
  gone. Risk engine no longer reads any earnings-derived data.
- `app/ai_sentiment.py` — `compute_valuation_flag` is gone. Forward-PE
  references in the synthesis pipeline are removed.
- `app/analysis.py` — `earnings_recs` signal gone from the weight
  table. `_WEIGHTS` is now 9 entries summing to 13 (was 10 / 14).
- `app/news.py` — `config.EARNINGS_UNIVERSE` dropped from the ticker
  set (mega-caps already covered by `AI_CAPEX_COHORTS`).
- Frontend (`static/index.html`, `static/js/earnings.js` deleted,
  cards.js, api.js, portfolio.js, tickerTable.js, watchColors.js,
  layout.js) — all earnings column defs, section rendering, API
  helpers, watchColors section, CARD_BAND entry removed.
- 8 earnings-derived columns stripped from the Portfolio table
  (next_earnings, pct_7d, high_52w, forward_pe, forward_peg,
  market_cap_fmt, sector, AI rec).

**Rule for future sections:** if a dashboard section's only reason for
existing is the data the section itself fetches, removing the section
means removing the data fetch too. Don't keep a thin backend wrapper
"just in case" — `validate_symbol` is the *right* kind of thin wrapper
to keep (it's used by another section); the rest of the earnings module
wasn't.

---

## Portfolio rename input — match width to span (2026-09-06)

**Status:** confirmed + fixed.

**Bug:** entering rename mode for a portfolio visibly shifted the
pencil icon ✎, totals ($X (+Y)), and close button ✕ ~25-30px to the
LEFT.  The span had `flex: 1` (grew to fill available header space);
the input had `field-sizing: content` (sized to text only).  The
input was narrower than the span was, so the elements to its right
shifted left.

**Fix:** `static/js/portfolio.js startEditForPid` now measures the
span's box width via `getBoundingClientRect()` BEFORE swapping in the
input and sets `inp.style.minWidth = ${spanWidth}px`.  The input box
matches the span's outer edge exactly, so the pencil / totals /
close button keep their position.  The plain `min-width: 8ch` CSS
floor (added in commit `55400a9`) stays as the accessibility floor
for a 1-2 char name.

**Why JS rather than CSS:** CSS `field-sizing: content` doesn't
expose a "match a sibling" mode; the alternatives are `width:
100%` (stretches beyond span when the flex container has extra space),
`width: max-content` (returns the input's intrinsic 20-char width
~160px), or `width: fit-content` (caps at container width but
doesn't match span).  Measuring in JS is the only way to get an
exact match without re-introducing the `flex: 1` stretch behavior
that the prior fix in commit `4716e02` was trying to avoid.

**Trade-off:** the input is now wide (~500-1000px on desktop) for a
3-char name like "IRA", whereas pre-fix it was ~74px content-sized.
The visual benefit (no shift) outweighs the compactness cost.

**Regression coverage:** `tests/frontend/portfolio-name-input.spec.mjs`
asserts the actual no-shift property (pencil / totals / close button
x-position unchanged between span and input states, with 1px slack
for sub-pixel rendering) plus the structural anti-reverts (`flex:
0 0 auto`, `field-sizing: content`, `min-width` not "160px").
Red-green verified with the fix reverted.




## Portfolio columns restored + per-portfolio state (2026-09-07)

**Status:** confirmed + shipped (commits `75b7c70` + `a8b60d2`).

**Request:** bring back the 8 columns the Earnings watchlist removal
had stripped from the Portfolio table (7-day %, 30-day %, Earnings
date, Marketcap, Forward PE, Forward PEG, 52W high, Sector) AND make
column settings independent per portfolio.

**Data sources (per "never fabricate" rule):**

| Column | Source |
|---|---|
| pct_7d, pct_30d, high_52w | `market.get_histories_bulk(symbols, days=260)` — one bulk yfinance download |
| sector, marketcap, forward_pe, forward_peg | `Ticker.info` per symbol |
| next_earnings | `Ticker.calendar` per symbol |

Per-symbol fetches cached via `functools.lru_cache(maxsize=128)` keyed
by `(symbol_upper, time_bucket)` where `bucket = int(time.time() // 300)`
(5 minutes). Cold-cache cost is one HTTP per unique symbol; warm-cache
is instant. Single `Ticker` instance shared between info + calendar to
avoid the 2-fetch pattern the old `app.earnings` had.

**Per-portfolio column state:** previous design used a single shared
`pfVisible.portfolio` / `pfOrder.portfolio` localStorage key — hiding
7-day % in Fidelity Cash also hid it in Roth IRA. New design namespaces
by `portfolio.<pid>`:

- `pfVisible.portfolio.<pid>` / `pfOrder.portfolio.<pid>`
- `pfSort.portfolio.<pid>`
- backend `column_order['portfolio.<pid>']` /
  `column_visibility['portfolio.<pid>']`

The bare `portfolio` key remains the default that new portfolios
inherit; existing portfolios continue to work. Two portfolios can show
different columns; hiding/showing one column in Portfolio A never
affects Portfolio B.

**`tickerTable.js` section validation** accepts the `portfolio.*`
prefix in addition to canonical `"portfolio"`. Any non-matching section
throws immediately (per the project's "shared-component persistence key"
rule — hardcoding or defaulting silently merges state across every
caller).

**Columns dropdown lives inside each expanded portfolio** now
(`controlsMode: 'columnsOnly'`). The header-level Columns dropdown is
gone — no single "active" portfolio anymore. Portfolio's bespoke
`+Add holding` / `+Add cash` buttons stay in the body alongside the
new dropdown.

**User clarification:** "all 8 visible by default" so new portfolios
show all the data immediately; user hides what they don't want per
portfolio. Default visibility set in
`app/portfolio.py:DEFAULT_COLUMN_VISIBILITY`.

**Pre-existing column order preserved:** the user listed the restored
columns in the order 7-day %, 30-day %, Earnings date, Marketcap,
Forward PE, Forward PEG, 52W high, Sector — that's the order they
appear after `pct_daily` (the 8 base columns first, then 8 restored
in user's listed order).

**Trade-off:** initial dashboard load is slower on a cold cache
because `enrich_portfolios` now does up to N+1 HTTP calls (one bulk
history + one `Ticker.info` per unique symbol). With ~10 holdings
this adds ~10-15s on first load; the 5-min cache amortizes within
the window. Next step if UX becomes a problem: defer per-symbol
info fetch behind an async `/api/portfolios/fundamentals/{pid}`
endpoint that fires only on portfolio expand.

**Regression coverage:**

- `tests/test_portfolio.py` — 9 new tests (enrich history derivation,
  enrich fundamentals, cache hit, per-portfolio PUT round-trip,
  per-portfolio 404 on unknown pid, default column set includes all 16).
- `tests/frontend/portfolio.spec.mjs` — 3 existing column tests updated
  for the new dropdown location + `_star` prepending index shift; +2
  new tests (per-portfolio visibility isolation, per-portfolio order
  isolation) — both FAIL on the pre-refactor shared-key code.

**Pre-existing test failures (unrelated):** the `dash-layout-*` and
`portfolio-star-scope*` Playwright specs were failing before this
change (confirmed against the pre-changes commit). They exercise
unrelated reload + star-scope paths and were not touched by this
refactor.


## AGENT-WORKFLOW-PROMPT.md removed (2026-09-07)

**Status:** removed.

The original session-start workflow template at
\rchived/AGENT-WORKFLOW-PROMPT.md\ was an early draft that seeded the
\project-rules\ skill (the canonical home for cross-session continuity
rules). Once the skill shipped, the file became redundant — every rule
in it lives in the skill + AGENTS.md, and the historical anchors
(\"§3a stuck-process hypothesis\", \"§3b shared-component state\") are
referenced from DECISIONS / SESSION_LOG / ROADMAP but no longer need
the source file to be present.

Remaining references to the file in those docs are historical anchors,
not live dependencies — the rationale for each anchored decision is in
the entry that cites it.


## project-rules skill generalised for separate publication (2026-09-07)

**Status:** shipped; the skill is now a portable, project-agnostic
core ready to be published as its own repo.

**Why:** the skill was originally designed for this project and grew
project-specific sections (Card tooltip / Risk gauge / Commodities
spot pricing). Once the project had its own decisions documented in
\project_rules/DECISIONS.md\, the skill no longer needed to carry
those sections - it could focus on the universal principles that
apply to any repo.

**What changed:**

- Dropped three project-specific sections (Card behavior + tooltip,
  Risk-gauge design, Commodities spot pricing). Their anti-pattern
  lessons are preserved here in DECISIONS.md; new repos adopt the
  skill without inheriting THIS repo's implementation details.
- Stripped repo-specific anchors from the universal sections
  (Server lifecycle no longer names pythonw.exe / wscript.exe /
  port 8000; Data integrity drops the yfinance / SEC EDGAR / Stooq
  specifics; Shared UI components drops the tickerTable.js example).
  Each rule now states the principle only.
- Added a Bootstrap section: on invocation in a fresh repo, the
  agent reads \	emplates/\, substitutes placeholders, and writes
  AGENTS.md + the five \project_rules/*.md\ seed files. No script
  required - the agent does the copy-paste from the shipped templates.
- Added \	emplates/\ directory with 6 placeholder-laden seed files
  + a README that documents the set and the placeholder map.
- Replaced repo-specific defaults in the Initialisation table
  (\Spirors/Market-Analysis\, \Market Analysis Tool\,
  \python run.py\) with obvious placeholder values so the published
  version doesn't bake in this repo's specifics.

**What did NOT change:**

- The universal rules themselves (Data integrity, Frozen files,
  Commit hygiene, Shared components, File ownership, Session
  continuity, Process hygiene) - same principles, same enforcement
  expectations, just with the project-specific examples stripped.
- This repo's project-specific rules - they still apply here, they
  just live in \project_rules/DECISIONS.md\ instead of the skill.

**Rule for future skill edits:** when adding a rule to the skill,
ask: does this apply to ANY project, or only to projects with this
specific feature? If only to a feature, document it in this repo's
DECISIONS.md instead. The skill stays portable by staying generic.


## Portfolio add/delete latency fix (2026-09-07)

**Status:** confirmed + shipped (commit pending; red-green verified
against `audit-2026-09-07.md` P0 root cause). Audit doc reproduced
the finding end-to-end (min/avg/max over 5 trials with mocked yfinance
on N=10 holdings: 23.1 / 29.9 / 54.2 ms — confirming the ~3 s user-
visible lag is entirely from yfinance HTTP calls, not Python
overhead).

**Bug repro:** Open the dashboard, click `+ Add holding`, enter a
ticker. On a cold cache (or within ~5 min of a cold load with >5
holdings), the new row takes ~3 seconds to appear. Same for `+ Add
cash`, portfolio `✕` delete, rename, cash row edit/delete.

**Three independent contributors** (any one would cause visible lag;
the audit confirmed all three were active simultaneously):

1. **`_patch_dashboard_cache` re-enriched all symbols on a 1-symbol
   change** (`app/portfolio.py:47`). Pre-fix the patch path called
   `enrich_portfolios(state)` inline, which does 1 bulk
   `yf.download(7d)` + 1 bulk `yf.download(260d)` + N × `Ticker.info`
   + N × `Ticker.calendar`. For ~10 holdings this is ~22 yfinance
   HTTP calls (~3 s cold, ~2.4 s warm).
2. **`_quote_snapshot` had no disk cache** for the portfolio path.
   `market.get_quotes(symbols)` (`app/market.py:133`) exists with a
   30-min `QUOTE_TTL` disk cache, but `holdings_add` /
   `holdings_edit` (`app/api.py:216,235`) called `_quote_snapshot`
   directly so every mutation paid a fresh yfinance fetch.
3. **Frontend `await refresh()` after every mutation.** Six bespoke
   button handlers in `static/js/portfolio.js` (rename blur, delete
   portfolio, `+Add holding`, `+Add cash`, cash row edit, cash row
   delete) called `await refresh()` after the API call. `refresh()`
   is `GET /api/portfolios` → `enrich_portfolios(state)` → another
   ~3 s of yfinance calls. Every mutation paid the enrichment cost
   at least twice — once server-side in the POST response, once
   client-side in the follow-up GET. The tickerTable row-level
   callbacks (`addRow`/`removeRow`/`editCell` at lines 340-360)
   already proved the optimistic-update pattern works; the bespoke
   handlers just hadn't been brought in line.

**Fix shape:**

1. **`_patch_dashboard_cache` is now structural-only.** Replaced
   `cached["portfolios"] = enrich_portfolios(state).get("portfolios",
   {})` with `cached["portfolios"] = state.get("portfolios", {})`.
   The state's holdings already carry `symbol` / `shares` /
   `total_cost` (and any user-edited values). Live prices
   (`last_price`, `pct_daily`, `sector`, etc.) for newly-added
   holdings stay `None` until the next full enrichment pass; the
   UI already renders `None` as "—". Per the "Earnings cache-miss
   path must not trigger a full universe rebuild" decision
   (`80d0fef`), a cache-patching helper must NOT fall through to a
   full rebuild — either patch minimally or invalidate and return.
   This is the "patch minimally" path.
2. **`market.get_quotes` is now symbol-aware.** Cache key changed
   from the shared `"quotes"` to `f"quotes_{sha1(sorted_symbols)
   [:16]}"`. Pre-fix the shared key silently lost symbols when
   different callers asked for different sets — latent bug masked
   because the only caller that mattered (`build_market_snapshot`)
   always asks for the full universe. `build_market_snapshot` is
   unaffected (deterministic cache key for a deterministic symbol
   set). `build_futures_snapshot` uses its own `"quotes_futures"`
   key and is unaffected.
3. **`holdings_add` / `holdings_edit` route through `get_quotes`.**
   One-line change at each call site. Cold cache for a never-seen
   symbol still pays one yfinance call; warm cache is instant.
4. **Six bespoke handlers use optimistic local state.** After the
   API call, push / filter the closure-captured `p.holdings` in
   place, then re-render only the affected holdings table
   (`renderHoldingsTable(pfSlot, p)`) plus the card-level totals
   (`renderGrandHeader()`). No follow-up `refresh()`. The rename
   blur's catch path still calls `refresh()` for error recovery
   (the server's name is the source of truth — pull it on failure).
   The bespoke handlers' `slot` discovery uses the same DOM
   selector (`document.querySelector(\`.pf-pf[data-pid="…"] .pf-pf-body\`)`)
   that `renderBody()` builds; the targeted re-render preserves the
   surrounding card header (so column state, expand/collapse, and
   the per-portfolio tickerTable instance all stay intact).

**Red-green verification:**

| Test | Pre-fix | Post-fix |
|---|---|---|
| `test_post_holdings_add_completes_under_500ms_with_15_holdings` | FAIL (~1.8 s) | PASS (~130 ms) |
| `test_post_holdings_add_does_not_call_enrich_portfolios` | FAIL (`get_histories_bulk`=1, `_info_cached`=16) | PASS (zero enrichment calls) |
| `portfolio-optimistic-ui.spec.mjs` (`+Add holding`) | n/a (new) | PASS (no follow-up GET) |
| `portfolio-optimistic-ui.spec.mjs` (`+Add cash`) | n/a (new) | PASS (no follow-up GET) |

Verified by `git checkout HEAD -- app/{market,portfolio,api}.py
static/js/portfolio.js` then running the new tests (both FAIL),
then restoring the fix files (both PASS). Full Python suite:
378 passed. Playwright suite: 72 passed, 3 failed (all 3 pre-existing
in `dash-layout-survives-reload` and `portfolio-star-scope`,
exercise `layout.js` / `watchColors.js` paths I did not touch).

**Rules established by this fix:**

- **Cache-patching helpers must NOT fall through to a full rebuild
  on cache miss.** When patching a cache after a mutation, either
  patch the structural state minimally and let the next full
  enrichment pass fill in derived fields, or invalidate and return.
  A full rebuild should only run from explicit user action (Refresh
  button) or the scheduled task — never from an additive
  mutation's side-effect. This is the same shape as the earlier
  `80d0fef` decision (earnings cache-miss path); consolidate in
  future helpers.
- **Cache keys for batch data must include the symbol set.** Any
  helper that returns a dict keyed by symbol and caches it must
  hash the requested symbols into the cache key. A shared cache
  key across callers with different symbol sets silently loses
  symbols. `market.get_quotes` is now the reference shape; future
  batch helpers should follow the same `f"<name>_{sym_hash}"` key
  pattern.
- **Bespoke mutation handlers should use optimistic local state,
  not full refresh.** When a UI handler triggers a single-row
  mutation, the response already carries the new state; push /
  filter the closure-captured state in place, re-render only the
  affected sub-tree, and call the card-level aggregate re-render
  (`renderGrandHeader()` for portfolio; equivalent for other
  sections). A full `refresh()` call here is a 3-second tax for
  data the user just sent. The tickerTable row-level callbacks
  (lines 340-360) are the reference pattern.
- **`_quote_snapshot` no-disk-cache is intentional for
  `build_market_snapshot`** (the market section wants fresh quotes
  on every refresh). It's only a bug in the portfolio enrichment
  path where it's used as enrichment for already-cached data. Do
  not "fix" `_quote_snapshot` globally — route the portfolio
  path through `market.get_quotes` instead. (This note mirrors
  the audit's "Findings explicitly cleared" entry for `_quote_snapshot`.)

**Regression coverage:**

- `tests/test_portfolio.py` — 2 new tests (N=15 holdings + 100 ms
  injected latency; call-count spies on the 3 enrichment call
  families).
- `tests/frontend/portfolio-optimistic-ui.spec.mjs` — 2 new tests
  intercepting POST + counting follow-up GETs.
- `tests/test_market_cache.py` — 2 existing tests updated for the
  new hash-based cache key (`glob("quotes_*.json")` instead of
  literal `"quotes.json"`).


## Next earnings date extraction — yfinance 1.6.0 returns datetime.date, not datetime.datetime (2026-09-07)

**Status:** confirmed + shipped (red-green verified). User-reported
follow-up to the P0 fix: portfolio `next_earnings` column rendered as
"—" for every holding.

**Root cause:** `app/portfolio.py:_extract_next_earnings(cal)` extracted
the earnings date from a `yf.Ticker.calendar` payload. The pre-fix
implementation was:

```python
ed = cal.get("Earnings Date")
if isinstance(ed, (list, tuple)) and ed:
    ed = ed[0]
if isinstance(ed, datetime):           # <-- BUG
    return ed.date().isoformat()
if isinstance(ed, str):
    return ed[:10]
return None
```

The check `isinstance(ed, datetime)` matches `datetime.datetime` but
**not** `datetime.date`. yfinance 1.6.0 returns `datetime.date`
instances for `Earnings Date` (verified live: `{'Earnings Date':
[datetime.date(2026, 11, 17)], ...}`), so the check fell through to
`return None`. Older yfinance versions returned `datetime.datetime`,
which the pre-fix check did handle — but `datetime.datetime` is a
subclass of `datetime.date`, so checking `isinstance(ed, date)` covers
both shapes.

**Fix:** broaden the check from `datetime` to `date` and call
`.isoformat()` directly (both classes implement it). Use `[:10]` to
strip the time portion if a `datetime.datetime` slips through.

```python
if isinstance(ed, date):
    return ed.isoformat()[:10]
```

Plus add `date` to the existing `from datetime import date, datetime,
timezone` import.

**Red-green verification:** 6 new tests in `tests/test_portfolio.py`.
Pre-fix: `test_extract_next_earnings_handles_datetime_date` and
`test_extract_next_earnings_handles_multiple_dates` FAIL (both rely on
the `datetime.date` shape). The other 4 tests (datetime.datetime,
string fallback, missing key, non-dict) PASS as controls. Post-fix:
all 6 PASS. Full Python suite: 384 passed.

**User-facing caveat:** because the P0 fix made `_patch_dashboard_cache`
structural-only, any holding added since the P0 fix has
`next_earnings=None` in the cached `data/dashboard.json`. The fix
above makes the *next* enrichment populate the column correctly, but
existing cached holdings need a one-time manual Refresh (forces full
rebuild via `service.refresh_all`) to surface their earnings dates.

**Rule for future yfinance shape compat:** when an extraction helper
inspects a yfinance field, check the **base class** that covers both
historical and current yfinance versions. `datetime.datetime` is the
specific class, but `datetime.date` is the base — prefer the base
when both have the methods you need (here: `.isoformat()`). The
broader check is forward-compatible with future yfinance shape
changes as long as the new type still subclasses `date`.

**Regression coverage:** `tests/test_portfolio.py` — 6 new tests
covering `datetime.date` (yfinance 1.6.0), `datetime.datetime`
(older yfinance), multi-element list (confirmed + tentative), string
fallback (some yfinance proxies), missing/empty/None values, and
non-dict payloads (defensive).


## Audit-2026-09-07 follow-up closure -- P3/P4/P5/P6 (2026-09-07)

Closed the remaining audit-2026-09-07 follow-ups this session (3 commits:
`4f8d92f`, `a8dbe7f`, `d91b519`). P0 (perf) and the earnings-date fix
shipped in the prior session. P1/P2/P7 were already CLEARED by the audit.
This entry records the durable decisions behind the cleanup so a future
session doesn't re-litigate.

**P4 critical (`tests/test_service_coverage.py`).** The file was excluded
from the default pytest run per the historical AGENTS.md note ("network-
heavy + long-running"). The exclusion was hiding 5 broken tests for
months: 3 with `from app import earnings` (ImportError -- module deleted
2026-09-06), 1 with an outdated `_recompute_ai_sentiment(events,
earnings)` 2-arg signature, and 1 with `cov["earnings"]` assertion
(earnings is no longer a coverage section in `_coverage_counts`).

**Rule (durable):** test files in `tests/` should run by default. Don't
add files to the `--ignore=` list for long-runtime or network-heavy
reasons -- fix the slowness (mock the network, parallelize the suite)
or accept the cost. Hiding broken tests via exclusion creates silent
regressions. `test_thirteenf.py` is now in the default run too (196
lines, properly mocked EDGAR responses); the historical "network-heavy"
exclusion was outdated.

**P5 (stale code).** Two flavors:

1. Stale docstrings pointing at deleted artifacts. `app/market.py:4,33`
   still named `earnings.py` as a caller; `:155` still mentioned the
   "user-editable earnings watchlist"; `app/portfolio.py:29` still
   pointed at the earnings cache pattern. All 4 fixed.

2. Dead skill file: `.opencode/skills/earnings-scan/SKILL.md` referenced
   `app/earnings.py`, `data/cache/earnings.json`, and `EARNINGS_UNIVERSE`
   -- all deleted 2026-09-06 with the watchlist section. Pruned (the
   whole directory was just SKILL.md; no consumers).

**Rule (durable):** when removing an `app/...py` module, grep for the
module name across `app/`, `static/js/`, `tests/`, `project_rules/`,
`.opencode/skills/`, and `docs/logs/` in one pass. Each match is either
a stale docstring/skill/test/doc reference to fix in the same commit, or
a historical audit-trail entry in `DECISIONS.md` to keep as-is. The
distinction: live code + runnable docs = fix; prose in `DECISIONS.md` /
`SESSION_LOG.md` = keep.

**P3 (shared-component regression test).** The audit claimed
`static/js/tickerTable.js` had no per-portfolio isolation regression
test for its sole consumer (`portfolio.js`). Two such tests already
exist in `tests/frontend/portfolio.spec.mjs` (lines 686 + 778, added
in `a8b60d2`): per-portfolio column visibility + column order isolation.
The audit's fix sketch (`Add tests/frontend/tickerTable-section-
isolation.spec.mjs... Or amend portfolio.spec.mjs with the cross-
portfolio isolation assertion.`) acknowledged `portfolio.spec.mjs` as
an acceptable alternative.

**Rule (durable):** the shared-component persistence rule ("new section
in `VALID_SECTIONS` requires a paired regression test") is satisfied by
either a dedicated `tickerTable-section-isolation.spec.mjs` or by
assertions in the consumer's own spec file. Document the chosen
location in `project_rules/TESTING.md` so future extractions know where
to add paired coverage. The tickerTable factory is currently consumed
by `portfolio.js` only -- the prior Earnings watchlist removal dropped
the second consumer.

**P6 (doc drift).** Six docs files were out of sync with the codebase
after the 2026-09-06 Earnings watchlist removal + the 2026-09-07 P0 perf
fix + the 2026-09-07 earnings-date fix. `project_rules/API.md` listed 14
routes (actual 25) + 3 deleted earnings routes. `project_rules/
ARCHITECTURE.md` listed `app/earnings.py` as active (deleted) and was
missing 4 modules (`validation.py`, `lifecycle.py`, `launcher_icon.py`,
`changelog.py`). `project_rules/TESTING.md` was claiming 3 closed test
gaps as open. `project_rules/ROADMAP.md` Phase 2 #5 was still "open"
despite the gaps being closed. `project_rules/HANDOFF.md` had
duplicated "Top 3 next actions" blocks + stale Notes section references
to removed earnings artifacts. `README.md` claimed RSS sources were
"MarketWatch / SCMP China / SCMP Business / Korea Herald" but the live
`app/config.py` has MarketWatch + BBC Business only.

**Rule (durable):** doc drift is a maintenance debt that compounds
quietly. After any module removal + 2+ related fixes, audit the
referencing docs (`project_rules/*.md` + `README.md` + `.opencode/
skills/*/SKILL.md`) in the same session that ships the removal. The
audit-2026-09-07 + this closure commit pair took ~2 hours end-to-end;
without it the drift would have grown for another quarter.

**Verification at session end:**

- `python -m pytest tests/`: 421 passed in 50.11 s (up from 384 in the
  prior session; the +37 are the re-included `test_service_coverage` +
  `test_thirteenf` files).
- `cd tests/frontend && npx playwright test --reporter=list`: 72 passed,
  3 failed (same pre-existing failures as the prior session --
  `dash-layout-survives-reload` x2 + `portfolio-star-scope` x1; unrelated
  to audit work).
- 3 commits land the work; working tree clean except for
  `data/events.json` (scheduler-owned, per AGENTS.md).


## renderBody must clear portfolioTables Map before innerHTML rebuild (2026-09-07)

**Status:** confirmed + durable rule.

**Context:** Patch C (the audit-2026-09-07 follow-up front-end fix) made
`renderHoldingsTable(slot, p)` early-return + reuse the existing
tickerTable instance via `existing.refresh({rows})` when one is already
in the `portfolioTables` Map (`static/js/portfolio.js:423-428`). This
preserves the user's current sort state and debounced edit timers
across add/remove holding mutations — the original "nuclear rebuild"
threw all of that away on every click.

**Failure mode discovered during red-green verification:** the
`tests/frontend/portfolio.spec.mjs` star cycling tests
("clicking a star cycles the color and tints the row", line 578 +
"right-clicking a starred row clears the watch", line 595) went red
with Patch C alone. Root cause: a star click triggers
`renderBody()` which does `el.innerHTML = html` and rebuilds every
`.pf-pf` div from scratch — including the `.pf-pf-body` slots. The
`portfolioTables` Map, however, still held tickerTable instances
bound to the now-DETACHED old slots. When `renderHoldingsTable`
ran for the expanded portfolios and called `existing.refresh({rows})`
on the orphaned tickerTable, the refresh updated the detached DOM
(no longer in the document). The NEW slot was never populated —
so the user clicked a star and saw their holdings table disappear.

**Fix:** `renderBody()` must call `portfolioTables.clear()`
immediately before the `el.innerHTML = html` assignment (and before
the empty-state placeholder branch). The cleared Map ensures
`renderHoldingsTable` falls through to the "first-time render" path
and creates a fresh tickerTable bound to the new slot.

```js
// static/js/portfolio.js:218-229
if (!portfolios.length) {
  portfolioTables.clear();        // <-- detached-slot guard
  el.innerHTML = `<div class="pf-empty">…</div>`;
  renderGrandHeader();
  return;
}
…
portfolioTables.clear();          // <-- detached-slot guard
el.innerHTML = html;
```

**Red-green verification:**

| Test                                                      | Pre-fix  | Patch C alone (no clear) | Patch C + clear |
|-----------------------------------------------------------|----------|---------------------------|------------------|
| `portfolio.spec.mjs:578` star cycles color                | PASS     | FAIL (NVDA row missing)  | PASS             |
| `portfolio.spec.mjs:595` right-click clears watch         | PASS     | FAIL (NVDA row missing)  | PASS             |
| `tickerTable-instance-preservation.spec.mjs` (2 new tests)| —        | PASS                      | PASS             |
| `portfolio-targeted-render.spec.mjs` (3 new tests)        | —        | PASS                      | PASS             |

**Rule (durable):** any function that wipes `#portfolioBody` via
`el.innerHTML = ...` (currently only `renderBody`) MUST call
`portfolioTables.clear()` first. A Map-of-DOM-handles outliving the
DOM it points to is the silent-failure class — the function returns
without error, the user sees an empty section. The fix
(`portfolioTables.clear()`) is one line, but the failure mode
only surfaces via UI tests, not via Python backend tests. New
sections sharing the `portfolioTables` Map must follow the same
discipline.
