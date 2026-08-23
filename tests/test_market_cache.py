"""Tests for app/market.py cache semantics — fully offline.

yfinance and Stooq are stubbed out; the assertions cover the failure-aware
caching rules (a failed fetch must never poison the cache) and the cache-key
sanitization that keeps user-supplied symbols inside CACHE_DIR.
"""

import pandas as pd
import pytest

from app import config, market


# ---- Fixtures / stubs --------------------------------------------------------

@pytest.fixture
def cache_dir(monkeypatch, tmp_path):
    d = tmp_path / "cache"
    monkeypatch.setattr(config, "CACHE_DIR", d)
    return d


class _RecordingYF:
    """Stands in for the yfinance module; counts download() invocations."""

    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls = 0

    def download(self, *args, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def _small_frame() -> pd.DataFrame:
    idx = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
    return pd.DataFrame({"Close": [10.0, 10.5, 11.0], "Volume": [1, 2, 3]}, index=idx)


# ---- get_history: failures are never cached ----------------------------------

def test_failed_history_fetch_not_cached_and_retried(cache_dir, monkeypatch):
    yf = _RecordingYF(error=RuntimeError("network disabled"))
    monkeypatch.setattr(market, "_yf", yf)

    key = f"hist_{market._safe_key('NOPE')}_5"
    assert market.get_history("NOPE", days=5) == []
    assert not (cache_dir / f"{key}.json").exists()

    # Second call must hit the sources again, not serve a poisoned cache.
    assert market.get_history("NOPE", days=5) == []
    assert yf.calls == 2
    assert not (cache_dir / f"{key}.json").exists()


def test_successful_history_populates_cache(cache_dir, monkeypatch):
    yf = _RecordingYF(result=_small_frame())
    monkeypatch.setattr(market, "_yf", yf)

    out = market.get_history("TEST", days=250)
    assert len(out) == 3
    assert out[-1] == {"date": "2026-01-06", "close": 11.0}

    cached = market._fresh(f"hist_TEST_250", config.HISTORY_TTL)
    assert cached == out

    # Second call is served entirely from cache.
    again = market.get_history("TEST", days=250)
    assert again == out
    assert yf.calls == 1


def test_empty_download_counts_as_failure_for_single_history(cache_dir, monkeypatch):
    """An empty frame is a failed fetch, not an empty truth."""
    yf = _RecordingYF(result=pd.DataFrame())
    monkeypatch.setattr(market, "_yf", yf)

    assert market.get_history("VOID", days=5) == []
    assert list(cache_dir.glob("hist_VOID_*")) == []


# ---- get_histories_bulk: failures are never cached ---------------------------

def test_failed_bulk_history_not_cached_and_retried(cache_dir, monkeypatch):
    yf = _RecordingYF(result=pd.DataFrame())  # empty => nothing fetched
    monkeypatch.setattr(market, "_yf", yf)

    out1 = market.get_histories_bulk(["AAA", "BBB"], days=250)
    assert out1 == {}
    assert list(cache_dir.glob("bulkhist_*")) == []

    out2 = market.get_histories_bulk(["AAA", "BBB"], days=250)
    assert out2 == {}
    # One bulk download per call (an empty frame short-circuits before the
    # per-symbol fallback); the point is the retry happened at all.
    assert yf.calls == 2
    assert list(cache_dir.glob("bulkhist_*")) == []


def test_successful_bulk_history_populates_cache(cache_dir, monkeypatch):
    idx = pd.to_datetime(["2026-01-02", "2026-01-05"])
    frame = pd.DataFrame(
        {"AAA": [1.0, 1.1], "BBB": [2.0, 2.2]}, index=idx,
    )
    # Bulk downloads come back with a column MultiIndex (price field on top).
    frame.columns = pd.MultiIndex.from_product([["Close"], ["AAA", "BBB"]])
    yf = _RecordingYF(result=frame)
    monkeypatch.setattr(market, "_yf", yf)

    out = market.get_histories_bulk(["AAA", "BBB"], days=250)
    assert set(out) == {"AAA", "BBB"}
    assert out["BBB"][-1] == {"date": "2026-01-05", "close": 2.2}

    files = list(cache_dir.glob("bulkhist_*.json"))
    assert len(files) == 1

    assert market.get_histories_bulk(["AAA", "BBB"], days=250) == out
    assert yf.calls == 1


# ---- Futures snapshot: all-null results are never cached ---------------------

def test_all_null_futures_snapshot_not_cached_and_retried(cache_dir, monkeypatch):
    calls = []

    def failing_quotes(symbols):
        calls.append(list(symbols))
        return {}

    monkeypatch.setattr(market, "_quote_snapshot", failing_quotes)

    snap = market.build_futures_snapshot()
    items = snap["index_futures"] + snap["commodities"]
    assert items, "futures universe must be non-empty"
    assert all(i["last"] is None and i["chg_pct"] is None for i in items)
    assert not (cache_dir / "quotes_futures.json").exists()

    market.build_futures_snapshot()
    assert len(calls) == 2  # retry happened instead of serving nulls


def test_futures_snapshot_with_data_is_cached(cache_dir, monkeypatch):
    calls = []

    def partial_quotes(symbols):
        calls.append(1)
        return {"ES=F": {"price": 5000.0, "change": 10.0, "pct_change": 0.2}}

    monkeypatch.setattr(market, "_quote_snapshot", partial_quotes)

    snap = market.build_futures_snapshot()
    es = next(i for i in snap["index_futures"] if i["symbol"] == "ES=F")
    assert es["last"] == 5000.0
    assert es["prior_close"] == 4990.0
    # Symbols without data stay explicitly null (never fabricated).
    nq = next(i for i in snap["index_futures"] if i["symbol"] == "NQ=F")
    assert nq["last"] is None

    assert (cache_dir / "quotes_futures.json").exists()
    market.build_futures_snapshot()
    assert len(calls) == 1  # served from cache


# ---- Cache-key sanitization ---------------------------------------------------

def test_safe_key_strips_traversal_and_separators():
    k = market._safe_key("../../evil")
    assert "/" not in k and "\\" not in k
    assert k == "....EVIL"  # dots survive, separators do not: no traversal

    assert market._safe_key("a/b") == "AB"
    assert market._safe_key(r"C:\temp\x") == "CTEMPX"
    assert market._safe_key("") == ""

    # Whatever comes in, the resulting cache path stays inside CACHE_DIR.
    p = market._cache_path(market._safe_key("../../evil"))
    assert p.parent == config.CACHE_DIR
    p2 = market._cache_path(market._safe_key("a/b/c"))
    assert p2.parent == config.CACHE_DIR


def test_safe_key_keeps_valid_yahoo_symbols_unchanged():
    assert market._safe_key("^VIX") == "^VIX"
    assert market._safe_key("BRK.B") == "BRK.B"
    assert market._safe_key("GC=F") == "GC=F"
    assert market._safe_key("BTC-USD") == "BTC-USD"
