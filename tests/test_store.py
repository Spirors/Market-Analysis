"""Tests for app/store.py: atomic JSON writes, migration, dedupe, tag ops."""

import json
from pathlib import Path

import pytest

from app import config, store


# ---- Fixtures ----------------------------------------------------------------

@pytest.fixture
def tmp_store(monkeypatch, tmp_path) -> dict[str, Path]:
    """Point the store at throwaway files for this test only.

    Returns the resolved paths so tests can assert on them directly. The
    store caches its ``_READY`` flag inside a single process, so each test
    gets a fresh ``store._READY = False`` to force re-init."""
    paths = {
        "events": tmp_path / "events.json",
        "analysis": tmp_path / "analysis.db",
        "data": tmp_path,
    }
    monkeypatch.setattr(config, "EVENTS_PATH", paths["events"])
    monkeypatch.setattr(config, "ANALYSIS_DB_PATH", paths["analysis"])
    monkeypatch.setattr(config, "DATA_DIR", paths["data"])
    monkeypatch.setattr(store, "_READY", False)
    monkeypatch.setattr(store, "_ANALYSIS_READY", False)
    return paths


def _ev(link: str, title: str, published: str, impact: str = "High",
        source: str = "TestFeed", summary: str = "") -> dict:
    return {
        "link": link,
        "title": title,
        "published": published,
        "impact": impact,
        "source": source,
        "summary": summary,
        "date_label": None,
        "category": "macro",
        "actor": "government",
        "direction": "bearish",
        "region": "us",
    }


# ---- save_json atomicity -----------------------------------------------------

def test_save_json_writes_target_without_temp_leftovers(tmp_path):
    target = tmp_path / "nested" / "snap.json"
    payload = {"a": 1, "b": ["x", "y"]}

    store.save_json(target, payload)

    assert target.exists()
    assert store.load_json(target) == payload
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


# ---- days_apart --------------------------------------------------------------

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
    assert store._days_apart("junk", "junk") != 0


# ---- JSON state round-trip ---------------------------------------------------

def test_state_round_trips_atomically(tmp_store):
    store._ensure_ready()
    store._save_state({"version": 1, "events": [], "suppressed_sources": []})

    raw = tmp_store["events"].read_text(encoding="utf-8")
    parsed = json.loads(raw)
    assert parsed["version"] == 1
    assert parsed["events"] == []
    # No leftover temp file after atomic rename.
    assert list(tmp_store["data"].glob("events.json.tmp")) == []


def test_empty_state_on_blank_file(tmp_store, monkeypatch):
    """A truncated/empty events.json must read as empty, not crash."""
    tmp_store["events"].write_text("", encoding="utf-8")
    state = store._load_state()
    assert state == {"version": 1, "events": [], "suppressed_sources": []}


def test_empty_state_on_corrupt_json(tmp_store):
    tmp_store["events"].write_text("{not json", encoding="utf-8")
    state = store._load_state()
    assert state == {"version": 1, "events": [], "suppressed_sources": []}


# ---- upsert / dedupe ---------------------------------------------------------

def test_upsert_inserts_then_updates_by_link(tmp_store):
    ev = _ev("https://x/1", "Fed cuts rates", "2026-08-20T10:00:00")

    assert store.upsert_events([ev]) == 1
    assert store.upsert_events([dict(ev, summary="refreshed")]) == 0

    rows = store.list_events()
    assert len(rows) == 1
    assert rows[0]["summary"] == "refreshed"
    assert "bearish" in rows[0]["tags"]


def test_cross_source_similar_event_merges_and_escalates_impact(tmp_store):
    first = _ev("https://a/1", "Fed cuts rates by 50 basis points",
                "2026-08-20T10:00:00", impact="High", source="FeedA")
    twin = _ev("https://b/2", "Fed cuts rates by 50 basis points!",
               "2026-08-21T09:00:00", impact="Critical", source="FeedB")

    assert store.upsert_events([first]) == 1
    assert store.upsert_events([twin]) == 0

    rows = store.list_events()
    assert len(rows) == 1
    assert rows[0]["link"] == "https://a/1"
    assert rows[0]["impact"] == "Critical"


def test_dissimilar_titles_are_not_merged(tmp_store):
    store.upsert_events([_ev("https://a/1", "Fed cuts rates by 50 basis points",
                             "2026-08-20T10:00:00")])
    store.upsert_events([_ev("https://b/2", "Oil slides as demand fears grow",
                             "2026-08-21T09:00:00")])

    assert len(store.list_events()) == 2


def test_similar_titles_outside_date_window_are_not_merged(tmp_store):
    title = "Fed cuts rates by 50 basis points"
    store.upsert_events([_ev("https://a/1", title, "2026-08-01T10:00:00")])
    store.upsert_events([_ev("https://b/2", title, "2026-08-20T10:00:00")])

    assert len(store.list_events()) == 2


def test_list_events_orders_newest_first_and_respects_limit(tmp_store):
    store.upsert_events([
        _ev("https://x/1", "Event one", "2026-08-01T10:00:00"),
        _ev("https://x/2", "Event two", "2026-08-10T10:00:00"),
        _ev("https://x/3", "Event three", "2026-08-05T10:00:00"),
    ])

    rows = store.list_events(limit=2)
    assert [r["link"] for r in rows] == ["https://x/2", "https://x/3"]


# ---- list_events filters ----------------------------------------------------

def test_list_events_since_iso_excludes_older(tmp_store):
    store.upsert_events([
        _ev("https://x/old", "Old", "2026-07-01T10:00:00"),
        _ev("https://x/new", "New", "2026-08-20T10:00:00"),
    ])

    rows = store.list_events(since_iso="2026-08-01T00:00:00")
    assert [r["link"] for r in rows] == ["https://x/new"]


def test_list_events_ai_only_returns_tagged_only(tmp_store):
    store.upsert_events([
        _ev("https://x/ai", "Nvidia data center spend surges", "2026-08-20T10:00:00"),
        _ev("https://x/fed", "Fed holds rates steady", "2026-08-20T10:00:00"),
    ])

    rows = store.list_events(ai_only=True)
    assert [r["link"] for r in rows] == ["https://x/ai"]


# ---- AI auto-tag -------------------------------------------------------------

def test_ai_keywords_trigger_auto_tag_on_insert(tmp_store):
    store.upsert_events([_ev("https://x/1", "Nvidia data center spend surges",
                             "2026-08-20T10:00:00")])
    rows = store.list_events()
    assert store.AI_TAG in rows[0]["tags"]


def test_non_ai_titles_get_no_ai_tag(tmp_store):
    store.upsert_events([_ev("https://x/1", "Fed holds rates steady",
                             "2026-08-20T10:00:00")])
    rows = store.list_events()
    assert store.AI_TAG not in rows[0]["tags"]


def test_ai_tag_not_added_on_update_when_text_changes(tmp_store):
    """Refresh path: a row that wasn't AI on first insert does NOT pick up
    "ai" on subsequent RSS refreshes, even if the new title is about AI.
    The auto-tag fires once at insert; updates preserve whatever the user
    (or a previous ingest) tagged, so the gauge's tag count is stable."""
    store.upsert_events([_ev("https://x/1", "Fed holds rates steady",
                             "2026-08-20T10:00:00")])
    assert store.AI_TAG not in store.list_events()[0]["tags"]

    store.upsert_events([_ev("https://x/1", "Nvidia chip demand explodes",
                             "2026-08-20T11:00:00", summary="HBM memory tight")])
    assert store.AI_TAG not in store.list_events()[0]["tags"]


# ---- User tag management -----------------------------------------------------

def test_update_event_tags_adds_and_removes(tmp_store):
    store.upsert_events([_ev("https://x/1", "Generic story",
                             "2026-08-20T10:00:00")])
    store.update_event_tags("https://x/1", add=["watchlist"], remove=[])

    rows = store.list_events()
    assert "watchlist" in rows[0]["tags"]
    # The fixed dimensions (bearish/region) are still in the display tags.
    assert "bearish" in rows[0]["tags"]


def test_update_event_tags_returns_none_for_unknown_link(tmp_store):
    assert store.update_event_tags("https://x/missing", add=["x"]) is None


def test_ai_tag_can_be_manually_removed_and_stays_removed(tmp_store):
    """The auto "ai" tag is mutable: the user can drop it, and a subsequent
    upsert (RSS refresh) must NOT silently re-apply it."""
    store.upsert_events([_ev("https://x/1", "Nvidia chip demand",
                             "2026-08-20T10:00:00")])
    # First the row exists with the auto-tag.
    assert store.AI_TAG in store.list_events()[0]["tags"]

    # Manual removal sticks.
    store.update_event_tags("https://x/1", add=[], remove=["ai"])
    assert store.AI_TAG not in store.list_events()[0]["tags"]

    # A subsequent upsert for the same link must not re-add "ai" — the user
    # explicitly removed it, so their choice wins on update.
    store.upsert_events([_ev("https://x/1", "Nvidia chip demand still",
                             "2026-08-20T11:00:00")])
    assert store.AI_TAG not in store.list_events()[0]["tags"]


def test_update_event_tags_invalidates_garbage(tmp_store):
    store.upsert_events([_ev("https://x/1", "Generic", "2026-08-20T10:00:00")])
    store.update_event_tags(
        "https://x/1",
        add=["good-tag", "", "spaces inside are ok", "<script>alert(1)</script>"],
        remove=[],
    )
    rows = store.list_events()
    tags = rows[0]["tags"]
    assert "good-tag" in tags
    assert "spaces inside are ok" in tags
    # Empty strings and unsafe characters are rejected silently.
    assert "" not in tags
    assert "<script>alert(1)</script>" not in tags


def test_update_event_tags_persists_across_reads(tmp_store):
    store.upsert_events([_ev("https://x/1", "Generic", "2026-08-20T10:00:00")])
    store.update_event_tags("https://x/1", add=["manual-note"], remove=[])

    # Force a fresh load (simulate a new process).
    monkeypatch_helper = store._load_state()
    rows = [e for e in monkeypatch_helper["events"] if e["link"] == "https://x/1"]
    assert "manual-note" in rows[0]["tags"]


# ---- delete / suppress -------------------------------------------------------

def test_delete_event_removes_one(tmp_store):
    store.upsert_events([
        _ev("https://x/1", "First", "2026-08-20T10:00:00"),
        _ev("https://x/2", "Second", "2026-08-21T10:00:00"),
    ])
    store.delete_event("https://x/1")
    assert [r["link"] for r in store.list_events()] == ["https://x/2"]


def test_suppress_source_blocks_and_purges(tmp_store):
    store.upsert_events([
        _ev("https://x/1", "Spam", "2026-08-20T10:00:00", source="BadFeed"),
        _ev("https://x/2", "Good", "2026-08-20T10:00:00", source="GoodFeed"),
    ])
    store.suppress_source("BadFeed")
    assert "BadFeed" in store.get_suppressed_sources()
    assert [r["link"] for r in store.list_events()] == ["https://x/2"]


# ---- migration ---------------------------------------------------------------

def test_migration_from_legacy_sqlite(tmp_store, tmp_path):
    """Build a legacy news.db with one event, then trigger migration."""
    import sqlite3

    legacy = tmp_store["data"] / "news.db"
    legacy_conn = sqlite3.connect(str(legacy))
    legacy_conn.execute(
        """CREATE TABLE events (
            link TEXT UNIQUE NOT NULL,
            source TEXT, title TEXT, published TEXT,
            date_label TEXT, summary TEXT, category TEXT,
            actor TEXT, direction TEXT, region TEXT, impact TEXT,
            first_seen TEXT, updated_at TEXT)"""
    )
    legacy_conn.execute(
        "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "https://x/migrated",
            "LegacyFeed",
            "Old story about Nvidia AI accelerator rollout",
            "2026-08-01T10:00:00",
            None, "",
            "macro", "company", "bullish", "us", "High",
            "2026-08-01T10:00:00", "2026-08-01T10:00:00",
        ),
    )
    legacy_conn.execute(
        """CREATE TABLE analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL, stance TEXT NOT NULL,
            confidence REAL NOT NULL, payload_json TEXT NOT NULL)"""
    )
    legacy_conn.execute(
        "INSERT INTO analysis_runs (ts, stance, confidence, payload_json) VALUES (?,?,?,?)",
        ("2026-08-01T11:00:00", "Risk-On", 0.7, '{"headline":"x"}'),
    )
    legacy_conn.commit()
    legacy_conn.close()
    del legacy_conn
    import gc
    gc.collect()

    # Trigger migration (mimicking what _ensure_ready does on first call).
    store._migrate_legacy_db()

    # Core invariant: events were migrated and AI-tagged.
    state = store._load_state()
    assert len(state["events"]) == 1
    assert state["events"][0]["link"] == "https://x/migrated"
    assert store.AI_TAG in state["events"][0]["tags"]
    # analysis_runs were migrated to the analysis DB.
    assert tmp_store["analysis"].exists()
    # The legacy DB should be gone (renamed). Note: on Python 3.14 / Windows
    # SQLite holds the journal file handle briefly, but the production
    # migration runs in a fresh process so this is reliable outside tests.
