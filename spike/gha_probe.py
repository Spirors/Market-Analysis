"""GHA probe: does the existing Python pipeline work on ubuntu-latest / py3.12?

Self-contained. Run from anywhere: it chdirs to the repo root derived from
``__file__``. Records everything (env + per-test evidence + logs) into
``spike/evidence/`` and writes ``spike/evidence/results.json`` before exiting.

Synthetic data only: a minimal portfolio fixture is written at runtime; no real
user data is ever read or copied. ``data/*`` is gitignored so the fixture never
enters the repo.

Exit code: 0 when every core test passed, else 1. main() is wrapped so a crash
still writes results.json.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "spike" / "evidence"
REGIME_REQS = ROOT / ".agents" / "skills" / "macro-regime-detector" / "requirements.txt"
REGIME_SCRIPT = ROOT / ".agents" / "skills" / "macro-regime-detector" / "scripts" / "macro_regime_detector.py"

CORE_TESTS = ["yf_direct", "regime_direct", "news_refresh", "full_refresh", "commit_events"]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tail(text, n=4000) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    return text[-n:]


def run_cmd(cmd, timeout_s, cwd=ROOT):
    """Run a command, capturing exit code / duration / output tails."""
    start = time.monotonic()
    try:
        p = subprocess.run(
            [str(c) for c in cmd],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return {
            "exit_code": p.returncode,
            "duration_s": round(time.monotonic() - start, 2),
            "stdout_tail": _tail(p.stdout),
            "stderr_tail": _tail(p.stderr),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "exit_code": None,
            "duration_s": round(time.monotonic() - start, 2),
            "stdout_tail": _tail(e.stdout),
            "stderr_tail": _tail(e.stderr),
            "timed_out": True,
        }


def run_threaded(fn, timeout_s):
    """Run fn() in a daemon thread with a wall-clock timeout (for in-process calls)."""
    box = {}
    start = time.monotonic()

    def worker():
        try:
            box["value"] = fn()
        except BaseException:  # noqa: BLE001 - capture everything verbatim
            box["error"] = traceback.format_exc()
        finally:
            box["done"] = True

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout_s)
    dur = round(time.monotonic() - start, 2)
    if "done" not in box:
        return {"completed": False, "duration_s": dur,
                "detail": f"timed out after {timeout_s}s"}
    return {
        "completed": True,
        "duration_s": dur,
        "value": box.get("value"),
        "error": box.get("error"),
    }


def copy_into_evidence(src: Path, dst_name: str | None = None) -> bool:
    try:
        if not src.exists() or not src.is_file():
            return False
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, EVIDENCE / (dst_name or src.name))
        return True
    except Exception:  # noqa: BLE001
        return False


def count_events() -> int | None:
    p = ROOT / "data" / "events.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("events"), list):
            return len(d["events"])
        return None
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# 1. Environment
# --------------------------------------------------------------------------- #

def collect_env() -> dict:
    env = {
        "utc": _now_iso(),
        "platform": platform.platform(),
        "sys_version": sys.version.replace("\n", " "),
        "machine": platform.machine(),
    }
    try:
        osr = Path("/etc/os-release")
        if osr.exists():
            lines = osr.read_text(encoding="utf-8", errors="replace").splitlines()
            env["os_release"] = "\n".join(lines[:15])
        else:
            env["os_release"] = "<absent>"
    except Exception as e:  # noqa: BLE001
        env["os_release_error"] = repr(e)

    env["runner_env"] = {k: v for k, v in os.environ.items() if k.startswith("RUNNER_")}

    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/New_York")
        env["zoneinfo_ny"] = {"ok": True, "sample": datetime.now(tz).isoformat()}
    except Exception:  # noqa: BLE001
        env["zoneinfo_ny"] = {"ok": False, "error": traceback.format_exc()}

    try:
        p = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True, text=True, timeout=120,
        )
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / "pip-freeze.txt").write_text(p.stdout or "", encoding="utf-8")
        env["pip_freeze_lines"] = len([ln for ln in (p.stdout or "").splitlines() if ln.strip()])
    except Exception:  # noqa: BLE001
        env["pip_freeze_error"] = traceback.format_exc()

    return env


# --------------------------------------------------------------------------- #
# 2. Seed synthetic portfolio
# --------------------------------------------------------------------------- #

def seed_portfolio() -> dict:
    path = ROOT / "data" / "portfolios.json"
    if path.exists():
        return {"seeded": False, "reason": "data/portfolios.json already present"}
    # Minimal synthetic fixture — public ticker only. Schema per app/portfolio.py:
    #   {"version": 1, "portfolios": {id: {"id", "name", "holdings": [...]}}}
    #   holding: {"symbol", "shares", "total_cost"}
    state = {
        "version": 1,
        "portfolios": {
            "probe": {
                "id": "probe",
                "name": "Probe",
                "holdings": [
                    {"symbol": "SPY", "shares": 1.0, "total_cost": 100.0},
                ],
            }
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return {"seeded": True, "path": str(path), "tickers": ["SPY"]}


# --------------------------------------------------------------------------- #
# 3. yfinance direct
# --------------------------------------------------------------------------- #

def test_yf_direct() -> dict:
    def work():
        import yfinance as yf
        out = {}
        df = yf.download(["SPY", "^VIX", "GC=F"], period="5d", progress=False)
        out["shape"] = list(df.shape)
        out["columns"] = [str(c) for c in list(df.columns)]
        try:
            closes = df["Close"]
            last = closes.iloc[-1]
            out["last_close"] = {
                str(k): (None if v != v else round(float(v), 4))
                for k, v in last.to_dict().items()
            }
        except Exception:  # noqa: BLE001
            out["last_close_error"] = traceback.format_exc()
        try:
            fi = yf.Ticker("SPY").fast_info
            fields = {}
            for k in ("last_price", "previous_close", "open", "day_high",
                      "day_low", "currency", "exchange"):
                try:
                    fields[k] = getattr(fi, k)
                except Exception:  # noqa: BLE001
                    pass
            out["fast_info"] = fields
        except Exception:  # noqa: BLE001
            out["fast_info_error"] = traceback.format_exc()
        return out

    return run_threaded(work, timeout_s=180)


# --------------------------------------------------------------------------- #
# 4. Regime detector direct
# --------------------------------------------------------------------------- #

def test_regime_direct() -> dict:
    detail = {}
    try:
        detail["requirements_txt"] = REGIME_REQS.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        detail["requirements_txt"] = f"<unreadable: {traceback.format_exc()}>"

    regime_dir = ROOT / "data" / "regime"
    before = set()
    if regime_dir.exists():
        before = {p.name for p in regime_dir.iterdir()}

    cmd = [sys.executable, str(REGIME_SCRIPT), "--output-dir", "data/regime", "--days", "600"]
    first = run_cmd(cmd, timeout_s=360)
    needed_skill_reqs = False
    retry = None

    combined = (first.get("stdout_tail", "") + "\n" + first.get("stderr_tail", ""))
    if first["exit_code"] not in (0, None) and "ModuleNotFoundError" in combined:
        needed_skill_reqs = True
        pip = run_cmd([sys.executable, "-m", "pip", "install", "-r", str(REGIME_REQS)], timeout_s=300)
        retry = run_cmd(cmd, timeout_s=360)

    final = retry or first
    produced = []
    if regime_dir.exists():
        produced = sorted({p.name for p in regime_dir.iterdir()} - before)

    return {
        "completed": final["exit_code"] == 0,
        "duration_s": round(first["duration_s"] + (retry["duration_s"] if retry else 0), 2),
        "detail": {
            "requirements_txt": detail["requirements_txt"],
            "needed_skill_reqs": needed_skill_reqs,
            "first": first,
            "retry": retry,
            "produced_files": produced,
        },
    }


# --------------------------------------------------------------------------- #
# 5. News refresh
# --------------------------------------------------------------------------- #

def test_news_refresh() -> dict:
    before = count_events()
    r = run_cmd(
        [sys.executable, "run.py", "--news-refresh", "--logfile-prefix", "data/logs/news-refresh"],
        timeout_s=600,
    )
    after = count_events()
    r["events_before"] = before
    r["events_after"] = after
    r["events_delta"] = (None if before is None or after is None else after - before)
    return r


# --------------------------------------------------------------------------- #
# 6. Full refresh
# --------------------------------------------------------------------------- #

def test_full_refresh() -> dict:
    r = run_cmd(
        [sys.executable, "run.py", "--refresh", "--logfile-prefix", "data/logs/refresh"],
        timeout_s=1800,
    )
    detail = {}
    dash = ROOT / "data" / "dashboard.json"
    try:
        d = json.loads(dash.read_text(encoding="utf-8"))
        detail["as_of"] = d.get("as_of")
        detail["section_keys"] = sorted(d.keys())
    except Exception:  # noqa: BLE001
        detail["dashboard_error"] = traceback.format_exc()

    hist = ROOT / "data" / "portfolio_history.json"
    if hist.exists():
        try:
            h = json.loads(hist.read_text(encoding="utf-8"))
            snaps = h.get("snapshots", {}) if isinstance(h, dict) else {}
            detail["portfolio_history"] = {"created": True, "entries": len(snaps),
                                           "note": "16:15 ET guard may legitimately skip"}
        except Exception:  # noqa: BLE001
            detail["portfolio_history"] = {"created": True, "entries": None,
                                           "error": traceback.format_exc()}
    else:
        detail["portfolio_history"] = {"created": False, "entries": 0,
                                       "note": "16:15 ET guard may legitimately skip"}

    # Copy verbatim artifacts into evidence.
    detail["dashboard_copied"] = copy_into_evidence(dash, "dashboard.json")
    detail["portfolio_history_copied"] = copy_into_evidence(hist, "portfolio_history.json")

    r["detail"] = detail
    return r


# --------------------------------------------------------------------------- #
# 7. Commit events
# --------------------------------------------------------------------------- #

def test_commit_events() -> dict:
    name = run_cmd(["git", "config", "user.name"], timeout_s=30)
    detail = {
        "identity_present": (name["exit_code"] == 0 and name["stdout_tail"].strip() != ""),
    }
    # Set the spike identity so the commit prerequisite exists in the runner repo.
    run_cmd(["git", "config", "user.name", "gha-spike"], timeout_s=30)
    run_cmd(["git", "config", "user.email", "gha-spike@users.noreply.github.com"], timeout_s=30)
    detail["identity_set"] = True

    r = run_cmd(
        [sys.executable, "run.py", "--commit-events", "--logfile-prefix", "data/logs/events-commit"],
        timeout_s=120,
    )
    log = run_cmd(["git", "log", "-1", "--format=%s"], timeout_s=30)
    detail["git_log_subject"] = log["stdout_tail"].strip()
    r["detail"] = detail
    return r


# --------------------------------------------------------------------------- #
# 8. Lock tests (LAST)
# --------------------------------------------------------------------------- #

def _write_lock(pid: int, mtime_epoch: float | None) -> Path:
    lock = ROOT / "data" / "refresh.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(f"pid={pid} started=2026-01-01 00:00:00\n", encoding="utf-8")
    if mtime_epoch is not None:
        os.utime(lock, (mtime_epoch, mtime_epoch))
    return lock


def test_lock_fresh_crash() -> dict:
    lock = _write_lock(999999, None)  # fresh mtime
    r = run_cmd([sys.executable, "run.py", "--news-refresh"], timeout_s=180)
    r["lock_mtime_age_s"] = round(time.time() - lock.stat().st_mtime, 1) if lock.exists() else None
    # clean up
    try:
        if lock.exists():
            lock.unlink()
    except OSError:
        pass
    r["lock_removed_after"] = not lock.exists()
    return r


def test_lock_stale_heal() -> dict:
    lock = _write_lock(999999, time.time() - 700)  # 700s in the past
    r = run_cmd([sys.executable, "run.py", "--news-refresh"], timeout_s=180)
    r["lock_removed_after"] = not lock.exists()
    try:
        if lock.exists():
            lock.unlink()
    except OSError:
        pass
    return r


# --------------------------------------------------------------------------- #
# 9. Copy logs + regime outputs
# --------------------------------------------------------------------------- #

def copy_logs() -> list[str]:
    copied = []
    logs_dir = ROOT / "data" / "logs"
    patterns = ["refresh-*.log", "news-refresh-*.log", "events-commit-*.log", "summary-*.md"]
    if logs_dir.exists():
        for pat in patterns:
            for f in sorted(logs_dir.glob(pat)):
                if copy_into_evidence(f):
                    copied.append(f.name)
    # Regime output files (data/regime/macro_regime_*).
    regime_dir = ROOT / "data" / "regime"
    if regime_dir.exists():
        for f in sorted(regime_dir.glob("macro_regime_*")):
            if copy_into_evidence(f):
                copied.append(f.name)
    return copied


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def _record(results: dict, name: str, status: str, duration_s, detail, error=None) -> None:
    entry = {"status": status, "duration_s": duration_s, "detail": detail}
    if error:
        entry["error"] = error
    results["tests"][name] = entry


def run_all(results: dict) -> None:
    try:
        results["env"] = collect_env()
    except Exception:  # noqa: BLE001
        results["env"] = {"error": traceback.format_exc()}

    try:
        results["seed"] = seed_portfolio()
    except Exception:  # noqa: BLE001
        results["seed"] = {"error": traceback.format_exc()}

    # --- yf_direct ---------------------------------------------------------
    try:
        r = test_yf_direct()
        if not r["completed"]:
            _record(results, "yf_direct", "timeout", r["duration_s"], {"detail": r.get("detail")})
        elif r.get("error"):
            _record(results, "yf_direct", "error", r["duration_s"], r.get("value"), r["error"])
        else:
            _record(results, "yf_direct", "ok", r["duration_s"], r.get("value"))
    except Exception:  # noqa: BLE001
        _record(results, "yf_direct", "error", None, None, traceback.format_exc())

    # --- regime_direct -----------------------------------------------------
    try:
        r = test_regime_direct()
        status = "ok" if r["completed"] else "error"
        err = None
        if not r["completed"]:
            f = r["detail"].get("retry") or r["detail"].get("first") or {}
            err = f.get("stderr_tail") or f.get("stdout_tail")
        _record(results, "regime_direct", status, r["duration_s"], r["detail"], err)
    except Exception:  # noqa: BLE001
        _record(results, "regime_direct", "error", None, None, traceback.format_exc())

    # --- news_refresh ------------------------------------------------------
    try:
        r = test_news_refresh()
        status = "ok" if r["exit_code"] == 0 else ("timeout" if r["timed_out"] else "error")
        _record(results, "news_refresh", status, r["duration_s"], r, r.get("stderr_tail"))
    except Exception:  # noqa: BLE001
        _record(results, "news_refresh", "error", None, None, traceback.format_exc())

    # --- full_refresh ------------------------------------------------------
    try:
        r = test_full_refresh()
        status = "ok" if r["exit_code"] == 0 else ("timeout" if r["timed_out"] else "error")
        d = r["detail"]
        detail = {
            "exit_code": r["exit_code"],
            "as_of": d.get("as_of"),
            "section_keys": d.get("section_keys"),
            "portfolio_history": d.get("portfolio_history"),
            "stderr_tail": r.get("stderr_tail", ""),
        }
        _record(results, "full_refresh", status, r["duration_s"], detail,
                None if status == "ok" else (r.get("stderr_tail") or d.get("dashboard_error")))
    except Exception:  # noqa: BLE001
        _record(results, "full_refresh", "error", None, None, traceback.format_exc())

    # --- commit_events -----------------------------------------------------
    try:
        r = test_commit_events()
        status = "ok" if r["exit_code"] == 0 else "error"
        detail = dict(r["detail"])
        detail["exit_code"] = r["exit_code"]
        detail["stderr_tail"] = r.get("stderr_tail", "")
        _record(results, "commit_events", status, r["duration_s"], detail,
                None if status == "ok" else r.get("stderr_tail"))
    except Exception:  # noqa: BLE001
        _record(results, "commit_events", "error", None, None, traceback.format_exc())

    # --- lock tests (LAST) -------------------------------------------------
    for name, fn in (("lock_fresh_crash", test_lock_fresh_crash),
                     ("lock_stale_heal", test_lock_stale_heal)):
        try:
            r = fn()
            status = "ok" if r["exit_code"] == 0 else ("timeout" if r["timed_out"] else "error")
            _record(results, name, status, r["duration_s"], r, r.get("stderr_tail"))
        except Exception:  # noqa: BLE001
            _record(results, name, "error", None, None, traceback.format_exc())

    # --- evidence copies ---------------------------------------------------
    try:
        results["copied_files"] = copy_logs()
    except Exception:  # noqa: BLE001
        results["copied_files"] = [f"<copy failed: {traceback.format_exc()}>"]

    core_ok = all(
        results["tests"].get(t, {}).get("status") == "ok" for t in CORE_TESTS
    )
    results["summary"] = {"core_ok": core_ok,
                          "core_tests": CORE_TESTS}


def main() -> int:
    os.chdir(ROOT)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = {"env": {}, "tests": {}, "summary": {"core_ok": False}}
    try:
        run_all(results)
    except Exception:  # noqa: BLE001 - crash still writes results.json
        results.setdefault("tests", {})["_fatal"] = {
            "status": "error", "error": traceback.format_exc()
        }
        results["summary"] = {"core_ok": False, "core_tests": CORE_TESTS}

    # Always persist results before exiting.
    try:
        (EVIDENCE / "results.json").write_text(
            json.dumps(results, indent=2, default=str), encoding="utf-8"
        )
    except Exception:  # noqa: BLE001
        pass

    core_ok = bool(results.get("summary", {}).get("core_ok"))
    print(f"gha_probe done: core_ok={core_ok}")
    return 0 if core_ok else 1


if __name__ == "__main__":
    sys.exit(main())
