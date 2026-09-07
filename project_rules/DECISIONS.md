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

**Status:** confirmed + fixed.

The 2026-09-06 entry above (`min-width: 160px`) fixed the original
"input stretches to 87% of header" bug, but introduced a layout-shift
bug for SHORT portfolio names: a 3-char name like "IRA" rendered the
title at ~30px but the inline edit input stayed at 160px (the fixed
pixel floor), so entering edit mode shoved the pencil icon / totals /
close button ~130px to the right. Same root cause family as the
earlier "shared component cross-section state" and "rename input
bubbles to header click" bugs (different axis: pixel-floor sizing vs
shared state vs event bubbling).

**Fix:** `static/style.css` swaps `min-width: 160px` for
`field-sizing: content` (the new CSS property that sizes form controls
to their actual content) plus `min-width: 8ch` as a character-width
usability floor. The input now sizes to its current value plus
padding/border (~74px for "IRA" at 13px font) — well under the old
160px pixel floor. The `8ch` floor ensures even a 1- or 2-char name
produces an input wide enough to click inside comfortably.

`field-sizing: content` is supported in Chrome 123+, Firefox 122+,
Safari 17.5+ (all current at time of writing). Older browsers fall
back to the default intrinsic size (20 chars ≈ 160px) — same as the
previous `min-width: 160px` behavior, no regression for users on older
browsers, just no improvement either.

**Why not `max(min-content, 8ch)` (the original plan)?** The CSS
`max()` function doesn't work with `field-sizing: content` — the
browser ignores the explicit `min-width` formula and uses the
content-sized width regardless. A plain `min-width: 8ch` is the
correct floor once `field-sizing: content` is doing the sizing.
This is the lesson: when a CSS property is the sizing mechanism,
`min-width` is just a hard lower bound, not a formula input.

**Rule for inline-rename / inline-edit inputs:** "Use
`field-sizing: content` for content-sized inputs in modern browsers,
with `min-width: <ch>` as the usability floor (NOT a fixed pixel
value). Fixed pixel floors regress for SHORT values — character
widths scale with font size and are robust across all name lengths."

Regression coverage: `tests/frontend/portfolio-name-input.spec.mjs`
extended with 2 tests for the short-name layout shift:

1. `input width does not visually exceed rendered title (short name)`
   — uses an "IRA" fixture, asserts the input width is < 130px and
   `field-sizing` is `content` (the structural fix).

2. `input width does not reintroduce pre-4716e02 stretch behavior`
   — asserts `flex: 0 0 auto`, `field-sizing: content`, and the input
   width ratio is < 0.5 of header width. Catches reverts to either
   the pre-4716e02 (`flex: 1; min-width: 0`) or the intermediate
   (`min-width: 160px`) shapes.

Red-green verified: with the fix reverted, both new tests fail (the
existing 3 tests still pass — they use the "Fidelity Main" fixture
where content > 160px anyway, so they didn't catch this regression).


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

**Status:** audit complete; classification decided; refactor pass
already landed in commit `b45858e`. This entry exists so a future
session doesn't re-derive the classification from scratch.

**Cluster observed by ROADMAP.md Phase 2 audit bullet:** add or
delete a row inside a portfolio writes correctly server-side, but a
plain page reload shows stale state while the in-page Refresh
button (full data/news/earnings/regime refresh) brings it current.
Same pattern for whole-portfolio add/delete and for portfolio
rename. Confirmed repro: add or delete a row → `data/portfolios.json`
reflects the change → plain reload shows pre-mutation state → click
Refresh → current.

**Classification — two separate issues, not the same root cause:**

1. **Dashboard-cache staleness** (the actual cluster). Pre-fix
   `app/portfolio.py` mutations wrote `data/portfolios.json`
   correctly but never touched `data/dashboard.json`. `service.get_dashboard`
   served the cached `dashboard.json` (with its embedded `portfolios`
   sub-tree) until `QUOTE_TTL` expired or the user clicked Refresh.
   **Already fixed by commit `b45858e`** — new
   `_patch_dashboard_cache(state)` helper called after
   `save_portfolios(state)` in all 9 mutation functions (create/delete/
   rename portfolio, add/edit/remove holding, add/edit/remove cash
   row). Mirrors `app/earnings.py`'s existing `EARNINGS_CACHE_PATH`
   patching pattern. Best-effort semantics — a failed patch degrades
   to "stale until QUOTE_TTL" (same as pre-fix), never a hard error.

2. **`tickerTable.js` shared-component state namespacing** (NOT
   this cluster). This is the bug class flagged for
   `pfSort.{section}` / `pfVisible.{section}` / `pfOrder.{section}` —
   a *different* axis (per-section localStorage key). Fixed in commit
   `94442b6` follow-ups via `VALID_SECTIONS` allowlist +
   `_assertValidSection()`. Different bug, different file, different
   surface. The stale-on-reload cluster is not a recurrence of this.

**Refactor pass (Phase 2 #2) — already landed.** The unification
called for in ROADMAP.md ("model the shape on `app/earnings.py`'s
cache-patching pattern") is exactly what `b45858e` does. The two
modules now share the same pattern:

- `app/earnings.py:add_ticker` / `remove_ticker` patch
  `data/cache/earnings.json` via `store.save_json` after mutating
  `data/watchlist.json`.
- `app/portfolio.py:*` mutation functions call
  `_patch_dashboard_cache(state)` after `save_portfolios(state)`.

Both bump the relevant `vintage` stamp so the per-card "As of"
footer reflects the mutation time. Both are best-effort (no hard
error on patch failure). The 5-test regression suite in
`tests/test_portfolio_cache_sync.py` covers add/remove holding +
add/delete portfolio through TestClient — extend it for any new
mutation type added in the future.

**Remaining debt surfaced by the audit (none blocking):**

- No `tickerTable.js`-style "shared component consumed by 2+ sections
  with independently-keyed persisted state" candidate was found
  beyond the existing per-portfolio star scoping
  (`static/js/watchColors.js:getPortfolioWatchColor(pid, sym)`,
  commit `1fafbc1`). Earnings and Portfolio sections still have
  their own column-order / sort / visibility / star state, and the
  per-section keys are correctly namespaced. The audit bullet
  "Audit for other shared-component extractions with the same risk
  profile as `tickerTable.js`" found no other candidates.

- The cache-invalidation shape is now consistent across `earnings`
  and `portfolio` modules. If a third module is added later (e.g.
  a watchlist section, an events section with mutations), the
  pattern to copy is:
  1. `save_<thing>(state)` writes the source-of-truth JSON.
  2. `_patch_<cache>_cache(state)` reads the cached dashboard
     payload, replaces the relevant sub-tree, bumps `vintage[<key>]`,
     writes back via `store.save_json`. Wrap in try/except so a
     failed patch degrades to "stale until QUOTE_TTL."

**Conclusion:** Phase 2 #1 (audit) + Phase 2 #2 (refactor pass) are
both effectively done — `b45858e` lands the unification the audit
bullet called for. No new commits required. Future sessions should
treat the existing `_patch_dashboard_cache(state)` helper as the
template for any new module's cache-invalidation logic.

---

## Phase 2 audit — earnings `validate_symbol` path diff (2026-09-06)

**Status:** investigation complete; root cause confirmed; fix landed
in commit `<this session>` (path diff and reproduction in this
entry).

**Bug repro from ROADMAP.md:** entering "NVDA" (a mega-cap,
unambiguously valid ticker) into the Earnings Watchlist Add field
returns "invalid symbol."

**Path diff — earnings vs portfolio yfinance surfaces:**

The two call paths hit *different* yfinance endpoints. Portfolio's
display/enrichment path uses the bulk-download surface
(`yf.download`), which is documented in `app/market.py:97-98` as
"reliable in yfinance 1.6.0". Earnings' validation path uses the
per-symbol info surface (`yf.Ticker.info`), which is rate-limited
independently of symbol validity by Yahoo.

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
`Ticker.info` AND history in sequence and silently swallowed
exceptions in both wrappers (`except Exception: return {}` /
`return []`), so a rate-limit hit both surfaces and produced a
flat `valid: False` — exactly the user-visible "invalid symbol"
message.

**Reproduction (mocked yfinance, no network — verified
2026-09-06):** All four scenarios were exercised against a clean
TestClient-style harness with `yf.Ticker` and `yf.download` both
mocked. Cache cleared between scenarios. Results:

| Scenario | Ticker.info | yf.download | CURRENT result | Notes |
|---|---|---|---|---|
| A (live happy) | full dict | works | `valid=True, name="NVIDIA Corporation", sector="Technology"` | both contribute |
| B (rate-limit) | empty | works | `valid=True, name="NVDA", sector=None` | history fallback rescues |
| C (full outage) | empty | empty | **`valid=False, reason="no yfinance profile and no price history found for NVDA"`** | **THE BUG** |
| D (info only) | works | empty | `valid=True, name="NVIDIA Corporation", sector="Technology"` | Ticker.info primary rescues |

Scenario C reproduces the user-visible "invalid symbol" error.
Scenarios B and D explain why the bug is intermittent — when *one*
surface is still working, the existing fallback rescues validation.
The bug only fires when *both* surfaces are rate-limited or
unavailable, which is the failure mode observed during the Yahoo
rate-limit incident.

**Why commit `a2c793a` didn't stick.** The earlier fix added
retry-with-1s-backoff and 60-second LRU caching around the
`Ticker.info` call, but kept `Ticker.info` as the PRIMARY surface.
Retrying a fundamentally-flaky call doesn't fix it — it just delays
the user's "invalid symbol" verdict by one second. The user's exact
diagnosis: "validate_symbol relying on `Ticker.info` (known to be
flaky/rate-limited by Yahoo independent of symbol validity) while
portfolio's working path uses `Ticker.history()` / `fast_info`
(more reliable). If that split is the cause, the fix is to validate
existence the same way portfolio already does successfully — not to
add retry/error-handling around a fundamentally flaky call."

**Fix (commit `<this session>`):** `_validate_uncached` now uses
`market.get_history(sym, days=5)` (the bulk-download surface, same
as portfolio) as the PRIMARY existence check. `Ticker.info` becomes
the SECONDARY fallback (no retry-with-backoff — that was masking
the same bug). Behaviour across the four scenarios:

| Scenario | PRIMARY: history | SECONDARY: Ticker.info | Result |
|---|---|---|---|
| A | works → valid=True | enrich: name+sector | `valid=True, name="NVIDIA Corporation", sector="Technology"` |
| B | works → valid=True | enrich fails → name=sym | `valid=True, name="NVDA", sector=None` |
| C | fails | fails | `valid=False, reason="yfinance unavailable (…); try again in a minute"` |
| D | fails | works → valid=True | `valid=True, name="NVIDIA Corporation", sector="Technology"` |

Same verdicts in every scenario as before, but the common rate-limit
case (B) now succeeds without depending on the history fallback's
rescue path — and the full-outage case (C, the bug) is still caught.
Removed `_yf_info_with_retry` since retrying a flaky call around the
fallback was the wrong shape of fix. Kept the `_yf_info` /
`(dict, error_str)` distinction so the "yfinance unavailable" vs
"symbol genuinely not found" reason still surfaces to the user.

**Regression coverage (added in same commit):** new tests in
`tests/test_earnings.py` use `monkeypatch` to mock
`market.get_history` and `yf.Ticker` independently — no network
involved, no rate-limit dependency. Covers all four scenarios plus
the user-facing `add_ticker` and `add_holding` call paths.

---

## Earnings watchlist section removed (2026-09-06)

**Status:** confirmed + removed.

The dashboard "Earnings watchlist" card was the section the user
wanted gone.  Choice of scope was: remove UI only, remove UI + keep
backend enrichment, or remove UI + strip portfolio earnings columns
too.  Chosen: strip everything except `validate_symbol` (which
`portfolio.add_holding` still uses to reject invalid symbols).

**What was removed:**

- `app/earnings.py` (530 lines) — `add_ticker`, `remove_ticker`,
  `earnings_calendar`, `earnings_force_refresh`, `_enrich`, `_ai_rec`,
  `_ticker_calendar`, `cached_payload`, `_has_usable_prices`, the
  watchlist/removed JSON helpers, and the `EARNINGS_CACHE_PATH`
  filesystem artifact.
- `app/validation.py` (NEW, ~155 lines) — extracted `validate_symbol`
  + its dependencies (`_yf_info`, `_validate_uncached`, `_validate_cached`,
  `_cache_bucket`, `_TICKER_RE`, `_CONFIRMATION_FIELDS`).  This module
  is the small footprint that survives the removal.
- `app/api.py` — four endpoints gone (`GET /api/earnings`,
  `GET /api/earnings/validate`, `POST /api/earnings/watchlist`,
  `DELETE /api/earnings/watchlist`) plus the `with_earnings` query
  param on `GET /api/portfolios`.
- `app/portfolio.py` — `enrich_portfolios_with_earnings` and the
  `_EARNINGS_FIELDS` constant are gone.  `add_holding` calls
  `validation.validate_symbol` directly.
- `app/config.py` — `EARNINGS_TTL`, `EARNINGS_UNIVERSE`,
  `VALUATION_STRETCH_PE`, and `AI_SENTIMENT_VALUATION_PENALTY` are
  gone.  `RISK_SIGNAL_TOTAL` adjusted from 9 to 8 (one signal removed).
  `EARNINGS` as a `FINANCE_KEYWORDS` string stays — it's still a
  finance-relevance signal for news classification.
- `app/service.py` — `refresh_earnings`, the `earnings` payload
  field, the `earnings` coverage entry, and the earnings arg passed
  through `compute_risk` / `compute_ai_sentiment` are gone.
- `app/risk.py` — `_valuation_stretched` and `_signal_valuation` are
  gone.  The risk engine no longer reads any earnings-derived data.
- `app/ai_sentiment.py` — `compute_valuation_flag` is gone.
  `compute_ai_sentiment` no longer reads earnings.  Forward-PE
  references in the synthesis pipeline are removed.
- `app/analysis.py` — the `earnings_recs` signal is gone from the
  weight table.  `_WEIGHTS` is now 9 entries summing to 13 (was 10 / 14).
- `app/news.py` — `config.EARNINGS_UNIVERSE` is dropped from the
  ticker set; the mega-cap tickers are already covered by the
  `AI_CAPEX_COHORTS` cohorts the function iterates over.
- Frontend (`static/index.html`, `static/js/earnings.js` (deleted),
  cards.js, api.js, portfolio.js, tickerTable.js, watchColors.js,
  layout.js) — all earnings column defs, section rendering, API
  helpers, watchColors section, CARD_BAND entry removed.
- 8 earnings-derived columns stripped from the Portfolio table
  (next_earnings, pct_7d, high_52w, forward_pe, forward_peg,
  market_cap_fmt, sector, AI rec).

**Rule for future sections:** "If a dashboard section's only reason
for existing is the data the section itself fetches, removing the
section means removing the data fetch too.  Don't keep a thin
backend wrapper 'just in case' — `validate_symbol` is the right kind
of thin wrapper to keep (it's used by another section); the rest of
the earnings module wasn't."

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

**Status:** confirmed + shipped (commits 75b7c70 + a8b60d2).

**Request:** user asked to bring back the 8 columns the Earnings
watchlist removal had stripped from the Portfolio table
(7-day %, 30-day %, Earnings date, Marketcap, Forward PE, Forward
PEG, 52W high, Sector) AND to make column settings independent
per portfolio.

**Data sources (per project 'never fabricate' rule):**

| Column | Source |
|---|---|
| pct_7d, pct_30d, high_52w | market.get_histories_bulk(symbols, days=260) - one bulk yfinance download |
| sector, marketcap, forward_pe, forward_peg | Ticker.info per symbol |
| next_earnings | Ticker.calendar per symbol |

Per-symbol fetches cached via unctools.lru_cache(maxsize=128) keyed
by (symbol_upper, time_bucket) where the bucket is
int(time.time() // 300) (5 minutes). Cold-cache cost is one HTTP
per unique symbol; warm-cache is instant. The single Ticker instance
is shared between info + calendar to avoid the 2-fetch pattern the
old pp.earnings had.

**Per-portfolio column state:** the previous design used a single
shared pfVisible.portfolio / pfOrder.portfolio localStorage
key. This means hiding 7-day % in Fidelity Cash also hides it in
Roth IRA. New design namespaces by portfolio.<pid>:
- pfVisible.portfolio.<pid> / pfOrder.portfolio.<pid>
- pfSort.portfolio.<pid>
- backend column_order['portfolio.<pid>'] /
  column_visibility['portfolio.<pid>']

The bare portfolio key remains as the default that new portfolios
inherit; existing portfolios continue to work. Two portfolios can
show different columns, hiding/showing one column in Portfolio A
never affects Portfolio B.

**	ickerTable.js section validation** accepts the portfolio.*
prefix in addition to the canonical "portfolio" default. Any
non-matching section throws immediately (per the project's
"shared-component persistence key" rule - hardcoding or defaulting
a section silently merges state across every caller).

**Columns dropdown lives inside each expanded portfolio** now
(controlsMode: 'columnsOnly' on the tickerTable factory). The
header-level Columns dropdown is gone - there is no single "active"
portfolio anymore. Portfolio's bespoke +Add holding / +Add cash
buttons stay in the body alongside the new dropdown.

**User clarification:** during the design question the user picked
'all 8 visible by default' (vs opt-in via per-portfolio) so new
portfolios show all the data immediately and the user hides what
they don't want per portfolio. Default visibility set in
pp/portfolio.py:DEFAULT_COLUMN_VISIBILITY.

**Pre-existing column order preserved:** the user listed the
restored columns in the order 7-day %, 30-day %, Earnings date,
Marketcap, Forward PE, Forward PEG, 52W high, Sector. That is the
order they appear after pct_daily in the table (the 8 base columns
come first, then the 8 restored in user's listed order).

**Trade-off:** initial dashboard load is slower on a cold cache
because nrich_portfolios now does up to N+1 HTTP calls (one
bulk history + one Ticker.info per unique symbol). With ~10
holdings this adds ~10-15s on first load. The 5-min cache
amortizes the cost for repeated reads within the same window.
If this becomes a UX problem, the next step is to defer the
per-symbol info fetch behind an async
/api/portfolios/fundamentals/{pid} endpoint that the frontend
calls only when a portfolio is expanded.

**Regression coverage:**
- 	ests/test_portfolio.py: 9 new tests (enrich history
  derivation, enrich fundamentals, cache hit, per-portfolio
  PUT round-trip, per-portfolio 404 on unknown pid, default
  column set includes all 16).
- 	ests/frontend/portfolio.spec.mjs: 3 existing column tests
  updated for the new dropdown location + _star prepending
  index shift; +2 new tests (per-portfolio visibility isolation,
  per-portfolio order isolation) - both would FAIL on the
  pre-refactor shared-key code.

**Pre-existing test failures (unrelated):** the dash-layout-...
and portfolio-star-scope... Playwright specs were failing before
this change (confirmed by running against the pre-changes commit).
They exercise unrelated reload + star-scope paths and were not
touched by this refactor.
