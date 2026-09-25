"""Tests for the bottleneck topic store (app/bottleneck_topics.py).

Pure local persistence: no network, no live data.  The autouse
``_isolate_data_files`` fixture in ``tests/conftest.py`` already redirects
``bottleneck_topics._TOPICS_PATH`` into ``tmp_path``; the explicit
``tmp_topics`` fixture re-states it for clarity, matching the house pattern
for the other isolated stores.
"""

import json

import pytest

from app import bottleneck_topics


@pytest.fixture
def tmp_topics(monkeypatch, tmp_path):
    path = tmp_path / "bottleneck_topics.json"
    monkeypatch.setattr(bottleneck_topics, "_TOPICS_PATH", path)
    return path


def _stock(**overrides):
    """A fully-populated, valid thesis card."""
    card = {
        "ticker": "NVDA",
        "name": "Nvidia",
        "stance": "long",
        "why_chokepoint": "Packaging capacity binds GPU output.",
        "layer": "advanced packaging",
        "role": "downstream",
        "tier": "anchor",
        "evidence": [
            {"claim": "Capex raised", "source": "10-K", "source_url": "", "tier": "primary-filing"}
        ],
        "catalyst": "Next-gen ramp",
        "catalyst_window": "H1 2027",
        "invalidation": ["Hyperscaler capex cut"],
        "dilution_atm": None,
        "customer_concentration": None,
        "gaap_margin": None,
        "financing_quality": None,
        "metrics": {
            "market_cap": 2_000_000_000,
            "roc_40d": None,
            "move_1y": None,
            "forward_pe": None,
            "revenue_growth": None,
            "as_of": "2026-09-25",
        },
        "provenance": {"model": "m", "skill_snapshot": "", "prompt_hash": "", "run_ts": ""},
    }
    card.update(overrides)
    return card


def _topic_with_stock(**stock_overrides):
    """A valid topic carrying one stock in downstream.anchor."""
    topic = bottleneck_topics.new_topic("AI power")
    topic["downstream"]["anchor"] = [_stock(**stock_overrides)]
    return topic


# ---- load_topics degradation ------------------------------------------------


def test_load_missing_file_returns_empty(tmp_topics):
    assert not tmp_topics.exists()
    assert bottleneck_topics.load_topics() == []


def test_load_empty_file_returns_empty(tmp_topics):
    tmp_topics.write_text("", encoding="utf-8")
    assert bottleneck_topics.load_topics() == []


def test_load_corrupt_file_returns_empty(tmp_topics):
    tmp_topics.write_text("not json!!!", encoding="utf-8")
    assert bottleneck_topics.load_topics() == []


def test_load_unexpected_root_type_returns_empty(tmp_topics):
    tmp_topics.write_text(json.dumps(123), encoding="utf-8")
    assert bottleneck_topics.load_topics() == []


# ---- round-trip -------------------------------------------------------------


def test_create_roundtrip_has_default_shape(tmp_topics):
    created = bottleneck_topics.create_topic("AI power")
    loaded = bottleneck_topics.load_topics()
    assert len(loaded) == 1
    topic = loaded[0]
    assert topic["id"] == created["id"]
    assert topic["name"] == "AI power"
    assert topic["upstream"] == []
    assert topic["downstream"] == {"anchor": [], "underdogs": []}
    assert topic["revisions"] == []
    assert topic["underdog_ceiling"] == bottleneck_topics.UNDERDOG_CEILING_DEFAULT
    assert topic["created"] and topic["updated"]


def test_get_topic_known_and_unknown(tmp_topics):
    created = bottleneck_topics.create_topic("Robots")
    assert bottleneck_topics.get_topic(created["id"])["name"] == "Robots"
    assert bottleneck_topics.get_topic("nope") is None


# ---- update_topic -----------------------------------------------------------


def test_update_topic_known_id_merges_and_persists(tmp_topics):
    created = bottleneck_topics.create_topic("AI power")
    updated = bottleneck_topics.update_topic(created["id"], {"name": "AI power v2"})
    assert updated is not None
    assert updated["name"] == "AI power v2"
    assert updated["id"] == created["id"]
    # Re-read from disk to prove persistence.
    assert bottleneck_topics.get_topic(created["id"])["name"] == "AI power v2"


def test_update_topic_unknown_id_returns_none(tmp_topics):
    assert bottleneck_topics.update_topic("nope", {"name": "x"}) is None


def test_update_topic_cannot_change_id(tmp_topics):
    created = bottleneck_topics.create_topic("AI power")
    updated = bottleneck_topics.update_topic(created["id"], {"id": "hijack"})
    assert updated["id"] == created["id"]


# ---- delete_topic -----------------------------------------------------------


def test_delete_topic_known_id(tmp_topics):
    created = bottleneck_topics.create_topic("AI power")
    assert bottleneck_topics.delete_topic(created["id"]) is True
    assert bottleneck_topics.load_topics() == []


def test_delete_topic_unknown_id(tmp_topics):
    bottleneck_topics.create_topic("AI power")
    assert bottleneck_topics.delete_topic("nope") is False
    assert len(bottleneck_topics.load_topics()) == 1


# ---- append_revision --------------------------------------------------------


def test_append_revision_numbers_from_one_newest_first(tmp_topics):
    created = bottleneck_topics.create_topic("AI power")
    for i in range(1, 4):
        bottleneck_topics.append_revision(created["id"], {}, "agent", f"rev{i}")
    topic = bottleneck_topics.get_topic(created["id"])
    revisions = topic["revisions"]
    assert [r["n"] for r in revisions] == [3, 2, 1]
    assert [r["summary"] for r in revisions] == ["rev3", "rev2", "rev1"]
    # Snapshot is the applied body, without nested history.
    assert "revisions" not in revisions[0]["snapshot"]


def test_append_revision_applies_snapshot_body(tmp_topics):
    created = bottleneck_topics.create_topic("AI power")
    snapshot = {"name": "AI power", "upstream": [{"name": "grid", "physical_constraint": "transformers",
                                                  "what_to_watch": "lead times", "stocks": ["ETN"]}]}
    bottleneck_topics.append_revision(created["id"], snapshot, "manual", "add grid layer")
    topic = bottleneck_topics.get_topic(created["id"])
    assert topic["upstream"][0]["name"] == "grid"
    assert topic["revisions"][0]["snapshot"]["upstream"][0]["name"] == "grid"


def test_append_revision_truncates_to_max(tmp_topics):
    created = bottleneck_topics.create_topic("AI power")
    for i in range(1, 26):
        bottleneck_topics.append_revision(created["id"], {}, "agent", f"rev{i}")
    revisions = bottleneck_topics.get_topic(created["id"])["revisions"]
    assert len(revisions) == bottleneck_topics.MAX_REVISIONS == 20
    assert revisions[0]["n"] == 25
    assert revisions[-1]["n"] == 6


def test_append_revision_unknown_id_returns_none(tmp_topics):
    assert bottleneck_topics.append_revision("nope", {}, "agent", "x") is None


# ---- validate_topic ---------------------------------------------------------


def test_validate_accepts_default_topic():
    assert bottleneck_topics.validate_topic(bottleneck_topics.new_topic("AI power")) == []


def test_validate_accepts_full_card():
    assert bottleneck_topics.validate_topic(_topic_with_stock()) == []


def test_validate_rejects_blank_name():
    topic = bottleneck_topics.new_topic("AI power")
    topic["name"] = "   "
    errors = bottleneck_topics.validate_topic(topic)
    assert any("name" in e for e in errors)


def test_validate_rejects_bad_role():
    errors = bottleneck_topics.validate_topic(_topic_with_stock(role="sideways"))
    assert any("role" in e for e in errors)


def test_validate_rejects_bad_tier():
    errors = bottleneck_topics.validate_topic(_topic_with_stock(tier="wizard"))
    assert any("tier" in e for e in errors)


def test_validate_rejects_bad_evidence_tier():
    errors = bottleneck_topics.validate_topic(
        _topic_with_stock(evidence=[{"claim": "x", "source": "s", "source_url": "", "tier": "twitter"}])
    )
    assert any("evidence" in e and "tier" in e for e in errors)


def test_validate_rejects_non_numeric_metric():
    card = _stock()
    card["metrics"]["market_cap"] = "lots"
    topic = bottleneck_topics.new_topic("AI power")
    topic["downstream"]["anchor"] = [card]
    errors = bottleneck_topics.validate_topic(topic)
    assert any("market_cap" in e for e in errors)


def test_validate_rejects_negative_metric():
    card = _stock()
    card["metrics"]["market_cap"] = -1
    topic = bottleneck_topics.new_topic("AI power")
    topic["downstream"]["anchor"] = [card]
    errors = bottleneck_topics.validate_topic(topic)
    assert any("market_cap" in e for e in errors)


def test_validate_accepts_negative_signed_metrics():
    """Returns, growth deltas and a loss-making PE are all legitimately negative."""
    card = _stock()
    card["metrics"].update(
        {"market_cap": 5e9, "roc_40d": -12.5, "move_1y": -38.0, "forward_pe": -7.4, "revenue_growth": -0.21}
    )
    topic = bottleneck_topics.new_topic("AI power")
    topic["downstream"]["anchor"] = [card]
    assert bottleneck_topics.validate_topic(topic) == []


def test_validate_rejects_non_finite_metric():
    card = _stock()
    card["metrics"]["roc_40d"] = float("nan")
    topic = bottleneck_topics.new_topic("AI power")
    topic["downstream"]["anchor"] = [card]
    errors = bottleneck_topics.validate_topic(topic)
    assert any("roc_40d" in e for e in errors)


def test_validate_rejects_non_positive_revision_n():
    topic = bottleneck_topics.new_topic("AI power")
    topic["revisions"] = [{"n": 0}]
    errors = bottleneck_topics.validate_topic(topic)
    assert any("revisions[0].n" in e for e in errors)


def test_validate_rejects_bad_checklist_flag():
    errors = bottleneck_topics.validate_topic(_topic_with_stock(dilution_atm="yes"))
    assert any("dilution_atm" in e for e in errors)


# ---- import / export --------------------------------------------------------


def test_import_bare_list():
    topic = bottleneck_topics.new_topic("AI power")
    imported, errors = bottleneck_topics.import_topics([topic])
    assert errors == []
    assert imported == [topic]


def test_import_document():
    topic = bottleneck_topics.new_topic("AI power")
    imported, errors = bottleneck_topics.import_topics({"version": 1, "topics": [topic]})
    assert errors == []
    assert imported == [topic]


def test_import_mix_keeps_valid_and_reports_invalid():
    good = bottleneck_topics.new_topic("AI power")
    bad = bottleneck_topics.new_topic("")
    imported, errors = bottleneck_topics.import_topics([good, bad, "not an object"])
    assert [t["id"] for t in imported] == [good["id"]]
    assert len(errors) == 2
    assert any("name" in e for e in errors)
    assert any("not an object" in e for e in errors)


def test_export_topics_sanitizes_nan():
    path = bottleneck_topics._TOPICS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        "version": 1,
        "topics": [
            {
                "id": "t1",
                "name": "AI power",
                "downstream": {
                    "anchor": [{"ticker": "AAA", "metrics": {"market_cap": float("nan")}}],
                    "underdogs": [],
                },
            }
        ],
    }
    # Bypass save_topics so the non-finite value reaches disk verbatim.
    path.write_text(json.dumps(raw), encoding="utf-8")
    exported = bottleneck_topics.export_topics()
    dumped = json.dumps(exported)
    assert "NaN" not in dumped
    assert exported["topics"][0]["downstream"]["anchor"][0]["metrics"]["market_cap"] is None


# ---- test isolation ---------------------------------------------------------


def test_topics_path_is_isolated_under_tmp_path(tmp_path):
    """The autouse fixture must resolve the store path inside this test's tmp_path."""
    resolved = bottleneck_topics._TOPICS_PATH.resolve()
    assert resolved == (tmp_path / "bottleneck_topics.json").resolve()
    assert str(resolved).startswith(str(tmp_path.resolve()))
