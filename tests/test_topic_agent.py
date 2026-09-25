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
import threading
import time

import pytest

from app import bottleneck_topics, store, topic_agent


# ---- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    """Never read the real ``.env`` or the live skill by default."""
    monkeypatch.setattr(topic_agent, "ENV_PATH", tmp_path / "env-absent")
    monkeypatch.delenv(topic_agent.KEY_NAME, raising=False)
    monkeypatch.setattr(topic_agent, "SKILL_DIR", tmp_path / "no-skill")
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
        "conviction_tier": "core",
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
        "upstream": [{"layer": "transformers", "stocks": ["ETN"]}],
        "downstream": {"anchor": [_stock()], "underdogs": []},
        "underdog_ceiling": 10_000_000_000,
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

    assert len(calls) == 1
    request = calls[0]
    assert request["url"] == topic_agent.ZEN_ENDPOINT
    assert request["payload"]["max_tokens"] >= 4096
    headers = request["headers"]
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["User-Agent"] == topic_agent.USER_AGENT
    assert headers["x-opencode-session"].startswith("topic-agent-")


def test_empty_content_is_retried_not_accepted(skill, key, monkeypatch):
    calls = _install_transport(monkeypatch, [
        FakeResponse(200, _envelope("", finish_reason="length")),
        FakeResponse(200, _envelope(_valid_json())),
    ])
    done = _wait(topic_agent.start_generation("AI power")["id"])
    assert done["status"] == "succeeded"
    assert len(calls) == 2
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
    assert len(calls) == 2
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


def test_cancel_mid_flight_marks_cancelled_promptly(skill, key, monkeypatch):
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
    assert cancelled["status"] == "cancelled"
    release.set()

    done = _wait(job["id"])
    assert done["status"] == "cancelled"
    assert done["draft"] is None


# ---- Job persistence + recovery ----------------------------------------------


def test_jobs_persist_round_trip_under_tmp_path(skill, key, monkeypatch, tmp_path):
    assert topic_agent._JOBS_PATH.parent == tmp_path
    _install_transport(monkeypatch, [FakeResponse(200, _envelope(_valid_json()))])
    done = _wait(topic_agent.start_generation("AI power")["id"])

    assert topic_agent.get_job(done["id"])["id"] == done["id"]
    assert topic_agent.list_jobs()[0]["id"] == done["id"]

    raw = json.loads(topic_agent._JOBS_PATH.read_text(encoding="utf-8"))
    assert raw["jobs"][0]["id"] == done["id"]
    for field in ("id", "status", "theme", "model", "created", "updated", "error", "draft"):
        assert field in raw["jobs"][0]


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
    assert topic_agent.apply_draft(done["id"], "missing") is None