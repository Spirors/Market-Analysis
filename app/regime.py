"""Regime detection: reuse the installed macro-regime-detector skill via subprocess."""

import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from . import config, store


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
    config.ensure_dirs()
    if not config.REGIME_DETECTOR_SCRIPT.exists():
        return {"error": "regime detector skill not installed"}

    cmd = [
        sys.executable,
        str(config.REGIME_DETECTOR_SCRIPT),
        "--output-dir", str(config.REGIME_DIR),
        "--days", str(days),
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=config.REGIME_SUBPROCESS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return {"error": "regime detection timed out"}
    except subprocess.SubprocessError as e:
        # Any other subprocess failure (e.g. the child could not be run)
        # must degrade to an error payload, not crash the refresh.
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
