"""CLI-contract tests for scripts/cloud_export.py ``pull-state`` (fail-loud)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "cloud_export_under_test", _REPO_ROOT / "scripts" / "cloud_export.py"
)
assert _SPEC and _SPEC.loader
cloud_export = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cloud_export)

from app import sync  # noqa: E402


def _write_all_state(state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "portfolios.json").write_text(json.dumps({"version": 1, "portfolios": {}}), encoding="utf-8")
    (state_dir / "portfolio_history.json").write_text(json.dumps({"version": 1, "snapshots": {}}), encoding="utf-8")
    (state_dir / "events.json").write_text(
        json.dumps({"version": 1, "suppressed_sources": [], "events": []}), encoding="utf-8"
    )
    (state_dir / "bottleneck_topics.json").write_text(json.dumps({}), encoding="utf-8")
    (state_dir / "watchlist.json").write_text(json.dumps({"tickers": []}), encoding="utf-8")
    (state_dir / "earnings_removed.json").write_text(json.dumps({"tickers": []}), encoding="utf-8")


def test_pull_state_complete_exits_zero(tmp_path, capsys):
    repo = tmp_path / "repo"
    _write_all_state(repo / "state")
    data = tmp_path / "data"
    data.mkdir()

    rc = cloud_export.main(["pull-state", "--repo-dir", str(repo), "--data-dir", str(data)])
    assert rc == 0
    out = capsys.readouterr().out
    assert f"complete ({len(sync.STATE_FILES)}/{len(sync.STATE_FILES)} state files)" in out


def test_pull_state_incomplete_exits_one(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "state").mkdir(parents=True)
    (repo / "state" / "portfolios.json").write_text(
        json.dumps({"version": 1, "portfolios": {}}), encoding="utf-8"
    )
    data = tmp_path / "data"
    data.mkdir()

    rc = cloud_export.main(["pull-state", "--repo-dir", str(repo), "--data-dir", str(data)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "INCOMPLETE restore" in err
    assert "missing:" in err
