"""Persistence: SQLite for market events, JSON snapshots for analysis output."""

import difflib
import json
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
        return 0


def _similar(title_a: str, title_b: str) -> bool:
    """True when two titles likely describe the same story."""
    jac = _jaccard(_tokens(title_a), _tokens(title_b))
    if jac >= DEDUP_JACCARD:
        return True
    return difflib.SequenceMatcher(None, _norm_title(title_a), _norm_title(title_b)).ratio() >= DEDUP_RATIO


def init_db() -> None:
    config.ensure_dirs()
    with _lock, sqlite3.connect(config.DB_PATH) as conn:
        # Legacy schema cleanup: the old raw-headlines table is gone, and any
        # events table that predates the explicit tag columns is rebuilt.
        conn.execute("DROP TABLE IF EXISTS news")
        cols = {r[1] for r in conn.execute("PRAGMA table_info(events)").fetchall()}
        if cols and ("category" not in cols or "ntype" in cols):
            conn.execute("DROP TABLE events")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT UNIQUE NOT NULL,
                source TEXT,
                title TEXT,
                published TEXT,
                date_label TEXT,
                summary TEXT,
                category TEXT,
                actor TEXT,
                direction TEXT,
                region TEXT,
                impact TEXT,
                first_seen TEXT,
                updated_at TEXT
            )
            """
        )
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


def upsert_events(items: list[dict[str, Any]]) -> int:
    """Insert significant events, dedupe by link + cross-source similarity.

    Returns number of newly inserted rows (updates are not counted).
    """
    init_db()
    inserted = 0
    now = _now_iso()
    with _lock, sqlite3.connect(config.DB_PATH) as conn:
        rows = [
            (r[0], r[1], r[2] or "", r[3] or "")
            for r in conn.execute("SELECT link, title, impact, published FROM events").fetchall()
        ]
        for it in items:
            link = it["link"]
            title = it.get("title", "")
            published = it.get("published", "")
            impact = it.get("impact", "High")

            # Cross-source dedupe: merge with an existing row (different link)
            # that describes the same story within a short date window.
            dup_link = None
            for ex_link, ex_title, ex_impact, ex_pub in rows:
                if ex_link == link:
                    continue
                if _days_apart(published, ex_pub) > DEDUP_WINDOW_DAYS:
                    continue
                if _similar(title, ex_title):
                    dup_link = ex_link
                    impact = "Critical" if "Critical" in (impact, ex_impact) else "High"
                    break

            target = dup_link or link
            exists = target in [r[0] for r in rows]
            if exists:
                conn.execute(
                    """
                    UPDATE events
                    SET source = ?, title = ?, summary = ?, date_label = ?,
                        category = ?, actor = ?, direction = ?, region = ?,
                        impact = ?, updated_at = ?
                    WHERE link = ?
                    """,
                    (
                        it.get("source", ""),
                        title,
                        it.get("summary", ""),
                        it.get("date_label"),
                        it.get("category"),
                        it.get("actor"),
                        it.get("direction"),
                        it.get("region"),
                        impact,
                        now,
                        target,
                    ),
                )
            else:
                try:
                    conn.execute(
                        """
                        INSERT INTO events (link, source, title, published,
                                            date_label, summary, category, actor,
                                            direction, region, impact,
                                            first_seen, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            link,
                            it.get("source", ""),
                            title,
                            published,
                            it.get("date_label"),
                            it.get("summary", ""),
                            it.get("category"),
                            it.get("actor"),
                            it.get("direction"),
                            it.get("region"),
                            impact,
                            now,
                            now,
                        ),
                    )
                    inserted += 1
                    rows.append((link, title, impact, published))
                except sqlite3.IntegrityError:
                    conn.execute(
                        """
                        UPDATE events
                        SET source = ?, title = ?, summary = ?, date_label = ?,
                            category = ?, actor = ?, direction = ?, region = ?,
                            impact = ?, updated_at = ?
                        WHERE link = ?
                        """,
                        (
                            it.get("source", ""),
                            title,
                            it.get("summary", ""),
                            it.get("date_label"),
                            it.get("category"),
                            it.get("actor"),
                            it.get("direction"),
                            it.get("region"),
                            impact,
                            now,
                            link,
                        ),
                    )
        conn.commit()
    return inserted


def delete_event(link: str) -> None:
    init_db()
    with _lock, sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("DELETE FROM events WHERE link = ?", (link,))
        conn.commit()


def delete_events_by_source(source: str) -> None:
    init_db()
    with _lock, sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("DELETE FROM events WHERE source = ?", (source,))
        conn.commit()


SUPPRESSED_PATH = config.DATA_DIR / "suppressed_sources.json"


def get_suppressed_sources() -> list[str]:
    data = load_json(SUPPRESSED_PATH, default=[])
    return [s for s in data if s] if isinstance(data, list) else []


def suppress_source(source: str) -> list[str]:
    """Persist a source to the blocklist and purge its existing events."""
    cur = set(get_suppressed_sources())
    cur.add(source)
    save_json(SUPPRESSED_PATH, sorted(cur))
    delete_events_by_source(source)
    return sorted(cur)


def list_events(limit: int = 500) -> list[dict[str, Any]]:
    init_db()
    q = (
        "SELECT source, title, link, published, date_label, summary, category, "
        "actor, direction, region, impact, first_seen, updated_at FROM events "
        "ORDER BY published DESC LIMIT ?"
    )
    with _lock, sqlite3.connect(config.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(q, (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["tags"] = [t for t in (d.get("category"), d.get("actor"), d.get("direction"), d.get("region")) if t]
        out.append(d)
    return out


def log_analysis_run(analysis: dict[str, Any]) -> None:
    """Persist one AI-analysis synthesis run (full payload JSON + key columns)."""
    init_db()
    with _lock, sqlite3.connect(config.DB_PATH) as conn:
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
    init_db()
    q = "SELECT ts, stance, confidence, payload_json FROM analysis_runs ORDER BY id DESC LIMIT ?"
    with _lock, sqlite3.connect(config.DB_PATH) as conn:
        rows = conn.execute(q, (limit,)).fetchall()
    out = []
    for ts, stance, confidence, payload_json in rows:
        try:
            headline = (json.loads(payload_json) or {}).get("headline") or ""
        except json.JSONDecodeError:
            headline = ""
        out.append({"ts": ts, "stance": stance, "confidence": confidence, "headline": headline})
    return out


def save_json(path: Path, data: Any) -> None:
    config.ensure_dirs()
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default
