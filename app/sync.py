"""Cloud capture + local fold for the off-PC data transport (phase 2).

Write scopes are **disjoint**, so the two halves can never conflict:

* **Cloud export** (CI, private data repo) writes only ``captures/**``:

  ==========================================  =====================================
  ``captures/history/<YYYY-MM-DD>.json``      exact snapshot entry (incl. ``backfilled``)
  ``captures/events/<runid>.json``            ``{"runid","captured_at","events":[...]}`` — NEW only
  ``captures/_status/<runid>.json``           sanitized run status (no holdings/values)
  ==========================================  =====================================

* **Local fold** (this machine) writes ``state/**`` in the data repo and the
  local ``data/`` store: it validates *every* capture first (all-or-nothing —
  any invalid file applies nothing), then applies history write-if-absent
  (``portfolio_history.merge_snapshots``) and events via ``store.upsert_events``
  (link dedupe, ``user_edited`` respected). Re-running the fold is a no-op.
  ``state/<file>.json`` holds exact copies of the local data files, published
  by ``copy_state_to_repo`` (called from ``run.py --sync``).

Every path is a parameter, so tests and rehearsals target scratch directories.
Nothing here reads or writes the real data dir unless it is explicitly pointed
at it. Output dicts are sanitized: counts, dates, ok flags and file names only.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import config, portfolio_history, store

# Repo layout (relative to the private data-repo checkout).
CAPTURES_DIRNAME = "captures"
STATE_DIRNAME = "state"
HISTORY_SUBDIR = "history"
EVENTS_SUBDIR = "events"
STATUS_SUBDIR = "_status"

# Local data files mirrored into ``state/``.
STATE_FILES = (
    "portfolios.json",
    "portfolio_history.json",
    "events.json",
    "bottleneck_topics.json",
)

_MISSING = object()


class SyncValidationError(RuntimeError):
    """A capture/state file failed validation. Nothing is applied."""

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__(
            "capture validation failed (nothing applied):\n  - " + "\n  - ".join(self.problems)
        )


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #

def _parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _events_list(path: Path) -> list[dict[str, Any]]:
    data = store.load_json(Path(path), {})
    if isinstance(data, dict) and isinstance(data.get("events"), list):
        return [e for e in data["events"] if isinstance(e, dict)]
    return []


def history_capture_entries(data_dir: Path) -> dict[str, dict[str, Any]]:
    """``{close_date: entry}`` from the local history store (``{}`` if absent)."""
    hist = store.load_json(Path(data_dir) / "portfolio_history.json", {})
    if not isinstance(hist, dict):
        return {}
    snaps = hist.get("snapshots")
    if not isinstance(snaps, dict):
        return {}
    return {k: v for k, v in snaps.items() if isinstance(k, str) and isinstance(v, dict)}


def new_events_since(
    current: list[dict[str, Any]], prior_links: set[str]
) -> list[dict[str, Any]]:
    """Events whose ``link`` is not in ``prior_links`` (the pre-refresh state)."""
    return [e for e in current if str(e.get("link") or "") not in prior_links]


# --------------------------------------------------------------------------- #
# validators (pure)
# --------------------------------------------------------------------------- #

def validate_history_entry(entry: object) -> list[str]:
    if not isinstance(entry, dict):
        return ["not a JSON object"]
    problems: list[str] = []
    if not isinstance(entry.get("close_date"), str) or not entry["close_date"]:
        problems.append("close_date missing/invalid")
    if not isinstance(entry.get("recorded_at"), str):
        problems.append("recorded_at missing")
    if not isinstance(entry.get("portfolios"), dict):
        problems.append("portfolios missing/not an object")
    return problems


def validate_events_doc(doc: object) -> list[str]:
    if not isinstance(doc, dict):
        return ["not a JSON object"]
    problems: list[str] = []
    if not isinstance(doc.get("runid"), str) or not doc["runid"]:
        problems.append("runid missing")
    if not isinstance(doc.get("captured_at"), str):
        problems.append("captured_at missing")
    events = doc.get("events")
    if not isinstance(events, list):
        problems.append("events missing/not a list")
    else:
        for i, e in enumerate(events):
            if not isinstance(e, dict) or not isinstance(e.get("link"), str) or not e["link"]:
                problems.append(f"events[{i}] missing link")
                break
    return problems


_STATUS_REQUIRED = (
    "runid", "mode", "started_at", "finished_at", "ok", "steps",
    "new_history_dates", "new_events", "latest_close_date",
)


def validate_status(doc: object) -> list[str]:
    if not isinstance(doc, dict):
        return ["not a JSON object"]
    problems = [f"{key} missing" for key in _STATUS_REQUIRED if key not in doc]
    if not isinstance(doc.get("ok"), bool):
        problems.append("ok not a boolean")
    if not isinstance(doc.get("steps"), list):
        problems.append("steps not a list")
    else:
        for i, s in enumerate(doc["steps"]):
            if not isinstance(s, dict) or not isinstance(s.get("name"), str) or not isinstance(s.get("ok"), bool):
                problems.append(f"steps[{i}] malformed")
                break
    if not isinstance(doc.get("new_history_dates"), list):
        problems.append("new_history_dates not a list")
    if not isinstance(doc.get("new_events"), int):
        problems.append("new_events not an int")
    return problems


def validate_state_file(name: str, data: object) -> list[str]:
    if not isinstance(data, dict):
        return ["not a JSON object"]
    if name == "portfolios.json":
        if data.get("version") != 1:
            return ["version != 1"]
        if not isinstance(data.get("portfolios"), dict):
            return ["portfolios missing/not an object"]
    elif name == "portfolio_history.json":
        if data.get("version") != 1:
            return ["version != 1"]
        if not isinstance(data.get("snapshots"), dict):
            return ["snapshots missing/not an object"]
    elif name == "events.json":
        if not isinstance(data.get("events"), list):
            return ["events missing/not a list"]
    # bottleneck_topics.json: loose shape (a dict is enough).
    return []


def _iter_capture_files(captures: Path) -> Iterator[Path]:
    for sub in (HISTORY_SUBDIR, EVENTS_SUBDIR, STATUS_SUBDIR):
        d = captures / sub
        if d.is_dir():
            yield from sorted(d.glob("*.json"))


def validate_captures(repo_dir: Path) -> dict[str, Any]:
    """Parse + shape-check every capture file under ``<repo>/captures``."""
    captures = Path(repo_dir) / CAPTURES_DIRNAME
    problems: list[str] = []
    count = 0
    for path in _iter_capture_files(captures):
        rel = path.relative_to(captures).as_posix()
        count += 1
        data = store.load_json(path, _MISSING)
        if data is _MISSING:
            problems.append(f"{rel}: unreadable JSON")
            continue
        if rel.startswith(f"{HISTORY_SUBDIR}/"):
            file_problems = validate_history_entry(data)
        elif rel.startswith(f"{EVENTS_SUBDIR}/"):
            file_problems = validate_events_doc(data)
        elif rel.startswith(f"{STATUS_SUBDIR}/"):
            file_problems = validate_status(data)
        else:
            file_problems = ["unknown capture path"]
        problems += [f"{rel}: {p}" for p in file_problems]
    return {"ok": not problems, "count": count, "problems": problems}


def validate_state_dir(repo_dir: Path) -> list[str]:
    state_dir = Path(repo_dir) / STATE_DIRNAME
    problems: list[str] = []
    if not state_dir.is_dir():
        return problems
    for path in sorted(state_dir.glob("*.json")):
        if path.name not in STATE_FILES:
            continue
        data = store.load_json(path, _MISSING)
        if data is _MISSING:
            problems.append(f"{STATE_DIRNAME}/{path.name}: unreadable JSON")
            continue
        problems += [
            f"{STATE_DIRNAME}/{path.name}: {p}" for p in validate_state_file(path.name, data)
        ]
    return problems


# --------------------------------------------------------------------------- #
# cloud export
# --------------------------------------------------------------------------- #

def export_captures(
    *,
    data_dir: Path,
    repo_dir: Path,
    runid: str,
    mode: str,
    started_at: str,
    finished_at: str,
    steps: list[dict[str, Any]] | None = None,
    events_before_path: Path | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Write captures + state into the data-repo checkout. Returns a sanitized summary.

    History captures are write-once (an existing capture file is skipped, never
    overwritten). Every written file is validated after the fact; any problem is
    reported (and makes the summary ``ok`` false) without raising, so the caller
    can surface it and still leave the evidence on disk.
    """
    data_dir = Path(data_dir)
    repo_dir = Path(repo_dir)
    captures = repo_dir / CAPTURES_DIRNAME
    written: list[str] = []
    skipped: list[str] = []
    problems: list[str] = []

    # --- history: one file per stored date, skip existing captures ---
    entries = history_capture_entries(data_dir)
    new_dates: list[str] = []
    for close_date in sorted(entries):
        rel = f"{HISTORY_SUBDIR}/{close_date}.json"
        target = captures / rel
        if target.exists():
            skipped.append(rel)
            continue
        entry = entries[close_date]
        entry_problems = validate_history_entry(entry)
        if entry_problems:
            problems += [f"{rel}: {p}" for p in entry_problems]
            continue
        store.save_json(target, entry)
        written.append(rel)
        new_dates.append(close_date)

    # --- events: NEW only (diff by link vs the pre-refresh state) ---
    current_events = _events_list(data_dir / "events.json")
    prior_links: set[str] = set()
    if events_before_path is not None and Path(events_before_path).exists():
        prior_links = {str(e.get("link") or "") for e in _events_list(Path(events_before_path))}
    new_events = new_events_since(current_events, prior_links)
    events_doc = {"runid": runid, "captured_at": finished_at, "events": new_events}
    ev_problems = validate_events_doc(events_doc)
    if ev_problems:
        problems += [f"{EVENTS_SUBDIR}/{runid}.json: {p}" for p in ev_problems]
    else:
        store.save_json(captures / EVENTS_SUBDIR / f"{runid}.json", events_doc)
        written.append(f"{EVENTS_SUBDIR}/{runid}.json")

    # --- status (sanitized: no holdings/values) ---
    latest_close = max(entries) if entries else None
    step_list = list(steps or [])
    ok = error is None and all(bool(s.get("ok")) for s in step_list)
    status: dict[str, Any] = {
        "runid": runid,
        "mode": mode,
        "started_at": started_at,
        "finished_at": finished_at,
        "ok": ok,
        "steps": step_list,
        "new_history_dates": new_dates,
        "new_events": len(new_events),
        "latest_close_date": latest_close,
    }
    if error:
        status["error"] = error
    st_problems = validate_status(status)
    if st_problems:
        problems += [f"{STATUS_SUBDIR}/{runid}.json: {p}" for p in st_problems]
    else:
        store.save_json(captures / STATUS_SUBDIR / f"{runid}.json", status)
        written.append(f"{STATUS_SUBDIR}/{runid}.json")

    # --- post-write verification: re-parse + shape-check every capture ---
    problems += validate_captures(repo_dir)["problems"]

    return {
        "written": written,
        "skipped": skipped,
        "new_history_dates": new_dates,
        "new_events": len(new_events),
        "latest_close_date": latest_close,
        "ok": ok and not problems,
        "problems": problems,
    }


# --------------------------------------------------------------------------- #
# local fold
# --------------------------------------------------------------------------- #

@contextmanager
def _events_store_at(data_dir: Path) -> Iterator[None]:
    """Temporarily point ``app.store`` at ``<data_dir>/events.json``.

    ``store.upsert_events`` is the canonical link-dedupe + ``user_edited``-aware
    merge, but it resolves its file from ``config.EVENTS_PATH``. Redirecting the
    config for the duration lets the fold reuse it against a scratch data dir
    without duplicating the merge rules. Restored on exit, even on error.
    """
    prev_events = config.EVENTS_PATH
    prev_data = config.DATA_DIR
    prev_ready = store._READY
    config.EVENTS_PATH = Path(data_dir) / "events.json"
    config.DATA_DIR = Path(data_dir)
    store._READY = False
    try:
        yield
    finally:
        config.EVENTS_PATH = prev_events
        config.DATA_DIR = prev_data
        store._READY = prev_ready


def _latest_status(statuses: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not statuses:
        return None
    return max(statuses, key=lambda s: str(s.get("finished_at") or ""))


def status_age_hours(status: dict[str, Any] | None, now: datetime | None = None) -> float | None:
    if not isinstance(status, dict):
        return None
    ts = _parse_ts(status.get("finished_at"))
    if ts is None:
        return None
    now = now or datetime.now(timezone.utc)
    return (now - ts).total_seconds() / 3600.0


def _is_status_stale(status: dict[str, Any] | None, max_age_hours: float) -> bool:
    if not isinstance(status, dict):
        return True
    if not status.get("ok"):
        return True
    age = status_age_hours(status)
    if age is None:
        return True
    return age > max_age_hours


def fold_captures(
    *, repo_dir: Path, data_dir: Path, max_status_age_hours: float = 48.0
) -> dict[str, Any]:
    """Validate every capture, then apply history + events into the local store.

    All-or-nothing: any invalid capture raises :class:`SyncValidationError` and
    nothing is applied. Idempotent: history is write-if-absent and events are
    filtered by link before upsert, so a re-fold writes nothing new.
    """
    repo_dir = Path(repo_dir)
    data_dir = Path(data_dir)
    captures = repo_dir / CAPTURES_DIRNAME

    history_entries: dict[str, dict[str, Any]] = {}
    events_incoming: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    problems: list[str] = []

    hist_dir = captures / HISTORY_SUBDIR
    if hist_dir.is_dir():
        for path in sorted(hist_dir.glob("*.json")):
            rel = f"{HISTORY_SUBDIR}/{path.name}"
            data = store.load_json(path, _MISSING)
            if data is _MISSING:
                problems.append(f"{rel}: unreadable JSON")
                continue
            file_problems = validate_history_entry(data)
            if file_problems:
                problems += [f"{rel}: {p}" for p in file_problems]
                continue
            key = path.stem
            if str(data.get("close_date") or "") != key:
                problems.append(f"{rel}: close_date mismatch ({data.get('close_date')!r} != {key!r})")
                continue
            history_entries[key] = data

    ev_dir = captures / EVENTS_SUBDIR
    if ev_dir.is_dir():
        for path in sorted(ev_dir.glob("*.json")):
            rel = f"{EVENTS_SUBDIR}/{path.name}"
            data = store.load_json(path, _MISSING)
            if data is _MISSING:
                problems.append(f"{rel}: unreadable JSON")
                continue
            file_problems = validate_events_doc(data)
            if file_problems:
                problems += [f"{rel}: {p}" for p in file_problems]
                continue
            events_incoming.extend(e for e in data["events"] if isinstance(e, dict))

    st_dir = captures / STATUS_SUBDIR
    if st_dir.is_dir():
        for path in sorted(st_dir.glob("*.json")):
            rel = f"{STATUS_SUBDIR}/{path.name}"
            data = store.load_json(path, _MISSING)
            if data is _MISSING:
                problems.append(f"{rel}: unreadable JSON")
                continue
            file_problems = validate_status(data)
            if file_problems:
                problems += [f"{rel}: {p}" for p in file_problems]
                continue
            statuses.append(data)

    if problems:
        raise SyncValidationError(problems)

    # Apply history write-if-absent.
    hist_result = portfolio_history.merge_snapshots(
        history_entries, path=data_dir / "portfolio_history.json"
    )

    # Apply events: pre-filter by link so a re-fold is a true no-op, then reuse
    # the canonical upsert (which also does cross-source dedupe + user_edited).
    existing_links = {str(e.get("link") or "") for e in _events_list(data_dir / "events.json")}
    fresh = [e for e in events_incoming if str(e.get("link") or "") not in existing_links]
    inserted = 0
    if fresh:
        with _events_store_at(data_dir):
            inserted = store.upsert_events(fresh)

    latest = _latest_status(statuses)
    return {
        "history_added": hist_result["added"],
        "history_existing": hist_result["existing"],
        "events_considered": len(events_incoming),
        "events_inserted": inserted,
        "latest_status": latest,
        "status_age_hours": status_age_hours(latest),
        "status_stale": _is_status_stale(latest, max_status_age_hours),
    }


# --------------------------------------------------------------------------- #
# state mirroring
# --------------------------------------------------------------------------- #

def copy_state_to_repo(data_dir: Path, repo_dir: Path) -> list[str]:
    """Copy the four local state files into ``<repo>/state/`` (atomic)."""
    written: list[str] = []
    for name in STATE_FILES:
        src = Path(data_dir) / name
        if not src.exists():
            continue
        data = store.load_json(src, _MISSING)
        if data is _MISSING:
            continue
        store.save_json(Path(repo_dir) / STATE_DIRNAME / name, data)
        written.append(f"{STATE_DIRNAME}/{name}")
    return written


def copy_state_from_repo(repo_dir: Path, data_dir: Path) -> dict[str, Any]:
    """Validate ``<repo>/state/*`` then copy into the data dir (all-or-nothing)."""
    state_dir = Path(repo_dir) / STATE_DIRNAME
    loaded: dict[str, Any] = {}
    problems: list[str] = []
    if state_dir.is_dir():
        for path in sorted(state_dir.glob("*.json")):
            if path.name not in STATE_FILES:
                continue
            data = store.load_json(path, _MISSING)
            if data is _MISSING:
                problems.append(f"{STATE_DIRNAME}/{path.name}: unreadable JSON")
                continue
            file_problems = validate_state_file(path.name, data)
            if file_problems:
                problems += [f"{STATE_DIRNAME}/{path.name}: {p}" for p in file_problems]
                continue
            loaded[path.name] = data
    if problems:
        raise SyncValidationError(problems)
    for name, data in loaded.items():
        store.save_json(Path(data_dir) / name, data)
    return {"copied": sorted(f"{STATE_DIRNAME}/{n}" for n in loaded)}
