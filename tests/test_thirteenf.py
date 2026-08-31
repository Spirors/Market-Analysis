"""Tests for app/thirteenf.py: mock EDGAR responses for issuer_ticker_map,
_norm_issuer, weight-% aggregation, and build_thirteenf.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app import config, thirteenf, store


# ---- _norm_issuer ------------------------------------------------------------

def test_norm_issuer_lowercases_and_strips():
    assert thirteenf._norm_issuer("  Berkshire  Hathaway  ") == "BERKSHIRE HATHAWAY"


def test_norm_issuer_removes_punctuation():
    assert thirteenf._norm_issuer("Berkshire-Hathaway Inc.") == "BERKSHIRE HATHAWAY INC"


def test_norm_issuer_empty():
    assert thirteenf._norm_issuer("") == ""
    assert thirteenf._norm_issuer("") == ""


# ---- issuer_ticker_map -------------------------------------------------------

def test_issuer_ticker_map_uses_cache(tmp_path, monkeypatch):
    """When a fresh cache exists, no HTTP request is made."""
    cache_path = tmp_path / "company_tickers.json"
    cached_data = {"BERKSHIRE HATHAWAY": "BRK-B", "PERSHING SQUARE": "PSHZF"}
    cache_path.write_text(json.dumps(cached_data), encoding="utf-8")

    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    result = thirteenf.issuer_ticker_map()
    assert result == cached_data


def test_issuer_ticker_map_fetches_when_no_cache(tmp_path, monkeypatch):
    """When no cache exists, fetch from SEC and cache the result."""
    cache_file = tmp_path / "company_tickers.json"
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    fake_raw = {
        "0": {"cik_str": 1, "ticker": "BRK-B", "title": "Berkshire Hathaway Inc"},
        "1": {"cik_str": 2, "ticker": "AAPL", "title": "Apple Inc"},
    }

    with patch.object(thirteenf, "_get_json", return_value=fake_raw):
        result = thirteenf.issuer_ticker_map()

    assert "BERKSHIRE HATHAWAY INC" in result
    assert result["BERKSHIRE HATHAWAY INC"] == "BRK-B"
    assert "APPLE INC" in result
    # Cache file was written
    assert cache_file.exists()


def test_issuer_ticker_map_returns_empty_on_fetch_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    with patch.object(thirteenf, "_get_json", side_effect=RuntimeError("network error")):
        result = thirteenf.issuer_ticker_map()
    assert result == {}


# ---- _parse_info_table -------------------------------------------------------

def test_parse_info_table_basic():
    xml_bytes = b"""<?xml version="1.0"?>
    <informationTable>
      <infoTable>
        <nameOfIssuer>Apple Inc</nameOfIssuer>
        <value>15000</value>
      </infoTable>
      <infoTable>
        <nameOfIssuer>Microsoft Corp</nameOfIssuer>
        <value>12000</value>
      </infoTable>
    </informationTable>"""
    rows = thirteenf._parse_info_table(xml_bytes)
    assert len(rows) == 2
    assert rows[0]["issuer"] == "Apple Inc"
    assert rows[0]["value"] == 15000.0
    assert rows[1]["issuer"] == "Microsoft Corp"
    assert rows[1]["value"] == 12000.0


def test_parse_info_table_empty():
    xml_bytes = b"""<?xml version="1.0"?><root/>"""
    rows = thirteenf._parse_info_table(xml_bytes)
    assert rows == []


def test_parse_info_table_skips_missing_fields():
    xml_bytes = b"""<?xml version="1.0"?>
    <informationTable>
      <infoTable>
        <nameOfIssuer>Apple Inc</nameOfIssuer>
      </infoTable>
      <infoTable>
        <nameOfIssuer>Microsoft Corp</nameOfIssuer>
        <value>12000</value>
      </infoTable>
    </informationTable>"""
    rows = thirteenf._parse_info_table(xml_bytes)
    assert len(rows) == 1
    assert rows[0]["issuer"] == "Microsoft Corp"


# ---- _build_fund (weight-% aggregation) --------------------------------------

def test_build_fund_aggregates_and_ranks():
    rows = [
        {"issuer": "Apple Inc", "value": 10000},
        {"issuer": "Apple Inc", "value": 5000},
        {"issuer": "Microsoft Corp", "value": 8000},
    ]
    with patch.object(thirteenf, "issuer_ticker_map", return_value={
        "APPLE INC": "AAPL",
        "MICROSOFT CORP": "MSFT",
    }):
        fund = thirteenf._build_fund("Test Fund", 12345, "2026-Q2", rows)

    assert fund["name"] == "Test Fund"
    assert fund["cik"] == 12345
    assert fund["quarter"] == "2026-Q2"
    assert fund["n_positions"] == 2  # two unique issuers

    # Top positions sorted by value (descending)
    assert fund["top"][0]["issuer"] == "Apple Inc"
    assert fund["top"][0]["ticker"] == "AAPL"
    assert fund["top"][0]["weight_pct"] == pytest.approx(65.2, abs=0.5)

    assert fund["top"][1]["issuer"] == "Microsoft Corp"
    assert fund["top"][1]["ticker"] == "MSFT"
    assert fund["top"][1]["weight_pct"] == pytest.approx(34.8, abs=0.5)


def test_build_fund_empty_rows():
    fund = thirteenf._build_fund("Empty", 99, "2026-Q1", [])
    assert fund["n_positions"] == 0
    assert fund["top"] == []


def test_build_fund_unknown_issuer():
    """Unknown issuer returns ticker=None."""
    rows = [{"issuer": "Mystery Corp", "value": 5000}]
    with patch.object(thirteenf, "issuer_ticker_map", return_value={}):
        fund = thirteenf._build_fund("Fund", 1, "2026-Q1", rows)
    assert fund["top"][0]["ticker"] is None


# ---- _apply_fund_meta --------------------------------------------------------

def test_apply_fund_meta_stamps_manager_and_link():
    payload = {
        "funds": [
            {"name": "Berkshire Hathaway", "cik": 1067983},
            {"name": "Unknown Fund", "cik": 999999},
        ]
    }
    result = thirteenf._apply_fund_meta(payload)
    berkshire = result["funds"][0]
    assert berkshire["manager"] == "Warren Buffett"
    assert "wikipedia" in berkshire["link"].lower()

    unknown = result["funds"][1]
    assert unknown.get("manager") is None
    assert unknown.get("link") is None


# ---- build_thirteenf (integration with cache) --------------------------------

def test_build_thirteenf_returns_cached_when_fresh(tmp_path, monkeypatch):
    """When the snapshot cache is fresh, no EDGAR requests are made."""
    snap_path = tmp_path / thirteenf._SNAPSHOT_CACHE
    payload = {
        "as_of": "2026-08-01T00:00:00+00:00",
        "quarter": "2026-Q2",
        "funds": [{"name": "Test", "cik": 1, "top": []}],
        "errors": [],
    }
    store.save_json(snap_path, {
        "cached_at": __import__("time").time(),
        "payload": payload,
    })
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    result = thirteenf.build_thirteenf()
    assert len(result["funds"]) == 1
    assert result["funds"][0]["name"] == "Test"
