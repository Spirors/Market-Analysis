# Migration Guide — Refactor 2026-08-30

The refactor preserved the public HTTP API (`/api/*`) byte-for-byte
(modulo `as_of`). This guide covers the **internal** module changes
so future contributors can navigate the new structure.

## TL;DR

| Aspect | Before | After |
|---|---|---|
| Public HTTP routes | `/api/*` | unchanged |
| Public HTTP payload keys | 12 sections | unchanged |
| Public Python entry points (`compute_risk`, `build_thirteenf`, etc.) | at original module paths | at original module paths |
| Internal `app/*.py` module structure | flat | flat (no renames) — patterns applied **inside** modules |
| Test suite | 250 | 302 (+52) |

If your code imported from `app.risk`, `app.store`, `app.market`,
`app.thirteenf`, `app.regime`, `app.news`, or `app.config`, nothing
changes. The patterns live **inside** those modules.

## Module-by-module

### `app/risk.py` — Strategy pattern

**Before:** `compute_risk` was a single ~200-line function with 9
inline signal blocks and inline fragility flag logic. Cyclomatic
complexity F (78).

**After:** 9 `_signal_*` strategies, each returning a
`RiskSignalResult` NamedTuple. A `_build_context()` helper computes
shared derived values once. `compute_risk` is a thin orchestrator
that aggregates tone counts and applies gate logic. Cyclomatic
complexity D (27), **−65%**.

Adding a new signal: implement `_signal_<name>(ctx)` and append to
the `results` list in `compute_risk`. See `docs/refactor-example.md`.

### `app/store.py` — Repository pattern

**Before:** SQLite access scattered across module-level functions
(`log_analysis_run`, `get_analysis_history`) plus a `_ANALYSIS_READY`
module flag guarding schema init.

**After:** `AnalysisRepository` class encapsulates schema init,
`log_run()`, and `get_history()`. The module-level public functions
delegate to a singleton `_analysis_repo`. Test fixtures (`tests/test_api_contract.py`,
`tests/test_store.py`) updated to reference the new singleton name
(`_analysis_repo`).

Callers (`app/api.py`, `app/analysis.py`, `app/service.py`) need no
changes — they still call the public module-level functions.

### `app/market.py` + `app/thirteenf.py` — Adapter pattern

**Before:** `get_quotes` / `get_history` / `get_histories_bulk` /
`build_thirteenf` were module-level functions with concrete
implementations (yfinance / curl_cffi EDGAR).

**After:** Two Protocols declared and `@runtime_checkable`:

```python
class MarketDataAdapter(Protocol):
    def get_quotes(self, symbols) -> dict: ...
    def get_history(self, symbol, period) -> list[dict]: ...
    def get_histories_bulk(self, symbols, period) -> dict: ...

class HoldingsAdapter(Protocol):
    def build_thirteenf(self) -> dict: ...
```

Today's yfinance adapter (`app/market.py`) and EDGAR adapter
(`app/thirteenf.py`) implement these implicitly. A future paid data
source plugs in as a second implementation — no caller changes.

### `app/regime.py` — Factory pattern

**Before:** `run_regime_detection()` directly invoked the skill CLI
via `subprocess.run`, hard-coding the path resolution inline.

**After:** `DetectorRunner` class wraps the subprocess invocation.
The skill location, output directory, timeout, and days window are
all config-driven (already true before; now encapsulated behind one
class). `run_regime_detection()` is a thin factory entry point.

### `app/news.py` + `app/config.py` — Finance-relevance + source weights

**Before:** `analyze()` returned five tag dimensions + importance.
`IMPORTANCE_THRESHOLD` (6.0) was the only gate. `NEWS_FEEDS` was the
only source governance.

**After:** `analyze()` returns:

```python
{
    "category": "macro"|"micro"|None,
    "actor": "government"|"company"|None,
    "direction": "bullish"|"bearish"|"neutral",
    "region": "us"|"global"|"asia"|"europe"|"middle-east"|"russia-ukraine"|"korea"|"japan"|"china",
    "impact": "High"|"Critical",
    "importance": float,           # raw keyword score
    "finance_relevance": float,    # 0..10 (keyword + ticker hits, uppercase-only)
    "composite_importance": float, # importance × source_weight × finance lift, capped 10.0
    "tags": [...],
}
```

The `composite_importance` is what's compared against
`IMPORTANCE_THRESHOLD`. Four enrichment fields
(`importance`, `finance_relevance`, `composite_importance`,
`source_weight`) are now persisted in `data/events.json` on every
event (newly inserted or updated). Existing rows were backfilled on
the next `_ensure_ready()` call.

**New knobs in `app/config.py`:**

```python
NEWS_SOURCE_WEIGHTS = {"MarketWatch": 1.2, "SCMP China": 0.7,
                       "SCMP Business": 0.7, "Korea Herald": 0.7}
FINANCE_KEYWORDS = [...]               # 30 high-signal terms
NEWS_ADDITIONAL_FEEDS = [("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml")]
ENABLE_ADDITIONAL_FEEDS = False        # flip to enable
FINANCE_RELEVANCE_BOOST = 1.5          # lift multiplier
```

**New CLI tool:** `python tools/news_source_audit.py [--days 60]`
prints a per-source table (n / median importance / median composite
/ hit rate / recommendation). The recommendation derives from
`median_composite` so it stays consistent with the storage gate.

### `static/js/tooltip.js` — Vanilla JS Tooltip component

New file (~163 lines). Reusable on every card. API:

```js
attachTooltip(el, {
  text: string,            // main body (rendered as textContent)
  placement: "top"|"bottom", // default "top", flips near viewport edge
  ariaLabel: string,       // optional accessible name
  deps: string[],          // optional cross-section dependency pills
})
```

Behavior: `role="tooltip"` surface + `aria-describedby` on the
trigger; shows on hover and focus; hides on mouseleave, blur, and
Escape; repositions on resize; one open at a time.

Wired into every major card via `static/js/cards.js`. Per-card ↻
icon removed everywhere except Analysis (which has its own async
`/api/analysis/history` reload).

### `static/js/events.js` — News chips + row metadata

Adds three filter chip rows (region multi, weight single, topic
multi), region pills, weight badges, and finance-relevance chips
to each event row. Reads `event.finance_relevance`,
`event.source_weight`, `event.region` from the API payload —
defensively handles missing fields (for seed events predating the
backfill).

A "Show seed items only" toggle preserves the legacy Wikipedia /
Curated view (hard rule from `AGENTS.md`).

## Rollout steps (for future breaking changes)

1. **Add new paths alongside old.** Never rename a public import
   without a shim.
2. **Shim first.** The shim is a thin re-export from the old path.
3. **Deprecation warning.** Add a `warnings.warn(DeprecationWarning)`
   in the shim.
4. **Update callers.** Migrate `app/*.py` callers to the new path.
5. **Tests first.** The shim's tests assert the old import still
   works AND emits the deprecation warning.
6. **Remove the shim** in a later release once all callers migrate.

The current refactor did not require shims because no public paths
moved — only internals were restructured.

## Hard rules preserved

From `AGENTS.md`, none of these changed:

- Never fabricate market data.
- Free, no-key sources only.
- Public HTTP API stable.
- Frozen `ai_*.html` files are read but never modified.
- No env vars — every knob lives in `app/config.py`.
- Cross-device sync model unchanged: `data/events.json` Git-synced,
  everything else local-only.

## Verification

```bash
# Full test suite
python -m pytest -q                  # 302 passed

# Frontend component + e2e
npx playwright test tests/frontend --config tests/frontend/playwright.config.mjs  # 20 passed

# Cyclomatic complexity
python -m radon cc -s app/risk.py app/store.py app/market.py app/thirteenf.py app/regime.py app/news.py

# News source audit
python tools/news_source_audit.py --days 0

# End-to-end dashboard refresh
python run.py --refresh

# Oracle payload shape
python -m pytest tests/test_dashboard_equivalence.py -v
```

See `docs/refactor-metrics-2026-08-30.md` for the full delta table.
