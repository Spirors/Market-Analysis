"""Tests for the per-day summary log (app/changelog.py)."""

from __future__ import annotations

import datetime

import pytest

from app import changelog


@pytest.fixture(autouse=True)
def _patch_log_dir(monkeypatch, tmp_path):
    """Redirect LOG_DIR to a temporary directory for every test."""
    monkeypatch.setattr(changelog, "LOG_DIR", tmp_path)
    return tmp_path


# ── log_change ──────────────────────────────────────────────────────


def test_log_change_creates_file_with_header(tmp_path):
    day = datetime.date(2026, 8, 27)
    result = changelog.log_change("scheduler", "installed daily task", day=day)
    assert result == tmp_path / "summary-2026-08-27.md"
    content = result.read_text(encoding="utf-8")
    assert content.startswith("## 2026-08-27\n")


def test_log_change_appends_entry(tmp_path):
    day = datetime.date(2026, 8, 27)
    changelog.log_change("scheduler", "first entry", day=day)
    changelog.log_change("commit", "second entry", day=day)
    content = changelog.read_day(day)
    assert "first entry" in content
    assert "second entry" in content
    # Header should appear exactly once.
    assert content.count("## 2026-08-27") == 1


def test_log_change_strips_newlines_in_message(tmp_path):
    day = datetime.date(2026, 8, 27)
    changelog.log_change("ui", "line one\nline two\r\nline three", day=day)
    content = changelog.read_day(day)
    assert "line one line two line three" in content
    # Embedded newlines must not produce extra ### lines.
    assert content.count("### ") == 1


def test_log_change_rejects_bad_category():
    with pytest.raises(ValueError, match="invalid characters"):
        changelog.log_change("has space", "msg")
    with pytest.raises(ValueError, match="invalid characters"):
        changelog.log_change("UPPER", "msg")
    with pytest.raises(ValueError, match="non-empty"):
        changelog.log_change("", "msg")


def test_read_day_returns_empty_when_no_file(tmp_path):
    result = changelog.read_day(datetime.date(2000, 1, 1))
    assert result == ""


def test_read_day_returns_full_content(tmp_path):
    day = datetime.date(2026, 8, 27)
    changelog.log_change("doc", "updated docs", day=day)
    content = changelog.read_day(day)
    assert "## 2026-08-27" in content
    assert "updated docs" in content


def test_log_change_creates_log_dir(tmp_path):
    """When LOG_DIR does not yet exist, log_change should create it."""
    nested = tmp_path / "deep" / "nested"
    changelog.LOG_DIR = nested  # type: ignore[attr-defined]
    day = datetime.date(2026, 8, 27)
    result = changelog.log_change("config", "changed config", day=day)
    assert nested.exists()
    assert result.exists()


def test_log_change_atomic_write_does_not_corrupt(tmp_path):
    """After a write the file should end cleanly with no leftover .tmp files."""
    day = datetime.date(2026, 8, 27)
    changelog.log_change("scheduler", "entry one", day=day)
    changelog.log_change("commit", "entry two", day=day)

    file_path = tmp_path / "summary-2026-08-27.md"
    content = file_path.read_text(encoding="utf-8")
    assert content.endswith("\n")
    # No .tmp remnants.
    assert not any(tmp_path.glob("*.tmp"))
    # File ends with a clean entry (the last ### line).
    lines = content.rstrip("\n").split("\n")
    assert lines[-1].startswith("### ") or lines[-2].startswith("### ")


def test_read_day_defaults_to_today(tmp_path):
    day = datetime.date.today()
    changelog.log_change("scheduler", "today entry", day=day)
    content = changelog.read_day()  # no arg → today
    assert "today entry" in content
