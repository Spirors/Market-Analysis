"""Global pytest fixtures for the Market Analysis Tool test suite.

The autouse ``_isolate_data_files`` fixture below is the safety net that
keeps every pytest run from touching the user's live ``data/`` directory.
Without it, any test that forgets to redirect ``portfolio.PORTFOLIOS_PATH``
(or any other persisted-state path) would silently write to / read from
the user's real ``data/portfolios.json`` — corrupting their holdings.

How it works
------------
* The fixture monkeypatches every module-level path constant that points
  into ``data/`` to a fresh ``tmp_path`` location. The constants are
  evaluated at module import time (e.g. ``PORTFOLIOS_PATH = config.DATA_DIR
  / "portfolios.json"`` in ``app/portfolio.py:95``), so patching
  ``config.DATA_DIR`` alone is not enough — each module's bound name must
  be patched separately.
* pytest applies autouse fixtures before per-test fixtures. Tests that
  already declare a more specific fixture (e.g. ``tmp_portfolios`` in
  ``test_portfolio.py``, ``tmp_store`` in ``test_api_contract.py``) will
  override the autouse's value with their own — the autouse just makes
  sure that no test that *forgets* to set up isolation can corrupt user
  data.
* ``tmp_path`` is per-test and auto-removed by pytest at teardown, so
  cleanup is automatic — no manual teardown needed in the fixture.
* ``app.store`` keeps a module-level ``_READY`` flag. It is reset so the
  next call picks up the new (tmp) paths instead of caching references to
  the originals.

Do not touch
------------
* ``app.config.STATIC_DIR`` — points at the read-only ``static/`` tree,
  never user data; no need to redirect and redirecting could break the
  dashboard payload contract tests.
* ``app.config.BASE_DIR`` — repo root, used for STATIC_DIR; not user data.

Adding a new persisted-state path
----------------------------------
If you add a new ``config.X = BASE_DIR / "data" / "..."`` (or any other
user-data path) and reference it as a module-level constant elsewhere,
add a ``monkeypatch.setattr(<module>, "<CONST>", tmp_path / "...")`` line
to ``_isolate_data_files`` below. The rule lives in
``.opencode/skills/project-rules/SKILL.md`` § "Test isolation".
"""

from __future__ import annotations

import time

import pytest

from app import ai_valuation, bottleneck_topics, changelog, config, portfolio, store, topic_agent


def _drain_generation_lock(timeout: float = 6.0) -> None:
    """Wait (bounded) for the topic-agent worker to release its serial lock.

    ``_run_job`` runs on a daemon thread and holds ``_generation_lock`` until its
    ``finally``. A test that returns on a ``cancelled``/``failed`` status can
    therefore end while the worker is still unwinding, and the worker's next
    ``_save_jobs`` would then run after monkeypatch restored the REAL
    ``_JOBS_PATH`` -- writing the tmp job list over the user's live data file.
    """
    deadline = time.time() + timeout
    while topic_agent._generation_lock.locked() and time.time() < deadline:
        time.sleep(0.01)


@pytest.fixture(autouse=True)
def _isolate_data_files(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Redirect every user-data path to a per-test temp directory.

    Autouse: every pytest test in this repo gets it for free, so a test
    that forgets to set up isolation can never corrupt the user's real
    ``data/`` files. Per-test fixtures (e.g. ``tmp_portfolios``) override
    these values when they apply — the autouse is the floor, not the
    ceiling.
    """
    # User-data paths — the most critical first.
    monkeypatch.setattr(portfolio, "PORTFOLIOS_PATH", tmp_path / "portfolios.json")
    monkeypatch.setattr(bottleneck_topics, "_TOPICS_PATH", tmp_path / "bottleneck_topics.json")
    monkeypatch.setattr(topic_agent, "_JOBS_PATH", tmp_path / "bottleneck_jobs.json")
    monkeypatch.setattr(store, "SUPPRESSED_PATH", tmp_path / "suppressed_sources.json")
    # The analytics paths on app.config — these are re-read each call, so
    # patching config itself is enough for them.
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "REGIME_DIR", tmp_path / "regime")
    monkeypatch.setattr(config, "EVENTS_PATH", tmp_path / "events.json")
    # changelog.LOG_DIR is a module-level constant resolved at import
    # time from __file__, so it does NOT see the config.DATA_DIR patch
    # above and must be redirected explicitly.
    monkeypatch.setattr(changelog, "LOG_DIR", tmp_path / "logs")
    # Reset the store's readiness flag so the next call re-reads the
    # redirected paths instead of holding references to the originals.
    monkeypatch.setattr(store, "_READY", False)
    monkeypatch.setattr(ai_valuation, "_CACHE_PATH", tmp_path / "ai_valuation.json")
    # Drain both sides of the test while the paths are still redirected: this
    # fixture summons ``monkeypatch``, so it tears down before monkeypatch
    # restores the real paths. Without the trailing drain, a worker left
    # unwinding by the test writes the tmp job list over the live file.
    _drain_generation_lock()
    yield
    _drain_generation_lock()