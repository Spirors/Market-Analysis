"""Tests for app/store.py: atomic JSON writes, one-time DB init, dedupe."""

from pathlib import Path

import pytest

from app import config, store


# ---- Fixtures ----------------------------------------------------------------

@pytest.fixture
def tmp_db(monkeypatch, tmp_path) -> Path:
    """Point the store at a throwaway database for this test only."""
    db_path = tmp_path / "news.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(store, "_DB_READY", False)
    return db_path


def _ev(link: str, title: str, published: str, impact: str = "High",
        source: str = "TestFeed") -> dict:
    return {
        "link": link,
        "title": title,
        "published": published,
        "impact": impact,
        "source": source,
        "summary": "",
        "date_label": None,
        "category": "macro",
        "actor": "Fed",
        "direction": "bearish",
        "region": "US",
    }


# ---- save_json atomicity -----------------------------------------------------

def test_save_json_writes_target_without_temp_leftovers(tmp_path):
    target = tmp_path / "nested" / "snap.json"
    payload = {"a": 1, "b": ["x", "y"]}

    store.save_json(target, payload)

    assert target.exists()
    assert store.load_json(target) == payload
    # The temp file must have been renamed onto the target, not left behind.
    assert list(tmp_path.glob("**/*.tmp")) == []


def test_save_json_overwrite_leaves_no_debris(tmp_path):
    target = tmp_path / "snap.json"
    store.save_json(target, {"v": 1})
    store.save_json(target, {"v": 2})

    assert store.load_json(target) == {"v": 2}
    assert list(tmp_path.glob("*.tmp")) == []


def test_load_json_missing_file_returns_default(tmp_path):
    assert store.load_json(tmp_path / "nope.json") is None
    assert store.load_json(tmp_path / "nope.json", default=[]) == []


# ---- init_db runs once per process -------------------------------------------

def test_ensure_db_initializes_exactly_once(tmp_db, monkeypatch):
    calls = []
    real_init = store.init_db

    def counting_init():
        calls.append(1)
        real_init()

    monkeypatch.setattr(store, "init_db", counting_init)
    monkeypatch.setattr(store, "_DB_READY", False)

    store._ensure_db()
    store._ensure_db()
    store._ensure_db()

    assert calls == [1]
    assert store._DB_READY is True


def test_init_db_is_idempotent_on_existing_schema(tmp_db):
    store.init_db()
    store.upsert_events([_ev("https://x/1", "Fed cuts rates", "2026-08-20T10:00:00")])
    store.init_db()  # second run must not raise or wipe rows

    rows = store.list_events()
    assert len(rows) == 1


# ---- _days_apart -------------------------------------------------------------

def test_days_apart_between_valid_dates():
    assert store._days_apart("2026-01-01T10:00:00", "2026-01-04T10:00:00") == 3
    assert store._days_apart("2026-01-04T10:00:00", "2026-01-01T10:00:00") == 3
    assert store._days_apart("2026-01-01T10:00:00", "2026-01-01T10:00:00") == 0
    # Quirk (documented, harmless for the 2-day dedupe window): timedelta.days
    # floors negative deltas, so intraday gaps round up to 1 "day".
    assert store._days_apart("2026-01-01T10:00:00", "2026-01-01T18:00:00") == 1


def test_days_apart_unparseable_dates_return_sentinel():
    """Undated items must never look 'in window' for dedupe."""
    assert store._days_apart("not-a-date", "2026-01-01T00:00:00") == 9999
    assert store._days_apart("2026-01-01T00:00:00", "garbage") == 9999
    assert store._days_apart(None, None) == 9999
    assert store._days_apart("", "") == 9999
    # The sentinel must be distinguishable from any real gap (incl. 0).
    assert store._days_apart("junk", "junk") != 0


# ---- Event insert / dedupe ---------------------------------------------------

def test_upsert_inserts_then_updates_by_link(tmp_db):
    ev = _ev("https://x/1", "Fed cuts rates by 50 basis points", "2026-08-20T10:00:00")

    assert store.upsert_events([ev]) == 1
    # Same link again is an update, not a new row.
    assert store.upsert_events([dict(ev, summary="refreshed")]) == 0

    rows = store.list_events()
    assert len(rows) == 1
    assert rows[0]["summary"] == "refreshed"
    assert "bearish" in rows[0]["tags"]


def test_cross_source_similar_event_merges_and_escalates_impact(tmp_db):
    first = _ev("https://a/1", "Fed cuts rates by 50 basis points",
                "2026-08-20T10:00:00", impact="High", source="FeedA")
    twin = _ev("https://b/2", "Fed cuts rates by 50 basis points!",
               "2026-08-21T09:00:00", impact="Critical", source="FeedB")

    assert store.upsert_events([first]) == 1
    assert store.upsert_events([twin]) == 0  # merged into the existing row

    rows = store.list_events()
    assert len(rows) == 1
    assert rows[0]["link"] == "https://a/1"
    assert rows[0]["impact"] == "Critical"  # escalation across sources


def test_dissimilar_titles_are_not_merged(tmp_db):
    store.upsert_events([_ev("https://a/1", "Fed cuts rates by 50 basis points",
                             "2026-08-20T10:00:00")])
    store.upsert_events([_ev("https://b/2", "Oil slides as demand fears grow",
                             "2026-08-21T09:00:00")])

    assert len(store.list_events()) == 2


def test_similar_titles_outside_date_window_are_not_merged(tmp_db):
    title = "Fed cuts rates by 50 basis points"
    store.upsert_events([_ev("https://a/1", title, "2026-08-01T10:00:00")])
    store.upsert_events([_ev("https://b/2", title, "2026-08-20T10:00:00")])

    # Same story text, but 19 days apart => two distinct events.
    assert len(store.list_events()) == 2


def test_list_events_orders_newest_first_and_respects_limit(tmp_db):
    store.upsert_events([
        _ev("https://x/1", "Event one", "2026-08-01T10:00:00"),
        _ev("https://x/2", "Event two", "2026-08-10T10:00:00"),
        _ev("https://x/3", "Event three", "2026-08-05T10:00:00"),
    ])

    rows = store.list_events(limit=2)
    assert [r["link"] for r in rows] == ["https://x/2", "https://x/3"]
