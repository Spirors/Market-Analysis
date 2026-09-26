"""Route tests for the bottleneck topic API (app/api.py).

Hermetic: the drafting agent's transport is mocked, ``yfinance`` is never
reached (every market history entry point is a tripwire on the computed read,
which is a pure snapshot read), the skill tree and ``.env`` are absent by
default, and every write path's metrics warm is either a no-op or asserted to
fail without failing the request.  ``refresh_skill`` — the app's only
child-process spawn site — is tested with ``subprocess.Popen`` mocked, proving
the child is reaped.

The autouse ``_isolate_data_files`` fixture in ``tests/conftest.py`` already
redirects ``bottleneck_topics._TOPICS_PATH``, ``topic_agent._JOBS_PATH`` and
``ai_valuation._CACHE_PATH`` into ``tmp_path``.
"""

from __future__ import annotations

import json
import threading
import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import (
    ai_valuation,
    api,
    bottleneck,
    bottleneck_topics,
    config,
    market,
    service,
    topic_agent,
)
from app.api import app


# ---- Fixtures ----------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, base_url="http://127.0.0.1:8000")


def _wait_lock_free(timeout: float = 2.0) -> bool:
    """Wait until no metrics-warm walk holds the module guard lock."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if api._bottleneck_warm_lock.acquire(blocking=False):
            api._bottleneck_warm_lock.release()
            return True
        time.sleep(0.01)
    return False


class _EmptyYF:
    """A yfinance stub whose download always returns an empty frame."""

    def download(self, *args, **kwargs):
        return pd.DataFrame()


class _RecordingYF:
    """A yfinance stub returning one canned frame and counting downloads."""

    def __init__(self, frame):
        self._frame = frame
        self.calls = 0

    def download(self, *args, **kwargs):
        self.calls += 1
        return self._frame


def _history_tripwire(*args, **kwargs):
    """Any reach into the market history layer from the render path is a bug."""
    raise AssertionError("the render path reached the market history layer")


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    """No network, no key, no skill; a fresh warm lock per test."""
    _wait_lock_free()  # let a prior test's warm walk finish first
    monkeypatch.setattr(topic_agent, "ENV_PATH", tmp_path / "env-absent")
    monkeypatch.delenv(topic_agent.KEY_NAME, raising=False)
    monkeypatch.setattr(topic_agent, "SKILL_DIR", tmp_path / "no-skill")
    # The computed read is a pure snapshot read: any history fetch is a defect.
    monkeypatch.setattr(market, "get_history", _history_tripwire)
    # No network anywhere: every yfinance download returns an empty frame.  A
    # test that needs real bulk data patches ``market._yf`` itself.
    monkeypatch.setattr(market, "_yf", _EmptyYF())
    # The write-path warm runs on a daemon thread; default it to a no-op so no
    # test spawns a real .info walk.
    monkeypatch.setattr(bottleneck, "ensure_metrics", lambda tickers: {})
    # Generation's stage 1 shells out to npx; stub the seam so no test spawns a
    # child process.  The explicit /skill/refresh endpoint is unaffected.
    monkeypatch.setattr(topic_agent, "_refresh_skill_stage", lambda: {"ok": True})
    # A fresh lock per test so a walk skipped in a prior test cannot leak in.
    monkeypatch.setattr(api, "_bottleneck_warm_lock", threading.Lock())
    yield
    _wait_lock_free()


@pytest.fixture
def skill(monkeypatch, tmp_path):
    root = tmp_path / "skill"
    (root / "references").mkdir(parents=True)
    (root / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    (root / "references" / "methodology.md").write_text("# Methodology\n", encoding="utf-8")
    (root / "references" / "theses.md").write_text("# Theses\n", encoding="utf-8")
    monkeypatch.setattr(topic_agent, "SKILL_DIR", root)
    return root


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv(topic_agent.KEY_NAME, "test-key")
    return "test-key"


# ---- Builders -----------------------------------------------------------------


def _ramp(base: float, current: float, n: int = 41) -> list[dict]:
    rows = [{"date": "2026-01-01", "close": float(base)} for _ in range(n - 1)]
    rows.append({"date": "2026-02-20", "close": float(current)})
    return rows


def _card(ticker: str, **overrides) -> dict:
    card = {field: None for field in bottleneck_topics.STOCK_CARD_FIELDS}
    card.update({
        "ticker": ticker,
        "name": ticker,
        "role": "downstream",
        "tier": "underdog",
        "evidence": [],
        "invalidation": [],
        "metrics": {field: None for field in bottleneck_topics.METRIC_FIELDS},
        "provenance": {"model": "", "skill_snapshot": "", "prompt_hash": "", "run_ts": ""},
    })
    card.update(overrides)
    return card


def _valid_topic() -> dict:
    return {
        "name": "AI power",
        "upstream": [{
            "name": "transformers",
            "physical_constraint": "transformer and switchgear capacity",
            "what_to_watch": "transformer lead times",
            "stocks": ["ETN"],
        }],
        "downstream": {"anchor": [_card("NVDA", tier="anchor")], "underdogs": []},
        "underdog_ceiling": 3_000_000_000,
        "revisions": [],
    }


def _seed_bulk_history(monkeypatch, base: float = 100.0, current: float = 150.0, n: int = 41) -> list[str]:
    """Write the refresh's bulk history cache for the current topic universe.

    Every symbol in ``market.history_universe_symbols()`` gets a ramp whose
    40-day ROC is ``(current / base - 1) * 100``.  Must be called *after* the
    topic store is populated so the topic's tickers are part of the universe.
    """
    symbols = market.history_universe_symbols()
    idx = pd.date_range("2025-11-01", periods=n, freq="D")
    data = {sym: [float(base)] * (n - 1) + [float(current)] for sym in symbols}
    frame = pd.DataFrame(data, index=idx)
    frame.columns = pd.MultiIndex.from_product([["Close"], symbols])
    monkeypatch.setattr(market, "_yf", _RecordingYF(frame))
    written = market.get_histories_bulk(symbols, days=250)
    assert set(written) == set(symbols)
    return symbols


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", json_error=False):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("invalid json")
        return self._payload


def _envelope(content: str) -> dict:
    return {
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
    }


def _install_transport(monkeypatch, responder):
    calls: list[dict] = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "payload": json, "headers": headers})
        index = len(calls) - 1
        if callable(responder):
            return responder(index)
        return responder[min(index, len(responder) - 1)]

    monkeypatch.setattr(topic_agent.requests, "post", fake_post)
    return calls


def _wait_job(client: TestClient, job_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/bottleneck/jobs/{job_id}")
        if response.status_code == 200 and \
                response.json().get("status") in topic_agent.TERMINAL_STATUSES:
            return response.json()
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not reach a terminal status")


# ---- GET /topics (the one render call) ---------------------------------------


def test_get_topics_empty_store_returns_both_halves(client):
    response = client.get("/api/bottleneck/topics")
    assert response.status_code == 200
    body = response.json()

    assert body["topics"] == []
    computed = body["bottleneck"]
    assert computed["topics"] == []
    assert computed["framework"] == "serenity-aleabitoreddit"
    assert computed["strongest_signal"] is None
    assert isinstance(computed["note"], str) and computed["note"]

    generation = body["generation"]
    assert generation["enabled"] is False
    # The absent key is named, not a 500.
    assert topic_agent.KEY_NAME in generation["error"]


def test_get_topics_crud_round_trip(client):
    created = client.post("/api/bottleneck/topics", json={"name": "AI power"})
    assert created.status_code == 201
    topic = created.json()
    topic_id = topic["id"]
    assert topic["name"] == "AI power"
    assert topic["upstream"] == []
    assert topic["downstream"] == {"anchor": [], "underdogs": []}

    listed = client.get("/api/bottleneck/topics").json()
    assert [t["id"] for t in listed["topics"]] == [topic_id]

    updated = client.put(f"/api/bottleneck/topics/{topic_id}", json={"name": "AI power v2"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "AI power v2"

    deleted = client.delete(f"/api/bottleneck/topics/{topic_id}")
    assert deleted.status_code == 204
    assert client.put(f"/api/bottleneck/topics/{topic_id}", json={"name": "x"}).status_code == 404
    assert client.delete(f"/api/bottleneck/topics/{topic_id}").status_code == 404
    assert client.get("/api/bottleneck/topics").json()["topics"] == []


def test_create_topic_blank_name_is_400(client):
    for body in ({}, {"name": ""}, {"name": "   "}, {"name": 5}):
        response = client.post("/api/bottleneck/topics", json=body)
        assert response.status_code == 400, body
        assert "name" in response.json()["detail"]


def test_update_topic_invalid_patch_is_400_and_not_persisted(client):
    topic_id = client.post("/api/bottleneck/topics", json={"name": "AI power"}).json()["id"]

    response = client.put(
        f"/api/bottleneck/topics/{topic_id}",
        json={"downstream": {"anchor": [{"ticker": ""}]}},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert any("ticker is required" in message for message in detail)

    # The invalid patch was rejected wholesale: the stored topic is untouched.
    stored = client.get("/api/bottleneck/topics").json()["topics"][0]
    assert stored["name"] == "AI power"
    assert stored["downstream"] == {"anchor": [], "underdogs": []}


def test_get_topics_computes_a_newly_created_topic(client, monkeypatch):
    """A new topic must render its ranked layers and tiered underdogs without
    a full market refresh."""
    ai_valuation.save_cache(
        metrics={
            "AAA": {"market_cap": 2_000_000_000, "revenue_growth": None,
                    "forward_pe": None, "as_of": "2026-09-25T00:00:00+00:00"},
        },
        fetched_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )

    def _no_full_refresh(*args, **kwargs):
        raise AssertionError("GET /topics triggered a full market refresh")

    monkeypatch.setattr(market, "build_market_snapshot", _no_full_refresh)

    topic_id = client.post("/api/bottleneck/topics", json={"name": "AI power"}).json()["id"]
    updated = client.put(f"/api/bottleneck/topics/{topic_id}", json={
        "upstream": [{"name": "transformers", "stocks": ["ETN"]}],
        "downstream": {"anchor": [], "underdogs": [_card("AAA")]},
    })
    assert updated.status_code == 200

    # Momentum comes from the shared bulk history cache, not a per-symbol
    # fallback fetch (that fallback is the render-fetch defect). Seed it the
    # way a refresh would, for the universe that now includes the topic.
    _seed_bulk_history(monkeypatch)

    computed = client.get("/api/bottleneck/topics").json()["bottleneck"]
    blocks = computed["topics"]
    assert [block["id"] for block in blocks] == [topic_id]
    assert blocks[0]["upstream"][0]["roc_40d_pct"] == 50.0
    underdogs = blocks[0]["downstream"]["underdogs"]
    assert [card["ticker"] for card in underdogs] == ["AAA"]
    assert "conviction_tier" not in underdogs[0]


def _topic_with_momentum(client) -> str:
    """Create one topic with an upstream ticker and an anchor card."""
    topic_id = client.post("/api/bottleneck/topics", json={"name": "AI power"}).json()["id"]
    updated = client.put(f"/api/bottleneck/topics/{topic_id}", json={
        "upstream": [{"name": "transformers", "stocks": ["ETN"]}],
        "downstream": {"anchor": [_card("NVDA")], "underdogs": []},
    })
    assert updated.status_code == 200
    return topic_id


def test_get_topics_issues_no_history_fetch_on_a_cold_cache(client, monkeypatch):
    """Defect 1: the render path must never reach yfinance or the fetch layer.

    The bulk history cache is cold (the fixture's yfinance stub returns an
    empty frame) and every history entry point is a tripwire, so a fallback to
    ``market.get_history`` — the old defect — would surface as an error rather
    than a cache hit.
    """
    _topic_with_momentum(client)

    def _tripwire(*args, **kwargs):
        raise AssertionError("the render path reached the market history layer")

    # Override the fixture's benign get_history stub: any call at all is a
    # failure, so a fallback cannot hide behind a mocked cache read.
    monkeypatch.setattr(market, "get_history", _tripwire)
    monkeypatch.setattr(market, "_yf_histories_bulk", _tripwire)
    monkeypatch.setattr(market, "_yf_history", _tripwire)

    response = client.get("/api/bottleneck/topics")
    assert response.status_code == 200
    computed = response.json()["bottleneck"]
    assert computed["topics"], "the topic should still render"
    for block in computed["topics"]:
        for layer in block["upstream"]:
            assert layer["roc_40d_pct"] is None
        for card in block["downstream"]["anchor"] + block["downstream"]["underdogs"]:
            assert card["metrics"]["roc_40d"] is None
            assert card["metrics"]["move_1y"] is None


def test_render_and_engine_report_the_same_momentum_from_one_bulk_cache(client, monkeypatch):
    """Defect 2: both views read one cached dataset, so a ticker's momentum is
    one number — pinned by exact equality, not approximation."""
    _topic_with_momentum(client)
    symbols = _seed_bulk_history(monkeypatch)

    render = service.bottleneck_read_cached()
    render_layer = render["topics"][0]["upstream"][0]

    # The engine payload built from the very same warm bulk cache.
    bulk = market.get_histories_bulk_cached(symbols, days=250)
    extra = {sym: bulk.get(sym, []) for sym in symbols}
    engine = bottleneck.bottleneck_read(
        {"as_of": render["as_of"], "histories": {"extra": extra}}
    )
    engine_layer = engine["topics"][0]["upstream"][0]

    assert render_layer["roc_40d_pct"] == engine_layer["roc_40d_pct"]
    # Pin the concrete value too, so two ``None``s cannot pass vacuously.
    assert render_layer["roc_40d_pct"] == 50.0


def test_get_topics_cold_bulk_cache_is_honest_about_missing_momentum(client, monkeypatch):
    """Cold cache: momentum is ``None``, ``as_of`` is still carried, and nothing
    is fabricated or raised."""
    dashboard = {"as_of": "2026-09-25T00:00:00+00:00", "bottleneck": {}}
    (config.DATA_DIR / "dashboard.json").write_text(
        json.dumps(dashboard), encoding="utf-8"
    )

    _topic_with_momentum(client)

    # The bulk cache stays cold (the fixture's yfinance stub returns empty).
    computed = client.get("/api/bottleneck/topics").json()["bottleneck"]

    assert computed["as_of"] == "2026-09-25T00:00:00+00:00"
    assert computed["topics"][0]["upstream"][0]["roc_40d_pct"] is None
    card = computed["topics"][0]["downstream"]["anchor"][0]
    assert card["metrics"]["roc_40d"] is None
    assert card["metrics"]["move_1y"] is None


# ---- Generate + jobs ----------------------------------------------------------


def test_generate_without_key_is_409_naming_the_key(client, skill):
    response = client.post("/api/bottleneck/topics/generate", json={"theme": "AI power"})
    assert response.status_code == 409
    assert topic_agent.KEY_NAME in response.json()["detail"]


def test_generate_happy_path_polls_to_terminal(client, skill, key, monkeypatch):
    _install_transport(
        monkeypatch, [_FakeResponse(200, _envelope(json.dumps(_valid_topic())))]
    )
    started = client.post("/api/bottleneck/topics/generate", json={"theme": "AI power"})
    assert started.status_code == 201
    job = started.json()
    assert job["status"] in (topic_agent.QUEUED, topic_agent.RUNNING)

    done = _wait_job(client, job["id"])
    assert done["status"] == topic_agent.SUCCEEDED
    assert done["draft"]["topic"]["name"] == "AI power"
    assert client.get("/api/bottleneck/jobs").json()[0]["id"] == job["id"]


def test_cancel_in_flight_job(client, skill, key, monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def responder(index):
        entered.set()
        release.wait(5)
        return _FakeResponse(200, _envelope(json.dumps(_valid_topic())))

    _install_transport(monkeypatch, responder)
    job = client.post("/api/bottleneck/topics/generate", json={"theme": "AI power"}).json()
    assert entered.wait(5)

    cancelled = client.post(f"/api/bottleneck/jobs/{job['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == topic_agent.CANCELLED

    release.set()
    assert _wait_job(client, job["id"])["status"] == topic_agent.CANCELLED


def test_jobs_survive_a_reload(client):
    """Jobs are read back from disk, so a restart-ish reload still lists them."""
    topic_agent._save_jobs([{
        "id": "j1", "status": topic_agent.SUCCEEDED, "theme": "AI power",
        "model": topic_agent.DEFAULT_MODEL, "created": "2026-09-25T00:00:00+00:00",
        "updated": "2026-09-25T00:00:00+00:00", "error": None, "draft": None,
    }])

    listed = client.get("/api/bottleneck/jobs")
    assert listed.status_code == 200
    assert [job["id"] for job in listed.json()] == ["j1"]

    single = client.get("/api/bottleneck/jobs/j1")
    assert single.status_code == 200
    assert single.json()["id"] == "j1"
    assert client.get("/api/bottleneck/jobs/missing").status_code == 404
    assert client.post("/api/bottleneck/jobs/missing/cancel").status_code == 404


def test_legacy_job_without_stages_is_tolerated_on_read(client):
    """A pre-stages persisted job must not crash the list/detail routes."""
    topic_agent._save_jobs([{
        "id": "legacy", "status": topic_agent.SUCCEEDED, "theme": "AI power",
        "model": topic_agent.DEFAULT_MODEL, "created": "2026-09-25T00:00:00+00:00",
        "updated": "2026-09-25T00:00:00+00:00", "error": None, "draft": None,
    }])

    listed = client.get("/api/bottleneck/jobs")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == "legacy"
    assert "stages" not in listed.json()[0]

    single = client.get("/api/bottleneck/jobs/legacy")
    assert single.status_code == 200
    assert single.json()["id"] == "legacy"


def test_started_job_carries_four_pending_stages(client, skill, key, monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def responder(index):
        entered.set()
        release.wait(5)
        return _FakeResponse(200, _envelope(json.dumps(_valid_topic())))

    _install_transport(monkeypatch, responder)
    started = client.post("/api/bottleneck/topics/generate", json={"theme": "AI power"})
    assert started.status_code == 201

    stages = started.json()["stages"]
    assert [s["key"] for s in stages] == [
        "refresh_skill", "read_lens", "draft", "warm_metrics",
    ]
    assert [s["label"] for s in stages] == [
        "Refresh skill", "Read lens", "Draft thesis", "Pull market data",
    ]
    # Polling on disk may already show the first stage running; all are valid
    # pending/running at this instant, but the shape is fixed.
    assert all(
        s["status"] in (topic_agent.STAGE_PENDING, topic_agent.STAGE_RUNNING)
        for s in stages
    )

    release.set()
    assert _wait_job(client, started.json()["id"])["status"] == topic_agent.SUCCEEDED


def test_succeeded_job_marks_every_stage_done(client, skill, key, monkeypatch):
    _install_transport(
        monkeypatch, [_FakeResponse(200, _envelope(json.dumps(_valid_topic())))]
    )
    job = client.post("/api/bottleneck/topics/generate", json={"theme": "AI power"}).json()
    done = _wait_job(client, job["id"])

    assert done["status"] == topic_agent.SUCCEEDED
    stages = done["stages"]
    assert [s["key"] for s in stages] == [
        "refresh_skill", "read_lens", "draft", "warm_metrics",
    ]
    assert all(s["status"] == topic_agent.STAGE_DONE for s in stages)

    # And the GET routes pass the stages through verbatim.
    single = client.get(f"/api/bottleneck/jobs/{job['id']}").json()
    assert single["stages"] == stages


def test_refresh_stage_failure_is_non_fatal(client, skill, key, monkeypatch):
    """An offline skill refresh must not fail the run: it is skipped with a note."""
    monkeypatch.setattr(
        topic_agent, "_refresh_skill_stage",
        lambda: {"ok": False, "timed_out": False},
    )
    _install_transport(
        monkeypatch, [_FakeResponse(200, _envelope(json.dumps(_valid_topic())))]
    )
    job = client.post("/api/bottleneck/topics/generate", json={"theme": "AI power"}).json()
    done = _wait_job(client, job["id"])

    assert done["status"] == topic_agent.SUCCEEDED
    by_key = {s["key"]: s for s in done["stages"]}
    assert by_key["refresh_skill"]["status"] == topic_agent.STAGE_SKIPPED
    assert by_key["refresh_skill"]["note"]
    assert by_key["draft"]["status"] == topic_agent.STAGE_DONE


def test_warm_stage_failure_is_non_fatal(client, skill, key, monkeypatch):
    """A warm that blows up leaves the succeeded draft intact."""
    def _boom(tickers):
        raise RuntimeError("warm blew up")

    monkeypatch.setattr(topic_agent, "_warm_draft_metrics", _boom)
    _install_transport(
        monkeypatch, [_FakeResponse(200, _envelope(json.dumps(_valid_topic())))]
    )
    job = client.post("/api/bottleneck/topics/generate", json={"theme": "AI power"}).json()
    done = _wait_job(client, job["id"])

    assert done["status"] == topic_agent.SUCCEEDED
    assert done["draft"]["topic"]["name"] == "AI power"
    by_key = {s["key"]: s for s in done["stages"]}
    assert by_key["warm_metrics"]["status"] == topic_agent.STAGE_FAILED
    assert by_key["warm_metrics"]["note"]


def test_apply_adds_one_agent_revision_with_provenance(client, skill, key, monkeypatch):
    _install_transport(
        monkeypatch, [_FakeResponse(200, _envelope(json.dumps(_valid_topic())))]
    )
    job = client.post("/api/bottleneck/topics/generate", json={"theme": "AI power"}).json()
    done = _wait_job(client, job["id"])
    assert done["status"] == topic_agent.SUCCEEDED

    topic_id = client.post("/api/bottleneck/topics", json={"name": "AI power"}).json()["id"]

    # A warming failure on the apply write must not fail the request.
    monkeypatch.setattr(bottleneck, "ensure_metrics",
                        lambda tickers: (_ for _ in ()).throw(RuntimeError("boom")))
    applied = client.post(f"/api/bottleneck/jobs/{job['id']}/apply", json={"topic_id": topic_id})
    assert applied.status_code == 200

    topic = applied.json()
    assert len(topic["revisions"]) == 1
    assert topic["revisions"][0]["source"] == "agent"

    run = done["draft"]["provenance"]
    cards = topic["downstream"]["anchor"] + topic["downstream"]["underdogs"]
    assert cards
    for card in cards:
        assert card["provenance"]["model"] == run["model"]
        assert card["provenance"]["prompt_hash"] == run["prompt_hash"]

    # Unknown job / unknown topic never writes.
    assert client.post(
        f"/api/bottleneck/jobs/{job['id']}/apply", json={"topic_id": "nope"}
    ).status_code == 404


# ---- Import / export ----------------------------------------------------------


def test_import_list_persists_valid_topics(client):
    payload = [bottleneck_topics.new_topic("T1")]
    response = client.post("/api/bottleneck/topics/import", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 1
    assert body["errors"] == []
    assert [t["name"] for t in body["topics"]] == ["T1"]
    assert [t["name"] for t in client.get("/api/bottleneck/topics").json()["topics"]] == ["T1"]


def test_import_document_persists_valid_topics(client):
    payload = {"version": 1, "topics": [bottleneck_topics.new_topic("Doc")]}
    response = client.post("/api/bottleneck/topics/import", json=payload)
    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert [t["name"] for t in response.json()["topics"]] == ["Doc"]


def test_import_mix_reports_errors_and_persists_valid(client):
    good = bottleneck_topics.new_topic("Good")
    bad = {"name": "", "upstream": [], "downstream": {}}
    response = client.post("/api/bottleneck/topics/import", json=[good, bad])
    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 1
    assert body["errors"]
    assert [t["name"] for t in body["topics"]] == ["Good"]


def test_import_garbage_payload_is_400(client):
    for payload in ("just a string", 42, {"version": 1}, {"topics": "nope"}):
        response = client.post("/api/bottleneck/topics/import", json=payload)
        assert response.status_code == 400, payload


def test_export_returns_the_document_json_safe(client):
    client.post("/api/bottleneck/topics", json={"name": "AI power"})
    response = client.get("/api/bottleneck/topics/export")
    assert response.status_code == 200
    document = response.json()
    assert document["version"] == 1
    assert [t["name"] for t in document["topics"]] == ["AI power"]
    assert "NaN" not in response.text


# ---- Skill --------------------------------------------------------------------


def test_skill_status_reports_absent_skill_and_generation(client):
    response = client.get("/api/bottleneck/skill/status")
    assert response.status_code == 200
    body = response.json()
    assert body["installed"] is False
    assert body["generation"]["enabled"] is False
    assert topic_agent.KEY_NAME in body["generation"]["error"]


def test_skill_refresh_returns_structured_body_and_reaps_child(client, skill, monkeypatch):
    class FakeProc:
        def __init__(self):
            self.returncode = 0
            self.killed = False
            self.wait_called = False
            self.communicate_calls = []

        def communicate(self, timeout=None):
            self.communicate_calls.append(timeout)
            return ("installed ok", None)

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.wait_called = True
            return self.returncode

        def kill(self):
            self.killed = True

    proc = FakeProc()
    monkeypatch.setattr(topic_agent.subprocess, "Popen", lambda *a, **k: proc)

    response = client.post("/api/bottleneck/skill/refresh")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["command"] == topic_agent.UPDATE_COMMAND
    assert "installed ok" in body["output_tail"]

    # Proof no live child remains: the process was communicated with, waited on,
    # and is not still running.
    assert proc.communicate_calls == [topic_agent.REFRESH_TIMEOUT_S]
    assert proc.wait_called is True
    assert proc.poll() is not None
    assert proc.killed is False


# ---- Write-path warming -------------------------------------------------------


def test_write_paths_return_promptly_when_metrics_warming_fails(client, monkeypatch):
    attempted = threading.Event()

    def _boom(tickers):
        attempted.set()
        raise RuntimeError("metrics walk blew up")

    monkeypatch.setattr(bottleneck, "ensure_metrics", _boom)

    started = time.monotonic()
    created = client.post("/api/bottleneck/topics", json={"name": "AI power"})
    updated = client.put(
        f"/api/bottleneck/topics/{created.json()['id']}", json={"name": "AI power v2"}
    )
    imported = client.post(
        "/api/bottleneck/topics/import", json=[bottleneck_topics.new_topic("Imported")]
    )
    elapsed = time.monotonic() - started

    assert created.status_code == 201
    assert updated.status_code == 200
    assert imported.status_code == 200
    # The request path never blocked on the walk.
    assert elapsed < 1.0
    # The walk really did run (and raise) off the request thread.
    assert attempted.wait(2.0), "warming was never attempted"
    # The failure released the guard lock, so a later write can warm again.
    assert _wait_lock_free()


# ---- Legacy surface -----------------------------------------------------------


def test_legacy_category_routes_are_gone(client):
    reorder = client.post("/api/bottleneck/categories/reorder", json={"order": []})
    assert reorder.status_code in (404, 405)
    rename = client.put(
        "/api/bottleneck/categories/Agentic%20AI", params={"new_name": "My AI"}
    )
    assert rename.status_code in (404, 405)
