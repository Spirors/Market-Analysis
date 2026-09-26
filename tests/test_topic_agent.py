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
    # Generation's stage 1 shells out to npx and stage 4 warms market data;
    # stub both seams so no test spawns a child or reaches the network.  The
    # explicit ``refresh_skill`` tests below bypass these seams on purpose.
    monkeypatch.setattr(topic_agent, "_refresh_skill_stage", lambda: {"ok": True})
    monkeypatch.setattr(topic_agent, "_warm_draft_metrics", lambda tickers: ("done", None))
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

    assert len(calls) == 1
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
    for field in ("id", "status", "theme", "model", "created", "updated", "error",
                  "draft", "stages"):
        assert field in raw["jobs"][0]
    assert [s["key"] for s in raw["jobs"][0]["stages"]] == [
        "refresh_skill", "read_lens", "draft", "warm_metrics",
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
        "refresh_skill", "read_lens", "draft", "warm_metrics",
    ]
    assert [s["label"] for s in done["stages"]] == [
        "Refresh skill", "Read lens", "Draft thesis", "Pull market data",
    ]
    assert all(s["status"] == topic_agent.STAGE_DONE for s in done["stages"])


def test_refresh_failure_is_non_fatal_and_noted(skill, key, monkeypatch):
    monkeypatch.setattr(
        topic_agent, "_refresh_skill_stage",
        lambda: {"ok": False, "timed_out": True},
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
    def _boom():
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
    assert topic_agent.apply_draft(done["id"], "missing") is None