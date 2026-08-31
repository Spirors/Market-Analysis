"""Tests for app/spot.py — FRED + Minted Metal fetchers and the unified snapshot.

Network is stubbed throughout: these tests must run offline. The CSV/JSON
parsing rules and per-source dispatcher are exercised end-to-end without
ever touching FRED or Minted Metal.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app import config, service, spot


# ---- FRED CSV fixtures ------------------------------------------------------

# FRED emits a header row + 3 observation-metadata lines; the parser must
# skip them and parse only the real observations.
_FRED_CSV_WTI = (
    "DATE,DCOILWTICO\n"
    ".\n"
    ".\n"
    ".\n"
    "2026-08-21,87.21\n"
    "2026-08-24,86.34\n"
    "2026-08-25,83.90\n"
)
# "." inside the body = FRED's placeholder for "no observation".
_FRED_CSV_BRENT = (
    "DATE,DCOILBRENTEU\n"
    "2026-08-21,96.92\n"
    "2026-08-24,.\n"
    "2026-08-25,88.24\n"
)
_FRED_CSV_NG = (
    "DATE,DHHNGSP\n"
    "2026-08-21,2.85\n"
    "2026-08-24,2.83\n"
    "2026-08-25,2.70\n"
)


# ---- Minted Metal fixtures --------------------------------------------------

_MINTED_METAL_FULL = {
    "publisher": {"name": "Minted Metal", "url": "https://mintedmetal.com"},
    "license": {"name": "Attribution 4.0 International (CC BY 4.0)"},
    "updatedAt": "2026-08-31T17:49:05.797Z",
    "metals": {
        "gold": {
            "price": 4562.75, "previousPrice": 4568.95,
            "currency": "USD", "unit": "troy oz",
            "source": "LBMA", "sourceLabel": "London PM Fix",
            "sourceUrl": "https://www.lbma.org.uk/prices-and-data/precious-metal-prices",
            "fixedAt": "2026-08-28T15:00:00Z",
        },
        "silver": {
            "price": 70.26, "previousPrice": 68.47,
            "currency": "USD", "unit": "troy oz",
            "source": "LBMA", "sourceLabel": "London Silver Fix",
            "sourceUrl": "https://www.lbma.org.uk/prices-and-data/precious-metal-prices",
            "fixedAt": "2026-08-28T12:00:00Z",
        },
    },
}


# ---- Fixtures / helpers -----------------------------------------------------

@pytest.fixture
def cache_dir(monkeypatch, tmp_path):
    d = tmp_path / "cache"
    monkeypatch.setattr(config, "CACHE_DIR", d)
    return d


class _FakeResponse:
    def __init__(self, payload: str | bytes, content_type: str = "text/csv"):
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        self._payload = payload
        self.headers = {"Content-Type": content_type}

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _UrlRecorder:
    """Stands in for urllib.request.urlopen; routes by URL prefix."""

    def __init__(self, *, csv_by_series: dict[str, str] | None = None,
                 minted_payload: dict | None = None,
                 fail_urls: set[str] | None = None):
        self.csv_by_series = csv_by_series or {}
        self.minted_payload = minted_payload
        self.fail_urls = fail_urls or set()
        self.urls_called: list[str] = []

    def __call__(self, req, timeout=15):
        url = req.full_url if hasattr(req, "full_url") else req
        self.urls_called.append(url)
        if url in self.fail_urls:
            raise RuntimeError(f"simulated outage: {url}")
        if url.startswith("https://fred.stlouisfed.org/graph/fredgraph.csv"):
            for sid, csv_text in self.csv_by_series.items():
                if sid in url:
                    return _FakeResponse(csv_text)
            raise RuntimeError(f"no FRED fixture for: {url}")
        if url == config.MINTED_METAL_URL:
            if self.minted_payload is None:
                raise RuntimeError("no Minted Metal fixture provided")
            return _FakeResponse(json.dumps(self.minted_payload), "application/json")
        raise RuntimeError(f"unexpected URL: {url}")


# ---- _fetch_fred_series -----------------------------------------------------

def test_fetch_fred_series_drops_metadata_and_parses_values():
    import urllib.request
    original = urllib.request.urlopen
    urllib.request.urlopen = lambda req, timeout=15: _FakeResponse(_FRED_CSV_WTI)
    try:
        rows = spot._fetch_fred_series("DCOILWTICO")
    finally:
        urllib.request.urlopen = original
    assert rows[0][0] == "2026-08-25"  # newest-first
    assert rows[1][0] == "2026-08-24"
    assert rows[0][1] == pytest.approx(83.90)


def test_fetch_fred_series_handles_placeholder_dot():
    """FRED uses "." for missing values; parser must convert to None."""
    import urllib.request
    original = urllib.request.urlopen
    urllib.request.urlopen = lambda req, timeout=15: _FakeResponse(_FRED_CSV_BRENT)
    try:
        rows = spot._fetch_fred_series("DCOILBRENTEU")
    finally:
        urllib.request.urlopen = original
    # Newest non-null is 88.24; the placeholder row in the middle is skipped.
    assert rows[0] == ("2026-08-25", 88.24)
    # The middle "." row is preserved as a None tuple so callers can see it.
    assert ("2026-08-24", None) in rows
    assert rows[-1] == ("2026-08-21", 96.92)


# ---- _item_from_fred --------------------------------------------------------

def test_item_from_fred_builds_full_payload(monkeypatch):
    monkeypatch.setattr(spot, "_fetch_fred_series", lambda sid: [
        ("2026-08-25", 83.90),
        ("2026-08-24", 86.34),
    ])
    item = spot._item_from_fred("DCOILWTICO", "WTI Spot ($/bbl)")
    assert item["id"] == "DCOILWTICO"
    assert item["name"] == "WTI Spot ($/bbl)"
    assert item["last"] == pytest.approx(83.90)
    assert item["prior_close"] == pytest.approx(86.34)
    assert item["chg"] == pytest.approx(-2.44)
    assert item["pct_change"] == pytest.approx(-2.826)
    assert item["source_date"] == "2026-08-25"
    assert "FRED" in item["source_label"]
    assert "DCOILWTICO" in item["source_url"]


def test_item_from_fred_handles_single_observation(monkeypatch):
    """A series with only one non-null point → no chg/pct_change."""
    monkeypatch.setattr(spot, "_fetch_fred_series",
                        lambda sid: [("2026-08-25", 83.90)])
    item = spot._item_from_fred("DCOILWTICO", "WTI")
    assert item["last"] == 83.90
    assert item["prior_close"] is None
    assert item["chg"] is None
    assert item["pct_change"] is None


def test_item_from_fred_handles_total_failure(monkeypatch):
    """A network failure leaves last=None and surfaces error; never raises."""
    def boom(*a, **kw):
        raise RuntimeError("connection refused")
    monkeypatch.setattr(spot, "_fetch_fred_series", boom)

    item = spot._item_from_fred("DCOILWTICO", "WTI")
    assert item["last"] is None
    assert item["prior_close"] is None
    assert item["chg"] is None
    assert item["pct_change"] is None
    assert "RuntimeError" in item["error"]


# ---- _item_from_minted_metal ------------------------------------------------

def test_item_from_minted_metal_uses_shared_payload():
    item = spot._item_from_minted_metal(
        "AU", "Gold Spot (LBMA, $/oz)", "gold",
        payload=_MINTED_METAL_FULL,
    )
    assert item["id"] == "AU"
    assert item["last"] == pytest.approx(4562.75)
    assert item["prior_close"] == pytest.approx(4568.95)
    assert item["chg"] == pytest.approx(-6.20)
    assert item["pct_change"] == pytest.approx(-0.136)
    assert item["source_date"] == "2026-08-28"
    assert "LBMA" in item["source_label"]
    assert item["source_url"].startswith("https://www.lbma.org.uk")


def test_item_from_minted_metal_missing_key_returns_error():
    """An unknown metal key surfaces as an error row, never a crash."""
    item = spot._item_from_minted_metal(
        "AU", "Gold", "plutonium", payload={"metals": {"gold": _MINTED_METAL_FULL["metals"]["gold"]}},
    )
    assert item["last"] is None
    assert "missing 'plutonium'" in item["error"]


def test_item_from_minted_metal_null_price_safe():
    """None for price/previousPrice → last=None, chg=None."""
    payload = {"metals": {"gold": {
        "price": None, "previousPrice": None,
        "fixedAt": "2026-08-28T15:00:00Z",
    }}}
    item = spot._item_from_minted_metal("AU", "Gold", "gold", payload=payload)
    assert item["last"] is None
    assert item["prior_close"] is None
    assert item["source_date"] == "2026-08-28"


# ---- build_spot_snapshot (offline, end-to-end) ------------------------------

def test_build_spot_snapshot_returns_all_five_items(monkeypatch, cache_dir):
    """3 FRED + 2 Minted Metal = 5 items (the spot-card universe)."""
    recorder = _UrlRecorder(
        csv_by_series={
            "DCOILWTICO": _FRED_CSV_WTI,
            "DCOILBRENTEU": _FRED_CSV_BRENT,
            "DHHNGSP": _FRED_CSV_NG,
        },
        minted_payload=_MINTED_METAL_FULL,
    )
    monkeypatch.setattr(spot.urllib.request, "urlopen", recorder)

    snap = spot.build_spot_snapshot()
    assert snap["as_of"]
    assert len(snap["items"]) == len(config.SPOT_SERIES) + len(config.SPOT_METALS)
    assert {i["id"] for i in snap["items"]} == {
        "DCOILWTICO", "DCOILBRENTEU", "DHHNGSP", "AU", "AG",
    }
    assert snap["attribution"] == config.MINTED_METAL_ATTRIBUTION


def test_build_spot_snapshot_shares_one_minted_metal_fetch(monkeypatch, cache_dir):
    """Both precious metals should share a single HTTP request."""
    recorder = _UrlRecorder(
        csv_by_series={
            "DCOILWTICO": _FRED_CSV_WTI,
            "DCOILBRENTEU": _FRED_CSV_BRENT,
            "DHHNGSP": _FRED_CSV_NG,
        },
        minted_payload=_MINTED_METAL_FULL,
    )
    monkeypatch.setattr(spot.urllib.request, "urlopen", recorder)

    spot.build_spot_snapshot()
    minted_calls = [u for u in recorder.urls_called if u == config.MINTED_METAL_URL]
    assert len(minted_calls) == 1, (
        f"expected 1 shared Minted Metal fetch, got {len(minted_calls)}"
    )


def test_build_spot_snapshot_minted_failure_does_not_break_fred(monkeypatch, cache_dir):
    """A Minted Metal outage reports errors on each metal row; FRED still works."""
    recorder = _UrlRecorder(
        csv_by_series={
            "DCOILWTICO": _FRED_CSV_WTI,
            "DCOILBRENTEU": _FRED_CSV_BRENT,
            "DHHNGSP": _FRED_CSV_NG,
        },
        fail_urls={config.MINTED_METAL_URL},
    )
    monkeypatch.setattr(spot.urllib.request, "urlopen", recorder)

    snap = spot.build_spot_snapshot()
    fred_ids = set(config.SPOT_SERIES)
    fred_items = [i for i in snap["items"] if i["id"] in fred_ids]
    metal_items = [i for i in snap["items"] if i["id"] in config.SPOT_METALS]
    assert all(i["last"] is not None for i in fred_items)
    assert all(i["last"] is None and i.get("error") for i in metal_items)


def test_build_spot_snapshot_caches_on_success(monkeypatch, cache_dir):
    """A populated snapshot is cached; the second call skips the network."""
    recorder = _UrlRecorder(
        csv_by_series={
            "DCOILWTICO": _FRED_CSV_WTI,
            "DCOILBRENTEU": _FRED_CSV_BRENT,
            "DHHNGSP": _FRED_CSV_NG,
        },
        minted_payload=_MINTED_METAL_FULL,
    )
    monkeypatch.setattr(spot.urllib.request, "urlopen", recorder)

    first = spot.build_spot_snapshot()
    assert (cache_dir / "spot_quotes.json").exists()

    # FRED has 3 series, each is its own URL → 3 fetches on the first call.
    # Minted Metal is shared across all precious metals → 1 fetch.
    fred_calls = [u for u in recorder.urls_called if "fred" in u]
    minted_calls = [u for u in recorder.urls_called if u == config.MINTED_METAL_URL]
    assert len(fred_calls) == 3, (
        f"expected 3 FRED fetches (one per series), got {len(fred_calls)}"
    )
    assert len(minted_calls) == 1

    # Second call: ALL network is skipped (cache hit).
    spot.build_spot_snapshot()
    later_fred = [u for u in recorder.urls_called if "fred" in u]
    later_minted = [u for u in recorder.urls_called if u == config.MINTED_METAL_URL]
    assert len(later_fred) == 3, "FRED count must not grow on cache hit"
    assert len(later_minted) == 1, "Minted Metal count must not grow on cache hit"
    assert first["as_of"]


def test_build_spot_snapshot_does_not_cache_all_null(monkeypatch, cache_dir):
    """An all-null snapshot must NOT poison the cache (retry next call)."""
    recorder = _UrlRecorder(
        csv_by_series={
            "DCOILWTICO": "DATE,DCOILWTICO\n",
            "DCOILBRENTEU": "DATE,DCOILBRENTEU\n",
            "DHHNGSP": "DATE,DHHNGSP\n",
        },
        fail_urls={config.MINTED_METAL_URL},
    )
    monkeypatch.setattr(spot.urllib.request, "urlopen", recorder)

    spot.build_spot_snapshot()
    assert not (cache_dir / "spot_quotes.json").exists()

    # Second call retries both sources — 3 FRED × 2 calls = 6.
    spot.build_spot_snapshot()
    fred_calls = [u for u in recorder.urls_called if "fred" in u]
    assert len(fred_calls) == 6


# ---- service.py wiring ------------------------------------------------------

def test_service_coverage_does_not_emit_spot_section():
    """Spot no longer has its own coverage key — it's folded into commodities."""
    spot_payload = {"items": [
        {"id": "DCOILWTICO", "last": 1.0, "chg": 0.1, "pct_change": 10.0,
         "name": "WTI", "source_label": "test"},
    ], "commodities_map": {}}
    cov = service._coverage_counts({"spot": spot_payload})
    # No standalone 'spot' key — its items are surfaced via commodities_map
    # for the Commodities card.
    assert "spot" not in cov


# ---- commodities_map (renderer contract) ------------------------------------

def test_spot_snapshot_emits_commodities_map_keyed_by_yahoo_futures_symbol(monkeypatch, cache_dir):
    """The Commodities card consumes ``spot.commodities_map`` keyed by the
    matching Yahoo futures ticker, not by FRED/Minted Metal ids. The renderer
    is therefore oblivious to the upstream source family."""
    from urllib.request import Request as _Req
    minted_payload = {"metals": {
        "gold": {"price": 4500.0, "previousPrice": 4490.0,
                 "source": "LBMA", "sourceLabel": "London PM Fix",
                 "sourceUrl": "https://www.lbma.org.uk/x",
                 "fixedAt": "2026-08-28T15:00:00Z"},
        "silver": {"price": 70.0, "previousPrice": 69.0,
                   "source": "LBMA", "sourceLabel": "London Silver Fix",
                   "sourceUrl": "https://www.lbma.org.uk/x",
                   "fixedAt": "2026-08-28T12:00:00Z"},
    }}
    recorder = _UrlRecorder(
        csv_by_series={
            "DCOILWTICO": _FRED_CSV_WTI,
            "DCOILBRENTEU": _FRED_CSV_BRENT,
            "DHHNGSP": _FRED_CSV_NG,
        },
        minted_payload=minted_payload,
    )
    monkeypatch.setattr(spot.urllib.request, "urlopen", recorder)

    snap = spot.build_spot_snapshot()
    cm = snap["commodities_map"]
    # Yahoo ticker → spot item, matching what the Commodities card iterates over.
    assert set(cm.keys()) == {"CL=F", "BZ=F", "NG=F", "GC=F", "SI=F"}
    assert cm["CL=F"]["name"] == "WTI Spot ($/bbl)"
    assert cm["CL=F"]["last"] == pytest.approx(83.90)
    assert cm["GC=F"]["last"] == pytest.approx(4500.0)
    assert cm["SI=F"]["last"] == pytest.approx(70.0)


def test_commodities_map_includes_failed_rows_with_null_last(monkeypatch, cache_dir):
    """Failed items still appear in commodities_map with last=None so the
    renderer can show '—' next to the matching futures row."""
    recorder = _UrlRecorder(
        csv_by_series={
            "DCOILWTICO": _FRED_CSV_WTI,
            "DCOILBRENTEU": _FRED_CSV_BRENT,
            "DHHNGSP": _FRED_CSV_NG,
        },
        fail_urls={config.MINTED_METAL_URL},
    )
    monkeypatch.setattr(spot.urllib.request, "urlopen", recorder)

    snap = spot.build_spot_snapshot()
    cm = snap["commodities_map"]
    # Energy: live (FRED worked).
    assert cm["CL=F"]["last"] == pytest.approx(83.90)
    assert cm["BZ=F"]["last"] == pytest.approx(88.24)
    assert cm["NG=F"]["last"] == pytest.approx(2.70)
    # Precious metals: present but null (renderer shows '—').
    assert cm["GC=F"]["last"] is None
    assert "error" in cm["GC=F"]
    assert cm["SI=F"]["last"] is None
    assert "error" in cm["SI=F"]