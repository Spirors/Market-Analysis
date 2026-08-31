"""Regime detection: reuse the installed macro-regime-detector skill via subprocess.

# Changelog:
# 2026-08-30 — regime: DetectorRunner factory pattern — subprocess invocation
#              is encapsulated behind a DetectorRunner keyed off
#              config.REGIME_DETECTOR_SCRIPT.  Behavior: none (pure refactor).
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from . import config, store


# ---- DetectorRunner factory --------------------------------------------------

class DetectorRunner:
    """Factory that encapsulates subprocess invocation of the regime detector.

    The script location is driven by ``config.REGIME_DETECTOR_SCRIPT`` so the
    factory itself never hard-codes paths.  Timeout and history window are
    also config-driven.
    """

    def __init__(
        self,
        script_path: Path,
        output_dir: Path,
        timeout: int = config.REGIME_SUBPROCESS_TIMEOUT_S,
        days: int = config.REGIME_DETECT_DAYS,
    ) -> None:
        self._script_path = script_path
        self._output_dir = output_dir
        self._timeout = timeout
        self._days = days

    def run(self) -> Optional[dict[str, Any]]:
        """Run the macro-regime-detector CLI and return its parsed JSON report."""
        config.ensure_dirs()
        if not self._script_path.exists():
            return {"error": "regime detector skill not installed"}

        cmd = [
            sys.executable,
            str(self._script_path),
            "--output-dir", str(self._output_dir),
            "--days", str(self._days),
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            return {"error": "regime detection timed out"}
        except subprocess.SubprocessError as e:
            return {"error": f"regime detection failed to run: {type(e).__name__}: {e}"}
        except OSError as e:
            return {"error": f"regime detection could not start: {type(e).__name__}: {e}"}

        if proc.returncode != 0:
            return {
                "error": "regime detection failed",
                "stderr": (proc.stderr or "")[-800:],
            }
        report = _latest_regime_json()
        if report is None:
            return {"error": "no regime report produced"}
        report["_stdout_tail"] = (proc.stdout or "")[-400:]
        return report


def _latest_regime_file() -> Optional[Path]:
    files = sorted(config.REGIME_DIR.glob("macro_regime_*.json"))
    return files[-1] if files else None


def _latest_regime_json() -> Optional[dict[str, Any]]:
    path = _latest_regime_file()
    if path is None:
        return None
    return store.load_json(path)


def run_regime_detection(days: int = config.REGIME_DETECT_DAYS) -> Optional[dict[str, Any]]:
    """Run the macro-regime-detector CLI and return its parsed JSON report."""
    runner = DetectorRunner(
        script_path=config.REGIME_DETECTOR_SCRIPT,
        output_dir=config.REGIME_DIR,
        days=days,
    )
    return runner.run()


def get_regime() -> dict[str, Any]:
    """Latest regime report, or run detection if none cached.

    Reports older than ``config.REGIME_MAX_AGE_DAYS`` are still served but
    flagged (``stale: true`` + ``age_days``) so neither the card nor the
    synthesis reader mistakes them for current — matching the 13F
    stale-cache-with-stamps fallback style.
    """
    path = _latest_regime_file()
    if path is not None:
        report = store.load_json(path)
        if report is not None:
            age_days = max(0.0, (time.time() - path.stat().st_mtime) / 86400)
            if age_days > config.REGIME_MAX_AGE_DAYS:
                report["stale"] = True
                report["age_days"] = round(age_days, 1)
            return report
    fresh = run_regime_detection()
    if fresh is not None and "error" not in fresh:
        return fresh
    return fresh or {"error": "regime report unavailable"}
