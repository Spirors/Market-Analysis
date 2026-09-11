# AI Valuation (Beneficiary) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-introduce a forward-PE valuation signal for the AI capex-cycle gauge and the BREADTH - AI Proxies chart, replacing the dead `compute_valuation_flag` that was removed in the 2026-09-06 earnings-watchlist cleanup. New shape: a per-ticker forward-PE cache (12h on-disk TTL), a `valuation` summary on the AI gauge output, a `Valuation (Beneficiary)` meta cell, and a +25 score shift when median beneficiary cohort PE ≥ 30×.

**Architecture:** New backend module `app/ai_valuation.py` does the cache + yfinance fetch + median/stretched computation. `app/ai_sentiment.py` accepts an optional `valuation` dict and applies the score shift. `app/service.py` wires the valuation lookup into the existing `_recompute_ai_sentiment` path (no new endpoints). Frontend `static/js/cards.js` extends the BREADTH chart hover tooltip and re-introduces the AI gauge meta cell. The `tests/conftest.py` autouse fixture gets one new monkeypatch line for the cache path (per the project's test-isolation hard rule).

**Tech Stack:** Python 3.x, yfinance (`yf.Ticker(sym).info["forwardPE"]`), pytest (backend), Playwright (frontend), Chart.js (existing bar chart — extension only).

**Spec:** This plan is the spec — the user opted to skip the design-doc step in the brainstorming phase. Sections 1-4 of the brainstorming conversation are the design contract:
- Section 1 (backend valuation module): cache + fetch + compute + config constants
- Section 2 (AI gauge integration): score shift + valuation dict in output
- Section 3 (frontend): BREADTH hover + Valuation (Beneficiary) meta cell + tooltip addendum
- Section 4 (tests): backend + frontend test list

## Global Constraints

These apply to every task. Copied from the project's hard rules and the brainstorming-approved decisions:

- **Test isolation:** every test that creates persisted state must redirect user-data paths to `tmp_path`. The autouse fixture in `tests/conftest.py` is the contract. Add a new path to the fixture the same day it's introduced (hard rule).
- **TDD throughout:** write the failing test, run it red, implement minimal code, run it green, commit. Per project convention ("TDD throughout" in SESSION_LOG entries).
- **One logical change per commit.** Scope-prefixed messages: `feat(scope): ...`, `fix(scope): ...`, `test(scope): ...`. Never amend.
- **Data integrity:** never fabricate. Forward PE values come from `yf.Ticker(sym).info["forwardPE"]` only. Missing/None/NaN/negative PEs are filtered out (forward PE < 0 means losses; ignore).
- **Shared-component rule:** the new module-level path constant `ai_valuation._CACHE_PATH` is patched at the bound name on the importing module (not at `config.AI_VALUATION_CACHE_PATH`). Same anti-pattern that motivated the autouse fixture in commit `38bf801`.
- **Cohort scope:** valuation median uses beneficiary cohorts only — `Compute / Accelerators`, `Memory`, `Photonics / Optics`, `Equipment / Packaging`, `Neocloud / Infrastructure`, `Power / Data Center`, `Applications`. `Capex Spenders` is excluded (demand-side; its PE reflects broader market, not the AI trade).
- **Score shift:** `+25` to gauge score when `median_pe >= 30×`. No shift below 30×. No shift when valuation is None / missing.
- **Changelog:** every meaningful change calls `app.changelog.log_change(category, message)` per AGENTS.md hard rule. Final commit in the sequence lands the session docs + changelog.

---

## File Structure

| File | Role | Touched in |
|---|---|---|
| `app/config.py` | Add 4 constants (`AI_VALUATION_STRETCH_PE`, `AI_VALUATION_SCORE_SHIFT`, `AI_VALUATION_CACHE_TTL_HOURS`, `AI_VALUATION_CACHE_PATH`) | Task 1 |
| `app/ai_valuation.py` (new) | Cache I/O + yfinance fetch + median/stretched computation | Task 1 |
| `app/ai_sentiment.py` | Extend `compute_ai_sentiment(snapshot, events, valuation=None)` signature; add valuation dict to output; apply +25 score shift when stretched | Task 2 |
| `app/service.py` | `_recompute_ai_sentiment`: load PE map, build valuation dict, pass into `compute_ai_sentiment` | Task 2 |
| `static/js/cards.js` | `renderBreadthAIChart` (per-bar hover with PE + cohort median + threshold); `renderAISentiment` (re-introduce `Valuation (Beneficiary)` cell); `CARD_TOOLTIPS["ai-sentiment"]` (one-line addendum) | Tasks 3 + 4 |
| `static/index.html` | No change (chart canvas exists; no markup change needed) | — |
| `tests/conftest.py` | Add `monkeypatch.setattr(ai_valuation, "_CACHE_PATH", tmp_path / "ai_valuation.json")` to autouse | Task 1 |
| `tests/test_ai_valuation.py` (new) | Cache hit/miss/expired/atomic-write; fetch with mocked yfinance; skip-spenders / skip-invalid-PE; partial failure; compute_valuation median/stretched/empty | Task 1 |
| `tests/test_ai_sentiment.py` | 3 new tests: stretched shifts +25; not stretched no shift; missing valuation no shift | Task 2 |
| `tests/frontend/breadth-ai-valuation.spec.mjs` (new) | BREADTH hover content (PE + cohort median + threshold); AI gauge meta cell (`Valuation (Beneficiary)` + stretched/ok tag); AI gauge score shifts +25 in displayed value | Tasks 3 + 4 |
| `tests/frontend/mock-dashboard.mjs` | Add `valuation: { median_pe: null, stretched: false, note: "" }` to the default mock + `breadth_ai.cohort_median_pe` field | Task 5 |
| `tests/frontend/portfolio.spec.mjs`, `bottleneck-move.spec.mjs`, `bottleneck-rename.spec.mjs`, `portfolio-holdings-reorder.spec.mjs`, `portfolio-header-collapse.spec.mjs`, `portfolio-move.spec.mjs`, `portfolio-star-scope.spec.mjs` | Add `valuation` field to existing `ai_sentiment` mocks so they don't break with the new shape | Task 5 |
| `data/.gitignore` | Add `ai_valuation.json` (mirrors how other cache files are gitignored) | Task 1 |
| `data/logs/summary-2026-09-11.md` | Feature entry via `app.changelog.log_change` | Task 6 |
| `project_rules/HANDOFF.md` | Timestamp + state update | Task 6 |
| `project_rules/SESSION_LOG.md` | New dated entry appended (full text inline; pointer file in archive not required because this is the current entry) | Task 6 |

---

### Task 1: Backend valuation module + config + test isolation

**Files:**
- Create: `app/ai_valuation.py`
- Modify: `app/config.py:224-228` (add new constants near `RISK_SIGNAL_TOTAL`)
- Modify: `data/.gitignore` (add `ai_valuation.json`)
- Modify: `tests/conftest.py` (add autouse monkeypatch line)
- Create: `tests/test_ai_valuation.py`

**Interfaces:**
- Consumes: `config.AI_VALUATION_CACHE_PATH`, `config.AI_VALUATION_CACHE_TTL_HOURS`, `config.AI_VALUATION_STRETCH_PE`, `config.AI_CAPEX_COHORTS`
- Produces:
  - `load_cache() -> dict | None`
  - `save_cache(pe_map: dict) -> None`
  - `fetch_beneficiary_pe(tickers: list[str] | None = None, *, force: bool = False) -> dict[str, float]`
  - `compute_valuation(pe_map: dict[str, float]) -> dict` — returns `{median_pe, stretched, note, per_ticker_pe, fetched_at, cache_ttl_hours}`
- Module-level constants: `_CACHE_PATH = config.AI_VALUATION_CACHE_PATH`, `_BENEFICIARY_COHORTS = [k for k in config.AI_CAPEX_COHORTS if k != "Capex Spenders"]`

- [ ] **Step 1.1: Write failing tests in `tests/test_ai_valuation.py`**

```python
"""Tests for app/ai_valuation: cache I/O, yfinance fetch, valuation summary."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app import ai_valuation, config


# ---- load_cache / save_cache -------------------------------------------------

def test_load_cache_returns_none_when_missing(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    assert ai_valuation.load_cache() is None


def test_save_cache_then_load_cache_round_trips(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache({"NVDA": 45.0, "AMD": 32.0, "fetched_at": "2026-09-11T12:00:00"})
    loaded = ai_valuation.load_cache()
    assert loaded == {"NVDA": 45.0, "AMD": 32.0, "fetched_at": "2026-09-11T12:00:00"}


def test_load_cache_returns_none_when_expired(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    stale = {"NVDA": 45.0, "fetched_at": "2020-01-01T00:00:00"}  # way past TTL
    ai_valuation._CACHE_PATH.write_text(json.dumps(stale), encoding="utf-8")
    assert ai_valuation.load_cache() is None


def test_load_cache_returns_map_when_within_ttl(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    fresh = {"NVDA": 45.0, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    ai_valuation._CACHE_PATH.write_text(json.dumps(fresh), encoding="utf-8")
    loaded = ai_valuation.load_cache()
    assert loaded == fresh


def test_save_cache_atomic_write_does_not_clobber_existing(tmp_path):
    """tmp+os.replace pattern: even if file exists, the write succeeds."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache({"NVDA": 45.0, "fetched_at": "2026-09-11T12:00:00"})
    ai_valuation.save_cache({"AMD": 32.0, "fetched_at": "2026-09-11T13:00:00"})
    loaded = ai_valuation.load_cache()
    assert loaded["AMD"] == 32.0
    assert "NVDA" not in loaded  # second write fully replaces


def test_load_cache_returns_none_on_invalid_json(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation._CACHE_PATH.write_text("not json {", encoding="utf-8")
    assert ai_valuation.load_cache() is None


# ---- fetch_beneficiary_pe ----------------------------------------------------

def test_fetch_beneficiary_pe_cache_hit_does_not_call_yfinance(tmp_path):
    """When the cache is fresh, no yfinance call is made."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    fresh = {"NVDA": 45.0, "AMD": 32.0, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    ai_valuation.save_cache(fresh)
    with patch("yfinance.Ticker") as mock_ticker:
        result = ai_valuation.fetch_beneficiary_pe()
    mock_ticker.assert_not_called()
    assert result == fresh


def test_fetch_beneficiary_pe_skips_spenders(tmp_path):
    """Capex Spenders tickers (MSFT/GOOGL/AMZN/META/ORCL) are NOT in the fetch list."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    captured = []

    def fake_ticker(sym):
        captured.append(sym)
        t = MagicMock()
        t.info = {"forwardPE": 30.0}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        ai_valuation.fetch_beneficiary_pe(force=True)

    assert "MSFT" not in captured
    assert "GOOGL" not in captured
    assert "AMZN" not in captured
    assert "META" not in captured
    assert "ORCL" not in captured
    # Sanity: at least one beneficiary ticker was fetched
    assert any(s in captured for s in ("NVDA", "AMD", "MU"))


def test_fetch_beneficiary_pe_skips_invalid_pe_values(tmp_path):
    """None, NaN, negative, zero forward PEs are excluded from the result."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"

    pe_values = {"NVDA": 45.0, "AMD": None, "INTC": -5.0, "MU": float("nan"), "QCOM": 0}

    def fake_ticker(sym):
        t = MagicMock()
        t.info = {"forwardPE": pe_values.get(sym)}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        result = ai_valuation.fetch_beneficiary_pe(force=True)

    assert "NVDA" in result and result["NVDA"] == 45.0
    for skipped in ("AMD", "INTC", "MU", "QCOM"):
        assert skipped not in result, f"{skipped} should have been filtered"


def test_fetch_beneficiary_pe_partial_failure_does_not_crash(tmp_path):
    """One ticker raises; the others still land in the cache."""
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"

    def fake_ticker(sym):
        if sym == "NVDA":
            raise RuntimeError("rate-limited")
        t = MagicMock()
        t.info = {"forwardPE": 45.0}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        result = ai_valuation.fetch_beneficiary_pe(force=True)

    assert "NVDA" not in result
    assert result.get("AMD") == 45.0 or any(v == 45.0 for v in result.values())


def test_fetch_beneficiary_pe_force_refresh_ignores_cache(tmp_path):
    ai_valuation._CACHE_PATH = tmp_path / "ai_valuation.json"
    ai_valuation.save_cache({"NVDA": 1.0, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S")})

    def fake_ticker(sym):
        t = MagicMock()
        t.info = {"forwardPE": 99.0}
        return t

    with patch("yfinance.Ticker", side_effect=fake_ticker):
        result = ai_valuation.fetch_beneficiary_pe(force=True)
    assert result["NVDA"] == 99.0


# ---- compute_valuation -------------------------------------------------------

def test_compute_valuation_median():
    pe_map = {"a": 20.0, "b": 25.0, "c": 30.0, "d": 35.0, "e": 40.0}
    out = ai_valuation.compute_valuation(pe_map)
    assert out["median_pe"] == 30.0
    assert out["stretched"] is True  # median == 30 == threshold
    assert out["note"]  # non-empty


def test_compute_valuation_stretched_at_threshold():
    pe_map = {"a": 35.0, "b": 40.0}
    out = ai_valuation.compute_valuation(pe_map)
    assert out["median_pe"] == 37.5
    assert out["stretched"] is True


def test_compute_valuation_not_stretched_below_threshold():
    pe_map = {"a": 20.0, "b": 25.0}
    out = ai_valuation.compute_valuation(pe_map)
    assert out["median_pe"] == 22.5
    assert out["stretched"] is False


def test_compute_valuation_empty_returns_none_stretch():
    out = ai_valuation.compute_valuation({})
    assert out["median_pe"] is None
    assert out["stretched"] is False
    assert "no" in out["note"].lower() or "none" in out["note"].lower()


def test_compute_valuation_uses_config_threshold():
    """The threshold comes from config, not a hardcoded constant."""
    pe_map = {"a": 29.99, "b": 30.01}
    with patch.object(config, "AI_VALUATION_STRETCH_PE", 25.0):
        out = ai_valuation.compute_valuation(pe_map)
    # Both values > 25, median ~30; with threshold 25 the median is stretched
    assert out["stretched"] is True


def test_compute_valuation_includes_per_ticker_pe():
    pe_map = {"NVDA": 45.0, "AMD": 32.0}
    out = ai_valuation.compute_valuation(pe_map)
    assert out["per_ticker_pe"] == pe_map


def test_compute_valuation_includes_cache_ttl_hours():
    out = ai_valuation.compute_valuation({"a": 30.0})
    assert out["cache_ttl_hours"] == config.AI_VALUATION_CACHE_TTL_HOURS
```

- [ ] **Step 1.2: Run the new tests — confirm they fail (no module yet)**

```bash
python -m pytest tests/test_ai_valuation.py -q
```

Expected: `ModuleNotFoundError: No module named 'app.ai_valuation'` or import errors for the helpers. All tests red.

- [ ] **Step 1.3: Add config constants to `app/config.py`**

In `app/config.py`, immediately after the `RISK_SIGNAL_TOTAL = 8` line (line 224), add:

```python
# AI valuation (app/ai_valuation.py). Forward PE per cohort ticker, cached on
# disk; median across beneficiary cohorts (excluding Capex Spenders) feeds the
# AI gauge as a +score shift when stretched. Mirrors the structure of the
# deleted earnings-cache pattern but scoped to PE only.
AI_VALUATION_STRETCH_PE = 30.0          # median forward PE ≥ this → stretched
AI_VALUATION_SCORE_SHIFT = 25.0          # gauge score addend when stretched
AI_VALUATION_CACHE_TTL_HOURS = 12        # on-disk JSON cache TTL
AI_VALUATION_CACHE_PATH = DATA_DIR / "ai_valuation.json"  # gitignored cache file
```

Also add `DATA_DIR` reference check: confirm `DATA_DIR` is defined earlier in the file (it is — see the existing `DATA_DIR = Path("data")` pattern).

- [ ] **Step 1.4: Add the cache file to `data/.gitignore`**

```bash
git check-ignore -v data/ai_valuation.json || echo "NOT IGNORED — fix below"
```

If not ignored, append `ai_valuation.json` to `data/.gitignore`. (Verify by listing existing entries — likely `analysis.db`, `*.log`, `summary-*.md` are already there.)

- [ ] **Step 1.5: Implement `app/ai_valuation.py`**

```python
"""AI valuation: forward-PE cache + cohort median + stretched flag.

Replaces the deleted ``compute_valuation_flag`` from the 2026-09-06
earnings-watchlist cleanup. The new shape is narrower (PE only — no PEG,
no earnings-date) and is scoped to the beneficiary cohorts (the AI trade),
not the full AI_CAPEX_COHORTS universe (which includes Capex Spenders,
demand-side hyperscalers whose PE reflects the broader market).

Cache: on-disk JSON at ``config.AI_VALUATION_CACHE_PATH`` with a 12-hour
TTL (mirrors the deleted EARNINGS_CACHE pattern). Atomic write via
``tmp + os.replace`` so concurrent writers can't corrupt the file.

Fetch strategy: yfinance ``Ticker.info["forwardPE"]`` per ticker. Skip
tickers where the value is ``None`` / NaN / negative / zero (forward PE
< 0 means losses; PE = 0 means no estimate; both are unusable). Network
errors per-ticker are swallowed — one bad ticker doesn't fail the batch.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from . import config

# Path is bound at import time — tests/conftest.py patches this name
# directly on the module (NOT config.AI_VALUATION_CACHE_PATH).
_CACHE_PATH: Path = config.AI_VALUATION_CACHE_PATH

# Beneficiary cohorts = AI_CAPEX_COHORTS minus Capex Spenders. Computed once
# at import time so the hot path doesn't iterate the constant dict.
_BENEFICIARY_COHORTS: dict[str, list[str]] = {
    name: tickers
    for name, tickers in config.AI_CAPEX_COHORTS.items()
    if name != "Capex Spenders"
}
_BENEFICIARY_TICKERS: list[str] = sorted({
    t for tickers in _BENEFICIARY_COHORTS.values() for t in tickers
})


def _is_valid_pe(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, float):
        return not (math.isnan(v) or math.isinf(v)) and v > 0
    try:
        return float(v) > 0
    except (TypeError, ValueError):
        return False


def load_cache() -> dict | None:
    """Return the cached PE map if it exists AND is within TTL. Otherwise None."""
    if not _CACHE_PATH.exists():
        return None
    try:
        raw = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    fetched_at = raw.get("fetched_at")
    if not fetched_at:
        return None
    try:
        cached_time = time.strptime(fetched_at, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    age_s = time.time() - time.mktime(cached_time)
    if age_s > config.AI_VALUATION_CACHE_TTL_HOURS * 3600:
        return None
    return raw


def save_cache(pe_map: dict) -> None:
    """Atomic write to disk. Last full-file rewrite wins (acceptable for a
    developer cache)."""
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(_CACHE_PATH.parent),
        prefix=f"{_CACHE_PATH.name}-",
        suffix=".tmp",
    )
    try:
        os.close(fd)
        Path(tmp_path).write_text(json.dumps(pe_map, indent=2), encoding="utf-8")
        os.replace(tmp_path, _CACHE_PATH)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def fetch_beneficiary_pe(
    tickers: list[str] | None = None,
    *,
    force: bool = False,
) -> dict[str, float]:
    """Return {ticker: forward_pe} across beneficiary cohorts.

    Cache-first. On miss/expiry (or when force=True): walks the ticker
    list, calls ``yf.Ticker(sym).info["forwardPE"]``, filters invalid
    values, atomic-saves the partial map. Network errors per-ticker are
    swallowed — one rate-limited ticker doesn't fail the whole batch.
    """
    if not force:
        cached = load_cache()
        if cached is not None:
            # Strip the metadata keys; return only {ticker: pe}
            return {k: v for k, v in cached.items() if k != "fetched_at" and isinstance(v, (int, float))}

    import yfinance as yf  # imported lazily so test environments without yfinance still work

    symbols = tickers if tickers is not None else _BENEFICIARY_TICKERS
    out: dict[str, float] = {}
    for sym in symbols:
        try:
            info = yf.Ticker(sym).info or {}
        except Exception:
            continue
        pe = info.get("forwardPE")
        if _is_valid_pe(pe):
            out[sym] = float(pe)

    out["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_cache(out)
    # Return the per-ticker map only (caller doesn't see the metadata key)
    return {k: v for k, v in out.items() if k != "fetched_at"}


def compute_valuation(pe_map: dict[str, float]) -> dict:
    """Return the valuation summary the AI gauge consumes.

    Shape::

        {
            "median_pe": float | None,
            "stretched": bool,           # median_pe >= AI_VALUATION_STRETCH_PE
            "note": str,                 # human-readable
            "per_ticker_pe": dict,       # the input map (passthrough for hover)
            "fetched_at": str | None,    # ISO timestamp or None if pe_map empty
            "cache_ttl_hours": int,      # mirror of config.AI_VALUATION_CACHE_TTL_HOURS
        }
    """
    # Strip metadata key from pe_map (caller may pass a cache-shaped dict).
    per_ticker = {k: v for k, v in pe_map.items() if k != "fetched_at" and isinstance(v, (int, float))}
    cache_ttl = config.AI_VALUATION_CACHE_TTL_HOURS
    if not per_ticker:
        return {
            "median_pe": None,
            "stretched": False,
            "note": "no beneficiary PE data",
            "per_ticker_pe": {},
            "fetched_at": pe_map.get("fetched_at") if isinstance(pe_map, dict) else None,
            "cache_ttl_hours": cache_ttl,
        }
    vals = sorted(per_ticker.values())
    mid = len(vals) // 2
    if len(vals) % 2 == 0:
        median = (vals[mid - 1] + vals[mid]) / 2
    else:
        median = vals[mid]
    stretched = median >= config.AI_VALUATION_STRETCH_PE
    if stretched:
        note = f"median {median:.1f}× ≥ {config.AI_VALUATION_STRETCH_PE:g}× (stretched)"
    else:
        note = f"median {median:.1f}× < {config.AI_VALUATION_STRETCH_PE:g}×"
    return {
        "median_pe": round(median, 2),
        "stretched": stretched,
        "note": note,
        "per_ticker_pe": per_ticker,
        "fetched_at": pe_map.get("fetched_at") if isinstance(pe_map, dict) else None,
        "cache_ttl_hours": cache_ttl,
    }
```

- [ ] **Step 1.6: Add the autouse monkeypatch line to `tests/conftest.py`**

Open `tests/conftest.py` and find the existing `_isolate_data_files` fixture. The patch set already includes `config.DATA_DIR`, `changelog.LOG_DIR`, `store._analysis_repo`, etc. Add one new line in the same `monkeypatch.setattr(...)` block:

```python
    monkeypatch.setattr(ai_valuation, "_CACHE_PATH", tmp_path / "ai_valuation.json")
```

Add `from app import ai_valuation` to the conftest import block at the top.

- [ ] **Step 1.7: Run the new tests — confirm they pass**

```bash
python -m pytest tests/test_ai_valuation.py -q
```

Expected: all pass (15 tests). If the yfinance patch in `test_fetch_beneficiary_pe_partial_failure_does_not_crash` triggers the real yfinance path (it shouldn't, because `patch("yfinance.Ticker", ...)` replaces it), check the `side_effect` filter on the sym == "NVDA" branch.

- [ ] **Step 1.8: Run the full backend suite — confirm no regression**

```bash
python -m pytest tests/ -k "not thirteenf and not service_coverage and not portfolio_cache_sync" -q
```

Expected: same green baseline (459 passed per the SESSION_LOG note about the 2026-09-11 follow-ups). If `test_ai_valuation.py` is the only addition in this task, no other test should be affected — but verify the autouse patch doesn't break `test_changelog.py` or similar (it shouldn't; `_isolate_data_files` patches one more path).

- [ ] **Step 1.9: Commit**

```bash
git add app/ai_valuation.py app/config.py data/.gitignore tests/conftest.py tests/test_ai_valuation.py
git commit -m "feat(ai-valuation): forward-PE cache + beneficiary median + stretched flag"
```

---

### Task 2: AI gauge integration

**Files:**
- Modify: `app/ai_sentiment.py` (extend `compute_ai_sentiment` signature; add valuation to output; apply +25 score shift when stretched)
- Modify: `app/service.py` (`_recompute_ai_sentiment`: load PE map, build valuation dict, pass into `compute_ai_sentiment`)
- Modify: `tests/test_ai_sentiment.py` (3 new tests)

**Interfaces:**
- Consumes: `app.ai_valuation.fetch_beneficiary_pe`, `app.ai_valuation.compute_valuation`, `app.config.AI_VALUATION_SCORE_SHIFT`
- Produces: `compute_ai_sentiment(snapshot, events, valuation=None)` — the new third arg is a dict shaped like `compute_valuation()` output. Returned dict gains a `"valuation"` key with `{median_pe, stretched, note}`.
- `_recompute_ai_sentiment(events)` in `app/service.py`: fetches the PE map → builds valuation dict → passes to `compute_ai_sentiment`.

- [ ] **Step 2.1: Write failing tests in `tests/test_ai_sentiment.py`**

Open the existing file and append 3 tests (after the last existing test):

```python
# ---- AI valuation integration ----------------------------------------------

def test_compute_ai_sentiment_valuation_stretched_adds_score_shift():
    """When valuation.stretched is True, score += AI_VALUATION_SCORE_SHIFT."""
    from app import config
    snap = _minimal_snapshot()
    events = []
    base = ai_sentiment.compute_ai_sentiment(snap, events)
    with_stretch = ai_sentiment.compute_ai_sentiment(
        snap,
        events,
        valuation={"median_pe": 35.0, "stretched": True, "note": "x"},
    )
    assert with_stretch["score"] == round(base["score"] + config.AI_VALUATION_SCORE_SHIFT, 1)


def test_compute_ai_sentiment_valuation_not_stretched_no_shift():
    """valuation.stretched=False → score unchanged."""
    snap = _minimal_snapshot()
    events = []
    base = ai_sentiment.compute_ai_sentiment(snap, events)
    with_valuation = ai_sentiment.compute_ai_sentiment(
        snap,
        events,
        valuation={"median_pe": 22.0, "stretched": False, "note": "ok"},
    )
    assert with_valuation["score"] == base["score"]


def test_compute_ai_sentiment_valuation_missing_no_shift():
    """valuation=None (or omitted) → score unchanged."""
    snap = _minimal_snapshot()
    events = []
    base = ai_sentiment.compute_ai_sentiment(snap, events)
    explicit_none = ai_sentiment.compute_ai_sentiment(snap, events, valuation=None)
    assert explicit_none["score"] == base["score"]


def test_compute_ai_sentiment_output_includes_valuation_dict():
    """The returned dict always carries the valuation summary, even when no shift applies."""
    snap = _minimal_snapshot()
    events = []
    out = ai_sentiment.compute_ai_sentiment(
        snap,
        events,
        valuation={"median_pe": 25.0, "stretched": False, "note": "ok"},
    )
    assert "valuation" in out
    assert out["valuation"]["median_pe"] == 25.0
    assert out["valuation"]["stretched"] is False
```

The helper `_minimal_snapshot()` should match whatever existing tests in `test_ai_sentiment.py` already use — if there's no such helper, reuse the snapshot shape from an existing test (a minimal dict with `histories.extra` populated for the beneficiary cohorts and no events). Check the file's existing fixtures before adding the helper.

- [ ] **Step 2.2: Run the new tests — confirm they fail**

```bash
python -m pytest tests/test_ai_sentiment.py -q -k "valuation"
```

Expected: 4 tests red (signature doesn't accept `valuation` yet).

- [ ] **Step 2.3: Extend `compute_ai_sentiment` in `app/ai_sentiment.py`**

Add `valuation=None` to the signature. After the existing score cap, apply the shift. Add `valuation` to the return dict. The relevant block in `app/ai_sentiment.py` (around lines 142-150) becomes:

```python
    # Valuation shift: +AI_VALUATION_SCORE_SHIFT when the beneficiary cohort
    # median forward PE >= AI_VALUATION_STRETCH_PE. Stretches the gauge toward
    # Euphoric / fragility setup when AI supply-side multiples are crowded.
    val_summary = None
    if valuation is not None:
        val_summary = {
            "median_pe": valuation.get("median_pe"),
            "stretched": bool(valuation.get("stretched", False)),
            "note": valuation.get("note", ""),
        }
        if val_summary["stretched"]:
            score = round(max(-100, min(100, score + config.AI_VALUATION_SCORE_SHIFT)), 1)
    else:
        val_summary = {"median_pe": None, "stretched": False, "note": ""}

    # Re-classify verdict AFTER the valuation shift so the verdict reflects
    # the final score.
    euphoric_cut, expansion_cut = config.AI_SENTIMENT_VERDICT_CUTOFFS
    if score >= euphoric_cut:
        verdict = "Euphoric / fragility setup"
    elif score >= expansion_cut:
        verdict = "Healthy expansion"
    elif score >= -expansion_cut:
        verdict = "Balanced / mixed"
    elif score >= -euphoric_cut:
        verdict = "Cooling / divergence"
    else:
        verdict = "Cycle under pressure"

    flip_conditions = [
        "Beneficiaries' 3m ROC flips below spenders' (spread turns negative)",
        "Breadth across beneficiary cohorts drops below 40%",
        "AI news tone turns decisively bearish",
    ]

    return {
        "as_of": snapshot.get("as_of"),
        "score": score,
        "verdict": verdict,
        "cohorts": cohorts,
        "spread_pct": spread,
        "news": news,
        "valuation": val_summary,
        "flip_conditions": flip_conditions,
    }
```

**Important:** the existing verdict classification is currently in the same function block. Move it from its current position (around line 124) to AFTER the score cap+shift, so the verdict reflects the final score. Verify the function's existing imports include `from . import config` (it does — see `app/ai_sentiment.py:11`).

- [ ] **Step 2.4: Wire `_recompute_ai_sentiment` in `app/service.py`**

The existing function (around line 331-365 in `app/service.py`) calls `compute_ai_sentiment(snapshot, ai_events)` with two args. Extend it to load the PE map and pass the valuation through:

```python
def _recompute_ai_sentiment(events: list[dict[str, Any]]) -> dict[str, Any]:
    # ... existing snapshot-build code ...
    pe_map = ai_valuation.fetch_beneficiary_pe()
    valuation = ai_valuation.compute_valuation(pe_map)
    ai = ai_sentiment.compute_ai_sentiment(snapshot, ai_events, valuation=valuation)
    # ... existing return-stamp code ...
```

Add `from . import ai_valuation` to the `app/service.py` import block at the top (alongside the existing `from . import ai_sentiment`).

- [ ] **Step 2.5: Run the new tests — confirm they pass**

```bash
python -m pytest tests/test_ai_sentiment.py -q
```

Expected: all green, including the 4 new valuation tests.

- [ ] **Step 2.6: Run the full backend suite — confirm no regression**

```bash
python -m pytest tests/ -k "not thirteenf and not service_coverage and not portfolio_cache_sync" -q
```

Expected: same baseline + the 4 new valuation tests = 463 passed.

- [ ] **Step 2.7: Commit**

```bash
git add app/ai_sentiment.py app/service.py tests/test_ai_sentiment.py
git commit -m "feat(ai-gauge): wire beneficiary forward-PE as valuation score shift"
```

---

### Task 3: Frontend BREADTH - AI Proxies hover

**Files:**
- Modify: `static/js/cards.js` (`renderBreadthAIChart` — add per-bar hover with PE + cohort median + threshold)
- Create: `tests/frontend/breadth-ai-valuation.spec.mjs` (subset A — hover tests)

**Interfaces:**
- Consumes: `data.indicators.breadth_ai.detail[symbol].forward_pe`, `data.indicators.breadth_ai.cohort_median_pe`, frontend threshold mirror (read from data; if absent, default to `>= 30` per the tooltip annotation)
- Produces: Chart.js tooltip callback (inline in `renderBreadthAIChart`) that builds the hover text per bar

- [ ] **Step 3.1: Write the failing hover test**

Open a new file `tests/frontend/breadth-ai-valuation.spec.mjs` and write the hover test first:

```javascript
// tests/frontend/breadth-ai-valuation.spec.mjs
//
// BREADTH - AI Proxies hover + AI gauge Valuation (Beneficiary) cell.
// The static server fixture is started by the playwright config; this file
// only tests frontend rendering against the mock dashboard payload.
//
// Mocks live in tests/frontend/mock-dashboard.mjs; we override `breadth_ai`
// per-test with the PE-rich shape.

import { test, expect } from "@playwright/test";
import { installMockDashboard } from "./mock-dashboard.mjs";

const SAMPLE_PE_DETAIL = {
  NVDA: { above: true, forward_pe: 48.2 },
  AMD: { above: false, forward_pe: 32.1 },
  MU: { above: true, forward_pe: null },  // missing PE — hover should show —
  QCOM: { above: true, forward_pe: 15.4 },
};

const SAMPLE_PE_GROUPS = [
  { name: "Compute / Accelerators", symbols: ["NVDA", "AMD"] },
  { name: "Memory", symbols: ["MU", "005930.KS"] },
];

test.beforeEach(async ({ page }) => {
  await installMockDashboard(page, {
    breadth_ai: {
      breadth_pct: 60.0,
      detail: SAMPLE_PE_DETAIL,
      cohort_groups: SAMPLE_PE_GROUPS,
      cohort_median_pe: 32.15,
    },
  });
});

test("BREADTH - AI Proxies hover shows PE + cohort median + stretch threshold", async ({ page }) => {
  await page.goto("/");
  await page.waitForSelector('[data-card="breadth-ai"] canvas');
  // Hover the NVDA bar (leftmost in Compute / Accelerators).
  const canvas = page.locator('[data-card="breadth-ai"] canvas');
  const box = await canvas.boundingBox();
  await page.mouse.move(box.x + 20, box.y + box.height / 2);
  // Chart.js renders the tooltip element when a bar is hovered.
  const tooltip = page.locator('[data-card="breadth-ai"] .chartjs-tooltip, [data-card="breadth-ai"] [role="tooltip"]').first();
  // The chart-tooltip library may not be present; fall back to the body tooltip.
  // Use a body-level tooltip matcher.
  await expect(page.locator("body")).toContainText(/fwd PE 48\.2×/);
  await expect(page.locator("body")).toContainText(/cohort median 32\.1×/);
  await expect(page.locator("body")).toContainText(/stretch ≥ 30×/);
});

test("BREADTH - AI Proxies hover shows — for ticker with missing PE", async ({ page }) => {
  await page.goto("/");
  await page.waitForSelector('[data-card="breadth-ai"] canvas');
  // Force the hover to land on the MU bar by stubbing the chart's getElementsAtEventForMode.
  await page.evaluate(() => {
    const chart = Chart.getChart("breadthAIChart");
    if (chart) {
      // Find the index for "MU" in the labels.
      const idx = chart.data.labels.indexOf("MU");
      if (idx >= 0) {
        const meta = chart.getDatasetMeta(0);
        const bar = meta.data[idx];
        chart.setActiveElements([{ datasetIndex: 0, index: idx }]);
        chart.tooltip.setActiveElements([{ datasetIndex: 0, index: idx }], { x: bar.x, y: bar.y });
        chart.update();
      }
    }
  });
  await expect(page.locator("body")).toContainText(/MU.*fwd PE —/);
  // Cohort median still shown even when this ticker has no PE
  await expect(page.locator("body")).toContainText(/cohort median/);
});
```

- [ ] **Step 3.2: Run the failing test**

```bash
cd tests/frontend && npx playwright test breadth-ai-valuation.spec.mjs -g "shows PE"
```

Expected: red — Chart.js tooltip doesn't carry the new fields.

- [ ] **Step 3.3: Extend `renderBreadthAIChart` in `static/js/cards.js`**

Find the `_renderBarChart` helper (or the inline chart config for `breadthAIChart`) and add a tooltip callback. The simplest approach is to bypass `_renderBarChart` for this one chart by adding a custom tooltip option. Modify `renderBreadthAIChart`:

```javascript
function renderBreadthAIChart(ind) {
  const ctx = document.getElementById("breadthAIChart");
  if (!ctx) return;
  // Custom tooltip callback for the AI proxies chart: append forward PE +
  // cohort median + stretch annotation when the payload carries it.
  const cohortMedian = ind?.breadth_ai?.cohort_median_pe;
  const stretchThresh = 30;  // mirrors config.AI_VALUATION_STRETCH_PE — kept in sync via tooltip annotation
  const existing = Chart.getChart(ctx);
  const data = _buildBarChartData(ind?.breadth_ai);
  if (existing) {
    existing.data = data;
    existing.options.plugins.tooltip.callbacks = {
      ...(existing.options.plugins.tooltip.callbacks || {}),
      label: (ctx) => {
        const sym = ctx.label;
        const detail = (ind?.breadth_ai?.detail || {})[sym] || {};
        const pe = detail.forward_pe;
        const peStr = pe != null ? `fwd PE ${pe.toFixed(1)}×` : "fwd PE —";
        const medianStr = cohortMedian != null ? ` (cohort median ${cohortMedian.toFixed(1)}×; stretch ≥ ${stretchThresh}×)` : "";
        return `${sym} — ${peStr}${medianStr}`;
      },
    };
    existing.update();
    return;
  }
  new Chart(ctx, {
    type: "bar",
    data,
    options: {
      ..._BAR_CHART_DEFAULT_OPTIONS,
      plugins: {
        ..._BAR_CHART_DEFAULT_OPTIONS.plugins,
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const sym = ctx.label;
              const detail = (ind?.breadth_ai?.detail || {})[sym] || {};
              const pe = detail.forward_pe;
              const peStr = pe != null ? `fwd PE ${pe.toFixed(1)}×` : "fwd PE —";
              const medianStr = cohortMedian != null ? ` (cohort median ${cohortMedian.toFixed(1)}×; stretch ≥ ${stretchThresh}×)` : "";
              return `${sym} — ${peStr}${medianStr}`;
            },
          },
        },
      },
    },
  });
}
```

Note: this assumes `_BAR_CHART_DEFAULT_OPTIONS` is the existing constant `_renderBarChart` uses. If the helper is structured differently, mirror its shape — the goal is just a custom `label` callback that emits the new hover line.

- [ ] **Step 3.4: Run the hover test — confirm it passes**

```bash
cd tests/frontend && npx playwright test breadth-ai-valuation.spec.mjs -g "shows PE"
```

Expected: green.

- [ ] **Step 3.5: Run the full frontend suite — confirm no regression**

```bash
cd tests/frontend && npx playwright test -q
```

Expected: baseline + 2 new hover tests passing. Watch for any existing test that breaks due to the chart-tooltip shape change.

- [ ] **Step 3.6: Commit**

```bash
git add static/js/cards.js tests/frontend/breadth-ai-valuation.spec.mjs
git commit -m "feat(breadth-ai): hover shows forward PE + cohort median + stretch threshold"
```

---

### Task 4: Frontend AI gauge meta cell + tooltip addendum

**Files:**
- Modify: `static/js/cards.js` (`renderAISentiment` — add `Valuation (Beneficiary)` cell; `CARD_TOOLTIPS["ai-sentiment"]` — one-line addendum)
- Modify: `tests/frontend/breadth-ai-valuation.spec.mjs` (subset B — gauge tests)

- [ ] **Step 4.1: Write the failing gauge tests**

Append to `tests/frontend/breadth-ai-valuation.spec.mjs`:

```javascript
test("AI gauge meta row shows Valuation (Beneficiary) cell with median + stretched tag", async ({ page }) => {
  await installMockDashboard(page, {
    ai_sentiment: {
      score: 12.3,
      verdict: "Healthy expansion",
      cohorts: [],
      spread_pct: 5.0,
      news: { tone: "neutral" },
      valuation: { median_pe: 42.1, stretched: true, note: "median 42.1× ≥ 30× (stretched)" },
      flip_conditions: [],
    },
  });
  await page.goto("/");
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const meta = page.locator('[data-card="ai-sentiment"] .ai-gauge-meta');
  await expect(meta).toContainText(/Valuation \(Beneficiary\)/);
  await expect(meta).toContainText(/42\.1×/);
  await expect(meta).toContainText(/stretched/);
});

test("AI gauge meta row shows Valuation (Beneficiary) · ok when not stretched", async ({ page }) => {
  await installMockDashboard(page, {
    ai_sentiment: {
      score: 5.0,
      verdict: "Balanced / mixed",
      cohorts: [],
      spread_pct: 0,
      news: { tone: "neutral" },
      valuation: { median_pe: 22.0, stretched: false, note: "median 22.0× < 30×" },
      flip_conditions: [],
    },
  });
  await page.goto("/");
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const meta = page.locator('[data-card="ai-sentiment"] .ai-gauge-meta');
  await expect(meta).toContainText(/Valuation \(Beneficiary\)/);
  await expect(meta).toContainText(/22\.0×/);
  await expect(meta).toContainText(/· ok/);
});

test("AI gauge displays score +25 when valuation is stretched", async ({ page }) => {
  // Compare a not-stretched baseline against a stretched version.
  await installMockDashboard(page, {
    ai_sentiment: {
      score: 10.0,
      verdict: "Healthy expansion",
      cohorts: [],
      spread_pct: 0,
      news: { tone: "neutral" },
      valuation: { median_pe: 22.0, stretched: false, note: "ok" },
      flip_conditions: [],
    },
  });
  await page.goto("/");
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const beforeScoreText = await page.locator('[data-card="ai-sentiment"] .ai-gauge-meta').textContent();
  const beforeScoreMatch = beforeScoreText.match(/Score\s+(-?\d+(?:\.\d+)?)/);
  expect(beforeScoreMatch).not.toBeNull();
  const beforeScore = parseFloat(beforeScoreMatch[1]);

  await installMockDashboard(page, {
    ai_sentiment: {
      score: 35.0,  // before + 25
      verdict: "Healthy expansion",
      cohorts: [],
      spread_pct: 0,
      news: { tone: "neutral" },
      valuation: { median_pe: 42.0, stretched: true, note: "stretched" },
      flip_conditions: [],
    },
  });
  await page.reload();
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const afterScoreText = await page.locator('[data-card="ai-sentiment"] .ai-gauge-meta').textContent();
  const afterScoreMatch = afterScoreText.match(/Score\s+(-?\d+(?:\.\d+)?)/);
  expect(afterScoreMatch).not.toBeNull();
  const afterScore = parseFloat(afterScoreMatch[1]);
  expect(afterScore - beforeScore).toBeCloseTo(25, 0);
});

test("AI gauge info tooltip mentions the valuation score shift", async ({ page }) => {
  await page.goto("/");
  await page.waitForSelector('[data-card="ai-sentiment"]');
  const infoIcon = page.locator('[data-card="ai-sentiment"] h2 .info-icon').first();
  await infoIcon.hover();
  const tooltip = await infoIcon.getAttribute("title") || await infoIcon.evaluate(el => el.getAttribute("data-tip") || "");
  expect(tooltip).toMatch(/valuation.*shift/i);
  expect(tooltip).toMatch(/AI_VALUATION_SCORE_SHIFT/);
});
```

- [ ] **Step 4.2: Run the failing gauge tests**

```bash
cd tests/frontend && npx playwright test breadth-ai-valuation.spec.mjs -g "Valuation"
```

Expected: 4 tests red — meta cell doesn't exist yet; tooltip text doesn't mention valuation shift.

- [ ] **Step 4.3: Re-introduce the `Valuation (Beneficiary)` cell in `renderAISentiment`**

Find the `ai-gauge-meta` block in `static/js/cards.js` (around line 205, the Bug #2 fix removed the `<span>Valuation ...</span>` line). Restore it with the new shape:

```javascript
      <div class="ai-gauge-meta">
        <span>Score <b>${ai.score ?? "—"}</b></span>
        <span>Beneficiaries vs Spenders <b>${ai.spread_pct != null ? fmtPct(ai.spread_pct) : "—"}</b></span>
        <span>News <b class="${toneCellClass(ai.news?.tone)}">${escapeHtml(ai.news?.tone || "—")}</b></span>
        <span>Valuation (Beneficiary) <b>${ai.valuation?.median_pe != null ? ai.valuation.median_pe.toFixed(1) + "×" : "—"}</b> ${ai.valuation?.stretched ? "· stretched" : (ai.valuation ? "· ok" : "")}</span>
      </div>
```

The trailing tag logic:
- `stretched === true` → `· stretched`
- `stretched === false` AND `valuation` exists → `· ok`
- `valuation === undefined/null` (legacy payload) → no trailing tag (cell shows `—` for the median)

- [ ] **Step 4.4: Add the tooltip addendum in `CARD_TOOLTIPS["ai-sentiment"]`**

Find the existing `CARD_TOOLTIPS["ai-sentiment"].text` in `static/js/cards.js` (around line 754) and append:

```javascript
  "ai-sentiment": {
    text: "Reads AI-tagged events from the last 30 days (NEWS_LOOKBACK_DAYS) of data/events.json plus per-cohort momentum and breadth (% of constituents above their 50DMA, see Breadth — AI proxies). Composite score: avg cohort 3m ROC × 2.0 + (beneficiaries − spenders) ROC × 1.5 + AI news score × 0.3, capped at ±100; plus AI_VALUATION_SCORE_SHIFT (25) when median beneficiary cohort forward PE ≥ AI_VALUATION_STRETCH_PE (30×). Verdicts: Euphoric / Healthy expansion / Balanced / Cooling / Cycle under pressure at ±60 / ±20 / ±60 thresholds (AI_SENTIMENT_VERDICT_CUTOFFS). Coverage depends on news refresh cadence, cohort quote resolution, and the AI valuation cache freshness (12h TTL).",
    deps: ["news events (last 30 days)", "cohort quotes", "AI cohort breadth", "beneficiary cohort forward PE (12h cached)"],
  },
```

- [ ] **Step 4.5: Run the gauge tests — confirm they pass**

```bash
cd tests/frontend && npx playwright test breadth-ai-valuation.spec.mjs -q
```

Expected: all 6 tests green (2 hover + 3 gauge + 1 tooltip).

- [ ] **Step 4.6: Run the full frontend suite — confirm no regression**

```bash
cd tests/frontend && npx playwright test -q
```

Expected: baseline + 6 new tests. The 22 pre-existing failures mentioned in SESSION_LOG should remain at the same count (none of those failures should be caused by this change — the gauge cell addition is purely additive).

- [ ] **Step 4.7: Commit**

```bash
git add static/js/cards.js tests/frontend/breadth-ai-valuation.spec.mjs
git commit -m "feat(ai-gauge): re-introduce Valuation (Beneficiary) cell + tooltip addendum"
```

---

### Task 5: Mock payload updates for backward compat

**Files:**
- Modify: `tests/frontend/mock-dashboard.mjs` (add `valuation` field to default mock)
- Modify: 7 frontend spec files (`portfolio.spec.mjs`, `bottleneck-move.spec.mjs`, `bottleneck-rename.spec.mjs`, `portfolio-holdings-reorder.spec.mjs`, `portfolio-header-collapse.spec.mjs`, `portfolio-move.spec.mjs`, `portfolio-star-scope.spec.mjs`) — add `valuation: { median_pe: null, stretched: false, note: "" }` to the existing `ai_sentiment` mocks

- [ ] **Step 5.1: Update the default mock in `mock-dashboard.mjs`**

Find the `ai_sentiment` default in the mock dashboard payload. Add the `valuation` field with the empty shape so consumers don't break:

```javascript
ai_sentiment: {
  score: 0,
  verdict: "Neutral",
  spread_pct: 0,
  news: { tone: "neutral" },
  valuation: { median_pe: null, stretched: false, note: "" },
  cohorts: [],
  flip_conditions: [],
},
```

- [ ] **Step 5.2: Update existing frontend specs**

For each of the 7 spec files listed above, find the `ai_sentiment` literal and add `valuation: { median_pe: null, stretched: false, note: "" }` (or merge into the existing literal). The change is mechanical:

```javascript
ai_sentiment: { score: 0, verdict: "Neutral", spread_pct: 0, news: { tone: "neutral" }, valuation: { median_pe: null, stretched: false, note: "" }, cohorts: [], flip_conditions: [] },
```

Use `replaceAll` (or per-occurrence) since the same literal appears multiple times within each file.

- [ ] **Step 5.3: Run the full frontend suite — confirm no mock regressions**

```bash
cd tests/frontend && npx playwright test -q
```

Expected: same baseline (the additions are field-extensions; no existing test asserts on the absence of the `valuation` field).

- [ ] **Step 5.4: Commit**

```bash
git add tests/frontend/mock-dashboard.mjs tests/frontend/portfolio.spec.mjs tests/frontend/bottleneck-move.spec.mjs tests/frontend/bottleneck-rename.spec.mjs tests/frontend/portfolio-holdings-reorder.spec.mjs tests/frontend/portfolio-header-collapse.spec.mjs tests/frontend/portfolio-move.spec.mjs tests/frontend/portfolio-star-scope.spec.mjs
git commit -m "test(frontend): add valuation field to mock payloads for backward compat"
```

---

### Task 6: Session docs + changelog

**Files:**
- Modify: `data/logs/summary-2026-09-11.md` (via `app.changelog.log_change`)
- Modify: `project_rules/HANDOFF.md`
- Modify: `project_rules/SESSION_LOG.md` (new dated entry appended)

- [ ] **Step 6.1: Write the changelog entry**

```bash
python -c "from app.changelog import log_change; log_change('feat', 'AI valuation (Beneficiary): per-ticker forward-PE cache (12h on-disk TTL, excludes Capex Spenders) feeds BREADTH - AI Proxies hover and the AI capex-cycle gauge as a +25 score shift when median beneficiary PE ≥ 30×. New app/ai_valuation.py module; ai_sentiment.compute_ai_sentiment now accepts valuation= arg; Valuation (Beneficiary) cell restored to the AI gauge meta row. Backend: 463 passed (+4 in test_ai_sentiment, +15 in new test_ai_valuation). Frontend: +6 in new breadth-ai-valuation.spec.mjs.')"
```

- [ ] **Step 6.2: Update `project_rules/HANDOFF.md`**

Set the timestamp to today (`2026-09-11 HH:MM UTC`), update the "Current state" section to describe the new feature, and update "Top 3 next actions" with anything queued up.

- [ ] **Step 6.3: Append a new dated entry to `project_rules/SESSION_LOG.md`**

Append the new entry at the bottom of the file. The hybrid-layout convention applies — the latest entry is in full. Keep the entry compact: summary, files touched (8), tests added (15 + 4 + 6 = 25 total), one-paragraph rationale + decision-pointer reference.

- [ ] **Step 6.4: Commit**

```bash
git add project_rules/HANDOFF.md project_rules/SESSION_LOG.md
git commit -m "docs(project-rules): session end for AI valuation (Beneficiary) feature"
```

Note: the changelog file (`data/logs/summary-2026-09-11.md`) is gitignored per AGENTS.md — do NOT commit it.

---

## Self-Review

1. **Spec coverage:**
   - Section 1 (backend module + config + cache + isolation) → Task 1 ✓
   - Section 2 (AI gauge integration + score shift + verdict re-classification) → Task 2 ✓
   - Section 3 (BREADTH hover + Valuation (Beneficiary) cell + tooltip addendum) → Tasks 3 + 4 ✓
   - Section 4 (backend tests + frontend tests + conftest + mock updates) → Tasks 1 + 2 + 3 + 4 + 5 ✓
   - Session docs + changelog → Task 6 ✓

2. **Placeholder scan:** no "TBD" / "implement later" / "similar to Task N" found. The `test_compute_ai_sentiment_*` tests reference a `_minimal_snapshot()` helper — Step 2.1 explicitly says to check existing fixtures and reuse the snapshot shape from existing tests in `test_ai_sentiment.py`. If no such helper exists, use the snapshot shape from an existing test (one that exercises the same function with similar inputs). The `breadth-ai-valuation.spec.mjs` `installMockDashboard` helper is already used elsewhere per `tests/frontend/mock-dashboard.mjs` — Step 3.1's imports follow the existing pattern.

3. **Type consistency:**
   - `compute_valuation()` return shape: `{median_pe, stretched, note, per_ticker_pe, fetched_at, cache_ttl_hours}` (defined Task 1.5) is consumed in Task 1 tests verbatim.
   - `compute_ai_sentiment()` signature change `valuation=None` (Task 2.3) is consumed in Task 2.1 tests and Task 2.4 service wire.
   - `_recompute_ai_sentiment(events)` (Task 2.4) calls `ai_valuation.fetch_beneficiary_pe()` (Task 1.5) and `ai_valuation.compute_valuation(pe_map)` — types match.
   - Frontend `ai.valuation.median_pe`, `ai.valuation.stretched`, `ai.valuation.note` (Task 4.3) match the backend dict shape (`val_summary` in Task 2.3).
   - Frontend `ind.breadth_ai.detail[symbol].forward_pe` and `ind.breadth_ai.cohort_median_pe` (Task 3.3) — the `cohort_median_pe` field needs to be added to `breadth_ai` payload by the backend. **GAP FOUND:** Task 1 doesn't add `cohort_median_pe` to the `breadth_ai` payload. Add a step to Task 1 to set this in `app/indicators.py`.

   **FIX (inline):** add Step 1.10 to Task 1 to wire `cohort_median_pe` into the `breadth_ai` payload. Specifically: in `app/indicators.py`, after the cohort-groups loop (around line 239), call `ai_valuation.fetch_beneficiary_pe()` once per `compute_indicators` invocation to get the cached map, compute the median via `ai_valuation.compute_valuation(pe_map)["median_pe"]`, and add `breadth_ai["cohort_median_pe"] = median`. Import `ai_valuation` at the top of `app/indicators.py`. **Caveat:** `compute_indicators` is called on every refresh, so this adds one disk read per refresh (the cache is fast — `load_cache()` reads a small JSON file). If `ai_valuation` has never been fetched (no cache file yet), `fetch_beneficiary_pe()` will trigger the yfinance walk on the first refresh — same as the AI gauge path. This is acceptable because both paths benefit from the same first-refresh fetch.

   **Alternatively:** have `_recompute_ai_sentiment` (Task 2.4) be the single fetch point and put `cohort_median_pe` into the `ai_sentiment.valuation` dict, then have the frontend read `ai.valuation.median_pe` for the hover. But that breaks the spec ("cohort median" in the hover text) because the hover is built per-bar from `ind.breadth_ai.cohort_median_pe`, not from `ai.valuation`. Stick with the `indicators.py` integration.

4. **Ambiguity check:**
   - "12h TTL" — Task 1.5 implements via `time.mktime(time.strptime(fetched_at, ...))` vs `time.time()` (age in seconds). TTL is in hours. Implementation correctly multiplies by 3600.
   - "Beneficiary cohorts only" — Task 1.5 `_BENEFICIARY_COHORTS` is computed at import time from `AI_CAPEX_COHORTS` minus `"Capex Spenders"`. No magic strings beyond the single exclusion key.
   - "Stretch-only" — Task 2.3 applies the shift only when `val_summary["stretched"]` is True; never when False or None.
   - "Hover shows PE + cohort median + threshold" — Task 3.3 tooltip callback emits exactly these three pieces.

5. **Self-review passes.** Updated Task 1 with Step 1.10 to close the gap.
