"""Tests for the DetectorRunner subprocess wrapper in app/regime.py.

The runner is the only place that sees the detector's exit code and stderr;
before it logged those, a failed detection left no trace beyond a missing
report file (the 2026-10-18/19 gap).
"""

import logging
import subprocess

from app import regime


def _stub_script(tmp_path):
    script = tmp_path / "detector.py"
    script.write_text("# stub\n", encoding="utf-8")
    return script


def _completed(returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["detector"], returncode=returncode, stdout=stdout, stderr=stderr,
    )


def test_detector_failure_is_logged_with_stderr(monkeypatch, tmp_path, caplog):
    runner = regime.DetectorRunner(
        script_path=_stub_script(tmp_path), output_dir=tmp_path,
    )
    monkeypatch.setattr(
        regime.subprocess, "run",
        lambda *a, **k: _completed(1, "", "ERROR: Cannot proceed without SPY data"),
    )

    with caplog.at_level(logging.WARNING, logger="app.regime"):
        result = runner.run()

    assert result["error"] == "regime detection failed"
    assert "SPY data" in result["stderr"]
    assert any(
        "regime detection failed (exit 1)" in record.message
        for record in caplog.records
    )


def test_detector_no_report_is_logged(monkeypatch, tmp_path, caplog):
    runner = regime.DetectorRunner(
        script_path=_stub_script(tmp_path), output_dir=tmp_path,
    )
    monkeypatch.setattr(
        regime.subprocess, "run", lambda *a, **k: _completed(0, "done", ""),
    )
    monkeypatch.setattr(regime, "_latest_regime_json", lambda: None)

    with caplog.at_level(logging.WARNING, logger="app.regime"):
        result = runner.run()

    assert result["error"] == "no regime report produced"
    assert any(
        "produced no report" in record.message for record in caplog.records
    )


def test_detector_timeout_is_logged(monkeypatch, tmp_path, caplog):
    runner = regime.DetectorRunner(
        script_path=_stub_script(tmp_path), output_dir=tmp_path, timeout=7,
    )

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="detector", timeout=7)

    monkeypatch.setattr(regime.subprocess, "run", _timeout)

    with caplog.at_level(logging.WARNING, logger="app.regime"):
        result = runner.run()

    assert result["error"] == "regime detection timed out"
    assert any(
        "timed out after 7s" in record.message for record in caplog.records
    )
