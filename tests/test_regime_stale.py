"""Tests for app/regime.py get_regime stale-detection logic (no subprocess)."""

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from app import config, regime, store


# ---- helpers ----------------------------------------------------------------

def _fresh_report():
    """A valid regime report dict."""
    return {
        "regime": {"regime_label": "Transitional", "confidence": 61},
        "composite": {"composite_score": 50, "zone": "Neutral"},
    }


# ---- Fresh report (no stale flag) -------------------------------------------

def test_fresh_report_not_flagged_stale(monkeypatch, tmp_path):
    report = _fresh_report()
    fake_path = tmp_path / "macro_regime_2026-08-25.json"
    store.save_json(fake_path, report)

    monkeypatch.setattr(regime, "_latest_regime_file", lambda: fake_path)
    monkeypatch.setattr(store, "load_json", lambda p, **kw: report)

    body = regime.get_regime()
    assert "stale" not in body
    assert body["regime"]["regime_label"] == "Transitional"


# ---- Stale report (> REGIME_MAX_AGE_DAYS) -----------------------------------

def test_stale_report_flagged(monkeypatch, tmp_path):
    report = _fresh_report()
    fake_path = tmp_path / "macro_regime_2026-05-01.json"
    store.save_json(fake_path, report)

    # Set file mtime to well in the past
    old = time.time() - (config.REGIME_MAX_AGE_DAYS + 5) * 86400
    import os
    os.utime(fake_path, (old, old))

    monkeypatch.setattr(regime, "_latest_regime_file", lambda: fake_path)
    monkeypatch.setattr(store, "load_json", lambda p, **kw: report)

    body = regime.get_regime()
    assert body.get("stale") is True
    assert body["age_days"] > config.REGIME_MAX_AGE_DAYS


def test_stale_report_age_days_is_numeric(monkeypatch, tmp_path):
    report = _fresh_report()
    fake_path = tmp_path / "macro_regime_2026-01-01.json"
    store.save_json(fake_path, report)

    old = time.time() - 10 * 86400
    import os
    os.utime(fake_path, (old, old))

    monkeypatch.setattr(regime, "_latest_regime_file", lambda: fake_path)
    monkeypatch.setattr(store, "load_json", lambda p, **kw: report)

    body = regime.get_regime()
    assert isinstance(body["age_days"], float)
    assert body["age_days"] >= 10.0


# ---- No cached file + run_regime_detection returns None ----------------------

def test_no_cache_detection_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(regime, "_latest_regime_file", lambda: None)
    monkeypatch.setattr(regime, "run_regime_detection", lambda **kw: None)

    body = regime.get_regime()
    assert "error" in body
    assert body["error"] == "regime report unavailable"


# ---- No cached file + run_regime_detection returns error ---------------------

def test_no_cache_detection_returns_error(monkeypatch, tmp_path):
    error_payload = {"error": "regime detector skill not installed"}
    monkeypatch.setattr(regime, "_latest_regime_file", lambda: None)
    monkeypatch.setattr(regime, "run_regime_detection", lambda **kw: error_payload)

    body = regime.get_regime()
    assert "error" in body
    assert body["error"] == "regime detector skill not installed"


# ---- No cached file + detection succeeds ------------------------------------

def test_no_cache_detection_succeeds(monkeypatch, tmp_path):
    fresh = _fresh_report()
    monkeypatch.setattr(regime, "_latest_regime_file", lambda: None)
    monkeypatch.setattr(regime, "run_regime_detection", lambda **kw: fresh)

    body = regime.get_regime()
    assert body == fresh
    assert "stale" not in body


# ---- Edge: cached file exists but load_json returns None ---------------------

def test_cached_file_load_returns_none(monkeypatch, tmp_path):
    fake_path = tmp_path / "macro_regime_2026-08-25.json"
    # File doesn't actually exist, but _latest_regime_file returns it
    monkeypatch.setattr(regime, "_latest_regime_file", lambda: fake_path)
    monkeypatch.setattr(store, "load_json", lambda p, **kw: None)
    monkeypatch.setattr(regime, "run_regime_detection", lambda **kw: {"error": "fail"})

    # load_json returns None → falls through to run_regime_detection
    body = regime.get_regime()
    assert "error" in body
