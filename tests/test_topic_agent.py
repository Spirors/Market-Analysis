"""Tests for the in-app topic-drafting agent (app/topic_agent.py).

The transport is mocked completely — no test makes a network call.  The
autouse ``_hermetic`` fixture below points ``ENV_PATH`` at a nonexistent file
and ``SKILL_DIR`` at a nonexistent directory so the suite never reads the
user's real ``.env`` (a secret) or depends on the live skill content; tests
that need a key or a skill opt in via the ``key`` / ``skill`` fixtures.
``refresh_skill`` is the module's only child-process spawn site and is tested
with ``subprocess.Popen`` mocked, asserting the child is reaped.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from datetime import datetime

import pytest

from app import bottleneck_topics, market, store, topic_agent


# Captured before the autouse ``_hermetic`` fixture swaps in a stub, so the
# seam-level tests below exercise the real ``_run_research`` with only
# ``subprocess.run``/``shutil.which`` mocked (no CLI is spawned).
_REAL_RUN_RESEARCH = topic_agent._run_research


# ---- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    """Never read the real ``.env`` or the live skill by default."""
    monkeypatch.setattr(topic_agent, "ENV_PATH", tmp_path / "env-absent")
    monkeypatch.delenv(topic_agent.KEY_NAME, raising=False)
    monkeypatch.setattr(topic_agent, "SKILL_DIR", tmp_path / "no-skill")
    # Generation's stage 1 shells out to npx and stage 4 warms market data; the
    # research stage shells out to opencode.  Stub every seam so no test spawns
    # a child or reaches the network.  The explicit ``refresh_skill`` tests
    # below bypass these seams on purpose.
    monkeypatch.setattr(topic_agent, "_refresh_skill_stage", lambda **_: {"ok": True})
    monkeypatch.setattr(
        topic_agent, "_run_research",
        lambda theme, tickers, cancel_event=None: (
            topic_agent.STAGE_DONE, None,
            "RESEARCH: a fact [source: https://example.com/r | date: 2026-01-01]",
        ),
    )
    monkeypatch.setattr(topic_agent, "_warm_draft_metrics", lambda tickers: ("done", None))
    # Stage 6 resolves the final topic's tickers against the market layer; stub
    # it so no test reaches yfinance and every ticker resolves by default.
    monkeypatch.setattr(
        market, "get_histories_bulk",
        lambda symbols, days=250, ttl=None: {
            s: [{"date": "2026-01-01", "close": 1.0}] for s in symbols
        },
    )
    yield


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv(topic_agent.KEY_NAME, "test-key")
    return "test-key"


@pytest.fixture
def skill(monkeypatch, tmp_path):
    """A tiny stand-in skill tree; content is intentionally irrelevant."""
    root = tmp_path / "skill"
    (root / "references").mkdir(parents=True)
    (root / "SKILL.md").write_text("# Skill\nrouting table at ~line 103\n", encoding="utf-8")
    (root / "references" / "methodology.md").write_text(
        "# Methodology\n## 1. bottleneck hunting\n## 15. The checklist\n", encoding="utf-8"
    )
    (root / "references" / "theses.md").write_text(
        "# Theses\nfrozen base ~2026-06-08\n", encoding="utf-8"
    )
    monkeypatch.setattr(topic_agent, "SKILL_DIR", root)
    return root


# ---- Transport + payload helpers --------------------------------------------


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", json_error=False):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("invalid json")
        return self._payload


def _envelope(content, finish_reason="stop"):
    """The real response envelope, including reasoning siblings."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1790000000,
        "model": "deepseek-v4.1-flash",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": content,
                "reasoning_content": "secret chain of thought",
            },
            "finish_reason": finish_reason,
            "logprobs": None,
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
            "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 11},
        },
    }


def _install_transport(monkeypatch, responder):
    """Patch ``requests.post`` and return the recorded call list.

    ``responder`` is either a list of responses (last one repeats) or a
    callable taking the zero-based call index.
    """
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "payload": json, "headers": headers, "timeout": timeout})
        index = len(calls) - 1
        if callable(responder):
            return responder(index)
        return responder[min(index, len(responder) - 1)]

    monkeypatch.setattr(topic_agent.requests, "post", fake_post)
    return calls


def _stock(**overrides):
    card = {
        "ticker": "NVDA",
        "name": "Nvidia",
        "stance": "long",
        "why_chokepoint": "Packaging capacity binds GPU output.",
        "layer": "advanced packaging",
        "role": "downstream",
        "tier": "anchor",
        "evidence": [
            {"claim": "Capex raised", "source": "10-K", "source_url": "",
             "tier": "primary-filing"}
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


def _topic(**overrides):
    topic = {
        "name": "AI power",
        "upstream": [{
            "name": "transformers",
            "physical_constraint": "transformer and switchgear capacity",
            "what_to_watch": "transformer lead times",
            "stocks": ["ETN"],
        }],
        "downstream": {"anchor": [_stock()], "underdogs": []},
        "underdog_ceiling": 3_000_000_000,
        "revisions": [],
    }
    topic.update(overrides)
    return topic


def _valid_json():
    return json.dumps(_topic())


def _wait(job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = topic_agent.get_job(job_id)
        if job and job.get("status") in topic_agent.TERMINAL_STATUSES:
            return job
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not reach a terminal status")


# ---- Key handling / import safety -------------------------------------------


def test_module_imports_and_other_functions_work_without_key():
    # No key, no skill (autouse): the module is importable and inert paths work.
    assert topic_agent.DEFAULT_MODEL == "deepseek-v4.1-flash"
    assert topic_agent.skill_status()["installed"] is False
    assert topic_agent.list_jobs() == []
    assert topic_agent.get_job("nope") is None
    avail = topic_agent.generation_availability()
    assert avail["enabled"] is False
    assert topic_agent.KEY_NAME in avail["error"]
    assert ".env" in avail["error"]


def test_missing_key_disables_generation_with_explicit_message(skill):
    job = topic_agent.start_generation("AI power")
    assert job["status"] == "failed"
    assert topic_agent.KEY_NAME in job["error"]
    assert ".env" in job["error"]
    # A precondition failure is not persisted as a job.
    assert topic_agent.get_job(job["id"]) is None
    assert topic_agent.list_jobs() == []


def test_skill_absent_blocks_generation_naming_install_command(key):
    job = topic_agent.start_generation("AI power")
    assert job["status"] == "failed"
    assert topic_agent.INSTALL_COMMAND in job["error"]


# ---- Skill status ------------------------------------------------------------


def test_skill_status_reports_hash_inventory_and_mtime(skill):
    status = topic_agent.skill_status()
    assert status["installed"] is True
    assert status["file_count"] == 3
    assert len(status["hash"]) == 64
    assert status["mtime"]
    assert {entry["path"] for entry in status["files"]} == {
        "SKILL.md", "references/methodology.md", "references/theses.md"
    }


def test_skill_hash_changes_when_content_changes(skill):
    first = topic_agent.skill_status()["hash"]
    (skill / "references" / "methodology.md").write_text("changed", encoding="utf-8")
    assert topic_agent.skill_status()["hash"] != first


# ---- Happy path + extraction -------------------------------------------------


def test_happy_path_returns_validated_reviewable_draft(skill, key, monkeypatch):
    calls = _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    job = topic_agent.start_generation("AI power")
    done = _wait(job["id"])

    assert done["status"] == "succeeded"
    draft = done["draft"]
    assert bottleneck_topics.validate_topic(draft["topic"]) == []

    provenance = draft["provenance"]
    assert set(provenance) == {"model", "skill_snapshot", "prompt_hash", "run_ts"}
    assert provenance["model"] == topic_agent.DEFAULT_MODEL
    assert provenance["skill_snapshot"] == topic_agent.skill_status()["hash"]
    assert len(provenance["prompt_hash"]) == 64

    # Nothing touches the topic store until the user applies the draft.
    assert bottleneck_topics.load_topics() == []
    assert not bottleneck_topics._TOPICS_PATH.exists()

    # Two completions: the draft skeleton, then the fill refinement.
    assert len(calls) == 2
    request = calls[0]
    assert request["url"] == topic_agent.ZEN_ENDPOINT
    assert request["payload"]["max_tokens"] >= 4096
    headers = request["headers"]
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["User-Agent"] == topic_agent.USER_AGENT
    assert headers["x-opencode-session"].startswith("topic-agent-")


def test_schema_instructions_state_each_field_type():
    """The prompt is the only place the field-type contract can be stated.

    The model is given the field *names*; without their *types* it emits a
    string ``invalidation`` and an object inside ``upstream[].stocks``, both of
    which ``validate_topic`` rejects — observed live on a real draft.
    """
    text = topic_agent._schema_instructions()
    assert "invalidation: a LIST of strings" in text
    assert "never a single string" in text
    assert "evidence: a LIST of objects" in text
    assert "metrics and provenance are objects" in text
    assert "PLAIN TICKER STRINGS" in text
    assert f"checklist flags {list(bottleneck_topics.CHECKLIST_FLAGS)}" in text
    assert "never a string" in text


def test_prompt_scopes_the_lens_to_the_theme():
    """The lens is one analyst's AI-datacenter thesis set, so it must be applied
    as method rather than reused as the answer.

    Observed live: an AR-eyewear theme came back as the InP datacenter chain,
    because the lens is ~98% of the prompt and the theme is a 92-char hint.
    """
    prompt = topic_agent._build_prompt("AI smart glasses", {}, None)
    assert "WHAT THE REFERENCE MATERIAL IS" in prompt
    assert "METHOD and EVIDENCE, not the answer" in prompt
    assert "SCOPE RULE" in prompt
    assert "not covered by the reference material" in prompt
    assert "never invent a citation" in prompt
    assert "THEME: AI smart glasses" in prompt


def test_empty_content_is_retried_not_accepted(skill, key, monkeypatch):
    calls = _install_transport(monkeypatch, [
        FakeResponse(200, _envelope("", finish_reason="length")),
        FakeResponse(200, _envelope(_valid_json())),
    ])
    done = _wait(topic_agent.start_generation("AI power")["id"])
    assert done["status"] == "succeeded"
    assert len(calls) == 3
    retry_prompt = calls[1]["payload"]["messages"][0]["content"]
    assert "empty or unusable" in retry_prompt


def test_fenced_json_is_extracted(skill, key, monkeypatch):
    content = "```json\n" + _valid_json() + "\n```"
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(content))])
    done = _wait(topic_agent.start_generation("AI power")["id"])
    assert done["status"] == "succeeded"
    assert bottleneck_topics.validate_topic(done["draft"]["topic"]) == []


def test_json_embedded_in_prose_is_extracted(skill, key, monkeypatch):
    content = "Here is the draft you asked for:\n" + _valid_json() + "\nHope that helps."
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(content))])
    done = _wait(topic_agent.start_generation("AI power")["id"])
    assert done["status"] == "succeeded"


# ---- Validation retries ------------------------------------------------------


def test_validation_failure_feeds_validator_errors_back(skill, key, monkeypatch):
    bad = _topic()
    bad["downstream"]["anchor"][0]["role"] = "sideways"
    calls = _install_transport(monkeypatch, [
        FakeResponse(200, _envelope(json.dumps(bad))),
        FakeResponse(200, _envelope(_valid_json())),
    ])
    done = _wait(topic_agent.start_generation("AI power")["id"])
    assert done["status"] == "succeeded"
    assert len(calls) == 3
    retry_prompt = calls[1]["payload"]["messages"][0]["content"]
    assert "role must be one of" in retry_prompt
    assert "sideways" in retry_prompt


def test_retries_exhausted_fails_with_no_draft(skill, key, monkeypatch):
    calls = _install_transport(monkeypatch, [FakeResponse(200, _envelope('{"not": a topic'))])
    done = _wait(topic_agent.start_generation("AI power")["id"])
    assert done["status"] == "failed"
    assert done["draft"] is None
    assert done["error"]
    assert len(calls) == topic_agent.MAX_RETRIES + 1


# ---- Transport degradation ---------------------------------------------------


def test_non_200_fails_cleanly(skill, key, monkeypatch):
    calls = _install_transport(monkeypatch, [FakeResponse(500, text="boom")])
    done = _wait(topic_agent.start_generation("AI power")["id"])
    assert done["status"] == "failed"
    assert "500" in done["error"]
    assert len(calls) == topic_agent.MAX_RETRIES + 1


def test_non_json_body_fails_cleanly(skill, key, monkeypatch):
    _install_transport(monkeypatch, [FakeResponse(200, text="<html>not json</html>", json_error=True)])
    done = _wait(topic_agent.start_generation("AI power")["id"])
    assert done["status"] == "failed"
    assert "non-JSON" in done["error"]


def test_missing_choices_fails_cleanly(skill, key, monkeypatch):
    _install_transport(monkeypatch, [FakeResponse(200, {"id": "x", "object": "chat.completion"})])
    done = _wait(topic_agent.start_generation("AI power")["id"])
    assert done["status"] == "failed"
    assert "no choices" in done["error"]


def test_unknown_model_override_is_rejected(skill, key, monkeypatch):
    calls = _install_transport(monkeypatch, [])
    job = topic_agent.start_generation("AI power", model="gpt-4o")
    assert job["status"] == "failed"
    assert "unknown model" in job["error"]
    assert calls == []


# ---- Serial behaviour + cancellation -----------------------------------------


def test_second_start_while_running_is_refused(skill, key, monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def responder(index):
        entered.set()
        release.wait(5)
        return FakeResponse(200, _envelope(_valid_json()))

    _install_transport(monkeypatch, responder)
    first = topic_agent.start_generation("AI power")
    assert entered.wait(5)

    second = topic_agent.start_generation("AI power")
    assert second["status"] == "failed"
    assert "already running" in second["error"]

    release.set()
    assert _wait(first["id"])["status"] == "succeeded"


def test_cancel_mid_flight_marks_cancelling_then_cancelled(skill, key, monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def responder(index):
        entered.set()
        release.wait(5)
        return FakeResponse(200, _envelope(_valid_json()))

    _install_transport(monkeypatch, responder)
    job = topic_agent.start_generation("AI power")
    assert entered.wait(5)

    cancelled = topic_agent.cancel_job(job["id"])
    # The intermediate state is non-terminal: the worker has not unwound yet.
    assert cancelled["status"] == topic_agent.CANCELLING
    assert topic_agent.CANCELLING not in topic_agent.TERMINAL_STATUSES
    release.set()

    done = _wait(job["id"])
    assert done["status"] == "cancelled"
    assert done["draft"] is None


def test_cancel_during_http_completion_releases_lock(skill, key, monkeypatch):
    """A cancelled in-flight completion is abandoned; the serial lock frees promptly."""
    entered = threading.Event()
    release = threading.Event()

    def responder(index):
        entered.set()
        release.wait(10)
        return FakeResponse(200, _envelope(_valid_json()))

    _install_transport(monkeypatch, responder)
    job = topic_agent.start_generation("AI power")
    assert entered.wait(5)

    cancelled = topic_agent.cancel_job(job["id"])
    assert cancelled["status"] == topic_agent.CANCELLING

    # The worker abandons the completion even though the responder is blocked.
    done = _wait(job["id"], timeout=2.0)
    assert done["status"] == topic_agent.CANCELLED
    assert done["draft"] is None

    deadline = time.time() + 2.0
    while topic_agent._generation_lock.locked() and time.time() < deadline:
        time.sleep(0.01)
    assert topic_agent._generation_lock.locked() is False

    second = None
    try:
        # The lock is free, so a fresh start is not refused.
        second = topic_agent.start_generation("AI power")
        assert second["status"] != topic_agent.FAILED
        assert "already running" not in (second.get("error") or "")
    finally:
        release.set()

    # Releasing the abandoned responder must not resurrect the cancelled job.
    assert _wait(job["id"])["status"] == topic_agent.CANCELLED
    assert topic_agent.get_job(job["id"])["draft"] is None
    if second is not None:
        _wait(second["id"], timeout=10.0)


def test_cancel_kills_the_research_child(skill, key, monkeypatch):
    """A cancel during the research child kills and reaps it; the job cancels."""
    monkeypatch.setattr(topic_agent, "_run_research", _REAL_RUN_RESEARCH)
    monkeypatch.setattr(topic_agent.shutil, "which", lambda name: None)
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])

    class _CancelProc:
        def __init__(self):
            self.returncode = None
            self.killed = False
            self.wait_called = False

        def communicate(self, input=None, timeout=None):
            # The child "sets the Event" (all live job events) and stays alive.
            for event in list(topic_agent._CANCEL_EVENTS.values()):
                event.set()
            raise topic_agent.subprocess.TimeoutExpired("opencode", timeout or 0)

        def poll(self):
            return None

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            self.wait_called = True
            return 0

    proc = _CancelProc()
    monkeypatch.setattr(topic_agent.subprocess, "Popen", lambda *a, **k: proc)

    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert proc.killed is True
    assert proc.wait_called is True
    assert done["status"] == topic_agent.CANCELLED
    assert done["draft"] is None


def test_cancel_kills_the_refresh_skill_child(skill, monkeypatch):
    """The cancel-aware reaper kills and reaps the installer child."""
    cancel_event = threading.Event()

    class _CancelProc:
        def __init__(self):
            self.returncode = None
            self.killed = False
            self.wait_called = False

        def communicate(self, input=None, timeout=None):
            cancel_event.set()
            raise topic_agent.subprocess.TimeoutExpired("npx", timeout or 0)

        def poll(self):
            return None

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            self.wait_called = True
            return 0

    proc = _CancelProc()
    monkeypatch.setattr(topic_agent.subprocess, "Popen", lambda *a, **k: proc)

    result = topic_agent.refresh_skill(timeout=5, cancel_event=cancel_event)

    assert proc.killed is True
    assert proc.wait_called is True
    assert result["timed_out"] is False
    assert result["ok"] is False


def test_cancel_while_completion_in_flight_is_never_succeeded(skill, key, monkeypatch):
    """A completion that lands after the Event is set is discarded, not applied."""
    def responder(index):
        for event in list(topic_agent._CANCEL_EVENTS.values()):
            event.set()
        return FakeResponse(200, _envelope(_valid_json()))

    _install_transport(monkeypatch, responder)

    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == topic_agent.CANCELLED
    assert done["status"] != topic_agent.SUCCEEDED
    assert done["draft"] is None


def test_cancel_does_not_touch_the_topic_store(skill, key, monkeypatch):
    """An abandoned completion never appends an agent revision to the store."""
    topic = bottleneck_topics.create_topic("AI power")
    before = bottleneck_topics._TOPICS_PATH.read_bytes()

    entered = threading.Event()
    release = threading.Event()

    def responder(index):
        entered.set()
        release.wait(10)
        return FakeResponse(200, _envelope(_valid_json()))

    _install_transport(monkeypatch, responder)
    job = topic_agent.start_generation("AI power", topic_id=topic["id"])
    assert entered.wait(5)
    topic_agent.cancel_job(job["id"])
    try:
        done = _wait(job["id"], timeout=2.0)
        assert done["status"] == topic_agent.CANCELLED
        assert done["draft"] is None
        assert bottleneck_topics._TOPICS_PATH.read_bytes() == before
        assert bottleneck_topics.get_topic(topic["id"])["revisions"] == []
        raw = json.loads(topic_agent._JOBS_PATH.read_text(encoding="utf-8"))
        record = next(j for j in raw["jobs"] if j["id"] == job["id"])
        assert record["status"] == topic_agent.CANCELLED
        assert record["draft"] is None
    finally:
        release.set()


def test_abandoned_completion_thread_writes_no_job_state(skill, key, monkeypatch):
    """The abandoned HTTP thread must not mutate the persisted job record."""
    entered = threading.Event()
    release = threading.Event()

    def responder(index):
        entered.set()
        release.wait(10)
        return FakeResponse(200, _envelope(_valid_json()))

    _install_transport(monkeypatch, responder)
    job = topic_agent.start_generation("AI power")
    assert entered.wait(5)
    topic_agent.cancel_job(job["id"])
    done = _wait(job["id"], timeout=2.0)
    assert done["status"] == topic_agent.CANCELLED

    def snapshot():
        current = topic_agent.get_job(job["id"])
        return (
            current["status"],
            current["draft"],
            json.dumps(current.get("stages"), sort_keys=True),
        )

    first = snapshot()
    time.sleep(0.15)
    assert snapshot() == first

    release.set()
    time.sleep(0.3)
    after = snapshot()
    assert after == first
    assert after[0] == topic_agent.CANCELLED
    assert after[1] is None


# ---- Job persistence + recovery ----------------------------------------------


def test_jobs_persist_round_trip_under_tmp_path(skill, key, monkeypatch, tmp_path):
    assert topic_agent._JOBS_PATH.parent == tmp_path
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert topic_agent.get_job(done["id"])["id"] == done["id"]
    assert topic_agent.list_jobs()[0]["id"] == done["id"]

    raw = json.loads(topic_agent._JOBS_PATH.read_text(encoding="utf-8"))
    assert raw["jobs"][0]["id"] == done["id"]
    for field in ("id", "status", "theme", "model", "created", "updated", "error",
                  "draft", "stages"):
        assert field in raw["jobs"][0]
    assert [s["key"] for s in raw["jobs"][0]["stages"]] == [
        "refresh_skill", "read_lens", "draft", "research", "fill", "warm_metrics",
    ]


def test_restart_recovery_marks_stale_running_failed(skill, key, monkeypatch):
    stale = {
        "id": "stale1",
        "status": topic_agent.RUNNING,
        "theme": "AI power",
        "model": topic_agent.DEFAULT_MODEL,
        "created": "2026-01-01T00:00:00+00:00",
        "updated": "2026-01-01T00:00:00+00:00",
        "error": None,
        "draft": None,
    }
    store.save_json(topic_agent._JOBS_PATH, {"version": 1, "jobs": [stale]})

    assert topic_agent.recover_stale_jobs() == 1
    recovered = topic_agent.get_job("stale1")
    assert recovered["status"] == "failed"
    assert "interrupted" in recovered["error"]
    # Idempotent: nothing left to recover, and the lock is not stuck.
    assert topic_agent.recover_stale_jobs() == 0
    assert _wait(topic_agent.start_generation("AI power")["id"])["status"] == "failed"


def test_restart_recovery_marks_stale_cancelling_failed(skill, key, monkeypatch):
    """A crash mid-cancel leaves ``cancelling``, which recovery must reconcile."""
    stale = {
        "id": "stale-cancelling",
        "status": topic_agent.CANCELLING,
        "theme": "AI power",
        "model": topic_agent.DEFAULT_MODEL,
        "created": "2026-01-01T00:00:00+00:00",
        "updated": "2026-01-01T00:00:00+00:00",
        "error": None,
        "draft": None,
    }
    store.save_json(topic_agent._JOBS_PATH, {"version": 1, "jobs": [stale]})

    assert topic_agent.recover_stale_jobs() == 1
    recovered = topic_agent.get_job("stale-cancelling")
    assert recovered["status"] == topic_agent.FAILED
    assert "interrupted" in recovered["error"]


def test_cancel_landing_after_the_last_check_is_cancelled_not_succeeded(
    skill, key, monkeypatch
):
    """A cancel that lands after the final cancel check still wins."""
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])

    def _cancel_then_resolve(tickers, *, timeout=90.0, cancel_event=None):
        for event in topic_agent._CANCEL_EVENTS.values():
            event.set()
        return list(tickers), []

    monkeypatch.setattr(topic_agent, "_resolve_tickers", _cancel_then_resolve)

    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == topic_agent.CANCELLED
    assert done["status"] != topic_agent.SUCCEEDED
    assert done["draft"] is None


def test_cancel_leaves_completed_stages_done(skill, key, monkeypatch):
    """A stage already ``done`` is never rewritten ``skipped`` by a later cancel."""
    def _research_then_cancel(theme, tickers, cancel_event=None):
        for event in topic_agent._CANCEL_EVENTS.values():
            event.set()
        return topic_agent.STAGE_DONE, None, (
            "RESEARCH: a fact [source: https://example.com/r | date: 2026-01-01]"
        )

    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    monkeypatch.setattr(topic_agent, "_run_research", _research_then_cancel)

    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == topic_agent.CANCELLED
    by_key = {s["key"]: s["status"] for s in done["stages"]}
    assert by_key["draft"] == topic_agent.STAGE_DONE
    assert by_key["research"] == topic_agent.STAGE_DONE
    assert by_key["fill"] == topic_agent.STAGE_SKIPPED
    assert by_key["warm_metrics"] == topic_agent.STAGE_SKIPPED


def test_job_retention_is_bounded():
    jobs = [
        {"id": f"j{i}", "status": topic_agent.SUCCEEDED}
        for i in range(topic_agent.MAX_JOBS + 5)
    ]
    store.save_json(topic_agent._JOBS_PATH, {"version": 1, "jobs": jobs})
    topic_agent._insert_job({"id": "newest", "status": topic_agent.QUEUED})
    retained = topic_agent.list_jobs()
    assert len(retained) == topic_agent.MAX_JOBS
    assert retained[0]["id"] == "newest"


# ---- Named stages ------------------------------------------------------------


def test_succeeded_job_marks_every_stage_done(skill, key, monkeypatch):
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    assert [s["key"] for s in done["stages"]] == [
        "refresh_skill", "read_lens", "draft", "research", "fill", "warm_metrics",
    ]
    assert [s["label"] for s in done["stages"]] == [
        "Refresh skill", "Read lens", "Draft chain", "Research web",
        "Draft thesis", "Pull market data",
    ]
    assert all(s["status"] == topic_agent.STAGE_DONE for s in done["stages"])


def test_refresh_failure_is_non_fatal_and_noted(skill, key, monkeypatch):
    monkeypatch.setattr(
        topic_agent, "_refresh_skill_stage",
        lambda **_: {"ok": False, "timed_out": True},
    )
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    by_key = {s["key"]: s for s in done["stages"]}
    assert by_key["refresh_skill"]["status"] == topic_agent.STAGE_SKIPPED
    assert by_key["refresh_skill"]["note"]
    assert by_key["read_lens"]["status"] == topic_agent.STAGE_DONE
    assert by_key["draft"]["status"] == topic_agent.STAGE_DONE


def test_raising_refresh_seam_still_succeeds(skill, key, monkeypatch):
    def _boom(cancel_event=None):
        raise RuntimeError("npx exploded")

    monkeypatch.setattr(topic_agent, "_refresh_skill_stage", _boom)
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    by_key = {s["key"]: s for s in done["stages"]}
    assert by_key["refresh_skill"]["status"] == topic_agent.STAGE_SKIPPED


def test_empty_lens_is_skipped_and_drafting_continues(skill, key, monkeypatch):
    monkeypatch.setattr(topic_agent, "_load_skill_documents", lambda theme: {})
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    by_key = {s["key"]: s for s in done["stages"]}
    assert by_key["read_lens"]["status"] == topic_agent.STAGE_SKIPPED
    assert by_key["read_lens"]["note"]
    assert by_key["draft"]["status"] == topic_agent.STAGE_DONE


def test_warm_failure_is_non_fatal(skill, key, monkeypatch):
    def _boom(tickers):
        raise RuntimeError("warm exploded")

    monkeypatch.setattr(topic_agent, "_warm_draft_metrics", _boom)
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    assert done["draft"]["topic"]["name"] == "AI power"
    by_key = {s["key"]: s for s in done["stages"]}
    assert by_key["warm_metrics"]["status"] == topic_agent.STAGE_FAILED
    assert by_key["warm_metrics"]["note"]


def test_draft_failure_fails_job_and_marks_draft_failed(skill, key, monkeypatch):
    _install_transport(monkeypatch, [FakeResponse(200, _envelope('{"not": a topic'))])
    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "failed"
    by_key = {s["key"]: s for s in done["stages"]}
    assert by_key["draft"]["status"] == topic_agent.STAGE_FAILED
    assert by_key["draft"]["note"]
    assert by_key["warm_metrics"]["status"] == topic_agent.STAGE_SKIPPED


# ---- Six-stage pipeline: research + fill -------------------------------------


def test_started_job_carries_six_pending_stages(skill, key, monkeypatch):
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    job = topic_agent.start_generation("AI power")

    assert [s["key"] for s in job["stages"]] == [
        "refresh_skill", "read_lens", "draft", "research", "fill", "warm_metrics",
    ]
    assert [s["label"] for s in job["stages"]] == [
        "Refresh skill", "Read lens", "Draft chain", "Research web",
        "Draft thesis", "Pull market data",
    ]
    assert all(s["status"] == topic_agent.STAGE_PENDING for s in job["stages"])
    _wait(job["id"])


def test_research_skipped_is_non_fatal_and_noted(skill, key, monkeypatch):
    monkeypatch.setattr(
        topic_agent, "_run_research",
        lambda theme, tickers, cancel_event=None: (
            topic_agent.STAGE_SKIPPED, "opencode CLI not found", None
        ),
    )
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    by_key = {s["key"]: s for s in done["stages"]}
    assert by_key["research"]["status"] == topic_agent.STAGE_SKIPPED
    assert by_key["research"]["note"] == "opencode CLI not found"
    assert by_key["fill"]["status"] == topic_agent.STAGE_DONE
    assert done["research"]["status"] == topic_agent.STAGE_SKIPPED
    assert done["research"]["findings"] is None
    assert done["research"]["sources"] == []


def test_raising_research_seam_still_succeeds(skill, key, monkeypatch):
    def _boom(theme, tickers, cancel_event=None):
        raise RuntimeError("opencode exploded")

    monkeypatch.setattr(topic_agent, "_run_research", _boom)
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    by_key = {s["key"]: s for s in done["stages"]}
    assert by_key["research"]["status"] == topic_agent.STAGE_FAILED
    assert by_key["research"]["note"]


def test_fill_failure_falls_back_to_draft_topic(skill, key, monkeypatch):
    draft_json = json.dumps(_topic(name="Draft skeleton"))
    _install_transport(monkeypatch, [
        FakeResponse(200, _envelope(draft_json)),
        FakeResponse(200, _envelope('{"not": a topic')),
    ])
    done = _wait(topic_agent.start_generation("AI power")["id"])

    # A failed refinement keeps the draft skeleton and the job still succeeds.
    assert done["status"] == "succeeded"
    assert done["draft"]["topic"]["name"] == "Draft skeleton"
    by_key = {s["key"]: s for s in done["stages"]}
    assert by_key["draft"]["status"] == topic_agent.STAGE_DONE
    assert by_key["fill"]["status"] == topic_agent.STAGE_FAILED
    assert by_key["fill"]["note"]
    assert by_key["warm_metrics"]["status"] == topic_agent.STAGE_DONE


def test_researched_findings_appear_in_fill_prompt(skill, key, monkeypatch):
    marker = "UNIQUE_RESEARCH_MARKER_XYZ"
    monkeypatch.setattr(
        topic_agent, "_run_research",
        lambda theme, tickers, cancel_event=None: (
            topic_agent.STAGE_DONE, None,
            f"{marker} [source: https://example.com/f | date: 2026-02-02]",
        ),
    )
    calls = _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    assert len(calls) == 2
    draft_prompt = calls[0]["payload"]["messages"][0]["content"]
    fill_prompt = calls[1]["payload"]["messages"][0]["content"]
    # The findings block belongs to the fill prompt only.
    assert "===== research findings =====" not in draft_prompt
    assert "===== research findings =====" in fill_prompt
    assert marker in fill_prompt
    assert "SKELETON TOPIC TO REFINE" in fill_prompt
    assert "REFINEMENT RULES" in fill_prompt


def test_research_outcome_is_persisted_on_the_job(skill, key, monkeypatch):
    monkeypatch.setattr(
        topic_agent, "_run_research",
        lambda theme, tickers, cancel_event=None: (
            topic_agent.STAGE_DONE, None,
            "a https://example.com/1 then https://example.com/1 then https://x.io/2",
        ),
    )
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])

    research = done["research"]
    assert research["status"] == topic_agent.STAGE_DONE
    assert research["note"] is None
    assert research["findings"].startswith("a https://example.com/1")
    assert research["sources"] == ["https://example.com/1", "https://x.io/2"]
    json.dumps(research)  # JSON-safe



# ---- Research seam (opencode CLI, no CLI is ever spawned) --------------------


def test_research_command_builds_the_frozen_argv():
    argv = topic_agent._research_command()
    assert argv == [
        "opencode", "run", "--agent", topic_agent.RESEARCH_AGENT,
        "--model", f"{topic_agent.RESEARCH_MODEL_PROVIDER}/{topic_agent.DEFAULT_MODEL}",
        "--format", "json", "--auto", "--standalone",
    ]
    # The prompt travels via stdin, never argv.
    assert "PROMPT" not in argv
    # The CLI needs ``provider/model``; a bare id does not select the Go
    # subscription, and ``opencode`` would be Zen pay-per-token instead.
    model = argv[argv.index("--model") + 1]
    assert model.startswith("opencode-go/")


def test_parse_research_output_handles_ndjson_events_and_garbage():
    # A single text event (one line) is the minimal stream.
    single = json.dumps({"type": "text", "part": {"text": "single object findings"}})
    assert topic_agent._parse_research_output(single) == "single object findings"

    # NDJSON: text events concatenate; step_finish (tokens/cost) and non-JSON
    # lines contribute nothing.
    stream = "\n".join([
        json.dumps({"type": "text", "part": {"text": "first "}}),
        "garbage line that is not json",
        json.dumps({"type": "text", "part": {"text": "second"}}),
        json.dumps({"type": "step_finish", "part": {"tokens": 42, "cost": 0.01}}),
    ])
    assert topic_agent._parse_research_output(stream) == "first second"

    assert topic_agent._parse_research_output("not json at all") is None
    assert topic_agent._parse_research_output(
        json.dumps({"type": "step_finish", "part": {"tokens": 1, "cost": 0.0}})
    ) is None
    assert topic_agent._parse_research_output("") is None
    assert topic_agent._parse_research_output(None) is None


def test_findings_are_truncated_at_max_research_chars():
    long = "A" * topic_agent.MAX_RESEARCH_CHARS + "ZZZ_SENTINEL"
    prompt = topic_agent._build_prompt("AI power", {}, "", findings=long)

    assert "===== research findings =====" in prompt
    assert "ZZZ_SENTINEL" not in prompt
    assert "research findings truncated" in prompt
    assert "A" * topic_agent.MAX_RESEARCH_CHARS in prompt


def test_run_research_missing_cli_is_skipped_not_fatal(monkeypatch):
    def _boom(*args, **kwargs):
        raise FileNotFoundError("opencode")

    monkeypatch.setattr(topic_agent.subprocess, "run", _boom)
    monkeypatch.setattr(topic_agent.shutil, "which", lambda name: None)

    status, note, findings = _REAL_RUN_RESEARCH("AI power", ["NVDA"])

    assert status == topic_agent.STAGE_SKIPPED
    assert note
    assert findings is None


def test_run_research_timeout_is_failed_not_fatal(monkeypatch):
    def _timeout(*args, **kwargs):
        raise topic_agent.subprocess.TimeoutExpired("opencode", 1)

    monkeypatch.setattr(topic_agent.subprocess, "run", _timeout)
    monkeypatch.setattr(topic_agent.shutil, "which", lambda name: None)

    status, note, findings = _REAL_RUN_RESEARCH("AI power", [])

    assert status == topic_agent.STAGE_FAILED
    assert "timed out" in note
    assert findings is None


def test_run_research_caps_the_returned_findings(monkeypatch):
    class _Proc:
        returncode = 0
        stdout = json.dumps(
            {"type": "text", "part": {"text": "B" * (topic_agent.MAX_RESEARCH_CHARS + 500)}}
        )
        stderr = ""

    monkeypatch.setattr(topic_agent.subprocess, "run", lambda *a, **k: _Proc())
    monkeypatch.setattr(topic_agent.shutil, "which", lambda name: None)

    status, note, findings = _REAL_RUN_RESEARCH("AI power", [])

    assert status == topic_agent.STAGE_DONE
    assert note is None
    assert findings is not None and "truncated" in findings
    assert len(findings) <= topic_agent.MAX_RESEARCH_CHARS + 200


def test_run_research_succeeds_on_final_text_even_with_nonzero_exit(monkeypatch):
    class _Proc:
        returncode = 1
        stdout = json.dumps({"type": "text", "part": {"text": "usable findings"}})
        stderr = "warning only"

    monkeypatch.setattr(topic_agent.subprocess, "run", lambda *a, **k: _Proc())
    monkeypatch.setattr(topic_agent.shutil, "which", lambda name: None)

    status, note, findings = _REAL_RUN_RESEARCH("AI power", [])

    assert status == topic_agent.STAGE_DONE
    assert note is None
    assert findings == "usable findings"


def test_spawn_kwargs_are_windowless_on_win32_only(monkeypatch):
    monkeypatch.setattr(topic_agent.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)

    monkeypatch.setattr(topic_agent.sys, "platform", "win32")
    assert topic_agent._spawn_kwargs() == {"creationflags": 0x08000000}

    monkeypatch.setattr(topic_agent.sys, "platform", "linux")
    assert topic_agent._spawn_kwargs() == {}


def test_refresh_skill_passes_no_window_flag_on_win32(skill, monkeypatch):
    monkeypatch.setattr(topic_agent.sys, "platform", "win32")
    monkeypatch.setattr(topic_agent.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)

    class FakeProc:
        returncode = 0

        def communicate(self, timeout=None):
            return ("ok", None)

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    captured = {}

    def fake_popen(*args, **kwargs):
        captured.update(kwargs)
        return FakeProc()

    monkeypatch.setattr(topic_agent.subprocess, "Popen", fake_popen)

    topic_agent.refresh_skill(timeout=5)

    assert captured["creationflags"] == 0x08000000


def test_run_research_passes_no_window_flag_on_win32(monkeypatch):
    monkeypatch.setattr(topic_agent.sys, "platform", "win32")
    monkeypatch.setattr(topic_agent.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)

    class _Proc:
        returncode = 0
        stdout = json.dumps({"type": "text", "part": {"text": "findings"}})
        stderr = ""

    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return _Proc()

    monkeypatch.setattr(topic_agent.subprocess, "run", fake_run)
    monkeypatch.setattr(topic_agent.shutil, "which", lambda name: None)

    status, _note, findings = _REAL_RUN_RESEARCH("AI power", ["NVDA"])

    assert status == topic_agent.STAGE_DONE
    assert findings == "findings"
    assert captured["creationflags"] == 0x08000000
    assert "shell" not in captured
    # The prompt is piped via stdin, not passed as an argument.
    assert "AI power" in captured["input"]
    assert "NVDA" in captured["input"]
    # The CLI must run at the repo root, or ``--agent researcher`` (a
    # project-scoped agent) is not discoverable.
    assert captured["cwd"] == str(topic_agent.config.BASE_DIR)
    # Decode the child's UTF-8 output explicitly: the Windows locale codec
    # (cp1252) raises on it and the findings are silently lost.
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"


def test_draft_tickers_extracts_upstream_and_downstream_deduped():
    draft = {
        "upstream": [
            {"name": "l1", "physical_constraint": "", "what_to_watch": "", "stocks": ["ETN", {"ticker": "TSM"}, "ETN"]},
            {"name": "l2", "physical_constraint": "", "what_to_watch": "", "stocks": ["  "]},
        ],
        "downstream": {
            "anchor": [{"ticker": "NVDA"}, {"ticker": ""}, "not-a-card"],
            "underdogs": [{"ticker": "AAOI"}],
        },
    }
    assert topic_agent._draft_tickers(draft) == ["ETN", "TSM", "NVDA", "AAOI"]
    assert topic_agent._draft_tickers(None) == []


def test_normalize_draft_promotes_legacy_layer_key_and_passes_validation():
    """The old agent shape (``layer`` + ``stocks`` only) repairs and validates."""
    draft = {
        "name": "",
        "upstream": [{"layer": "transformers", "stocks": ["ETN"]}],
        "downstream": {"anchor": [], "underdogs": []},
        "underdog_ceiling": 3_000_000_000,
        "revisions": [],
    }

    normalized = topic_agent._normalize_draft(draft, "AI power")

    assert normalized["name"] == "AI power"
    layer = normalized["upstream"][0]
    assert layer["name"] == "transformers"
    assert layer["physical_constraint"] == ""
    assert layer["what_to_watch"] == ""
    assert layer["stocks"] == ["ETN"]
    assert bottleneck_topics.validate_topic(normalized) == []
    # Copy-on-write: the caller's draft is untouched.
    assert draft["upstream"][0] == {"layer": "transformers", "stocks": ["ETN"]}


def test_normalize_draft_keeps_unknown_layer_fields_as_empty_strings():
    draft = {
        "name": "AI power",
        "upstream": [{
            "name": "grid",
            "physical_constraint": None,
            "what_to_watch": 7,
            "stocks": ["ETN"],
            "extra": "kept",
        }],
    }

    layer = topic_agent._normalize_draft(draft, "AI power")["upstream"][0]

    assert layer == {
        "name": "grid",
        "physical_constraint": "",
        "what_to_watch": "",
        "stocks": ["ETN"],
        "extra": "kept",
    }


def test_set_stage_tolerates_a_legacy_job_without_stages():
    topic_agent._save_jobs([{
        "id": "legacy", "status": topic_agent.SUCCEEDED, "theme": "AI power",
        "model": topic_agent.DEFAULT_MODEL, "created": "2026-09-25T00:00:00+00:00",
        "updated": "2026-09-25T00:00:00+00:00", "error": None, "draft": None,
    }])

    updated = topic_agent._set_stage("legacy", "draft", topic_agent.STAGE_DONE)

    assert updated is not None
    by_key = {s["key"]: s for s in updated["stages"]}
    assert by_key["draft"]["status"] == topic_agent.STAGE_DONE
    assert by_key["refresh_skill"]["status"] == topic_agent.STAGE_PENDING


# ---- refresh_skill (only child-process spawn site) ---------------------------


def test_refresh_skill_runs_cli_and_reaps_child(skill, monkeypatch):
    class FakeProc:
        def __init__(self):
            self.returncode = 0
            self.killed = False
            self.wait_called = False
            self.communicate_calls = []

        def communicate(self, timeout=None):
            self.communicate_calls.append(timeout)
            return ("installed serenity-aleabitoreddit ok", None)

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.wait_called = True
            return self.returncode

        def kill(self):
            self.killed = True

    proc = FakeProc()
    monkeypatch.setattr(topic_agent.subprocess, "Popen", lambda *a, **k: proc)

    result = topic_agent.refresh_skill(timeout=5)

    assert result["ok"] is True
    assert result["command"] == topic_agent.UPDATE_COMMAND
    assert result["returncode"] == 0
    assert result["timed_out"] is False
    assert "installed serenity-aleabitoreddit ok" in result["output_tail"]
    assert result["new_hash"] == topic_agent.skill_status()["hash"]
    # The child was communicated with and reaped — no live handle left.
    assert proc.communicate_calls == [5]
    assert proc.wait_called is True
    assert proc.killed is False


def test_refresh_skill_timeout_kills_and_reaps_child(skill, monkeypatch):
    class TimeoutProc:
        def __init__(self):
            self.returncode = None
            self.killed = False
            self.wait_called = False
            self._raised = False

        def communicate(self, timeout=None):
            if not self._raised:
                self._raised = True
                raise topic_agent.subprocess.TimeoutExpired("cmd", timeout)
            self.returncode = 0
            return ("", None)

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.wait_called = True
            return self.returncode

        def kill(self):
            self.killed = True

    proc = TimeoutProc()
    monkeypatch.setattr(topic_agent.subprocess, "Popen", lambda *a, **k: proc)

    result = topic_agent.refresh_skill(timeout=1)

    assert result["timed_out"] is True
    assert result["ok"] is False
    assert proc.killed is True
    assert proc.wait_called is True


# ---- Applying a draft --------------------------------------------------------


def test_apply_draft_appends_exactly_one_agent_revision(skill, key, monkeypatch):
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])
    assert done["status"] == "succeeded"

    topic = bottleneck_topics.create_topic("AI power")
    updated = topic_agent.apply_draft(done["id"], topic["id"], summary="agent draft")

    assert updated is not None
    assert updated["id"] == topic["id"]
    assert len(updated["revisions"]) == 1
    assert updated["revisions"][0]["source"] == "agent"
    assert updated["revisions"][0]["summary"] == "agent draft"

    # Every downstream card carries the run's provenance, not the empty default,
    # and the applied revision snapshot carries it too.
    run = done["draft"]["provenance"]
    assert run["model"] and run["skill_snapshot"] and run["prompt_hash"] and run["run_ts"]
    cards = updated["downstream"]["anchor"] + updated["downstream"]["underdogs"]
    assert cards, "fixture must produce at least one downstream card"
    for card in cards:
        assert card["provenance"] == {
            "model": run["model"],
            "skill_snapshot": run["skill_snapshot"],
            "prompt_hash": run["prompt_hash"],
            "run_ts": run["run_ts"],
        }
    snapshot_cards = (
        updated["revisions"][0]["snapshot"]["downstream"]["anchor"]
        + updated["revisions"][0]["snapshot"]["downstream"]["underdogs"]
    )
    assert snapshot_cards[0]["provenance"] == cards[0]["provenance"]

    # Applying must not rewrite the persisted record of what was reviewed: the
    # job's own draft must not have gained the run's stamp.
    reviewed = done["draft"]["topic"]["downstream"]["anchor"][0]
    assert reviewed.get("provenance") != cards[0]["provenance"]

    # Unknown job / unknown topic never writes.
    assert topic_agent.apply_draft("missing", topic["id"]) is None
    # The job is now applied, so a repeat call is idempotent: it returns the
    # already-applied topic rather than appending another revision.
    again = topic_agent.apply_draft(done["id"], "missing")
    assert again is not None and again["id"] == topic["id"]


def test_apply_draft_records_applied_marker_on_the_job(skill, key, monkeypatch):
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])
    assert done["status"] == "succeeded"
    assert not done["applied"]

    topic = bottleneck_topics.create_topic("AI power")
    updated = topic_agent.apply_draft(done["id"], topic["id"], summary="agent draft")
    assert updated is not None

    recorded = topic_agent.get_job(done["id"])
    assert recorded["applied"]["topic_id"] == topic["id"]
    at = recorded["applied"]["at"]
    assert at
    # ISO 8601 with a UTC offset, matching ``_now_iso``.
    assert datetime.fromisoformat(at).tzinfo is not None


def test_apply_draft_unknown_topic_leaves_job_unapplied(skill, key, monkeypatch):
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])
    assert done["status"] == "succeeded"

    assert topic_agent.apply_draft(done["id"], "missing") is None
    assert not topic_agent.get_job(done["id"])["applied"]


def test_apply_draft_is_idempotent(skill, key, monkeypatch):
    """Applying twice appends exactly one revision and returns the topic."""
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])
    assert done["status"] == "succeeded"

    topic = bottleneck_topics.create_topic("AI power")
    assert bottleneck_topics.get_topic(topic["id"])["revisions"] == []

    first = topic_agent.apply_draft(done["id"], topic["id"], summary="agent draft")
    assert first is not None
    assert len(first["revisions"]) == 1

    second = topic_agent.apply_draft(done["id"], topic["id"], summary="agent draft")
    assert second is not None
    assert second["id"] == topic["id"]
    assert len(second["revisions"]) == 1  # not two
    # And the store agrees.
    assert len(bottleneck_topics.get_topic(topic["id"])["revisions"]) == 1

    # If the already-applied topic is deleted, the idempotent call returns None.
    bottleneck_topics.delete_topic(topic["id"])
    assert topic_agent.apply_draft(done["id"], topic["id"]) is None


# ---- Strict-refinement reconciliation (fill vs skeleton) ---------------------


def _layer(name, stocks, constraint="", watch=""):
    return {
        "name": name,
        "physical_constraint": constraint,
        "what_to_watch": watch,
        "stocks": list(stocks),
    }


def test_norm_name_and_layer_stock_tickers_are_defensive():
    assert topic_agent._norm_name("  Transformers ") == "transformers"
    assert topic_agent._norm_name(None) == ""
    assert topic_agent._norm_name(7) == ""

    layer = {"stocks": ["ETN", {"ticker": "TSM"}, "ETN", {"ticker": "  "}, ""]}
    assert topic_agent._layer_stock_tickers(layer) == ["ETN", "TSM"]
    assert topic_agent._layer_stock_tickers({"stocks": None}) == []
    assert topic_agent._layer_stock_tickers({"stocks": "not-a-list"}) == []
    assert topic_agent._layer_stock_tickers(None) == []


def test_reconcile_fill_restores_a_dropped_skeleton_layer():
    skeleton = _topic(upstream=[_layer("transformers", ["ETN"])])
    final = _topic(upstream=[], downstream={"anchor": [], "underdogs": []})

    out, adjustments = topic_agent._reconcile_fill(skeleton, final)

    assert [layer["name"] for layer in out["upstream"]] == ["transformers"]
    assert any("kept layer 'transformers'" in note for note in adjustments)


def test_reconcile_fill_restores_a_renamed_layer_name():
    skeleton = _topic(upstream=[_layer("transformers", ["ETN"])])
    # A case/whitespace-only rename still matches case-insensitively, so the
    # skeleton's own spelling is restored.
    final = _topic(upstream=[_layer("  Transformers ", ["ETN"])])

    out, adjustments = topic_agent._reconcile_fill(skeleton, final)

    assert out["upstream"][0]["name"] == "transformers"
    assert any("restored layer name 'transformers'" in note for note in adjustments)


def test_reconcile_fill_unions_a_dropped_ticker_back_into_its_layer():
    skeleton = _topic(upstream=[_layer("transformers", ["ETN", "GEV"])])
    final = _topic(upstream=[_layer("transformers", ["ETN"])])

    out, adjustments = topic_agent._reconcile_fill(skeleton, final)

    assert out["upstream"][0]["stocks"] == ["ETN", "GEV"]
    assert any("kept GEV in layer 'transformers'" in note for note in adjustments)


def test_reconcile_fill_restores_a_dropped_downstream_card():
    skeleton = _topic()  # anchor carries NVDA
    final = _topic(downstream={"anchor": [], "underdogs": []})

    out, adjustments = topic_agent._reconcile_fill(skeleton, final)

    assert [card["ticker"] for card in out["downstream"]["anchor"]] == ["NVDA"]
    assert any("kept NVDA (anchor)" in note for note in adjustments)


def test_reconcile_fill_preserves_additions_with_no_adjustments():
    skeleton = _topic()  # one layer "transformers" ["ETN"], anchor NVDA
    final = _topic(
        upstream=[
            _layer("transformers", ["ETN"]),
            _layer("grid", ["GEV"]),
        ],
        downstream={"anchor": [_stock(), _stock(ticker="AAOI")], "underdogs": []},
    )

    out, adjustments = topic_agent._reconcile_fill(skeleton, final)

    assert [layer["name"] for layer in out["upstream"]] == ["transformers", "grid"]
    assert [card["ticker"] for card in out["downstream"]["anchor"]] == ["NVDA", "AAOI"]
    assert adjustments == []


def test_reconcile_fill_does_not_mutate_its_inputs():
    skeleton = _topic(upstream=[_layer("transformers", ["ETN", "GEV"])])
    final = _topic(upstream=[_layer("power gear", ["ETN"])],
                   downstream={"anchor": [], "underdogs": []})
    skeleton_before = json.loads(json.dumps(skeleton))
    final_before = json.loads(json.dumps(final))

    topic_agent._reconcile_fill(skeleton, final)

    assert skeleton == skeleton_before
    assert final == final_before


def test_reconcile_fill_empty_skeleton_is_a_noop():
    final = _topic()
    before = json.loads(json.dumps(final))

    out, adjustments = topic_agent._reconcile_fill({}, final)

    assert out == before
    assert adjustments == []


def test_reconcile_fill_non_dict_inputs_return_safely():
    assert topic_agent._reconcile_fill(None, None) == (None, [])
    assert topic_agent._reconcile_fill({"upstream": []}, "not-a-dict") == (
        "not-a-dict", []
    )


def test_reconcile_fill_falls_back_to_skeleton_layer_text():
    skeleton = _topic(upstream=[_layer("transformers", ["ETN"], "binding constraint", "watch lead times")])
    final = _topic(upstream=[_layer("transformers", ["ETN"], "", None)])

    out, _adjustments = topic_agent._reconcile_fill(skeleton, final)

    layer = out["upstream"][0]
    assert layer["physical_constraint"] == "binding constraint"
    assert layer["what_to_watch"] == "watch lead times"


def test_fill_rules_require_skeleton_content_to_survive():
    prompt = topic_agent._build_prompt("AI power", {}, "", findings="findings", skeleton=_topic())

    assert "must survive the refinement" in prompt
    assert "never drop or rename" in prompt


# ---- Strict refinement at the worker level -----------------------------------


def test_fill_dropping_skeleton_content_is_restored_and_noted(skill, key, monkeypatch):
    skeleton_json = json.dumps(
        _topic(upstream=[_layer("transformers", ["ETN", "GEV"])])
    )
    dropped = _topic(
        name="Refined",
        upstream=[_layer("transformers", ["ETN"])],
        downstream={"anchor": [], "underdogs": []},
    )
    _install_transport(monkeypatch, [
        FakeResponse(200, _envelope(skeleton_json)),
        FakeResponse(200, _envelope(json.dumps(dropped))),
    ])

    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    final = done["draft"]["topic"]
    layer = next(ly for ly in final["upstream"] if ly["name"] == "transformers")
    assert "GEV" in layer["stocks"]
    assert [card["ticker"] for card in final["downstream"]["anchor"]] == ["NVDA"]
    assert done["fill_adjustments"]
    by_key = {stage["key"]: stage for stage in done["stages"]}
    assert by_key["fill"]["status"] == topic_agent.STAGE_DONE
    assert by_key["fill"]["note"] is not None


def test_fill_clean_superset_reports_no_adjustments(skill, key, monkeypatch):
    skeleton_json = json.dumps(_topic())
    superset = _topic(upstream=[
        _layer("transformers", ["ETN"], "transformer and switchgear capacity", "transformer lead times"),
        _layer("grid", ["GEV"]),
    ])
    _install_transport(monkeypatch, [
        FakeResponse(200, _envelope(skeleton_json)),
        FakeResponse(200, _envelope(json.dumps(superset))),
    ])

    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    assert done["fill_adjustments"] == []
    by_key = {stage["key"]: stage for stage in done["stages"]}
    assert by_key["fill"]["status"] == topic_agent.STAGE_DONE
    assert by_key["fill"]["note"] is None


def test_job_persists_the_draft_skeleton_apart_from_the_final(skill, key, monkeypatch):
    skeleton_json = json.dumps(_topic())
    superset = _topic(upstream=[
        _layer("transformers", ["ETN"], "transformer and switchgear capacity", "transformer lead times"),
        _layer("grid", ["GEV"]),
    ])
    _install_transport(monkeypatch, [
        FakeResponse(200, _envelope(skeleton_json)),
        FakeResponse(200, _envelope(json.dumps(superset))),
    ])

    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    assert [ly["name"] for ly in done["skeleton"]["upstream"]] == ["transformers"]
    assert [ly["name"] for ly in done["draft"]["topic"]["upstream"]] == [
        "transformers", "grid",
    ]


# ---- US-listed ticker filtering -----------------------------------------------


def test_max_research_chars_is_raised_to_120k():
    # Raised at the source from 20_000: nine of sixteen real topics hit the old
    # cap. Assert the constant itself, never a duplicated magic number in prose.
    assert topic_agent.MAX_RESEARCH_CHARS == 120_000


def test_is_us_listed_accepts_us_and_rejects_foreign_suffixes():
    assert topic_agent._is_us_listed("NVDA") is True
    assert topic_agent._is_us_listed("ETN") is True
    # A class share survives: the suffix list cannot disambiguate it.
    assert topic_agent._is_us_listed("BRK.A") is True
    for foreign in ("NEO.TO", "SHOP.T", "0700.HK", "600519.SH"):
        assert topic_agent._is_us_listed(foreign) is False
    assert topic_agent._is_us_listed("") is False
    assert topic_agent._is_us_listed("   ") is False
    assert topic_agent._is_us_listed(None) is False
    assert topic_agent._is_us_listed(7) is False


def test_strip_non_us_tickers_drops_foreign_layer_tickers_and_dedupes():
    topic = _topic(upstream=[
        _layer("materials", ["ETN", "HPS.A", "NEO.TSX", "NEO.TSX"]),
    ])

    stripped, removed = topic_agent._strip_non_us_tickers(topic)

    assert stripped["upstream"][0]["stocks"] == ["ETN", "HPS.A"]
    assert removed == ["NEO.TSX"]  # deduped


def test_strip_non_us_tickers_drops_foreign_cards_and_orders_removed():
    topic = _topic(downstream={
        "anchor": [_stock(ticker="BRK.A"), _stock(ticker="NEO.TSX")],
        "underdogs": [_stock(ticker="0700.HK"), _stock(ticker="AAOI")],
    })

    stripped, removed = topic_agent._strip_non_us_tickers(topic)

    assert [card["ticker"] for card in stripped["downstream"]["anchor"]] == ["BRK.A"]
    assert [card["ticker"] for card in stripped["downstream"]["underdogs"]] == ["AAOI"]
    assert removed == ["NEO.TSX", "0700.HK"]  # first-seen order


def test_strip_non_us_tickers_does_not_mutate_and_tolerates_junk():
    topic = _topic(upstream=[_layer("materials", ["ETN", "NEO.TSX"])])
    before = json.loads(json.dumps(topic))

    topic_agent._strip_non_us_tickers(topic)

    assert topic == before
    assert topic_agent._strip_non_us_tickers(None) == (None, [])
    assert topic_agent._strip_non_us_tickers("not-a-dict") == ("not-a-dict", [])
    # Non-dict layers/cards and missing keys are tolerated without raising.
    assert topic_agent._strip_non_us_tickers(
        {"upstream": ["junk"], "downstream": {"anchor": ["junk"]}}
    ) == ({"upstream": ["junk"], "downstream": {"anchor": []}}, [])


def test_prompts_require_us_listed_tickers():
    assert "US-listed" in topic_agent._schema_instructions()

    fill_prompt = topic_agent._build_prompt(
        "AI power", {}, "", "a fact", _topic()
    )
    assert "US-listed" in fill_prompt

    assert "US-listed" in topic_agent._research_prompt("AI power", ["NVDA"])


def test_worker_strips_foreign_tickers_from_skeleton_and_fill(skill, key, monkeypatch):
    skeleton = _topic(
        upstream=[_layer("materials", ["ETN", "NEO.TSX"])],
        downstream={
            "anchor": [_stock(ticker="NVDA"), _stock(ticker="NEO.TSX")],
            "underdogs": [],
        },
    )
    refined = _topic(
        name="Refined",
        upstream=[_layer("materials", ["ETN", "NEO.TSX", "GEV"])],
        downstream={
            "anchor": [
                _stock(ticker="NVDA"), _stock(ticker="NEO.TSX"),
                _stock(ticker="AAOI"),
            ],
            "underdogs": [],
        },
    )
    _install_transport(monkeypatch, [
        FakeResponse(200, _envelope(json.dumps(skeleton))),
        FakeResponse(200, _envelope(json.dumps(refined))),
    ])

    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    final = done["draft"]["topic"]
    layer_tickers = [t for ly in final["upstream"] for t in ly["stocks"]]
    card_tickers = [card["ticker"] for card in final["downstream"]["anchor"]]
    assert "NEO.TSX" not in layer_tickers + card_tickers
    assert {"ETN", "GEV"}.issubset(set(layer_tickers))
    assert {"NVDA", "AAOI"}.issubset(set(card_tickers))


# ---- ADR / OTC mapping rule in the prompts -----------------------------------


def test_prompts_require_adr_otc_mapping_with_examples():
    """Every prompt must tell the model to map a foreign company to its US line.

    The user explicitly chose mapping (X-FAB -> XFABF) over dropping a company
    that has a US OTC/ADR line.
    """
    schema = topic_agent._schema_instructions()
    fill_prompt = topic_agent._build_prompt("AI power", {}, "", "a fact", _topic())
    research_prompt = topic_agent._research_prompt("AI power", ["NVDA"])

    for text in (schema, fill_prompt, research_prompt):
        assert "US OTC" in text
        assert "ADR" in text
        assert "XFABF" in text


# ---- Resolution-based ticker drop --------------------------------------------


def test_resolve_tickers_splits_available_and_unavailable(monkeypatch):
    def fake_bulk(symbols, days=250, ttl=None):
        return {"NVDA": [{"date": "2026-01-01", "close": 1.0}]}

    monkeypatch.setattr(market, "get_histories_bulk", fake_bulk)

    available, unavailable = topic_agent._resolve_tickers(["NVDA", "ZZZZ"])

    assert available == ["NVDA"]
    assert unavailable == ["ZZZZ"]


def test_resolve_tickers_matches_case_insensitively_and_dedupes(monkeypatch):
    def fake_bulk(symbols, days=250, ttl=None):
        return {"nvda": [{"date": "2026-01-01", "close": 1.0}]}

    monkeypatch.setattr(market, "get_histories_bulk", fake_bulk)

    available, unavailable = topic_agent._resolve_tickers(["NVDA", "nvda", "ZZZZ"])

    assert available == ["NVDA"]
    assert unavailable == ["ZZZZ"]


def test_resolve_tickers_never_drops_on_error(monkeypatch):
    def boom(symbols, days=250, ttl=None):
        raise RuntimeError("market data unavailable")

    monkeypatch.setattr(market, "get_histories_bulk", boom)

    assert topic_agent._resolve_tickers(["NVDA", "AAA"], timeout=5.0) == (
        ["NVDA", "AAA"], []
    )


def test_resolve_tickers_never_drops_on_timeout(monkeypatch):
    release = threading.Event()

    def slow(symbols, days=250, ttl=None):
        release.wait(5)
        return {}

    monkeypatch.setattr(market, "get_histories_bulk", slow)
    try:
        assert topic_agent._resolve_tickers(["NVDA"], timeout=0.05) == (
            ["NVDA"], []
        )
    finally:
        release.set()


def test_resolve_tickers_empty_input_is_a_noop():
    assert topic_agent._resolve_tickers([]) == ([], [])


def test_strip_unresolved_tickers_drops_matching_stock_and_card():
    topic = _topic(
        upstream=[_layer("materials", ["ETN", "NOPMF", "GEV"])],
        downstream={
            "anchor": [_stock(ticker="NVDA"), _stock(ticker="NOPMF")],
            "underdogs": [_stock(ticker="AAOI")],
        },
    )
    before = json.loads(json.dumps(topic))

    stripped, removed = topic_agent._strip_unresolved_tickers(topic, ["nopmf"])

    assert stripped["upstream"][0]["stocks"] == ["ETN", "GEV"]
    assert [c["ticker"] for c in stripped["downstream"]["anchor"]] == ["NVDA"]
    assert [c["ticker"] for c in stripped["downstream"]["underdogs"]] == ["AAOI"]
    assert removed == ["NOPMF"]  # original spelling, not the match key
    assert topic == before  # the input is never mutated


def test_strip_unresolved_tickers_tolerates_junk_and_dedupes():
    assert topic_agent._strip_unresolved_tickers(None, ["X"]) == (None, [])
    assert topic_agent._strip_unresolved_tickers("not-a-dict", ["X"]) == (
        "not-a-dict", []
    )
    assert topic_agent._strip_unresolved_tickers({"upstream": ["junk"]}, None) == (
        {"upstream": ["junk"]}, []
    )

    topic = _topic(
        upstream=[_layer("m1", ["AAA"]), _layer("m2", ["AAA", "BBB"])],
    )
    stripped, removed = topic_agent._strip_unresolved_tickers(topic, ["AAA"])

    assert removed == ["AAA"]  # deduped
    assert stripped["upstream"][0]["stocks"] == []
    assert stripped["upstream"][1]["stocks"] == ["BBB"]


def test_worker_drops_tickers_with_no_market_data(skill, key, monkeypatch):
    skeleton = _topic(upstream=[_layer("materials", ["ETN", "ZZZZ"])])
    refined = _topic(name="Refined")

    def fake_bulk(symbols, days=250, ttl=None):
        return {
            s: [{"date": "2026-01-01", "close": 1.0}]
            for s in symbols if s != "ZZZZ"
        }

    monkeypatch.setattr(market, "get_histories_bulk", fake_bulk)
    _install_transport(monkeypatch, [
        FakeResponse(200, _envelope(json.dumps(skeleton))),
        FakeResponse(200, _envelope(json.dumps(refined))),
    ])

    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    final = done["draft"]["topic"]
    layer_tickers = [t for ly in final["upstream"] for t in ly["stocks"]]
    assert "ZZZZ" not in layer_tickers
    assert done["dropped_tickers"] == ["ZZZZ"]
    by_key = {stage["key"]: stage for stage in done["stages"]}
    assert by_key["warm_metrics"]["status"] == topic_agent.STAGE_DONE
    assert "dropped 1 ticker(s) with no market data" in by_key["warm_metrics"]["note"]


def test_worker_leaves_dropped_tickers_empty_when_all_resolve(skill, key, monkeypatch):
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])

    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert done["status"] == "succeeded"
    assert done["dropped_tickers"] == []


# ---- Source liveness filter --------------------------------------------------


def _public_getaddrinfo(host, *args, **kwargs):
    """Resolve any host to a public IP so the probe guard lets it through."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


def test_filter_dead_sources_drops_4xx_keeps_2xx_and_errors(monkeypatch):
    dead = "https://dead.example/x"
    ok = "https://ok.example/y"
    flaky = "https://flaky.example/z"
    findings = "\n".join([
        f"- A: fact [source: {dead} | date: 2026-01-01]",
        f"- B: fact [source: {ok} | date: 2026-01-02]",
        f"- C: fact [source: {flaky} | date: 2026-01-03]",
    ])

    class _Resp:
        def __init__(self, status_code):
            self.status_code = status_code

    def fake_get(url, timeout=None, stream=None, allow_redirects=None, headers=None):
        if url == dead:
            return _Resp(404)
        if url == ok:
            return _Resp(200)
        raise RuntimeError("tls handshake failed")

    monkeypatch.setattr(topic_agent.socket, "getaddrinfo", _public_getaddrinfo)
    monkeypatch.setattr(topic_agent.requests, "get", fake_get)

    filtered, dropped = topic_agent._filter_dead_sources(findings)

    assert dropped == [dead]
    assert dead not in filtered
    assert ok in filtered
    assert flaky in filtered


def test_filter_dead_sources_none_and_empty_are_noops():
    assert topic_agent._filter_dead_sources(None) == (None, [])
    assert topic_agent._filter_dead_sources("") == ("", [])


def test_filter_dead_sources_probe_cap_keeps_the_remainder(monkeypatch):
    urls = [f"https://s{i}.example/x" for i in range(3)]
    findings = "\n".join(
        f"- {i}: fact [source: {url} | date: 2026-01-01]"
        for i, url in enumerate(urls)
    )
    probed: list[str] = []

    class _Resp:
        status_code = 404

    def fake_get(url, timeout=None, stream=None, allow_redirects=None, headers=None):
        probed.append(url)
        return _Resp()

    monkeypatch.setattr(topic_agent.socket, "getaddrinfo", _public_getaddrinfo)
    monkeypatch.setattr(topic_agent.requests, "get", fake_get)

    filtered, dropped = topic_agent._filter_dead_sources(findings, max_probes=1)

    assert probed == [urls[0]]
    assert dropped == [urls[0]]
    assert urls[1] in filtered
    assert urls[2] in filtered


# ---- SSRF guard on the source probe ------------------------------------------


def test_probe_source_never_fetches_private_or_non_http_targets(monkeypatch):
    """Untrusted findings must not turn the probe into an SSRF primitive."""
    fetched: list[str] = []

    class _Resp:
        status_code = 200

    def spy(url, *args, **kwargs):
        fetched.append(url)
        return _Resp()

    def fake_getaddrinfo(host, *args, **kwargs):
        if host == "evil.example":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]
        return _public_getaddrinfo(host)

    monkeypatch.setattr(topic_agent.requests, "get", spy)
    monkeypatch.setattr(topic_agent.socket, "getaddrinfo", fake_getaddrinfo)

    unsafe = [
        "http://127.0.0.1:8000/api/shutdown",
        "http://localhost:8000/x",
        "https://10.0.0.1/",
        "https://[::1]/",
        "ftp://example.com/x",
        "https://evil.example/x",
    ]
    for url in unsafe:
        assert topic_agent._probe_source_is_dead(url, 1.0) is False, url
    assert fetched == []

    # A normal public URL is probed (the spy returns 200 -> not dead).
    assert topic_agent._probe_source_is_dead("https://example.com/x", 1.0) is False
    assert fetched == ["https://example.com/x"]


def test_probe_source_refuses_when_name_does_not_resolve(monkeypatch):
    fetched: list[str] = []
    monkeypatch.setattr(
        topic_agent.requests, "get", lambda *a, **k: fetched.append(a)
    )

    def _boom(host, *args, **kwargs):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(topic_agent.socket, "getaddrinfo", _boom)

    assert topic_agent._probe_source_is_dead("https://nowhere.example/x", 1.0) is False
    assert fetched == []


def test_probe_source_treats_a_redirect_as_not_dead(monkeypatch):
    class _Resp:
        status_code = 302

    monkeypatch.setattr(topic_agent.socket, "getaddrinfo", _public_getaddrinfo)
    monkeypatch.setattr(topic_agent.requests, "get", lambda *a, **k: _Resp())

    assert topic_agent._probe_source_is_dead("https://example.com/x", 1.0) is False


def test_run_research_all_dead_sources_degrades_to_skipped(monkeypatch):
    dead = "https://dead.example/only"
    body = f"a fact [source: {dead} | date: 2026-01-01]"

    class _Proc:
        returncode = 0
        stdout = json.dumps({"type": "text", "part": {"text": body}})
        stderr = ""

    class _Resp:
        status_code = 404

    monkeypatch.setattr(topic_agent.subprocess, "run", lambda *a, **k: _Proc())
    monkeypatch.setattr(topic_agent.shutil, "which", lambda name: None)
    monkeypatch.setattr(topic_agent.socket, "getaddrinfo", _public_getaddrinfo)
    monkeypatch.setattr(topic_agent.requests, "get", lambda *a, **k: _Resp())

    status, _note, findings = _REAL_RUN_RESEARCH("AI power", ["NVDA"])

    assert status == topic_agent.STAGE_SKIPPED
    assert findings is None
