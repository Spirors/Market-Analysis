"""Tests for the local fold flow `run.py --sync` (run.sync_data_repo).

Guards are cheap; the round-trip is a real git integration test against a bare
origin. Skips if git is unavailable.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("run_under_test", _REPO_ROOT / "run.py")
assert _SPEC and _SPEC.loader
run = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run)

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def test_sync_requires_env(monkeypatch):
    monkeypatch.delenv("MARKET_ANALYSIS_DATA_REPO", raising=False)
    assert run.sync_data_repo() == 1


def test_sync_rejects_non_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_ANALYSIS_DATA_REPO", str(tmp_path / "not-a-repo"))
    assert run.sync_data_repo() == 1


@requires_git
def test_sync_round_trip_publishes_state(tmp_path, monkeypatch, capfd):
    """A real pull->fold->state->commit->push round trip against a bare origin."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True, capture_output=True)

    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True)
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")

    # Seed the origin's future content locally WITHOUT pushing: a fresh data
    # repo has no upstream ref yet, so sync must skip the pull (not error).
    (work / "captures" / "history").mkdir(parents=True)
    (work / "captures" / "history" / "2020-01-01.json").write_text(
        json.dumps({"close_date": "2020-01-01", "recorded_at": "2020-01-01T21:00:00Z", "portfolios": {}}),
        encoding="utf-8",
    )
    _git(work, "add", "captures")
    _git(work, "commit", "-q", "-m", "capture")

    # Local data dir is the conftest-redirected config.DATA_DIR (a tmp path).
    from app import config
    (config.DATA_DIR / "events.json").write_text(
        json.dumps({"version": 1, "suppressed_sources": [], "events": []}), encoding="utf-8"
    )

    monkeypatch.setenv("MARKET_ANALYSIS_DATA_REPO", str(work))
    assert run.sync_data_repo() == 0
    out = capfd.readouterr().out
    assert "sync complete" in out

    # History folded write-if-absent into the local store.
    hist = json.loads((config.DATA_DIR / "portfolio_history.json").read_text(encoding="utf-8"))
    assert "2020-01-01" in hist["snapshots"]
    # State published to the origin.
    assert (work / "state" / "portfolio_history.json").exists()
    assert (work / "state" / "events.json").exists()

    # Re-running is a no-op.
    assert run.sync_data_repo() == 0
    assert "nothing to publish" in capfd.readouterr().out


@requires_git
def test_sync_pushes_previously_stranded_commit(tmp_path, monkeypatch, capfd):
    """A state commit stranded by a failed push is recovered on the next run."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True, capture_output=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True)
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")

    # Seed the branch + upstream so @{u} resolves on the recovery run.
    (work / "README.md").write_text("data repo\n", encoding="utf-8")
    _git(work, "add", "README.md")
    _git(work, "commit", "-q", "-m", "init")
    _git(work, "push", "-u", "origin", "HEAD")

    from app import config, sync as sync_mod
    (config.DATA_DIR / "events.json").write_text(
        json.dumps({"version": 1, "suppressed_sources": [], "events": []}), encoding="utf-8"
    )
    # A state commit made but never pushed (the stranded commit). Its content
    # matches what the next sync re-derives, so nothing else stages.
    sync_mod.copy_state_to_repo(config.DATA_DIR, work)
    _git(work, "add", "state")
    _git(work, "commit", "-q", "-m", "state: stranded [skip ci]")
    stranded_head = _git(work, "rev-parse", "HEAD").stdout.strip()
    origin_before = subprocess.run(
        ["git", "-C", str(origin), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    assert origin_before != stranded_head  # stranded, not yet on origin

    monkeypatch.setenv("MARKET_ANALYSIS_DATA_REPO", str(work))
    assert run.sync_data_repo() == 0
    assert "previously stranded" in capfd.readouterr().out

    origin_after = subprocess.run(
        ["git", "-C", str(origin), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    assert origin_after == stranded_head  # the stranded commit reached origin


@requires_git
def test_sync_noop_when_clean_and_up_to_date(tmp_path, monkeypatch, capfd):
    """Clean tree with an upstream and nothing ahead → no push, no new commit."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True, capture_output=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True)
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")
    (work / "README.md").write_text("data repo\n", encoding="utf-8")
    _git(work, "add", "README.md")
    _git(work, "commit", "-q", "-m", "init")
    _git(work, "push", "-u", "origin", "HEAD")

    from app import config, sync as sync_mod
    (config.DATA_DIR / "events.json").write_text(
        json.dumps({"version": 1, "suppressed_sources": [], "events": []}), encoding="utf-8"
    )
    sync_mod.copy_state_to_repo(config.DATA_DIR, work)
    _git(work, "add", "state")
    _git(work, "commit", "-q", "-m", "state: published [skip ci]")
    _git(work, "push")
    head_before = _git(work, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.setenv("MARKET_ANALYSIS_DATA_REPO", str(work))
    assert run.sync_data_repo() == 0
    out = capfd.readouterr().out
    assert "nothing to publish" in out
    assert "previously stranded" not in out
    assert _git(work, "rev-parse", "HEAD").stdout.strip() == head_before
    origin_head = subprocess.run(
        ["git", "-C", str(origin), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    assert origin_head == head_before
