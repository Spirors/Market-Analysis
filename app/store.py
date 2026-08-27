"""Persistence: Git-synced JSON for market events, SQLite for analysis log.

Events live in a single pretty-printed file (``data/events.json``, sorted by
``published`` DESC) so the news timeline can sync across devices via Git.
Cross-source dedupe and the suppressed-sources blocklist are unchanged.

Legacy ``data/news.db`` (events + analysis_runs in one SQLite file) is
auto-migrated on first load: events go to ``events.json``, analysis_runs
go to ``ANALYSIS_DB_PATH`` (a new SQLite file), and the old DB is renamed
to ``news.db.migrated`` so the data is never destroyed.
"""

import difflib
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (t or "").lower()).strip()


# Dedupe thresholds. Conservative on purpose: a wrongly-merged event hides real
# information, so prefer missing a duplicate over merging two distinct stories.
DEDUP_JACCARD = 0.6
DEDUP_RATIO = 0.85
DEDUP_WINDOW_DAYS = 2

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "for", "to", "of", "in", "on", "at",
    "with", "by", "as", "is", "are", "was", "were", "be", "been", "it", "its",
    "this", "that", "these", "those", "from", "after", "before", "into", "over",
    "under", "says", "said", "will", "would", "could", "should", "can", "may",
    "not", "no", "new", "up", "down", "his", "her", "their", "our", "your",
    "amid", "just", "about", "than", "then", "vs", "via", "report", "news",
    "update", "live", "market", "markets", "stock", "stocks", "shares", "week",
    "today", "day", "daily",
}


def _tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (title or "").lower())
            if w not in STOPWORDS and len(w) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def _days_apart(a: str | None, b: str | None) -> int:
    try:
        da = datetime.fromisoformat((a or "")[:19])
        db = datetime.fromisoformat((b or "")[:19])
        return abs((da - db).days)
    except Exception:
        # Undated items must never look "in window" for dedupe; a large
        # sentinel keeps them out of every date-window comparison.
        return 9999


def _similar(title_a: str, title_b: str) -> bool:
    """True when two titles likely describe the same story."""
    jac = _jaccard(_tokens(title_a), _tokens(title_b))
    if jac >= DEDUP_JACCARD:
        return True
    return difflib.SequenceMatcher(None, _norm_title(title_a), _norm_title(title_b)).ratio() >= DEDUP_RATIO


# ---- AI auto-tag -------------------------------------------------------------

# Reused by the AI capex-cycle gauge (app/ai_sentiment.py): events whose
# title+summary match any of these are automatically tagged "ai" on insert.
_AI_TAG_KEYWORDS: list[str] = [
    "ai", "artificial intelligence", "nvidia", "amd", "semiconductor", "semiconductors",
    "chip", "chips", "datacenter", "data center", "hyperscaler",
    "tsmc", "memory", "hbm", "dram", "photonics", "optic", "optics",
    "foundry", "accelerator", "gpu", "compute",
]
AI_TAG = "ai"


def _is_ai_text(text: str) -> bool:
    return any(re.search(rf"\b{re.escape(k)}\b", text or "") for k in _AI_TAG_KEYWORDS)


def _normalize_user_tags(raw: Any) -> list[str]:
    """Sanitize a user-supplied tag list: lowercase, deduped, sorted, length-capped.

    Empty strings and oversized labels are dropped silently — the front-end
    constrains input, but never trust client data."""
    out: list[str] = []
    seen: set[str] = set()
    for item in raw or []:
        if not isinstance(item, str):
            continue
        t = item.strip().lower()
        if not t or len(t) > 32 or not re.match(r"^[a-z0-9][a-z0-9 _\-]*$", t):
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


# ---- JSON events store -------------------------------------------------------

# Fields every event row carries. Used both for forward-compat defaults when
# reading older files and for trimming unknown keys on write.
_EVENT_FIELDS: tuple[str, ...] = (
    "link", "source", "title", "published", "date_label", "summary",
    "category", "actor", "direction", "region", "impact",
    "tags", "first_seen", "updated_at",
)


def _empty_state() -> dict[str, Any]:
    return {"version": 1, "events": [], "suppressed_sources": []}


def _load_state() -> dict[str, Any]:
    """Load the events JSON, returning an empty state on missing/empty file.

    A blank file (size 0) is treated as empty rather than failing — useful
    after a botched write that left the rename half-done."""
    if not config.EVENTS_PATH.exists():
        return _empty_state()
    try:
        raw = config.EVENTS_PATH.read_text(encoding="utf-8")
    except OSError:
        return _empty_state()
    if not raw.strip():
        return _empty_state()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _empty_state()
    if not isinstance(data, dict):
        return _empty_state()
    events = data.get("events")
    suppressed = data.get("suppressed_sources")
    return {
        "version": int(data.get("version") or 1),
        "events": events if isinstance(events, list) else [],
        "suppressed_sources": [s for s in (suppressed or []) if isinstance(s, str) and s],
    }


def _save_state(state: dict[str, Any]) -> None:
    """Atomic write: serialize, write to ``events.json.tmp``, then rename.

    Ensures the GitHub-synced file is never partially written — readers see
    either the old full file or the new full file, never torn bytes."""
    config.ensure_dirs()
    payload = {
        "version": state.get("version") or 1,
        "events": state.get("events") or [],
        "suppressed_sources": state.get("suppressed_sources") or [],
    }
    tmp = config.EVENTS_PATH.with_name(f"{config.EVENTS_PATH.name}.tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        os.replace(tmp, config.EVENTS_PATH)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _sort_state(state: dict[str, Any]) -> None:
    """Keep events sorted newest-first so Git diffs stay minimal on rewrite.

    Stable secondary sort on ``link`` so equal timestamps don't churn order."""
    state["events"].sort(
        key=lambda e: (
            str(e.get("published") or ""),
            str(e.get("link") or ""),
        ),
        reverse=True,
    )


# Set once the storage has been verified/migrated in this process.
_READY = False


def _migrate_legacy_db() -> None:
    """One-time: copy events + analysis_runs out of the old ``news.db``.

    Events go to ``events.json``; analysis_runs go to ``analysis.db``. The
    legacy file is renamed to ``news.db.migrated`` (never deleted) so a
    user can recover the original SQLite if anything looks off.

    Both reads use a single shared connection — opening and closing the
    legacy DB multiple times on Windows holds a transient lock that
    blocks the final rename (``WinError 32``). The final move uses
    ``os.replace`` rather than ``Path.rename`` because the latter uses
    ``os.rename`` which fails against a recently-released locked handle
    on Windows Python 3.14; ``os.replace`` (MoveFileEx with
    MOVEFILE_REPLACE_EXISTING) succeeds in the same situation."""
    legacy = config.DATA_DIR / "news.db"
    if not legacy.exists():
        return

    state = _load_state()
    need_events = not state["events"]
    need_runs = not config.ANALYSIS_DB_PATH.exists()
    migrated_path = config.DATA_DIR / "news.db.migrated"
    if not need_events and not need_runs:
        # Already migrated; just rename for the idempotency guard.
        try:
            os.replace(str(legacy), str(migrated_path))
        except OSError:
            pass
        return

    try:
        src = sqlite3.connect(str(legacy))
    except sqlite3.DatabaseError:
        return
    try:
        src.row_factory = sqlite3.Row

        if need_events:
            try:
                rows = src.execute(
                    "SELECT link, source, title, published, date_label, summary, "
                    "category, actor, direction, region, impact, first_seen, "
                    "updated_at FROM events"
                ).fetchall()
            except sqlite3.DatabaseError:
                rows = []
            migrated: list[dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                text = f"{d.get('title') or ''} {d.get('summary') or ''}".lower()
                d["tags"] = [AI_TAG] if _is_ai_text(text) else []
                for f in _EVENT_FIELDS:
                    d.setdefault(f, None)
                migrated.append(d)
            state["events"] = migrated
            _sort_state(state)
            _save_state(state)

        if need_runs:
            try:
                rows = src.execute(
                    "SELECT ts, stance, confidence, payload_json FROM analysis_runs ORDER BY id"
                ).fetchall()
            except sqlite3.DatabaseError:
                rows = []
            try:
                dst = sqlite3.connect(str(config.ANALYSIS_DB_PATH))
                try:
                    dst.execute(
                        """
                        CREATE TABLE IF NOT EXISTS analysis_runs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            ts TEXT NOT NULL,
                            stance TEXT NOT NULL,
                            confidence REAL NOT NULL,
                            payload_json TEXT NOT NULL
                        )
                        """
                    )
                    for r in rows:
                        dst.execute(
                            "INSERT INTO analysis_runs (ts, stance, confidence, payload_json) VALUES (?, ?, ?, ?)",
                            (r["ts"], r["stance"], r["confidence"], r["payload_json"]),
                        )
                    dst.commit()
                finally:
                    dst.close()
            except sqlite3.DatabaseError:
                pass
    finally:
        src.close()

    # Rename the legacy file so we don't migrate twice and the user has a
    # rollback path if anything went wrong.
    try:
        os.replace(str(legacy), str(migrated_path))
    except OSError:
        pass


def _ensure_ready() -> None:
    global _READY
    if _READY:
        return
    config.ensure_dirs()
    _migrate_legacy_db()
    _READY = True


# ---- Event operations --------------------------------------------------------

def upsert_events(items: list[dict[str, Any]]) -> int:
    """Insert significant events, dedupe by link + cross-source similarity.

    Returns the number of newly inserted rows (updates are not counted).
    Applies the AI auto-tag on insert and on update so legacy RSS rows that
    get refreshed pick it up too."""
    _ensure_ready()
    inserted = 0
    now = _now_iso()
    with _lock:
        state = _load_state()
        events = state["events"]
        # Build (link, title, impact, published) index for dedupe comparisons.
        index: list[tuple[str, str, str, str]] = [
            (e.get("link", ""), e.get("title", ""), e.get("impact", ""), e.get("published", ""))
            for e in events
        ]

        for it in items:
            link = it["link"]
            title = it.get("title", "")
            published = it.get("published", "")
            impact = it.get("impact", "High")
            text = f"{title} {it.get('summary') or ''}".lower()
            ai_tagged = _is_ai_text(text)
            # Inherit existing user-managed tags if the row already exists.
            existing_row = next((e for e in events if e.get("link") == link), None)

            # Cross-source dedupe: merge with an existing row (different link)
            # that describes the same story within a short date window.
            dup_link = None
            for ex_link, ex_title, ex_impact, ex_pub in index:
                if not ex_link or ex_link == link:
                    continue
                if _days_apart(published, ex_pub) > DEDUP_WINDOW_DAYS:
                    continue
                if _similar(title, ex_title):
                    dup_link = ex_link
                    impact = "Critical" if "Critical" in (impact, ex_impact) else "High"
                    break

            target_row = None
            if dup_link:
                target_row = next((e for e in events if e.get("link") == dup_link), None)
            elif existing_row:
                target_row = existing_row

            if target_row is not None:
                # Update in place; preserve user-added tags except "ai"
                # (which is always recomputed from current text).
                preserved_tags = [t for t in (target_row.get("tags") or []) if t != AI_TAG]
                if ai_tagged:
                    preserved_tags.append(AI_TAG)
                target_row.update({
                    "source": it.get("source", ""),
                    "title": title,
                    "summary": it.get("summary", ""),
                    "date_label": it.get("date_label"),
                    "category": it.get("category"),
                    "actor": it.get("actor"),
                    "direction": it.get("direction"),
                    "region": it.get("region"),
                    "impact": impact,
                    "tags": sorted(set(preserved_tags)),
                    "updated_at": now,
                })
            else:
                tags = [AI_TAG] if ai_tagged else []
                new_row = {
                    "link": link,
                    "source": it.get("source", ""),
                    "title": title,
                    "published": published,
                    "date_label": it.get("date_label"),
                    "summary": it.get("summary", ""),
                    "category": it.get("category"),
                    "actor": it.get("actor"),
                    "direction": it.get("direction"),
                    "region": it.get("region"),
                    "impact": impact,
                    "tags": tags,
                    "first_seen": now,
                    "updated_at": now,
                }
                events.append(new_row)
                index.append((link, title, impact, published))
                inserted += 1

        _sort_state(state)
        _save_state(state)
    return inserted


def delete_event(link: str) -> None:
    _ensure_ready()
    with _lock:
        state = _load_state()
        before = len(state["events"])
        state["events"] = [e for e in state["events"] if e.get("link") != link]
        if len(state["events"]) != before:
            _save_state(state)


def delete_events_by_source(source: str) -> None:
    _ensure_ready()
    with _lock:
        state = _load_state()
        before = len(state["events"])
        state["events"] = [e for e in state["events"] if e.get("source") != source]
        if len(state["events"]) != before:
            _save_state(state)


# ---- Tag management ----------------------------------------------------------

def update_event_tags(link: str, add: list[str] | None = None, remove: list[str] | None = None) -> dict[str, Any] | None:
    """Add and/or remove user tags from one event. Returns the updated event
    (with merged display ``tags``) or ``None`` if the link was not found.

    "ai" cannot be removed manually — it's the auto-tag; it stays as long as
    the title/summary still matches the AI keywords, and re-appears after a
    refresh if the user clears it. All other user tags are mutable."""
    _ensure_ready()
    add_clean = _normalize_user_tags(add)
    remove_clean = set(_normalize_user_tags(remove))
    # Strip "ai" out of removal — it's the auto-tag.
    remove_clean.discard(AI_TAG)

    with _lock:
        state = _load_state()
        target = next((e for e in state["events"] if e.get("link") == link), None)
        if target is None:
            return None

        current = list(target.get("tags") or [])
        # Apply removals first so an "add" can re-add a tag in the same call.
        current = [t for t in current if t not in remove_clean]
        for t in add_clean:
            if t not in current:
                current.append(t)
        target["tags"] = sorted(set(current))
        target["updated_at"] = _now_iso()
        _save_state(state)
        return _build_event_payload(target)


def _build_event_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Shape one stored row for the API response: fixed dimensions preserved,
    ``tags`` is the union of fixed-dimension tags and user tags so the
    front-end filter chips see both."""
    payload = {f: row.get(f) for f in _EVENT_FIELDS}
    fixed = [row.get("category"), row.get("actor"), row.get("direction"), row.get("region")]
    user_tags = list(row.get("tags") or [])
    payload["tags"] = sorted({t for t in (*fixed, *user_tags) if t})
    return payload


# ---- Suppressed sources ------------------------------------------------------

SUPPRESSED_PATH = config.DATA_DIR / "suppressed_sources.json"


def get_suppressed_sources() -> list[str]:
    state = _load_state()
    return list(state.get("suppressed_sources") or [])


def suppress_source(source: str) -> list[str]:
    """Persist a source to the blocklist and purge its existing events."""
    with _lock:
        state = _load_state()
        current = set(state.get("suppressed_sources") or [])
        current.add(source)
        state["suppressed_sources"] = sorted(current)
        state["events"] = [e for e in state["events"] if e.get("source") != source]
        _save_state(state)
        return list(state["suppressed_sources"])


# ---- Listing -----------------------------------------------------------------

def list_events(limit: int = 500, since_iso: str | None = None, ai_only: bool = False) -> list[dict[str, Any]]:
    """Return events sorted newest-first.

    ``since_iso``: optional ISO timestamp; rows older than this are excluded.
    Used by the AI capex-cycle gauge to look back ~30 days instead of just
    the latest 500.

    ``ai_only``: when True, only events tagged "ai" are returned. Used by
    the gauge so non-AI news doesn't pollute the AI sentiment computation."""
    _ensure_ready()
    state = _load_state()
    events = state["events"]
    if since_iso:
        events = [e for e in events if (e.get("published") or "") >= since_iso]
    if ai_only:
        events = [e for e in events if AI_TAG in (e.get("tags") or [])]
    events = events[: max(0, int(limit))]
    return [_build_event_payload(e) for e in events]


# ---- analysis_runs (still SQLite) -------------------------------------------

def _init_analysis_db() -> None:
    config.ensure_dirs()
    with sqlite3.connect(str(config.ANALYSIS_DB_PATH)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                stance TEXT NOT NULL,
                confidence REAL NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.commit()


_ANALYSIS_READY = False


def _ensure_analysis_db() -> None:
    global _ANALYSIS_READY
    if _ANALYSIS_READY:
        return
    _init_analysis_db()
    _ANALYSIS_READY = True


def log_analysis_run(analysis: dict[str, Any]) -> None:
    """Persist one AI-analysis synthesis run (full payload JSON + key columns)."""
    _ensure_analysis_db()
    with _lock, sqlite3.connect(str(config.ANALYSIS_DB_PATH)) as conn:
        conn.execute(
            "INSERT INTO analysis_runs (ts, stance, confidence, payload_json) VALUES (?, ?, ?, ?)",
            (
                analysis.get("generated_at") or _now_iso(),
                analysis.get("stance") or "Neutral",
                float(analysis.get("confidence") or 0),
                json.dumps(analysis, default=str),
            ),
        )
        conn.commit()


def get_analysis_history(limit: int = 20) -> list[dict[str, Any]]:
    """Logged runs newest-first as {ts, stance, confidence, headline}."""
    _ensure_analysis_db()
    q = "SELECT ts, stance, confidence, payload_json FROM analysis_runs ORDER BY id DESC LIMIT ?"
    with _lock, sqlite3.connect(str(config.ANALYSIS_DB_PATH)) as conn:
        rows = conn.execute(q, (limit,)).fetchall()
    out = []
    for ts, stance, confidence, payload_json in rows:
        try:
            headline = (json.loads(payload_json) or {}).get("headline") or ""
        except json.JSONDecodeError:
            headline = ""
        out.append({"ts": ts, "stance": stance, "confidence": confidence, "headline": headline})
    return out


# ---- Generic JSON helpers (used by other modules for cache/state files) -----

def save_json(path: Path, data: Any) -> None:
    """Atomically persist JSON: write a temp file in the same directory,
    then os.replace it onto the target (no torn/partial files on crash)."""
    config.ensure_dirs()
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default
