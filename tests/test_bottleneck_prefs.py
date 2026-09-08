"""Tests for bottleneck category preferences (reorder + rename)."""

import pytest
from fastapi.testclient import TestClient

from app import bottleneck, bottleneck_prefs, config, store
from app.api import app


CANONICAL = [c["category"] for c in bottleneck.BOTTLENECK_CATEGORIES]


@pytest.fixture
def client():
    return TestClient(app, base_url="http://127.0.0.1:8000")


@pytest.fixture
def tmp_prefs(monkeypatch, tmp_path):
    """Redirect bottleneck prefs to a temp dir so tests don't clobber the real file."""
    prefs_path = tmp_path / "bottleneck_prefs.json"
    monkeypatch.setattr(bottleneck_prefs, "_PREFS_PATH", prefs_path)
    return prefs_path


# ---- BOTTLENECK_CATEGORIES is never mutated ----------------------------------

def test_bottleneck_categories_unchanged():
    """The module constant's order must not be mutated by prefs operations."""
    original = [c["category"] for c in bottleneck.BOTTLENECK_CATEGORIES]
    # Simulate a rename + reorder
    prefs = {"version": 1, "order": list(reversed(CANONICAL)), "renames": {"Agentic AI": "My AI"}}
    bottleneck_prefs.save_prefs(prefs)
    result = [c["category"] for c in bottleneck.BOTTLENECK_CATEGORIES]
    assert result == original


# ---- load_prefs / save_prefs ------------------------------------------------

def test_load_prefs_returns_default_when_file_missing(tmp_prefs):
    prefs = bottleneck_prefs.load_prefs()
    assert prefs["version"] == 1
    assert prefs["order"] == []
    assert prefs["renames"] == {}


def test_load_prefs_returns_default_on_corrupt_file(tmp_prefs):
    tmp_prefs.write_text("not json!!!", encoding="utf-8")
    prefs = bottleneck_prefs.load_prefs()
    assert prefs["version"] == 1


def test_save_and_load_roundtrip(tmp_prefs):
    data = {"version": 1, "order": ["Robots", "Agentic AI", "AI gadgets",
                                     "Autonomous Driving", "Power / data-center infrastructure"],
            "renames": {"Agentic AI": "My AI"}}
    bottleneck_prefs.save_prefs(data)
    loaded = bottleneck_prefs.load_prefs()
    assert loaded["order"] == data["order"]
    assert loaded["renames"] == data["renames"]


# ---- reorder_categories -----------------------------------------------------

def test_reorder_valid_permutation_succeeds(tmp_prefs):
    order = list(reversed(CANONICAL))
    prefs = bottleneck_prefs.reorder_categories(order)
    assert prefs["order"] == order


def test_reorder_missing_category_raises(tmp_prefs):
    order = ["Agentic AI", "Autonomous Driving", "AI gadgets", "Power / data-center infrastructure"]
    with pytest.raises(ValueError, match="missing"):
        bottleneck_prefs.reorder_categories(order)


def test_reorder_duplicate_raises(tmp_prefs):
    order = ["Agentic AI", "Agentic AI", "AI gadgets",
             "Autonomous Driving", "Power / data-center infrastructure"]
    with pytest.raises(ValueError, match="missing"):
        bottleneck_prefs.reorder_categories(order)


def test_reorder_non_list_raises(tmp_prefs):
    with pytest.raises(ValueError, match="list"):
        bottleneck_prefs.reorder_categories("not a list")  # type: ignore[arg-type]


def test_reorder_empty_raises(tmp_prefs):
    with pytest.raises(ValueError, match="empty"):
        bottleneck_prefs.reorder_categories([])


def test_reorder_unknown_category_raises(tmp_prefs):
    order = CANONICAL + ["Nonexistent Category"]
    with pytest.raises(ValueError, match="unknown"):
        bottleneck_prefs.reorder_categories(order)


def test_reorder_persists_and_patches_cache(tmp_prefs, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_prefs.parent)
    cache_path = tmp_prefs.parent / "dashboard.json"
    # Write a minimal cache with bottleneck categories
    cache = {
        "bottleneck": {
            "categories": [{"category": c, "streams": {}, "proxy_40d_roc_pct": None}
                           for c in CANONICAL]
        },
        "vintage": {},
    }
    store.save_json(cache_path, cache)
    order = list(reversed(CANONICAL))
    bottleneck_prefs.reorder_categories(order)
    cached = store.load_json(cache_path)
    assert [c["category"] for c in cached["bottleneck"]["categories"]] == order
    assert "bottleneck" in cached.get("vintage", {})


# ---- rename_category --------------------------------------------------------

def test_rename_valid_succeeds_and_persists(tmp_prefs):
    result = bottleneck_prefs.rename_category("Agentic AI", "My AI")
    assert result == {"original": "Agentic AI", "display": "My AI"}
    prefs = bottleneck_prefs.load_prefs()
    assert prefs["renames"]["Agentic AI"] == "My AI"


def test_rename_empty_new_name_raises(tmp_prefs):
    with pytest.raises(ValueError, match="empty"):
        bottleneck_prefs.rename_category("Agentic AI", "  ")


def test_rename_unknown_original_returns_none(tmp_prefs):
    result = bottleneck_prefs.rename_category("Nonexistent", "Foo")
    assert result is None


def test_rename_persists_and_patches_cache(tmp_prefs, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_prefs.parent)
    cache_path = tmp_prefs.parent / "dashboard.json"
    cache = {
        "bottleneck": {
            "categories": [{"category": c, "category_original": c, "streams": {},
                            "proxy_40d_roc_pct": None}
                           for c in CANONICAL]
        },
        "vintage": {},
    }
    store.save_json(cache_path, cache)
    bottleneck_prefs.rename_category("Agentic AI", "My AI")
    cached = store.load_json(cache_path)
    cats = cached["bottleneck"]["categories"]
    assert cats[0]["category"] == "My AI"
    assert cats[0]["category_original"] == "Agentic AI"
    assert "bottleneck" in cached.get("vintage", {})


# ---- bottleneck_read integration --------------------------------------------

def test_bottleneck_read_applies_order(tmp_prefs, monkeypatch):
    """Reordered prefs change the category order in bottleneck_read output."""
    order = list(reversed(CANONICAL))
    bottleneck_prefs.save_prefs({"version": 1, "order": order, "renames": {}})
    # Create a minimal snapshot that doesn't require market data
    snapshot = {"histories": {"extra": {}}}
    result = bottleneck.bottleneck_read(snapshot)
    assert [c["category"] for c in result["categories"]] == order


def test_bottleneck_read_applies_rename(tmp_prefs, monkeypatch):
    """Renamed prefs change the display name in bottleneck_read output."""
    bottleneck_prefs.save_prefs({"version": 1, "order": [], "renames": {"Agentic AI": "My AI"}})
    snapshot = {"histories": {"extra": {}}}
    result = bottleneck.bottleneck_read(snapshot)
    cats = result["categories"]
    # First category should be renamed
    ai_cat = next(c for c in cats if c["category_original"] == "Agentic AI")
    assert ai_cat["category"] == "My AI"
    # Other categories should keep canonical names
    other_names = [c["category"] for c in cats if c["category_original"] != "Agentic AI"]
    for name in other_names:
        assert name in CANONICAL


def test_bottleneck_read_fallback_to_canonical_order(tmp_prefs, monkeypatch):
    """Empty order falls back to canonical definition order."""
    bottleneck_prefs.save_prefs({"version": 1, "order": [], "renames": {}})
    snapshot = {"histories": {"extra": {}}}
    result = bottleneck.bottleneck_read(snapshot)
    assert [c["category_original"] for c in result["categories"]] == CANONICAL


def test_bottleneck_read_fallback_on_invalid_order(tmp_prefs, monkeypatch):
    """Invalid order (missing a category) falls back to canonical order."""
    bottleneck_prefs.save_prefs({"version": 1, "order": ["Agentic AI", "AI gadgets"], "renames": {}})
    snapshot = {"histories": {"extra": {}}}
    result = bottleneck.bottleneck_read(snapshot)
    # Invalid order → fallback to canonical
    assert [c["category_original"] for c in result["categories"]] == CANONICAL


def test_bottleneck_read_category_original_always_present(tmp_prefs, monkeypatch):
    """category_original is always the canonical name, even after rename."""
    bottleneck_prefs.save_prefs({"version": 1, "order": [], "renames": {"Robots": "Botz"}})
    snapshot = {"histories": {"extra": {}}}
    result = bottleneck.bottleneck_read(snapshot)
    for cat in result["categories"]:
        assert "category_original" in cat
        assert cat["category_original"] in CANONICAL


# ---- API endpoints ----------------------------------------------------------

def test_reorder_endpoint_success(client, tmp_prefs):
    r = client.post(
        "/api/bottleneck/categories/reorder",
        json={"order": list(reversed(CANONICAL))},
        headers={"Host": "127.0.0.1:8000"},
    )
    assert r.status_code == 200
    assert r.json()["order"] == list(reversed(CANONICAL))


def test_reorder_endpoint_invalid_order(client, tmp_prefs):
    r = client.post(
        "/api/bottleneck/categories/reorder",
        json={"order": ["Agentic AI"]},
        headers={"Host": "127.0.0.1:8000"},
    )
    assert r.status_code == 400
    assert "permutation" in r.json()["detail"] or "missing" in r.json()["detail"]


def test_reorder_endpoint_not_a_list(client, tmp_prefs):
    r = client.post(
        "/api/bottleneck/categories/reorder",
        json={"order": "not a list"},
        headers={"Host": "127.0.0.1:8000"},
    )
    assert r.status_code == 400


def test_rename_endpoint_success(client, tmp_prefs):
    r = client.put(
        "/api/bottleneck/categories/Agentic%20AI",
        params={"new_name": "My AI"},
        headers={"Host": "127.0.0.1:8000"},
    )
    assert r.status_code == 200
    assert r.json() == {"original": "Agentic AI", "display": "My AI"}


def test_rename_endpoint_empty_name(client, tmp_prefs):
    r = client.put(
        "/api/bottleneck/categories/Agentic%20AI",
        params={"new_name": "  "},
        headers={"Host": "127.0.0.1:8000"},
    )
    assert r.status_code == 400


def test_rename_endpoint_unknown_category(client, tmp_prefs):
    r = client.put(
        "/api/bottleneck/categories/Nonexistent",
        params={"new_name": "Foo"},
        headers={"Host": "127.0.0.1:8000"},
    )
    assert r.status_code == 404
